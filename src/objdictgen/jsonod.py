"""OD dict/json serialization and deserialization functions."""
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
# USA

import copy
import json
import logging
import re
from datetime import datetime
from typing import (TYPE_CHECKING, Any, Iterable, Mapping, Sequence, TypeVar, cast)

import deepdiff  # type: ignore[import]  # Due to missing typing stubs for deepdiff
import deepdiff.model # type: ignore[import]  # Due to missing typing stubs for deepdiff
import jsonschema

import objdictgen
# Accessed by node.py, so we need to import node as module to avoid circular references
from objdictgen import maps
from objdictgen import node as nodelib
from objdictgen.maps import OD, ODMapping, ODMappingList
from objdictgen.typing import (TDiffNodes, TIndexEntry, TODJson, TODObjJson,
                               TODObj, TODSubObj, TODSubObjJson, TODValue, TParamEntry, TPath, TProfileMenu)

T = TypeVar('T')
M = TypeVar('M', bound=Mapping)

if TYPE_CHECKING:
    from objdictgen.node import Node

log = logging.getLogger('objdictgen')


SCHEMA: dict[str, Any]|None = None


class ValidationError(Exception):
    """ Validation failure """


# JSON Version history/formats
# ----------------------------
# 0 - JSON representation of internal OD memory structure
# 1 - Default JSON format
JSON_ID = "od data"
JSON_DESCRIPTION = "Canfestival object dictionary data"
JSON_INTERNAL_VERSION = "0"
JSON_VERSION = "1"

# Output order in JSON file
JSON_TOP_ORDER = (
    "$id", "$version", "$description", "$tool", "$date", "$schema",
    "name", "description", "type", "id", "profile",
    "default_string_size", "dictionary",
)
# Output order for the "dictionary" list in the JSON file
JSON_DICTIONARY_ORDER = (
    "index", "name", "__name",
    "repeat", "struct", "group",
    "need", "mandatory", "profile_callback", "callback", "unused",
    "default", "size", "incr", "nbmax",
    "each", "sub",
    # Not in use, but useful to keep in place for development/debugging
    "values", "dictionary", "params",
    "user", "profile", "ds302", "built-in",
)
# Output order of the "sub" list in the JSON file
JSON_SUB_ORDER = (
    "name", "__name", "type", "__type",
    "access", "pdo",
    "nbmin", "nbmax",
    "save", "comment",
    "default", "value",
)

# Reverse validation (mem -> dict):
# ---------------------------------

# Fields that must be present in the mapping (where the object is defined)
# mapping[index] = { ..dict.. }
FIELDS_MAPPING_MUST = {'name', 'struct', 'values'}
FIELDS_MAPPING_OPT = {'need', 'incr', 'nbmax', 'size', 'default'}

# Fields that must be present in the subindex values from mapping,
# mapping[index]['value'] = [ dicts ]
FIELDS_MAPVALS_MUST = {'name', 'type', 'access', 'pdo'}
FIELDS_MAPVALS_OPT = {'nbmin', 'nbmax', 'default'}

# Fields that must be present in object dictionary (user settings)
# node.ParamDictionary[index] = { N: { ..dict..}, ..dict.. }
FIELDS_PARAMS = {'comment', 'save', 'buffer_size'}
FIELDS_PARAMS_PROMOTE = {'callback'}

# Fields representing the dictionary value
FIELDS_VALUE = {'value'}

# Forward validation (dict -> mem)
# --------------------------------

# Fields contents of the top-most level, json = { ..dict.. }
FIELDS_DATA_MUST = {
    '$id', '$version', 'name', 'description', 'type', 'dictionary',
}
FIELDS_DATA_OPT = {
    '$description',         # info only
    '$tool',                # info only
    '$date',                # info only
    'id',                   # default 0
    'profile',              # default "None"
    'default_string_size',  # set if present
}

# Fields contents of the dictionary, data['dictionary'] = [ ..dicts.. ]
FIELDS_DICT_MUST = {
    'index',
    'name',             # optional if repeat is True
    'struct',
    'sub',
}
FIELDS_DICT_OPT = {
                        # R = omitted if repeat is True
    'group',            # R, default 'user'
    'each',             # R, only when struct != *var
    'callback',         #    set if present
    'profile_callback', # R, set if present
    'unused',           #    default False
    'mandatory',        # R, set if present
    'repeat',           #    default False
    'incr',             # R, only when struct is "N"-type
    'nbmax',            # R, only when struct is "N"-type
    'size',             # R, only when index < 0x1000
    'default',          # R, only when index < 0x1000
}

# When 'repeat' is present, it indicates that the entry is a repeated
# objecttype and it needs lesser fields present
# Fields contents of the dictionary, data['dictionary'] = [ ..dicts.. ]
FIELDS_DICT_REPEAT_MUST = FIELDS_DICT_MUST - {'name'}
FIELDS_DICT_REPEAT_OPT = {
    'callback', 'repeat', 'unused',
}

# Valid values of data['dictionary'][index]['group']
GROUPS = {'user', 'profile', 'ds302', 'built-in'}

# Standard values of subindex 0 that can be omitted
SUBINDEX0 = {
    'name': 'Number of Entries',
    'type': 5,
    'access': 'ro',
    'pdo': False,
}

# Remove jsonc annotations
# Copied from https://github.com/NickolaiBeloguzov/jsonc-parser/blob/master/jsonc_parser/parser.py#L11-L39
RE_JSONC = re.compile(r"(\".*?(?<!\\)\"|\'.*?\')|(\s*/\*.*?\*/\s*|\s*//[^\r\n]*$)", re.MULTILINE | re.DOTALL)


def remove_jsonc(text: str) -> str:
    """ Remove jsonc annotations """
    def _re_sub(match: re.Match[str]) -> str:
        if match.group(2) is not None:
            return ""
        return match.group(1)

    return RE_JSONC.sub(_re_sub, text,)


# FIXME: Move to generic utils/funcs?
def exc_amend(exc: Exception, text: str) -> Exception:
    """ Helper to prefix text to an exception """
    args = list(exc.args)
    if len(args) > 0:
        args[0] = text + str(args[0])
    else:
        args.append(text)
    exc.args = tuple(args)
    return exc


def str_to_int(string: str|int) -> int:
    """ Convert string or int to int. Fail if not possible."""
    i = maybe_number(string)
    if not isinstance(i, int):
        raise ValueError(f"Expected integer, got '{string}'")
    return i


def maybe_number(string: str|int) -> int|str:
    """ Convert string to a number, otherwise pass it through as-is"""
    if isinstance(string, int):
        return string
    s = string.strip()
    if s.startswith('0x') or s.startswith('-0x'):
        return int(s.replace('0x', ''), 16)
    if s.isdigit():
        return int(string)
    return string


def copy_in_order(d: M, order: Sequence[T]) -> M:
    """ Remake dict d with keys in order """
    out = {
        k: d[k]
        for k in order
        if k in d
    }
    out.update({
        k: v
        for k, v in d.items()
        if k not in out
    })
    return cast(M, out)  # FIXME: For mypy


def remove_underscore(d: T) -> T:
    """ Recursively remove any keys prefixed with '__' """
    if isinstance(d, dict):
        return {  # type: ignore[return-value]
            k: remove_underscore(v)
            for k, v in d.items()
            if not k.startswith('__')
        }
    if isinstance(d, list):
        return [  # type: ignore[return-value]
            remove_underscore(v)
            for v in d
        ]
    return d


def member_compare(
        a: Iterable[str], *,
        must: set[str]|None = None,
        optional: set[str]|None = None,
        not_want: set[str]|None = None,
        msg: str = '', only_if : bool|None = None
    ) -> None:
    """ Compare the membes of a with set of wants
        must: Raise if a is missing any from must
        optional: Raise if a contains members that is not must or optional
        not_want: Raise error if any is present in a
        only_if: If False, raise error if must is present in a
    """
    have = set(a)

    if only_if is False:  # is is important here
        not_want = must
        must = None

    # Check mandatory members are present
    if must:
        unexpected = must - have
        if unexpected:
            unexp = "', '".join(unexpected)
            raise ValidationError(f"Missing required parameters '{unexp}'{msg}")

    # Check if there are any fields beyond the expected
    if optional:
        unexpected = have - ((must or set()) | optional)
        if unexpected:
            unexp = "', '".join(unexpected)
            raise ValidationError(f"Unexpected parameters '{unexp}'{msg}")

    if not_want:
        unexpected = have & not_want
        if unexpected:
            unexp = "', '".join(unexpected)
            raise ValidationError(f"Unexpected parameters '{unexp}'{msg}")


def get_object_types(
        node: "Node|None" = None,
        dictionary: list[TODObjJson]|None = None
) -> tuple[dict[int, str], dict[str, int]]:
    """ Return two dicts with the object type mapping """

    # Get the object mappings, either supplied or built-in
    if node:
        mappinglist = node.GetMappings(withmapping=True)
    else:
        mappinglist = ODMappingList([maps.MAPPING_DICTIONARY])

    # Build a integer to string and string to integer mapping for object types
    # i2s: integer to string, s2i: string to integer
    i2s: dict[int, str] = {}
    s2i: dict[str, int] = {}
    for k, v in mappinglist.find(lambda i, o: i < 0x1000):
        n = v['name']
        i2s[k] = n
        s2i[n] = k

    if len(i2s) != len(s2i):
        raise ValidationError("Multiple names or numbers for object types in OD")

    # Get the name and index from the dictionary input
    # Must check everything, as this is used with unvalidated input
    for obj in dictionary or []:
        if not isinstance(obj, dict):
            continue
        index = str_to_int(obj['index'])
        name = obj.get('name')
        # FIXME: Maybe this check is not needed here?
        if not isinstance(index, int) or not isinstance(name, str):
            continue
        if index >= 0x1000 or not name:
            continue
        if index in i2s:
            raise ValidationError(f"Index {index} ('{name}') is already defined as a type with name '{i2s[index]}'")
        if name in s2i:
            raise ValidationError(f"Name '{name}' in index {index} is already defined in index {s2i[name]}")
        i2s[index] = name
        s2i[name] = index

    return i2s, s2i


def compare_profile(profilename: TPath, params: ODMapping, menu: TProfileMenu|None = None) -> tuple[bool, bool]:
    """Compare a profile with a set of parameters and menu. Return tuple of
    (loaded, identical) where loaded is True if the profile was loaded and
    identical is True if the profile is identical with the givens params.
    """
    try:
        dsmap, menumap = maps.import_profile(profilename)
        identical = all(
            k in dsmap and k in params and dsmap[k] == params[k]
            for k in set(dsmap) | set(params)
        )
        if menu and not menu == menumap:
            raise ValueError("Menu in OD not identical with profile")
        return True, identical

    except ValueError as exc:
        log.warning("WARNING: Loading profile '%s' failed: %s", profilename, exc)
        return False, False


def generate_jsonc(node: "Node", compact=False, sort=False, internal=False, validate=True) -> str:
    """ Export a JSONC string representation of the node """

    # Get the dict representation
    jd, objtypes_s2i = node_todict(
        node, sort=sort, internal=internal, validate=validate,
        rich=not compact,
    )

    if compact:
        # Return a compact representation
        return json.dumps(jd, separators=(',', ':'))

    # Generate the json string
    text = json.dumps(jd, separators=(',', ': '), indent=2)

    # Convert the special __ fields to jasonc comments
    out = re.sub(
        r'^(\s*)"__(\w+)": "(.*)",?$',
        r'\1// "\2": "\3"',
        text,
        flags=re.MULTILINE,
    )

    # Annotate symbolic fields with comments of the value
    def _index_repl(m: re.Match[str]) -> str:
        p = m.group(1)
        n = v = m.group(2)
        if p == 'index':
            n = str_to_int(v)
        if p == 'type':
            n = objtypes_s2i.get(v, v)
        if n != v:
            return m.group(0) + f'  // {n}'
        return m.group(0)
    out = re.sub(  # As object entries
        r'"(index|type)": "([a-zA-Z0-9_]+)",?$',
        _index_repl,
        out,
        flags=re.MULTILINE,
    )
    out = re.sub(  # As comments
        r'// (index|type): "([a-zA-Z0-9_]+)"',
        _index_repl,
        out,
        flags=re.MULTILINE,
    )

    return out


def generate_node(contents: str|TODJson) -> "Node":
    """ Import from JSON string or objects """

    if isinstance(contents, str):

        # Remove jsonc annotations
        jsontext = remove_jsonc(contents)

        # Load the json
        jd: TODJson = json.loads(jsontext)

        # Remove any __ in the file
        jd = remove_underscore(jd)

    else:
        # Use provided object
        jd = contents

    # FIXME: Dilemma: In what order to run validation? It would make sense to
    #        place it after running the built-in validator. Often
    #        validate_fromdict() is better at giving useful errors
    #        than the json validator. However the type checking of the json
    #        validator is better.
    global SCHEMA  # pylint: disable=global-statement
    if not SCHEMA:
        with open(objdictgen.JSON_SCHEMA, 'r', encoding="utf-8") as f:
            SCHEMA = json.loads(remove_jsonc(f.read()))

    if SCHEMA and jd.get('$version') == JSON_VERSION:
        jsonschema.validate(jd, schema=SCHEMA)

    # Get the object type mappings forwards (int to str) and backwards (str to int)
    objtypes_i2s, objtypes_s2i = get_object_types(dictionary=jd.get("dictionary", []))

    # Validate the input json against for the OD format specifics
    validate_fromdict(jd, objtypes_i2s, objtypes_s2i)

    return node_fromdict(jd, objtypes_s2i)


def node_todict(node: "Node", sort=False, rich=True, internal=False, validate=True) -> tuple[TODJson, dict[str, int]]:
    """
        Convert a node to dict representation for serialization.

        sort: Set if the output dictionary should be sorted before output.
        rich: Generate tich output intended for human reading. It will add
            text to the output that will ease the readabiliy of the output.
            1) It will add __fields to the output. These fields are redundant
               and and will be skipped when reading the file
            2) Replace struct and type fields with strings instead of numerical
               value
            3) Use hex index instead of numerical value in dictionary index
        internal: Enable to dump the internal data model as-is. Used for
            low-level format debugging
        validate: Set if the output JSON should be validated to check if the
            output is valid. Used to double check format.

        Returns a tuple with the JSON dict and the object type mapping
        str to int. The latter is for convenience when importing the JSON and
        can be used for display purposes.
    """

    # Get the object type mappings forwards (int to str) and backwards (str to int)
    objtypes_i2s, objtypes_s2i = get_object_types(node=node)

    # Parse through all parameters indexes
    dictionary: list[TODObjJson] = []
    for index in node.GetAllIndices(sort=sort):
        try:
            obj: TODObjJson = {}

            # Get the internal dict representation of the object, termed "index entry"
            ientry = node.GetIndexEntry(index)

            # Don't wrangle further if the internal format is wanted, just add it as-is
            if internal:
                # FIXME: This works as long as GetIndexEntry() returns a dict
                obj = cast(TODObjJson, ientry)
                continue

            # The internal memory model of Node is complex, this function exists
            # to validate the input data, i.e. the Node object before migrating
            # to JSON format. This is mainly to ensure no wrong assumptions
            # produce unexpected output.
            if validate:
                validate_indexentry(ientry)

            # Convert the internal dict representation to generic dict structure
            obj = indexentry_to_jsondict(ientry)

            # JSON format adoptions
            obj = rearrage_for_json(obj, node, objtypes_i2s, rich=rich)

        except Exception as exc:
            exc_amend(exc, f"Index 0x{index:04x} ({index}): ")
            raise

        finally:
            # Add in a fancyer index (do it here after index is finished being used)
            if rich:
                obj["index"] = f"0x{index:04X}"

            dictionary.append(obj)

    # Make the json dict
    jd: TODJson = copy_in_order({
        '$id': JSON_ID,
        '$version': JSON_INTERNAL_VERSION if internal else JSON_VERSION,
        '$description': JSON_DESCRIPTION,
        '$tool': str(objdictgen.ODG_PROGRAM) + ' ' + str(objdictgen.__version__),
        '$date': datetime.isoformat(datetime.now()),
        'name': node.Name,
        'description': node.Description,
        'type': node.Type,
        'id': node.ID,
        'profile': node.ProfileName,
        'default_string_size': node.DefaultStringSize,
        'dictionary': [
            copy_in_order(k, JSON_DICTIONARY_ORDER)
            for k in dictionary
        ],
    }, JSON_TOP_ORDER)  # type: ignore[assignment]

    # FIXME: Somewhat a hack, find better way to optionally include this
    if 'DefaultStringSize' not in node.__dict__:
        jd.pop('default_string_size')  # type: ignore[misc]

    # Rearrange the order of the top-level dict
    jd = copy_in_order(jd, JSON_TOP_ORDER)

    # Cross check verification to see if we later can import the generated dict
    if validate and not internal:
        validate_fromdict(remove_underscore(jd), objtypes_i2s, objtypes_s2i)

    return jd, objtypes_s2i


def indexentry_to_jsondict(ientry: TIndexEntry) -> TODObjJson:
    """ Modify obj from internal dict representation to generic dict structure
        which is suitable for serialization into JSON.
    """

    # Ensure the incoming object is not mutated
    ientry = copy.deepcopy(ientry)

    # Observations:
    # =============
    # - 'callback' might be set in the mapping. If it is, then the
    #   user cannot change the value from the UI. Otherwise 'callback'
    #   is defined by user in 'params'
    # - In [N]ARRAY formats, the number of elements is determined by the
    #   length of 'dictionary'
    # - 'params' stores by subindex num (integer), except for [N]VAR, where
    #   the data is stored directly in 'params'
    # - 'dictionary' is a list of number of subindexes minus 1 for the
    #   number of subindexes. If [N]VAR the value is immediate.
    # - ARRAY expects mapping 'values[1]' to contain the repeat specification,
    #   RECORD only if 'nbmax' is defined in said values. Attempting to use
    #   named array entries fails.
    # - "nbmax" (on values level) is used for indicating "each" elements
    #   and must be present in index 1.
    # - "incr" an "nbmax" (on mapping level) is used for N* types
    # - "default" on values level is only used for custom types <0x100
    # - NVAR with empty dictionary value is not possible

    # -- STEP 1) --
    # Blend the mapping type (odobj) with obj

    # Get group membership (what object type it is) and if the prarmeter is repeated
    index = ientry["index"]

    # New output object
    obj: TODObjJson = {
        "index": index,
    }
    odobj: TODObj  # The OD object (set below)

    # Is the object not a repeat object (where base is the same)?
    if ientry.get("base", index) == index:

        # The validator have checked that only one group is present
        # Note the key rename
        obj['group'] = ientry["groups"][0]

        # Get the object itself
        odobj = ientry['object']
        struct = odobj["struct"]

    else:
        # Mark the object a repeated object
        obj["repeat"] = True

        odobj = {}
        struct = ientry["basestruct"]

    # Callback in mapping collides with the user set callback, so it is renamed
    if 'callback' in odobj:
        obj['profile_callback'] = odobj.pop('callback')

    # Move known members from odobj to top-level object.
    for k in FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT:
        if k in odobj:
            newk = k
            if k == 'need':  # Mutate the field name
                newk = 'mandatory'
            # FIXME: mypy: TypedDict doesn't work with k
            obj[newk] = odobj.pop(k)  # type: ignore[literal-required,misc]

    # Ensure fields exists
    obj['struct'] = struct
    obj['sub'] = obj.pop('values', [])  # type: ignore[typeddict-item]  # values is about to be renamed

    # Move subindex[1] to 'each' on objecs that contain 'nbmax'
    if len(obj['sub']) > 1 and 'nbmax' in obj['sub'][1]:
        obj['each'] = obj['sub'].pop(1)  # type: ignore[typeddict-item]

    # Baseobj should have been emptied
    if odobj != {}:
        raise ValidationError(f"Mapping data not empty. Contains: {odobj}")

    # -- STEP 2) --
    # Migrate 'params' and 'dictionary' to common 'sub'

    # Extract the params
    has_params = 'params' in ientry
    has_dictionary = 'dictionary' in ientry
    params = ientry.get("params", {})
    dictvals = ientry.get("dictionary", [])

    # These types places the params in the top-level dict
    if has_params and struct in (OD.VAR, OD.NVAR):
        # FIXME: Here is would be nice to validate that 'params' is a TParamEntry
        param0 = {}
        for k in FIELDS_PARAMS:
            if k in params:
                param0[k] = params.pop(k)  # type: ignore[misc,call-overload]
        params[0] = param0  # type: ignore[literal-required,assignment,arg-type]  # TypedDict doesn't work with 0

    # Promote the global parameters from params into top-level object
    for k in FIELDS_PARAMS_PROMOTE:
        if k in params:
            obj[k] = params.pop(k)  # type: ignore[literal-required,misc,call-overload]  # TypedDict doesn't work with k

    # FIXME: By now, params should contain only subindex parameters
    if TYPE_CHECKING:
        params = cast(dict[int, TParamEntry], params)

    # Extract the dictionary values
    # NOTE! It is important to capture that 'dictionary' exists is obj, even if
    #       empty. This might happen on a ARRAY with 0 elements.
    start = 0
    if has_dictionary:
        if struct in (OD.VAR, OD.NVAR):
            # FIXME: In this struct type it should never return a list
            assert not isinstance(dictvals, list)
            # Ensures dictvals is always a list
            dictvals = [dictvals]
        else:
            # FIXME: In this struct type it should always return a list
            assert isinstance(dictvals, list)
            start = 1  # Have "number of entries" first

        # Write the dictionary into the ParameterEntry
        for i, v in enumerate(dictvals, start=start):
            params.setdefault(i, {})['value'] = v  # type: ignore[typeddict-unknown-key]
    else:
        # This is an unused object
        obj['unused'] = True

    # Commit the params to the 'sub' list
    if params:
        # FIXME: This assumption should be true
        assert isinstance(dictvals, list)

        # Ensure there are enough items in 'sub' to hold the param items
        dictlen = start + len(dictvals)
        sub = obj["sub"]  # Get the list of values, now sub
        if dictlen > len(sub):
            sub += [{} for i in range(len(sub), dictlen)]  # type: ignore[typeddict-item]

        # Commit the params to 'sub'
        for i, val in enumerate(sub):
            val.update(params.pop(i, {}))  # type: ignore[typeddict-item]

    # Params should have been emptied
    if params != {}:
        raise ValidationError(f"User parameters not empty. Contains: {params}")

    return obj


def rearrage_for_json(obj: TODObjJson, node: "Node", objtypes_i2s: dict[int, str], rich=True) -> TODObjJson:
    """ Rearrange the object to fit the wanted JSON format """

    # The struct describes what kind of object structure this object have
    # See OD_* in node.py
    struct = obj["struct"]
    index = obj["index"]
    unused = obj.get("unused", False)

    # FIXME: In this context it should always be an integer
    assert isinstance(index, int)

    # Replace numerical struct with symbolic value
    if rich:
        # FIXME: This gives mypy error because to_string() might return None
        obj["struct"] = OD.to_string(struct, struct)  # type: ignore[arg-type,typeddict-item]

    # Add duplicate name field which will be commented out
    if rich and "name" not in obj:
        obj["__name"] = node.GetEntryName(index)

    # Iterater over the sub-indexes (if present)
    for i, sub in enumerate(obj.get("sub", [])):

        # Get the subentry info for rich format
        info: TODSubObj = node.GetSubentryInfos(index, i) if rich and not unused else {}

        # Add __name when rich format
        if info and "name" not in sub:
            sub["__name"] = info["name"]

        # Replace numeric type with string value
        if rich and "type" in sub:
            # FIXME: The cast is to ensure mypy is able keep track
            sub["type"] = objtypes_i2s.get(cast(int, sub["type"]), sub["type"])

        # # Add __type when rich format
        if info and "type" not in sub:
            sub["__type"] = objtypes_i2s.get(info["type"], info["type"])

    if 'each' in obj:
        each = obj["each"]

        # Replace numeric type with string value
        if rich and "type" in each:
            # FIXME: The cast is to ensure mypy is able keep track
            each["type"] = objtypes_i2s.get(cast(int, each["type"]), each["type"])

    # Rearrage order of 'sub' and 'each'
    obj["sub"] = [
        copy_in_order(k, JSON_SUB_ORDER)
        for k in obj["sub"]
    ]
    if 'each' in obj:
        obj["each"] = copy_in_order(obj["each"], JSON_SUB_ORDER)

    return obj


def validate_indexentry(ientry: TIndexEntry):
    """ Validate index dict contents (see Node.GetIndexDict). The purpose is to
        validate the assumptions in the data format.

        NOTE: This function exists to validate the node data in node_todict()
        to verify that the programmed assumptions are not wrong.
    """

    groups = ientry["groups"]
    index = ientry["index"]

    # Is the definition for the object present?
    if ientry.get("base", index) == index:

        # A) Ensure only one definition of the object group
        if len(groups) == 0:
            raise ValidationError("Missing mapping")
        if len(groups) != 1:
            raise ValidationError(f"Contains uexpected number of groups ({len(groups)}) for the object")

        # Extract the definition
        odobj = ientry["object"]

        # B) Check baseobj object members is present
        member_compare(
            odobj.keys(),
            must=FIELDS_MAPPING_MUST, optional=FIELDS_MAPPING_OPT | FIELDS_PARAMS_PROMOTE,
            msg=' in mapping object'
        )

        struct = odobj['struct']

    else:
        # If this is a repeated parameter, this object should not contain any definitions

        # A) Ensure no definition of the object group
        if len(groups) != 0:
            t_gr = ", ".join(groups)
            raise ValidationError(f"Unexpected to find any groups ({t_gr}) in repeated object")

        odobj = {}
        struct = ientry["basestruct"]

    # Helpers
    is_var = struct in (OD.VAR, OD.NVAR)

    # Ensure obj does NOT contain any fields found in baseobj (sanity check really)
    member_compare(
        ientry.keys(),
        not_want=FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT | FIELDS_PARAMS_PROMOTE,
        msg=' in object'
    )

    # Check baseobj object members
    for val in odobj.get('values', []):
        member_compare(
            val.keys(),
            must=FIELDS_MAPVALS_MUST, optional=FIELDS_MAPVALS_OPT,
            msg=' in mapping values'
        )

    # Collect some information
    params = ientry.get('params', {})
    dictvalues = ientry.get('dictionary', [])
    dictlen = 0

    # These types places the params in the top-level dict
    if params and is_var:
        # FIXME: Here it would be nice to validate that 'params' is a TParamEntry
        if TYPE_CHECKING:
            params = cast(TParamEntry, params)

        params = params.copy()  # Important, as it is mutated below

        # Move all known paramtert fields to a separate dict indexed by 0
        param0: TParamEntry = {}
        for k in FIELDS_PARAMS:
            if k in params:
                param0[k] = params.pop(k)  # type: ignore[literal-required,misc]
        params[0] = param0  # type: ignore[typeddict-item,literal-required]

    # Verify type of dictionary
    if 'dictionary' in ientry:
        if is_var:
            if isinstance(dictvalues, list):
                raise ValidationError(f"Unexpected list type in dictionary '{dictvalues}'")
            dictlen = 1
            # dictvalues = [dictvalues]
        else:
            if not isinstance(dictvalues, list):
                raise ValidationError(f"Unexpected type in dictionary '{dictvalues}'")
            dictlen = len(dictvalues) + 1
            # dictvalues = [None] + dictvalues  # Which is a copy

    # Check numbered params
    excessive: dict[int, TParamEntry] = {}
    for param in params:
        # All int keys corresponds to a numbered index
        if isinstance(param, int):
            # Check that there are no unexpected fields in numbered param

            # FIXME: Need a separate type to get the type hinter to work
            if TYPE_CHECKING:
                params = cast(dict[int, TParamEntry], params)

            member_compare(params[param].keys(),
                must=set(),
                optional=FIELDS_PARAMS,
                not_want=FIELDS_PARAMS_PROMOTE | FIELDS_MAPVALS_MUST | FIELDS_MAPVALS_OPT,
                msg=' in params'
            )

            if param > dictlen:
                excessive[param] = params[param]

    # Do we have too many params?
    if excessive:
        raise ValidationError(f"Excessive params, or too few dictionary values: {excessive}")

    # Find all non-numbered params and check them against
    promote: set[str] = {k for k in params if not isinstance(k, int)}
    if promote:
        member_compare(promote, optional=FIELDS_PARAMS_PROMOTE, msg=' in params')

    # Check that we got the number of values and nbmax we expect for the type
    nbmax = ['nbmax' in v for v in odobj.get('values', [])]
    lenok, nbmaxok = False, False

    if not odobj:
        # Bypass tests if no baseobj is present
        lenok, nbmaxok = True, True

    elif struct in (OD.VAR, OD.NVAR):
        if len(nbmax) == 1:
            lenok = True
        if sum(nbmax) == 0:
            nbmaxok = True

    elif struct in (OD.ARRAY, OD.NARRAY):
        if len(nbmax) == 2:
            lenok = True
        if sum(nbmax) == 1 and nbmax[1]:
            nbmaxok = True

    elif struct in (OD.RECORD, OD.NRECORD):
        if sum(nbmax) and len(nbmax) > 1 and nbmax[1]:
            nbmaxok = True
            if len(nbmax) == 2:
                lenok = True
        elif sum(nbmax) == 0:
            nbmaxok = True
            if len(nbmax) > 1:
                lenok = True
    else:
        raise ValidationError(f"Unknown struct '{struct}'")

    if not nbmaxok:
        raise ValidationError(f"Unexpected 'nbmax' use in mapping values, used {sum(nbmax)} times")
    if not lenok:
        raise ValidationError(f"Unexpexted count of subindexes in mapping object, found {len(nbmax)}")


def node_fromdict(jd: TODJson, objtypes_s2i: dict[str, int]) -> "Node":
    """ Convert a dict jd into a Node """

    # Create the node and fill the most basic data
    node = nodelib.Node(
        name=jd["name"], type=jd["type"], id=jd.get("id", 0),
        description=jd["description"], profilename=jd.get("profile", "None"),
    )

    # Restore optional values
    if 'default_string_size' in jd:
        node.DefaultStringSize = jd["default_string_size"]

    # An import of a internal JSON file?
    internal = jd['$version'] == JSON_INTERNAL_VERSION

    # Iterate over the items to convert them to Node object
    for obj in jd["dictionary"]:

        # Convert the index number (which might be "0x" string)
        index = str_to_int(obj['index'])
        obj["index"] = index

        # There is a weakness to the Node implementation: There is no store
        # of the order of the incoming parameters, instead the data is spread
        # over many dicts, e.g. Profile, DS302, UserMapping, Dictionary,
        # ParamsDictionary. Node.IndexOrder has been added to store the order
        # of the parameters.
        node.IndexOrder.append(index)

        try:
            if not internal:
                # Mutate obj containing the generic dict to the TIndexEntry
                ientry = rearrange_for_node(obj, objtypes_s2i)

            else:
                # FIXME: Cast this to mutate the object type
                ientry = cast(TIndexEntry, obj)

        except Exception as exc:
            exc_amend(exc, f"Index 0x{index:04x} ({index}): ")
            raise

        # Copy the object to node object entries
        if 'dictionary' in ientry:
            node.Dictionary[index] = ientry['dictionary']
        if 'params' in ientry:
            node.ParamsDictionary[index] = {  # pyright: ignore[reportArgumentType]
                maybe_number(k): v  # type: ignore[misc]
                for k, v in ientry['params'].items()
            }

        groups: list[str] = ientry.get('groups', ['user'])

        # Do not restore mapping object on repeated objects
        if 'repeat' in groups:
            continue
        elif 'profile' in groups:
            node.Profile[index] = ientry['object']
        elif 'ds302' in groups:
            node.DS302[index] = ientry['object']
        elif 'user' in groups:
            node.UserMapping[index] = ientry['object']

        # Verify against built-in data
        elif 'built-in' in groups:
            refobj = maps.MAPPING_DICTIONARY.get(index)

            diff = deepdiff.DeepDiff(refobj, ientry['object'], view='tree')
            if diff:
                log.debug("Index 0x%04x (%s) Difference between built-in object and imported:", index, index)
                for line in diff.pretty().splitlines():
                    log.debug('  %s', line)
                raise ValidationError(
                    f"Built-in object index 0x{index:04x} ({index}) "
                    "does not match against system parameters"
                )

    return node


def rearrange_for_node(obj: TODObjJson, objtypes_s2i: dict[str, int]) -> TIndexEntry:
    """ Convert a json OD object into an object adapted for load into a Node
        object.
    """

    # This function is mutating obj, so we need to copy it
    obj = copy.deepcopy(obj)

    # -- STEP 1) --
    # Move 'definition' into individual mapping type category

    ientry: TIndexEntry = {}
    odobj: TODObj = {}

    # FIXME: We know by design this is already int
    ientry["index"] = obj.pop("index")  # type: ignore[typeddict-item]

    # Read "struct" (must)
    struct = obj["struct"]
    if not isinstance(struct, int):
        # FIXME: The "or 0" can be removed when from_string() doesn't produce None
        struct = OD.from_string(struct) or 0
        obj["struct"] = struct  # Write value back into object

    # Read "group" (optional, default 'user', omit if repeat is True
    ientry["groups"] = [obj.pop("group", None) or 'user']

    # Read "profile_callback" (optional)
    if 'profile_callback' in obj:
        odobj['callback'] = obj.pop('profile_callback')

    # Restore the definition entries
    for k in FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT:
        oldk = k
        if k == "need":  # Mutate the field name
            oldk = "mandatory"
        if oldk in obj:
            odobj[k] = obj.pop(oldk)  # type: ignore[literal-required,misc]

    # -- STEP 2) --
    # Migrate 'sub' into 'params' and 'dictionary'

    # Restore the param entries that has been promoted to obj
    params: dict[int, TParamEntry] = {}
    for k in FIELDS_PARAMS_PROMOTE:
        if k in obj:
            params[k] = obj.pop(k)  # type: ignore[misc,index]

    # Restore the values and dictionary
    subitems: list[TODSubObjJson] = obj.pop('sub')

    # Recreate the dictionary list
    dictionary: list[TODValue] = [
        v.pop('value')  # type: ignore[misc]
        for v in subitems
        if v and 'value' in v
    ]

    # Restore the dictionary values
    if dictionary:
        # [N]VAR needs them as immediate values
        if struct in (OD.VAR, OD.NVAR):
            dictionary = dictionary[0]  # type: ignore[assignment]
        ientry['dictionary'] = dictionary

    # The "unused" field is used to indicate that the object has no
    # dictionary value. Otherwise there must be an empty dictionary list
    # ==> "unused" is only read iff dictionary is empty
    elif not obj.pop('unused', False):
        # NOTE: If struct in VAR and NVAR, it is not correct to set to [], but
        #       the should be captured by the validator.
        ientry['dictionary'] = []

    # Restore param dictionary
    for i, vals in enumerate(subitems):
        paramentry = params.setdefault(i, {})
        for k in FIELDS_PARAMS:
            if k in vals:
                paramentry[k] = vals.pop(k)  # type: ignore[misc,literal-required]

    # Move entries from item 0 into the params object
    if 0 in params and struct in (OD.VAR, OD.NVAR):
        params.update(params.pop(0))  # type: ignore[arg-type]

    # Remove the empty params and values
    params = {k: v for k, v in params.items() if not isinstance(v, dict) or v}
    subitems = [v for v in subitems if v]

    # Commit params if there is any data
    if params:
        ientry['params'] = params

    # -- STEP 3) --
    # Rebuild the object

    # Move back the each object
    if 'each' in obj:
        subitems.append(obj.pop('each'))  # type: ignore[arg-type]

    # Check if the object is a repeat object
    repeat = obj.pop('repeat', False)
    if repeat:
        ientry["groups"].append("repeat")

    # Restore optional items from subindex 0
    if not repeat and struct in (OD.ARRAY, OD.NARRAY, OD.RECORD, OD.NRECORD):
        index0 = subitems[0]
        for k, v in SUBINDEX0.items():
            index0.setdefault(k, v)  # type: ignore[misc]

    # Restore 'type' text encoding into value
    for sub in subitems:
        if 'type' in sub:
            # FIXME: Use case to help mypy
            sub['type'] = objtypes_s2i.get(cast(str, sub['type']), sub['type'])

    # Restore values
    if subitems:
        # FIXME: Remaining issue is to ensure the subitems object is correct
        odobj['values'] = subitems
        ientry["object"] = odobj

    if obj:
        raise ValidationError(f"Unexpected fields in object: {obj}")

    # Params should have been emptied
    if obj != {}:
        raise ValidationError(f"JSON object not empty. Contains: {obj}")

    return ientry


def validate_fromdict(jsonobj: TODJson, objtypes_i2s: dict[int, str], objtypes_s2i: dict[str, int]):
    """ Validate that jsonobj is a properly formatted dictionary that may
        be imported to the internal OD-format
    """

    jd = jsonobj

    # Validated: (See FIELDS_DATA_MUST, FIELDS_DATA_OPT)
    # ----------
    # Y "$id" (must)
    # Y "$version" (must)
    #   "name" (must)
    #   "description" (must)
    #   "type" (must)
    # Y "dictionary" (must)
    #   "$description" (optional)
    #   "$tool" (optional)
    #   "$date" (optional)
    #   "id" (optional, default 0)
    #   "profile" (optional, default "None")
    #   "default_string_size" (optional)

    if not jd or not isinstance(jd, dict):
        raise ValidationError("Not data or not dict")

    # Validate "$id" (must)
    if jd.get('$id') != JSON_ID:
        raise ValidationError(
            f"Unknown file format, expected '$id' to be '{JSON_ID}', found '{jd.get('$id')}'"
        )

    # Validate "$version" (must)
    if jd.get('$version') not in (JSON_INTERNAL_VERSION, JSON_VERSION):
        raise ValidationError(
            f"Unknown file version, expected '$version' to be '{JSON_VERSION}', found '{jd.get('$version')}'"
        )

    # Don't validate the internal format any further
    if jd['$version'] == JSON_INTERNAL_VERSION:
        return

    # Verify that we have the expected members
    member_compare(jsonobj.keys(), must=FIELDS_DATA_MUST, optional=FIELDS_DATA_OPT)

    def _validate_sub(obj, idx=0, is_var=False, is_repeat=False, is_each=False):

        # Validated: (See FIELDS_MAPVAPS_*, FIELDS_PARAMS and FIELDS_VALUE)
        # ----------
        # Y "name" (must)
        # Y "type" (must)
        #   "access" (must)
        #   "pdo" (must)
        #   "nbmin" (optional)
        #   "nbmax" (optional)
        #   "default" (optiona)
        #   "comment" (optional)
        #   "save" (optional)
        #   "buffer_size" (optional)
        #   "value" (optional)

        if not isinstance(obj, dict):
            raise ValidationError("Is not a dict")

        if idx > 0 and is_var:
            raise ValidationError("Expects only one subitem on VAR/NVAR")

        # Subindex 0 of a *ARRAY, *RECORD cannot hold any value
        if idx == 0 and not is_var:
            member_compare(obj.keys(), not_want=FIELDS_VALUE)

        # Validate "nbmax" if parsing the "each" sub
        member_compare(obj.keys(), must={'nbmax'}, only_if=idx == -1)

        # Default object presense
        defs = 'must'   # Parameter definition (FIELDS_MAPVALS_*)
        params = 'opt'  # User parameters (FIELDS_PARAMS)
        value = 'no'    # User value (FIELDS_VALUE)

        # Set what parameters should be present, optional or not present
        if idx == -1:  # Checking "each" section. No object or value
            params = 'no'

        elif is_repeat:  # Object repeat = defined elsewhere. No definition needed.
            defs = 'no'
            if is_var or idx > 0:
                value = 'must'

        elif is_var:  # VAR type, guaranteed idx==0 here
            value = 'opt'

        elif is_each:  # Param have "each". Should never have any defs in idx > 0
            if idx > 0:
                defs = 'no'
                value = 'must'

        else:  # All other (not each, not repeat, not VAR)
            if idx > 0:
                value = 'opt'

        # Calculate the expected parameters
        must = set()
        opts = set()
        if defs == 'must':
            must |= FIELDS_MAPVALS_MUST
            opts |= FIELDS_MAPVALS_OPT
        # if defs == 'opt':
        #     opts |= FIELDS_MAPVALS_MUST | FIELDS_MAPVALS_OPT
        # if params == 'must':
        #     must |= FIELDS_PARAMS
        if params == 'opt':
            opts |= FIELDS_PARAMS
        if value == 'must':
            must |= FIELDS_VALUE
        if value == 'opt':
            opts |= FIELDS_VALUE

        # Verify parameters
        member_compare(obj.keys(), must=must, optional=opts)

        # Validate "name"
        if 'name' in obj and not obj['name']:
            raise ValidationError("Must have a non-zero length name")

        # Validate "type"
        if 'type' in obj:
            if isinstance(obj['type'], str) and objtypes_s2i and obj['type'] not in objtypes_s2i:
                raise ValidationError(f"Unknown object type '{obj['type']}'")
            if isinstance(obj['type'], int) and objtypes_i2s and obj['type'] not in objtypes_i2s:
                raise ValidationError(f"Unknown object type id {obj['type']}")

    def _validate_dictionary(index, obj):

        # Validated: (See FIELDS_DICT_MUST, FIELDS_DICT_OPT)
        # ----------
        # Y "index" (must)
        #   "name" (must, optional if repeat is True)
        # Y "struct" (must)
        # Y "sub" (must)
        # Y "group" (optional, default 'user', omit if repeat is True)
        # Y "each" (optional, omit if repeat is True)
        #   "callback" (optional, default False)
        #   "profile_callback" (optional, omit if repeat is True)
        # Y "unused" (optional)
        #   "mandatory" (optional, omit if repeat is True, default False)
        # Y "repeat" (optional, default False)
        #   "incr" (optional)
        #   "nbmax" (optional)
        # Y "size" (optional)
        # Y "default" (optional)

        # Validate "repeat" (optional, default False)
        is_repeat = obj.get('repeat', False)

        # Validate all present fields
        if is_repeat:
            member_compare(obj.keys(),
                must=FIELDS_DICT_REPEAT_MUST, optional=FIELDS_DICT_REPEAT_OPT,
                msg=' in dictionary'
            )
        else:
            member_compare(obj.keys(),
                must=FIELDS_DICT_MUST, optional=FIELDS_DICT_OPT,
                msg=' in dictionary'
            )

        # Validate "index" (must)
        if not isinstance(index, int):
            raise ValidationError(f"Invalid dictionary index '{obj['index']}'")
        if index <= 0 or index > 0xFFFF:
            raise ValidationError(f"Invalid dictionary index value '{index}'")

        # Validate "struct" (must)
        struct = obj["struct"]
        if not isinstance(struct, int):
            struct = OD.from_string(struct)
        if struct not in OD.STRINGS:
            raise ValidationError(f"Unknown struct value '{obj['struct']}'")

        # Validate "group" (optional, default 'user', omit if repeat is True)
        group = obj.get("group", None) or 'user'
        if group and group not in GROUPS:
            raise ValidationError(f"Unknown group value '{group}'")

        # Validate "default" (optional)
        if 'default' in obj and index >= 0x1000:
            raise ValidationError("'default' cannot be used in index 0x1000 and above")

        # Validate "size" (optional)
        if 'size' in obj and index >= 0x1000:
            raise ValidationError("'size' cannot be used in index 0x1000 and above")

        # Validate that "nbmax" and "incr" is only present in right struct type
        need_nbmax = not is_repeat and struct in (OD.NVAR, OD.NARRAY, OD.NRECORD)
        member_compare(obj.keys(), must={'nbmax', 'incr'}, only_if=need_nbmax)

        subitems = obj['sub']
        if not isinstance(subitems, list):
            raise ValidationError("'sub' is not a list")

        has_name = ['name' in v for v in subitems]
        has_value = ['value' in v for v in subitems]

        # Validate "sub" (must)
        for idx, sub in enumerate(subitems):
            try:
                is_var = struct in (OD.VAR, OD.NVAR)
                _validate_sub(sub, idx, is_var=is_var, is_repeat=is_repeat, is_each='each' in obj)
            except Exception as exc:
                exc_amend(exc, f"sub[{idx}]: ")
                raise

        # Validate "each" (optional, omit if repeat is True)
        if 'each' in obj:
            sub = obj["each"]

            if struct in (OD.VAR, OD.NVAR):
                raise ValidationError("Unexpected 'each' use in VAR/NVAR object")

            # Having 'each' requires use of only one sub item with 'name' in it
            if not (sum(has_name) == 1 and has_name[0]):
                raise ValidationError("Unexpected subitems. Subitem 0 must contain name")

            try:
                _validate_sub(sub, idx=-1)
            except Exception as exc:
                exc_amend(exc, "'each': ")
                raise

            # Ensure the format is correct
            # NOTE: Not all seems to be the same. E.g. default is 'access'='ro',
            # however in 0x1600, 'access'='rw'.
            # if not all(subitems[0].get(k, v) == v for k, v in SUBINDEX0.items()):
            #     raise ValidationError(f"Incorrect definition in subindex 0. Found {subitems[0]}, expects {SUBINDEX0}")

        elif not is_repeat:
            if struct in (OD.ARRAY, OD.NARRAY):
                raise ValidationError("Field 'each' missing from ARRAY/NARRAY object")

        # Validate "unused" (optional)
        unused = obj.get('unused', False)
        if unused and sum(has_value):
            raise ValidationError(f"There are {sum(has_value)} values in subitems, but 'unused' is true")
        if not unused and not sum(has_value) and struct in (OD.VAR, OD.NVAR):
            raise ValidationError("VAR/NVAR cannot have 'unused' false")

        # Validate the count of subs with name and value in them
        if struct in (OD.VAR, OD.NVAR):
            if not is_repeat and sum(has_name) != 1:
                raise ValidationError("Must have name definition in subitem 0")
            if is_repeat and sum(has_value) == 0:
                raise ValidationError("Must have value in subitem 0")

        if struct in (OD.ARRAY, OD.NARRAY, OD.RECORD, OD.NRECORD):
            if not is_repeat and len(subitems) < 1:
                raise ValidationError("Expects at least two subindexes")
            if sum(has_value) and has_value[0]:
                raise ValidationError("Subitem 0 should not contain any value")
            if sum(has_value) and sum(has_value) != len(has_value) - 1:
                raise ValidationError("All subitems except item 0 must contain value")

        if struct in (OD.RECORD, OD.NRECORD):
            if not is_repeat and 'each' not in obj:
                if sum(has_name) != len(has_name):
                    raise ValidationError(f"Not all subitems have name, {sum(has_name)} of {len(has_name)}")

    # Validate "dictionary" (must)
    if not isinstance(jd['dictionary'], list):
        raise ValidationError("No dictionary or dictionary not list")

    for num, obj in enumerate(jd['dictionary']):
        if not isinstance(obj, dict):
            raise ValidationError(f"Item number {num} of 'dictionary' is not a dict")

        sindex = obj.get('index', f'item {num}')
        index = str_to_int(sindex)

        try:
            _validate_dictionary(index, obj)
        except Exception as exc:
            exc_amend(exc, f"Index 0x{index:04x} ({index}): ")
            raise


def diff_nodes(node1: "Node", node2: "Node", asdict=True, validate=True) -> TDiffNodes:
    """Compare two nodes and return the differences."""

    diffs: dict[int|str, list] = {}

    if asdict:
        jd1, _ = node_todict(node1, sort=True, validate=validate)
        jd2, _ = node_todict(node2, sort=True, validate=validate)

        dt = datetime.isoformat(datetime.now())
        jd1['$date'] = jd2['$date'] = dt

        # DeepDiff does not have typing, but the diff object is a dict-like object
        #   DeepDiff[str, deepdiff.model.PrettyOrderedSet].
        # PrettyOrderedSet is a list-like object
        #   PrettyOrderedSet[deepdiff.model.DiffLevel]

        diff = deepdiff.DeepDiff(jd1, jd2, exclude_paths=[
            "root['dictionary']"
        ], view='tree')

        chtype: str
        for chtype, changes in diff.items():
            change: deepdiff.model.DiffLevel
            for change in changes:
                path: str = change.path(force='fake')  # pyright: ignore[reportAssignmentType]
                entries = diffs.setdefault('', [])
                entries.append((chtype, change, path.replace('root', '')))

        diff = deepdiff.DeepDiff(jd1['dictionary'], jd2['dictionary'], view='tree', group_by='index')

        res = re.compile(r"root\[('0x[0-9a-fA-F]+'|\d+)\]")

        for chtype, changes in diff.items():
            for change in changes:
                path = change.path(force='fake')  # pyright: ignore[reportAssignmentType]
                m = res.search(path)
                if m:
                    num = str_to_int(m.group(1).strip("'"))
                    entries = diffs.setdefault(num, [])
                    entries.append((chtype, change, path.replace(m.group(0), '')))
                else:
                    entries = diffs.setdefault('', [])
                    entries.append((chtype, change, path.replace('root', '')))

    else:
        diff = deepdiff.DeepDiff(node1.__dict__, node2.__dict__, exclude_paths=[
            "root.IndexOrder"
        ], view='tree')

        res = re.compile(r"root\.(Profile|Dictionary|ParamsDictionary|UserMapping|DS302)\[(\d+)\]")

        for chtype, changes in diff.items():
            for change in changes:
                path = change.path(force='fake')  # pyright: ignore[reportAssignmentType]
                m = res.search(path)
                if m:
                    entries = diffs.setdefault(int(m.group(2)), [])
                    entries.append((chtype, change, path.replace(m.group(0), m.group(1))))
                else:
                    entries = diffs.setdefault('', [])
                    entries.append((chtype, change, path.replace('root.', '')))

    return diffs
