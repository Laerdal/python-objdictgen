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
RE_JSONC = re.compile(r"(\".*?\"|\'.*?\')|(/\*.*?\*/|//[^\r\n]*$)", re.MULTILINE | re.DOTALL)


def remove_jasonc(text: str) -> str:
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


def str_to_number(string: str|int|float|None) -> str|int|float|None:
    """ Convert string to a number, otherwise pass it through """
    if string is None or isinstance(string, (int, float)):
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

    groups = [maps.MAPPING_DICTIONARY]
    if node:
        groups += node.GetMappings()

    # i2s: integer to string, s2i: string to integer
    i2s, s2i = {}, {}
    for group in groups:
        for k, v in group.items():
            if k >= 0x1000:
                continue
            n = v['name']
            i2s[k] = n
            s2i[n] = k

    if len(i2s) != len(s2i):
        raise ValidationError("Multiple names or numbers for object types in OD")

    # Must check everything, as this is used with unvalidated input
    for obj in dictionary or []:
        if not isinstance(obj, dict):
            continue
        index = str_to_number(obj.get('index'))
        name = obj.get('name')
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
        dsmap, menumap = nodelib.Node.ImportProfile(profilename)
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


def generate_json(node: "Node", compact=False, sort=False, internal=False, validate=True) -> str:
    """ Export a JSON string representation of the node """

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
            n = str_to_number(v)
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

    jd = contents
    if isinstance(contents, str):

        # Remove jsonc annotations
        jsontext = remove_jasonc(contents)

        # Load the json
        jd = json.loads(jsontext)

        # Remove any __ in the file
        jd = remove_underscore(jd)

    # FIXME: Dilemma: Where to place this. It belongs here with JSON, but it
    #        would make sense to place it after running the built-in validator.
    #        Often the od validator is better at giving useful errors
    #        than the json validator. However the type checking of the json
    #        validator is better.
    global SCHEMA  # pylint: disable=global-statement
    if not SCHEMA:
        with open(objdictgen.JSON_SCHEMA, 'r', encoding="utf-8") as f:
            SCHEMA = json.loads(remove_jasonc(f.read()))

    if SCHEMA:
        jsonschema.validate(jd, schema=SCHEMA)

    return node_fromdict(jd)


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

    # Get the dict representation of the node object
    jd = node.GetDict()

    # Rename the top-level fields
    for k, v in {
        'Name': 'name',
        'Description': 'description',
        'Type': 'type',
        'ID': 'id',
        'ProfileName': 'profile',
        'DefaultStringSize': 'default_string_size',
    }.items():
        if k in jd:
            jd[v] = jd.pop(k)

    # Insert meta-data
    jd.update({
        '$id': JSON_ID,
        '$version': JSON_INTERNAL_VERSION if internal else JSON_VERSION,
        '$description': JSON_DESCRIPTION,
        '$tool': str(objdictgen.ODG_PROGRAM) + ' ' + str(objdictgen.__version__),
        '$date': datetime.isoformat(datetime.now()),
    })

    # Get the order for the indexes
    order = node.GetAllParameters(sort=sort)

    # Get the object type mappings forwards (int to str) and backwards (str to int)
    objtypes_i2s, objtypes_s2i = get_object_types(node=node)

    # Parse through all parameters
    dictionary = []
    for index in order:
        obj = None
        try:
            # Get the internal dict representation of the node parameter
            obj = node.GetIndexDict(index)

            # Add in the index (as dictionary is a list)
            obj["index"] = f"0x{index:04X}" if rich else index

            # Don't wrangle further if the internal format is wanted
            if internal:
                continue

            # The internal memory model of Node is complex, this function exists
            # to validate the input data, i.e. the Node object before migrating
            # to JSON format. This is mainly to ensure no wrong assumptions
            # produce unexpected output.
            if validate:
                validate_nodeindex(node, index, obj)

            # Get the parameter for the index
            obj = node_todict_parameter(obj, node, index)

            # JSON format adoptions
            # ---------------------

            # The struct describes what kind of object structure this object have
            # See OD_* in node.py
            struct = obj["struct"]
            unused = obj.get("unused", False)

            info = []
            if not unused:
                info = list(node.GetAllSubentryInfos(index))

            # Rename the mandatory field
            if "need" in obj:
                obj["mandatory"] = obj.pop("need")

            # Replace numerical struct with symbolic value
            if rich:
                obj["struct"] = OD.to_string(struct, struct)

            if rich and "name" not in obj:
                obj["__name"] = node.GetEntryName(index)

            # Iterater over the sub-indexes (if present)
            for i, sub in enumerate(obj.get("sub", [])):

                # Add __name when rich format
                if rich and info and "name" not in sub:
                    sub["__name"] = info[i]["name"]

                # Replace numeric type with string value
                if rich and "type" in sub:
                    sub["type"] = objtypes_i2s.get(sub["type"], sub["type"])

                # # Add __type when rich format
                if rich and info and "type" not in sub:
                    sub["__type"] = objtypes_i2s.get(info[i]["type"], info[i]["type"])

            if 'each' in obj:
                sub = obj["each"]

                # Replace numeric type with string value
                if rich and "type" in sub:
                    sub["type"] = objtypes_i2s.get(sub["type"], sub["type"])

            # ---------------------

            # Rearrage order of 'sub' and 'each'
            obj["sub"] = [
                copy_in_order(k, JSON_SUB_ORDER)
                for k in obj["sub"]
            ]
            if 'each' in obj:
                obj["each"] = copy_in_order(obj["each"], JSON_SUB_ORDER)

        except Exception as exc:
            exc_amend(exc, f"Index 0x{index:04x} ({index}): ")
            raise

        finally:
            dictionary.append(obj)

    # Rearrange order of Dictionary[*]
    jd["dictionary"] = [
        copy_in_order(k, JSON_DICTIONARY_ORDER) for k in dictionary
    ]

    # Rearrange the order of the top-level dict
    jd = copy_in_order(jd, JSON_TOP_ORDER)

    # Cleanup of unwanted members
    # - NOTE: SpecificMenu is not used in dict representation
    for k in ('Dictionary', 'ParamsDictionary', 'Profile', 'SpecificMenu',
                'DS302', 'UserMapping', 'IndexOrder'):
        jd.pop(k, None)

    # Cross check verification to see if we later can import the generated dict
    if validate and not internal:
        validate_fromdict(remove_underscore(jd), objtypes_i2s, objtypes_s2i)

    return jd, objtypes_s2i


def node_todict_parameter(obj, node, index):
    """ Modify obj from internal dict representation to generic dict structure
        which is suitable for serialization into JSON.
    """

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
    # Blend the mapping type (baseobj) with obj

    # Get group membership (what object type it is) and if the prarmeter is repeated
    groups = obj.pop('groups')
    is_repeat = obj.pop('base', index) != index

    # Is the definition for the parameter present?
    if not is_repeat:

        # Extract mapping baseobject that contains the object definitions. Checked in A
        group = groups[0]
        if group != 'user':
            obj['group'] = group

        baseobj = obj.pop(group)
        struct = baseobj["struct"]  # Checked in B

    else:
        obj["repeat"] = True
        info = node.GetEntryInfos(index)
        baseobj = {}
        struct = info['struct']

    # Callback in mapping collides with the user set callback, so it is renamed
    if 'callback' in baseobj:
        obj['profile_callback'] = baseobj.pop('callback')

    # Move members from baseobj to top-level object. Checked in B
    for k in FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT:
        if k in baseobj:
            obj[k] = baseobj.pop(k)

    # Ensure fields exists
    obj['struct'] = struct
    obj['sub'] = obj.pop('values', [])

    # Move subindex[1] to 'each' on objecs that contain 'nbmax'
    if len(obj['sub']) > 1 and 'nbmax' in obj['sub'][1]:
        obj['each'] = obj['sub'].pop(1)

    # Baseobj should have been emptied
    if baseobj != {}:
        raise ValidationError(f"Mapping data not empty. Programming error?. Contains: {baseobj}")

    # -- STEP 2) --
    # Migrate 'params' and 'dictionary' to common 'sub'

    # Extract the params
    has_params = 'params' in obj
    has_dictionary = 'dictionary' in obj
    params = obj.pop("params", {})
    dictvals = obj.pop("dictionary", [])

    # These types places the params in the top-level dict
    if has_params and struct in (OD.VAR, OD.NVAR):
        params = params.copy()  # Important, as its mutated here
        param0 = {}
        for k in FIELDS_PARAMS:
            if k in params:
                param0[k] = params.pop(k)
        params[0] = param0

    # Promote the global parameters from params into top-level object
    for k in FIELDS_PARAMS_PROMOTE:
        if k in params:
            obj[k] = params.pop(k)

    # Extract the dictionary values
    # NOTE! It is important to capture that 'dictionary' exists is obj, even if
    #       empty. This might happen on a ARRAY with 0 elements.
    start = 0
    if has_dictionary:
        if struct in (OD.VAR, OD.NVAR):
            dictvals = [dictvals]
        else:
            start = 1  # Have "number of entries" first

        for i, v in enumerate(dictvals, start=start):
            params.setdefault(i, {})['value'] = v
    else:
        # This is now unused profile parameters are stored
        obj['unused'] = True

    # Commit the params to the 'sub' list
    if params:
        # Ensure there are enough items in 'sub' to hold the param items
        dictlen = start + len(dictvals)
        sub = obj["sub"]
        if dictlen > len(sub):
            sub += [{} for i in range(len(sub), dictlen)]

        # Commit the params to 'sub'
        for i, val in enumerate(sub):
            val.update(params.pop(i, {}))

    # Params should have been emptied
    if params != {}:
        raise ValidationError(f"User parameters not empty. Programming error? Contains: {params}")

    return obj


def validate_nodeindex(node: "Node", index: int, obj):
    """ Validate index dict contents (see Node.GetIndexDict). The purpose is to
        validate the assumptions in the data format.

        NOTE: This function exists to validate the node data in node_todict()
        to verify that the programmed assumptions are not wrong.
    """

    groups = obj['groups']
    is_repeat = obj.get('base', index) != index

    # Is the definition for the parameter present?
    if not is_repeat:

        # A) Ensure only one definition of the object group
        if len(groups) == 0:
            raise ValidationError("Missing mapping")
        if len(groups) != 1:
            raise ValidationError("Contains uexpected number of definitions for the object")

        # Extract the definition
        group = groups[0]
        baseobj = obj[group]

        # B) Check baseobj object members is present
        member_compare(
            baseobj.keys(),
            must=FIELDS_MAPPING_MUST, optional=FIELDS_MAPPING_OPT | FIELDS_PARAMS_PROMOTE,
            msg=' in mapping object'
        )

        struct = baseobj['struct']

    else:
        # If this is a repeated paramter, this object should not contain any definitions

        # A) Ensure no definition of the object group
        if len(groups) != 0:
            t_gr = ", ".join(groups)
            raise ValidationError(f"Unexpected to find any groups ({t_gr}) in repeated object")

        info = node.GetEntryInfos(index)
        baseobj = {}
        struct = info["struct"]  # Implicit

    # Helpers
    is_var = struct in (OD.VAR, OD.NVAR)

    # Ensure obj does NOT contain any fields found in baseobj (sanity check really)
    member_compare(
        obj.keys(),
        not_want=FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT | FIELDS_PARAMS_PROMOTE,
        msg=' in object'
    )

    # Check baseobj object members
    for val in baseobj.get('values', []):
        member_compare(
            val.keys(),
            must=FIELDS_MAPVALS_MUST, optional=FIELDS_MAPVALS_OPT,
            msg=' in mapping values'
        )

    # Collect some information
    params = obj.get('params', {})
    dictvalues = obj.get('dictionary', [])
    dictlen = 0

    # These types places the params in the top-level dict
    if params and is_var:
        params = params.copy()  # Important, as its mutated here
        param0 = {}
        for k in FIELDS_PARAMS:
            if k in params:
                param0[k] = params.pop(k)
        params[0] = param0

    # Verify type of dictionary
    if 'dictionary' in obj:
        if is_var:
            dictlen = 1
            # dictvalues = [dictvalues]
        else:
            if not isinstance(dictvalues, list):
                raise ValidationError(f"Unexpected type in dictionary '{dictvalues}'")
            dictlen = len(dictvalues) + 1
            # dictvalues = [None] + dictvalues  # Which is a copy

    # Check numbered params
    excessive = {}
    for param in params:
        # All int keys corresponds to a numbered index
        if isinstance(param, int):
            # Check that there are no unexpected fields in numbered param
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
    nbmax = ['nbmax' in v for v in baseobj.get('values', [])]
    lenok, nbmaxok = False, False

    if not baseobj:
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


def node_fromdict(jd: TODJson, internal=False) -> "Node":
    """ Convert a dict jd into a Node """

    # Remove all underscore keys from the file
    jd = remove_underscore(jd)
    assert isinstance(jd, dict)  # For mypy

    # Get the object type mappings forwards (int to str) and backwards (str to int)
    objtypes_i2s, objtypes_s2i = get_object_types(dictionary=jd.get("dictionary", []))

    # Validate the input json against the schema
    validate_fromdict(jd, objtypes_i2s, objtypes_s2i)

    # Create default values for optional components
    jd.setdefault("id", 0)
    jd.setdefault("profile", "None")

    # Create the node and fill the most basic data
    node = nodelib.Node(
        name=jd["name"], type=jd["type"], id=jd["id"],
        description=jd["description"], profilename=jd["profile"],
    )

    # Restore optional values
    if 'default_string_size' in jd:
        node.DefaultStringSize = jd["default_string_size"]

    # An import of a internal JSON file?
    internal = internal or jd['$version'] == JSON_INTERNAL_VERSION

    # Iterate over the items to convert them to Node object
    for obj in jd["dictionary"]:

        # Convert the index number (which might be "0x" string)
        index = str_to_number(obj['index'])
        obj["index"] = index
        assert isinstance(index, int)  # For mypy

        try:
            if not internal:
                # Mutate obj containing the generic dict to the internal node format
                obj = node_fromdict_parameter(obj, objtypes_s2i)

        except Exception as exc:
            exc_amend(exc, f"Index 0x{index:04x} ({index}): ")
            raise

        # Copy the object to node object entries
        if 'dictionary' in obj:
            node.Dictionary[index] = obj['dictionary']
        if 'params' in obj:
            node.ParamsDictionary[index] = {str_to_number(k): v for k, v in obj['params'].items()}
        if 'profile' in obj:
            node.Profile[index] = obj['profile']
        if 'ds302' in obj:
            node.DS302[index] = obj['ds302']
        if 'user' in obj:
            node.UserMapping[index] = obj['user']

        # Verify against built-in data (don't verify repeated params)
        if 'built-in' in obj and not obj.get('repeat', False):
            baseobj = maps.MAPPING_DICTIONARY.get(index)

            diff = deepdiff.DeepDiff(baseobj, obj['built-in'], view='tree')
            if diff:
                log.debug("Index 0x%04x (%s) Difference between built-in object and imported:", index, index)
                for line in diff.pretty().splitlines():
                    log.debug('  %s', line)
                raise ValidationError(
                    f"Built-in parameter index 0x{index:04x} ({index}) "
                    "does not match against system parameters"
                )

    # There is a weakness to the Node implementation: There is no store
    # of the order of the incoming parameters, instead the data is spread over
    # many dicts, e.g. Profile, DS302, UserMapping, Dictionary, ParamsDictionary
    # Node.IndexOrder has been added to store the order of the parameters.
    node.IndexOrder = [obj["index"] for obj in jd['dictionary']]

    return node


def node_fromdict_parameter(obj: TODObjJson, objtypes_s2i: dict[str, int]) -> TIndexEntry:
    """ Convert a json OD object into an object adapted for load into a Node
        object.
    """

    # -- STEP 1a) --
    # Move 'definition' into individual mapping type category

    baseobj = {}

    # Read "struct" (must)
    struct = obj["struct"]
    if not isinstance(struct, int):
        struct = OD.from_string(struct)
        obj["struct"] = struct  # Write value back into object

    # Read "group" (optional, default 'user', omit if repeat is True
    group = obj.pop("group", None) or 'user'

    # Read "profile_callback" (optional)
    if 'profile_callback' in obj:
        baseobj['callback'] = obj.pop('profile_callback')

    # Read "mandatory" (optional) into "need"
    if 'mandatory' in obj:
        obj['need'] = obj.pop('mandatory')

    # Restore the definition entries
    for k in FIELDS_MAPPING_MUST | FIELDS_MAPPING_OPT:
        if k in obj:
            baseobj[k] = obj.pop(k)

    # -- STEP 2) --
    # Migrate 'sub' into 'params' and 'dictionary'

    # Restore the param entries that has been promoted to obj
    params = {}
    for k in FIELDS_PARAMS_PROMOTE:
        if k in obj:
            params[k] = obj.pop(k)

    # Restore the values and dictionary
    subitems = obj.pop('sub')

    # Recreate the dictionary list
    dictionary = [
        v.pop('value')
        for v in subitems
        if v and 'value' in v
    ]

    # Restore the dictionary values
    if dictionary:
        # [N]VAR needs them as immediate values
        if struct in (OD.VAR, OD.NVAR):
            dictionary = dictionary[0]
        obj['dictionary'] = dictionary

    # The "unused" field is used to indicate that the parameter has no
    # dictionary value. Otherwise there must be an empty dictionary list
    # ==> "unused" is only read iff dictionary is empty
    elif not obj.get('unused', False):
        # NOTE: If struct in VAR and NVAR, it is not correct to set to [], but
        #       the should be captured by the validator.
        obj['dictionary'] = []

    # Restore param dictionary
    for i, vals in enumerate(subitems):
        pars = params.setdefault(i, {})
        for k in FIELDS_PARAMS:
            if k in vals:
                pars[k] = vals.pop(k)

    # Move entries from item 0 into the params object
    if 0 in params and struct in (OD.VAR, OD.NVAR):
        params.update(params.pop(0))

    # Remove the empty params and values
    params = {k: v for k, v in params.items() if not isinstance(v, dict) or v}
    subitems = [v for v in subitems if v]

    # Commit params if there is any data
    if params:
        obj['params'] = params

    # -- STEP 1b) --

    # Move back the each object
    if 'each' in obj:
        subitems.append(obj.pop('each'))

    # Restore optional items from subindex 0
    if not obj.get('repeat', False) and struct in (OD.ARRAY, OD.NARRAY, OD.RECORD, OD.NRECORD):
        index0 = subitems[0]
        for k, v in SUBINDEX0.items():
            index0.setdefault(k, v)

    # Restore 'type' text encoding into value
    for sub in subitems:
        if 'type' in sub:
            sub['type'] = objtypes_s2i.get(sub['type'], sub['type'])

    # Restore values
    if subitems:
        baseobj['values'] = subitems
        obj[group] = baseobj

    return obj


def validate_fromdict(jsonobj: TODJson, objtypes_i2s: dict[int, str]|None = None, objtypes_s2i: dict[str, int]|None = None):
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
        index = str_to_number(sindex)

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

        for chtype, changes in diff.items():
            for change in changes:
                path = change.path()
                entries = diffs.setdefault('', [])
                entries.append((chtype, change, path.replace('root', '')))

        diff = deepdiff.DeepDiff(jd1['dictionary'], jd2['dictionary'], view='tree', group_by='index')

        res = re.compile(r"root\[('0x[0-9a-fA-F]+'|\d+)\]")

        for chtype, changes in diff.items():
            for change in changes:
                path = change.path()
                m = res.search(path)
                if m:
                    num = str_to_number(m.group(1).strip("'"))
                    entries = diffs.setdefault(num, [])
                    entries.append((chtype, change, path.replace(m.group(0), '')))
                else:
                    entries = diffs.setdefault('', [])
                    entries.append((chtype, change, path.replace('root', '')))

    else:
        diff = deepdiff.DeepDiff(node1, node2, exclude_paths=[
            "root.IndexOrder"
        ], view='tree')

        res = re.compile(r"root\.(Profile|Dictionary|ParamsDictionary|UserMapping|DS302)\[(\d+)\]")

        for chtype, changes in diff.items():
            for change in changes:
                path = change.path()
                m = res.search(path)
                if m:
                    entries = diffs.setdefault(int(m.group(2)), [])
                    entries.append((chtype, change, path.replace(m.group(0), m.group(1))))
                else:
                    entries = diffs.setdefault('', [])
                    entries.append((chtype, change, path.replace('root.', '')))

    return diffs
