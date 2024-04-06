"""Object mappings."""
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
# Copyright (C): Edouard TISSERANT, Francis DUPIN and Laurent BESSARD
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

import ast
import itertools
import logging
import re
import traceback
from collections import UserDict, UserList
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar

import objdictgen
from objdictgen.typing import (TODObj, TODSubObj, TODValue, TParamEntry, TPath,
                               TProfileMenu)

T = TypeVar('T')

if TYPE_CHECKING:
    from objdictgen.node import Node

log = logging.getLogger('objdictgen')


#
# Dictionary of translation between access symbol and their signification
#
ACCESS_TYPE = {"ro": "Read Only", "wo": "Write Only", "rw": "Read/Write"}
BOOL_TYPE = {True: "True", False: "False"}
OPTION_TYPE = {True: "Yes", False: "No"}

# The first value is the type of the object, the second is the type of the subobject
# 0 indicates a numerical value, 1 indicates a non-numerical value such as strings
CUSTOMISABLE_TYPES: list[tuple[int, int]] = [
    (0x02, 0), (0x03, 0), (0x04, 0), (0x05, 0), (0x06, 0), (0x07, 0), (0x08, 0),
    (0x09, 1), (0x0A, 1), (0x0B, 1), (0x10, 0), (0x11, 0), (0x12, 0), (0x13, 0),
    (0x14, 0), (0x15, 0), (0x16, 0), (0x18, 0), (0x19, 0), (0x1A, 0), (0x1B, 0),
]
# FIXME: Using None is not to the type of these fields. Consider changing this
DEFAULT_PARAMS: TParamEntry = {"comment": None, "save": False, "buffer_size": None}


# ------------------------------------------------------------------------------
#                      Object Types and Organisation
# ------------------------------------------------------------------------------

class ODStructTypes:
    """Object Dictionary Structure Types"""
    #
    # Properties of entry structure in the Object Dictionary
    #
    Subindex = 1             # Entry has at least one subindex
    MultipleSubindexes = 2   # Entry has more than one subindex
    IdenticalSubindexes = 4  # Subindexes of entry have the same description
    IdenticalIndexes = 8     # Entry has the same description on multiple indexes

    #
    # Structures of entry in the Object Dictionary, sum of the properties described above
    # for all sorts of entries use in CAN Open specification
    #
    NOSUB = 0  # Entry without subindex (only for type declaration)
    VAR = Subindex  # 1
    RECORD = Subindex | MultipleSubindexes  # 3
    ARRAY = Subindex | MultipleSubindexes | IdenticalSubindexes  # 7
    # Entries identical on multiple indexes
    NVAR = Subindex | IdenticalIndexes  # 9
    NRECORD = Subindex | MultipleSubindexes | IdenticalIndexes  # 11, Example : PDO Parameters
    NARRAY = Subindex | MultipleSubindexes | IdenticalSubindexes | IdenticalIndexes  # 15, Example : PDO Mapping

    #
    # Mapping against name and structure number
    #
    STRINGS: dict[int, str|None] = {
        NOSUB: None,
        VAR: "var",
        RECORD: "record",
        ARRAY: "array",
        NVAR: "nvar",
        NRECORD: "nrecord",
        NARRAY: "narray",
    }
    # FIXME: Having None here should be avoided. Look into setting this to
    # an empty string instead. It will simplify the typing for to_string and from_string

    @classmethod
    def to_string(cls: type["ODStructTypes"], val: int, default: str = '') -> str|None:
        """Return the string representation of the structure value."""
        return cls.STRINGS.get(val, default)

    @classmethod
    def from_string(cls: type["ODStructTypes"], val: str, default: int|None = None) -> int|None:
        """Return the structure value from the string representation."""
        try:
            return next(k for k, v in cls.STRINGS.items() if v == val)
        except StopIteration:
            return default


# Convenience shortcut
OD = ODStructTypes

#
# List of the Object Dictionary ranges
#
INDEX_RANGES = [
    {"min": 0x0001, "max": 0x0FFF, "name": "dtd", "description": "Data Type Definitions"},
    {"min": 0x1000, "max": 0x1029, "name": "cp", "description": "Communication Parameters"},
    {"min": 0x1200, "max": 0x12FF, "name": "sdop", "description": "SDO Parameters"},
    {"min": 0x1400, "max": 0x15FF, "name": "rpdop", "description": "Receive PDO Parameters"},
    {"min": 0x1600, "max": 0x17FF, "name": "rpdom", "description": "Receive PDO Mapping"},
    {"min": 0x1800, "max": 0x19FF, "name": "tpdop", "description": "Transmit PDO Parameters"},
    {"min": 0x1A00, "max": 0x1BFF, "name": "tpdom", "description": "Transmit PDO Mapping"},
    {"min": 0x1C00, "max": 0x1FFF, "name": "ocp", "description": "Other Communication Parameters"},
    {"min": 0x2000, "max": 0x5FFF, "name": "ms", "description": "Manufacturer Specific"},
    {"min": 0x6000, "max": 0x9FFF, "name": "sdp", "description": "Standardized Device Profile"},
    {"min": 0xA000, "max": 0xBFFF, "name": "sip", "description": "Standardized Interface Profile"},
]

# ------------------------------------------------------------------------------
#                      Evaluation of values
# ------------------------------------------------------------------------------

# Used to match strings such as 'Additional Server SDO %d Parameter %d[(idx, sub)]'
# This example matches to two groups
# ['Additional Server SDO %d Parameter %d', 'idx, sub']
RE_NAME_SYNTAX = re.compile(r'(.*)\[[(](.*)[)]\]')

# Regular expression to match $NODEID in a string
RE_NODEID = re.compile(r'\$NODEID\b', re.IGNORECASE)


def eval_value(value, base, nodeid, compute=True):
    """
    Evaluate the value. They can be strings that needs additional
    parsing. Such as "'$NODEID+0x600'" and
    "'{True:"$NODEID+0x%X00"%(base+2),False:0x80000000}[base<4]'".
    """

    # Non-string and strings that doens't contain $NODEID can return as-is
    if not (isinstance(value, str) and RE_NODEID.search(value)):
        return value

    # This will remove any surrouning quotes on strings ('"$NODEID+0x20"')
    # and will resolve "{True:"$NODEID..." expressions.
    value = evaluate_expression(value,
        {   # These are the vars that can be used within the string
            'base': base,
        }
    )

    if compute and isinstance(value, str):
        # Replace $NODEID with 'nodeid' so it can be evaluated.
        value = RE_NODEID.sub("nodeid", value)

        # This will resolve '$NODEID' expressions
        value = evaluate_expression(value,
            {   # These are the vars that can be used within the string
                'nodeid': nodeid,
            }
        )

    return value


def eval_name(text, idx, sub):
    """
    Format the text given with the index and subindex defined.
    Used to parse dynamic values such as
    "Additional Server SDO %d Parameter[(idx)]"
    """
    result = RE_NAME_SYNTAX.match(text)
    if not result:
        return text

    # NOTE: Legacy Python2 format evaluations are baked
    #       into the OD and must be supported for legacy
    return result.group(1) % evaluate_expression(
        result.group(2).strip(),
        {   # These are the vars that can be used in the string
            'idx': idx,
            'sub': sub,
        }
    )


def evaluate_expression(expression: str, localvars: dict[str, Any]|None = None):
    """Parses a string expression and attempts to calculate the result
    Supports:
        - Binary operations: addition, subtraction, multiplication, modulo
        - Comparisons: less than
        - Subscripting: (i.e. "a[1]")
        - Constants: int, float, complex, str, boolean
        - Variable names: from the localvars dict
        - Function calls: from the localvars dict
        - Tuples: (i.e. "(1, 2, 3)")
        - Dicts: (i.e. "{1: 2, 3: 4}")
    Parameters:
        expression (str): string to parse
        localvars (dict): dictionary of local variables and functions to
            access in the expression
    """
    localvars = localvars or {}

    def _evnode(node: ast.AST):
        """
        Recursively parses ast.Node objects to evaluate arithmatic expressions
        """
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                return _evnode(node.left) + _evnode(node.right)
            if isinstance(node.op, ast.Sub):
                return _evnode(node.left) - _evnode(node.right)
            if isinstance(node.op, ast.Mult):
                return _evnode(node.left) * _evnode(node.right)
            if isinstance(node.op, ast.Mod):
                return _evnode(node.left) % _evnode(node.right)
            raise SyntaxError(f"Unsupported arithmetic operation {type(node.op)}")
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise SyntaxError(f"Chained comparisons not supported")
            if isinstance(node.ops[0], ast.Lt):
                return _evnode(node.left) < _evnode(node.comparators[0])
            raise SyntaxError(f"Unsupported comparison operation {type(node.ops[0])}")
        if isinstance(node, ast.Subscript):
            return _evnode(node.value)[_evnode(node.slice)]
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int | float | complex | str):
                return node.value
            raise TypeError(f"Unsupported constant {node.value}")
        if isinstance(node, ast.Name):
            if node.id not in localvars:
                raise NameError(f"Name '{node.id}' is not defined")
            return localvars[node.id]
        if isinstance(node, ast.Call):
            return _evnode(node.func)(
                *[_evnode(arg) for arg in node.args],
                **{k.arg: _evnode(k.value) for k in node.keywords}
            )
        if isinstance(node, ast.Tuple):
            return tuple(_evnode(elt) for elt in node.elts)
        if isinstance(node, ast.Dict):
            return {_evnode(k): _evnode(v) for k, v in zip(node.keys, node.values)}
        raise TypeError(f"Unsupported syntax of type {type(node)}")

    try:
        tree = ast.parse(expression, mode="eval")
        return _evnode(tree.body)
    except Exception as exc:
        raise type(exc)(f"{exc.args[0]} in parsing of expression '{expression}'"
                        ).with_traceback(exc.__traceback__) from None


# ------------------------------------------------------------------------------
#                      Misc functions
# ------------------------------------------------------------------------------

def import_profile(profilename):

    # Test if the profilename is a filepath which can be used directly. If not
    # treat it as the name
    # The UI use full filenames, while all other uses use profile names
    profilepath = Path(profilename)
    if not profilepath.exists():
        fname = f"{profilename}.prf"

        try:
            profilepath = next(
                base / fname
                for base in objdictgen.PROFILE_DIRECTORIES
                if (base / fname).exists()
            )
        except StopIteration:
            raise ValueError(
                f"Unable to load profile '{profilename}': '{fname}': No such file or directory"
            ) from None

    # Mapping and AddMenuEntries are expected to be defined by the execfile
    # The profiles requires some vars to be set
    # pylint: disable=unused-variable
    try:
        with open(profilepath, "r", encoding="utf-8") as f:
            log.debug("EXECFILE %s", profilepath)
            code = compile(f.read(), profilepath, 'exec')
            exec(code, globals(), locals())  # FIXME: Using exec is unsafe
            # pylint: disable=undefined-variable
            return Mapping, AddMenuEntries  # pyright: ignore  # noqa: F821
    except Exception as exc:  # pylint: disable=broad-except
        log.debug("EXECFILE FAILED: %s", exc)
        log.debug(traceback.format_exc())
        raise ValueError(f"Loading profile '{profilepath}' failed: {exc}") from exc

def get_index_range(index):
    for irange in INDEX_RANGES:
        if irange["min"] <= index <= irange["max"]:
            return irange
    raise ValueError(f"Cannot find index range for value '0x{index:x}'")

def be_to_le(value):
    """
    Convert Big Endian to Little Endian
    @param value: value expressed in Big Endian
    @param size: number of bytes generated
    @return: a string containing the value converted
    """

    # FIXME: This function is used in assosciation with DCF files, but have
    # not been able to figure out how that work. It is very likely that this
    # function is not working properly after the py2 -> py3 conversion
    raise NotImplementedError("be_to_le() may be broken in py3")

    # FIXME: The function title is confusing as the input data type (str) is
    # different than the output (int)
    return int("".join([f"{ord(char):02X}" for char in reversed(value)]), 16)

def le_to_be(value, size):
    """
    Convert Little Endian to Big Endian
    @param value: value expressed in integer
    @param size: number of bytes generated
    @return: a string containing the value converted
    """

    # FIXME: This function is used in assosciation with DCF files, but have
    # not been able to figure out how that work. It is very likely that this
    # function is not working properly after the py2 -> py3 conversion due to
    # the change of chr() behavior
    raise NotImplementedError("le_to_be() is broken in py3")

    # FIXME: The function title is confusing as the input data type (int) is
    # different than the output (str)
    data = ("%" + str(size * 2) + "." + str(size * 2) + "X") % value
    list_car = [data[i:i + 2] for i in range(0, len(data), 2)]
    list_car.reverse()
    return "".join([chr(int(car, 16)) for car in list_car])


# ------------------------------------------------------------------------------
#                      Objects and mapping
# ------------------------------------------------------------------------------

class ODMapping(UserDict[int, TODObj]):
    """Object Dictionary Mapping."""

    @staticmethod
    def FindIndex(index, mappingdictionary):
        """
        Return the index of the informations in the Object Dictionary in case of identical
        indexes
        """
        if index in mappingdictionary:
            return index
        listpluri = [
            idx for idx, mapping in mappingdictionary.items()
            if mapping["struct"] & OD.IdenticalIndexes
        ]
        for idx in sorted(listpluri):
            nb_max = mappingdictionary[idx]["nbmax"]
            incr = mappingdictionary[idx]["incr"]
            if idx < index < idx + incr * nb_max and (index - idx) % incr == 0:
                return idx
        return None

    @staticmethod
    def FindTypeIndex(typename, mappingdictionary):
        """
        Return the index of the typename given by searching in mappingdictionary
        """
        return {
            values["name"]: index
            for index, values in mappingdictionary.items()
            if index < 0x1000
        }.get(typename)

    @staticmethod
    def FindTypeName(typeindex, mappingdictionary):
        """
        Return the name of the type by searching in mappingdictionary
        """
        if typeindex < 0x1000 and typeindex in mappingdictionary:
            return mappingdictionary[typeindex]["name"]
        return None

    @staticmethod
    def FindTypeDefaultValue(typeindex, mappingdictionary):
        """
        Return the default value of the type by searching in mappingdictionary
        """
        if typeindex < 0x1000 and typeindex in mappingdictionary:
            return mappingdictionary[typeindex]["default"]
        return None

    @staticmethod
    def FindTypeList(mappingdictionary):
        """
        Return the list of types defined in mappingdictionary
        """
        return [
            mappingdictionary[index]["name"]
            for index in mappingdictionary
            if index < 0x1000
        ]

    @staticmethod
    def FindMandatoryIndexes(mappingdictionary):
        """
        Return the list of mandatory indexes defined in mappingdictionary
        """
        return [
            index
            for index in mappingdictionary
            if index >= 0x1000 and mappingdictionary[index]["need"]
        ]

    @staticmethod
    def FindEntryName(index, mappingdictionary, compute=True):
        """
        Return the name of an entry by searching in mappingdictionary
        """
        base_index = ODMapping.FindIndex(index, mappingdictionary)
        if base_index:
            infos = mappingdictionary[base_index]
            if infos["struct"] & OD.IdenticalIndexes and compute:
                return eval_name(
                    infos["name"], idx=(index - base_index) // infos["incr"] + 1, sub=0
                )
            return infos["name"]
        return None

    @staticmethod
    def FindEntryInfos(index, mappingdictionary, compute=True):
        """
        Return the informations of one entry by searching in mappingdictionary
        """
        base_index = ODMapping.FindIndex(index, mappingdictionary)
        if base_index:
            obj = mappingdictionary[base_index].copy()
            if obj["struct"] & OD.IdenticalIndexes and compute:
                obj["name"] = eval_name(
                    obj["name"], idx=(index - base_index) // obj["incr"] + 1, sub=0
                )
            obj.pop("values")
            return obj
        return None

    @staticmethod
    def FindSubentryInfos(index, subindex, mappingdictionary, compute=True):
        """
        Return the informations of one subentry of an entry by searching in mappingdictionary
        """
        base_index = ODMapping.FindIndex(index, mappingdictionary)
        if base_index:
            struct = mappingdictionary[base_index]["struct"]
            if struct & OD.Subindex:
                infos = None
                if struct & OD.IdenticalSubindexes:
                    if subindex == 0:
                        infos = mappingdictionary[base_index]["values"][0].copy()
                    elif 0 < subindex <= mappingdictionary[base_index]["values"][1]["nbmax"]:
                        infos = mappingdictionary[base_index]["values"][1].copy()
                elif struct & OD.MultipleSubindexes:
                    idx = 0
                    for subindex_infos in mappingdictionary[base_index]["values"]:
                        if "nbmax" in subindex_infos:
                            if idx <= subindex < idx + subindex_infos["nbmax"]:
                                infos = subindex_infos.copy()
                                break
                            idx += subindex_infos["nbmax"]
                        else:
                            if subindex == idx:
                                infos = subindex_infos.copy()
                                break
                            idx += 1
                elif subindex == 0:
                    infos = mappingdictionary[base_index]["values"][0].copy()

                if infos is not None and compute:
                    if struct & OD.IdenticalIndexes:
                        incr = mappingdictionary[base_index]["incr"]
                    else:
                        incr = 1
                    infos["name"] = eval_name(
                        infos["name"], idx=(index - base_index) // incr + 1, sub=subindex
                    )

                return infos
        return None

    @staticmethod
    def FindMapVariableList(mappingdictionary, node, compute=True):
        """
        Return the list of variables that can be mapped defined in mappingdictionary
        """
        for index in mappingdictionary:
            if node.IsEntry(index):
                for subindex, values in enumerate(mappingdictionary[index]["values"]):
                    if mappingdictionary[index]["values"][subindex]["pdo"]:
                        infos = node.GetEntryInfos(mappingdictionary[index]["values"][subindex]["type"])
                        name = mappingdictionary[index]["values"][subindex]["name"]
                        if mappingdictionary[index]["struct"] & OD.IdenticalSubindexes:
                            values = node.GetEntry(index)
                            for i in range(len(values) - 1):
                                computed_name = name
                                if compute:
                                    computed_name = eval_name(computed_name, idx=1, sub=i + 1)
                                yield (index, i + 1, infos["size"], computed_name)
                        else:
                            computed_name = name
                            if compute:
                                computed_name = eval_name(computed_name, idx=1, sub=subindex)
                            yield (index, subindex, infos["size"], computed_name)

    #
    # HELPERS
    #

    def find(self, predicate: Callable[[int, TODObj], bool|int]) -> Generator[tuple[int, TODObj], None, None]:
        """Return the first object that matches the function"""
        for index, obj in self.items():
            if predicate(index, obj):
                yield index, obj


class ODMappingList(UserList[ODMapping]):
    """List of Object Dictionary Mappings."""


#
# MAPPING_DICTIONARY is the structure used for writing a good organised Object
# Dictionary. It follows the specifications of the CANOpen standard.
# Change the informations within it if there is a mistake. But don't modify the
# organisation of this object, it will involve in a malfunction of the application.
#
# FIXME: Move this to a separate json file
MAPPING_DICTIONARY = ODMapping({
    # -- Static Data Types
    0x0001: {"name": "BOOLEAN", "struct": OD.NOSUB, "size": 1, "default": False, "values": []},
    0x0002: {"name": "INTEGER8", "struct": OD.NOSUB, "size": 8, "default": 0, "values": []},
    0x0003: {"name": "INTEGER16", "struct": OD.NOSUB, "size": 16, "default": 0, "values": []},
    0x0004: {"name": "INTEGER32", "struct": OD.NOSUB, "size": 32, "default": 0, "values": []},
    0x0005: {"name": "UNSIGNED8", "struct": OD.NOSUB, "size": 8, "default": 0, "values": []},
    0x0006: {"name": "UNSIGNED16", "struct": OD.NOSUB, "size": 16, "default": 0, "values": []},
    0x0007: {"name": "UNSIGNED32", "struct": OD.NOSUB, "size": 32, "default": 0, "values": []},
    0x0008: {"name": "REAL32", "struct": OD.NOSUB, "size": 32, "default": 0.0, "values": []},
    0x0009: {"name": "VISIBLE_STRING", "struct": OD.NOSUB, "size": 8, "default": "", "values": []},
    0x000A: {"name": "OCTET_STRING", "struct": OD.NOSUB, "size": 8, "default": "", "values": []},
    0x000B: {"name": "UNICODE_STRING", "struct": OD.NOSUB, "size": 16, "default": "", "values": []},
    # 0x000C: {"name": "TIME_OF_DAY", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    # 0x000D: {"name": "TIME_DIFFERENCE", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    # 0x000E: RESERVED
    0x000F: {"name": "DOMAIN", "struct": OD.NOSUB, "size": 0, "default": "", "values": []},
    0x0010: {"name": "INTEGER24", "struct": OD.NOSUB, "size": 24, "default": 0, "values": []},
    0x0011: {"name": "REAL64", "struct": OD.NOSUB, "size": 64, "default": 0.0, "values": []},
    0x0012: {"name": "INTEGER40", "struct": OD.NOSUB, "size": 40, "default": 0, "values": []},
    0x0013: {"name": "INTEGER48", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    0x0014: {"name": "INTEGER56", "struct": OD.NOSUB, "size": 56, "default": 0, "values": []},
    0x0015: {"name": "INTEGER64", "struct": OD.NOSUB, "size": 64, "default": 0, "values": []},
    0x0016: {"name": "UNSIGNED24", "struct": OD.NOSUB, "size": 24, "default": 0, "values": []},
    # 0x0017: RESERVED
    0x0018: {"name": "UNSIGNED40", "struct": OD.NOSUB, "size": 40, "default": 0, "values": []},
    0x0019: {"name": "UNSIGNED48", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    0x001A: {"name": "UNSIGNED56", "struct": OD.NOSUB, "size": 56, "default": 0, "values": []},
    0x001B: {"name": "UNSIGNED64", "struct": OD.NOSUB, "size": 64, "default": 0, "values": []},
    # 0x001C-0x001F: RESERVED

    # -- Communication Profile Area
    0x1000: {"name": "Device Type", "struct": OD.VAR, "need": True, "values": [
        {"name": "Device Type", "type": 0x07, "access": 'ro', "pdo": False}]},
    0x1001: {"name": "Error Register", "struct": OD.VAR, "need": True, "values": [
        {"name": "Error Register", "type": 0x05, "access": 'ro', "pdo": True}]},
    0x1002: {"name": "Manufacturer Status Register", "struct": OD.VAR, "need": False, "values": [
        {"name": "Manufacturer Status Register", "type": 0x07, "access": 'ro', "pdo": True}]},
    0x1003: {"name": "Pre-defined Error Field", "struct": OD.ARRAY, "need": False, "callback": True, "values": [
        {"name": "Number of Errors", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Standard Error Field", "type": 0x07, "access": 'ro', "pdo": False, "nbmin": 1, "nbmax": 0xFE}]},
    0x1005: {"name": "SYNC COB ID", "struct": OD.VAR, "need": False, "callback": True, "values": [
        {"name": "SYNC COB ID", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1006: {"name": "Communication / Cycle Period", "struct": OD.VAR, "need": False, "callback": True, "values": [
        {"name": "Communication Cycle Period", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1007: {"name": "Synchronous Window Length", "struct": OD.VAR, "need": False, "values": [
        {"name": "Synchronous Window Length", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1008: {"name": "Manufacturer Device Name", "struct": OD.VAR, "need": False, "values": [
        {"name": "Manufacturer Device Name", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x1009: {"name": "Manufacturer Hardware Version", "struct": OD.VAR, "need": False, "values": [
        {"name": "Manufacturer Hardware Version", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x100A: {"name": "Manufacturer Software Version", "struct": OD.VAR, "need": False, "values": [
        {"name": "Manufacturer Software Version", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x100C: {"name": "Guard Time", "struct": OD.VAR, "need": False, "values": [
        {"name": "Guard Time", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x100D: {"name": "Life Time Factor", "struct": OD.VAR, "need": False, "values": [
        {"name": "Life Time Factor", "type": 0x05, "access": 'rw', "pdo": False}]},
    0x1010: {"name": "Store parameters", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Save All Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Save Communication Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Save Application Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Save Manufacturer Parameters %d[(sub - 3)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmax": 0x7C}]},
    0x1011: {"name": "Restore Default Parameters", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Restore All Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Restore Communication Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Restore Application Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Restore Manufacturer Defined Default Parameters %d[(sub - 3)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmax": 0x7C}]},
    0x1012: {"name": "TIME COB ID", "struct": OD.VAR, "need": False, "values": [
        {"name": "TIME COB ID", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1013: {"name": "High Resolution Timestamp", "struct": OD.VAR, "need": False, "values": [
        {"name": "High Resolution Time Stamp", "type": 0x07, "access": 'rw', "pdo": True}]},
    0x1014: {"name": "Emergency COB ID", "struct": OD.VAR, "need": False, "values": [
        {"name": "Emergency COB ID", "type": 0x07, "access": 'rw', "pdo": False, "default": '"$NODEID+0x80"'}]},
    0x1015: {"name": "Inhibit Time Emergency", "struct": OD.VAR, "need": False, "values": [
        {"name": "Inhibit Time Emergency", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1016: {"name": "Consumer Heartbeat Time", "struct": OD.ARRAY, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Consumer Heartbeat Time", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 1, "nbmax": 0x7F}]},
    0x1017: {"name": "Producer Heartbeat Time", "struct": OD.VAR, "need": False, "callback": True, "values": [
        {"name": "Producer Heartbeat Time", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1018: {"name": "Identity", "struct": OD.RECORD, "need": True, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Vendor ID", "type": 0x07, "access": 'ro', "pdo": False},
        {"name": "Product Code", "type": 0x07, "access": 'ro', "pdo": False},
        {"name": "Revision Number", "type": 0x07, "access": 'ro', "pdo": False},
        {"name": "Serial Number", "type": 0x07, "access": 'ro', "pdo": False}]},
    0x1019: {"name": "Synchronous counter overflow value", "struct": OD.VAR, "need": False, "values": [
        {"name": "Synchronous counter overflow value", "type": 0x05, "access": 'rw', "pdo": False}]},
    0x1020: {"name": "Verify Configuration", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Configuration Date", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Configuration Time", "type": 0x07, "access": 'rw', "pdo": False}]},
    # 0x1021: {"name": "Store EDS", "struct": OD.VAR, "need": False, "values": [
    #     {"name": "Store EDS", "type": 0x0F, "access": 'rw', "pdo": False}]},
    # 0x1022: {"name": "Storage Format", "struct": OD.VAR, "need": False, "values": [
    #     {"name": "Storage Format", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1023: {"name": "OS Command", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Command", "type": 0x0A, "access": 'rw', "pdo": False},
        {"name": "Status", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Reply", "type": 0x0A, "access": 'ro', "pdo": False}]},
    0x1024: {"name": "OS Command Mode", "struct": OD.VAR, "need": False, "values": [
        {"name": "OS Command Mode", "type": 0x05, "access": 'wo', "pdo": False}]},
    0x1025: {"name": "OS Debugger Interface", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Command", "type": 0x0A, "access": 'rw', "pdo": False},
        {"name": "Status", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Reply", "type": 0x0A, "access": 'ro', "pdo": False}]},
    0x1026: {"name": "OS Prompt", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "StdIn", "type": 0x05, "access": 'wo', "pdo": True},
        {"name": "StdOut", "type": 0x05, "access": 'ro', "pdo": True},
        {"name": "StdErr", "type": 0x05, "access": 'ro', "pdo": True}]},
    0x1027: {"name": "Module List", "struct": OD.ARRAY, "need": False, "values": [
        {"name": "Number of Connected Modules", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Module %d[(sub)]", "type": 0x06, "access": 'ro', "pdo": False, "nbmin": 1, "nbmax": 0xFE}]},
    0x1028: {"name": "Emergency Consumer", "struct": OD.ARRAY, "need": False, "values": [
        {"name": "Number of Consumed Emergency Objects", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Emergency Consumer", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 1, "nbmax": 0x7F}]},
    0x1029: {"name": "Error Behavior", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Error Classes", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "Communication Error", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Device Profile", "type": 0x05, "access": 'rw', "pdo": False, "nbmax": 0xFE}]},

    # -- Server SDO Parameters
    0x1200: {"name": "Server SDO Parameter", "struct": OD.RECORD, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "COB ID Client to Server (Receive SDO)", "type": 0x07, "access": 'ro', "pdo": False, "default": '"$NODEID+0x600"'},
        {"name": "COB ID Server to Client (Transmit SDO)", "type": 0x07, "access": 'ro', "pdo": False, "default": '"$NODEID+0x580"'}]},
    0x1201: {"name": "Additional Server SDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x7F, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "COB ID Client to Server (Receive SDO)", "type": 0x07, "access": 'ro', "pdo": False},
        {"name": "COB ID Server to Client (Transmit SDO)", "type": 0x07, "access": 'ro', "pdo": False},
        {"name": "Node ID of the SDO Client", "type": 0x05, "access": 'ro', "pdo": False}]},

    # -- Client SDO Parameters
    0x1280: {"name": "Client SDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x100, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "COB ID Client to Server (Transmit SDO)", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "COB ID Server to Client (Receive SDO)", "type": 0x07, "access": 'rw', "pdo": False},
        {"name": "Node ID of the SDO Server", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Receive PDO Communication Parameters
    0x1400: {"name": "Receive PDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x200, "need": False, "values": [
        {"name": "Highest SubIndex Supported", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "COB ID used by PDO", "type": 0x07, "access": 'rw', "pdo": False, "default": "{True:\"$NODEID+0x%X00\"%(base+2),False:0x80000000}[base<4]"},
        {"name": "Transmission Type", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Inhibit Time", "type": 0x06, "access": 'rw', "pdo": False},
        {"name": "Compatibility Entry", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Event Timer", "type": 0x06, "access": 'rw', "pdo": False},
        {"name": "SYNC start value", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Receive PDO Mapping Parameters
    0x1600: {"name": "Receive PDO %d Mapping[(idx)]", "struct": OD.NARRAY, "incr": 1, "nbmax": 0x200, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "PDO %d Mapping for an application object %d[(idx,sub)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 0, "nbmax": 0x40}]},

    # -- Transmit PDO Communication Parameters
    0x1800: {"name": "Transmit PDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x200, "need": False, "callback": True, "values": [
        {"name": "Highest SubIndex Supported", "type": 0x05, "access": 'ro', "pdo": False},
        {"name": "COB ID used by PDO", "type": 0x07, "access": 'rw', "pdo": False, "default": "{True:\"$NODEID+0x%X80\"%(base+1),False:0x80000000}[base<4]"},
        {"name": "Transmission Type", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Inhibit Time", "type": 0x06, "access": 'rw', "pdo": False},
        {"name": "Compatibility Entry", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "Event Timer", "type": 0x06, "access": 'rw', "pdo": False},
        {"name": "SYNC start value", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Transmit PDO Mapping Parameters
    0x1A00: {"name": "Transmit PDO %d Mapping[(idx)]", "struct": OD.NARRAY, "incr": 1, "nbmax": 0x200, "need": False, "values": [
        {"name": "Number of Entries", "type": 0x05, "access": 'rw', "pdo": False},
        {"name": "PDO %d Mapping for a process data variable %d[(idx,sub)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 0, "nbmax": 0x40}]},
})
