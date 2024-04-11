"""Typing stubs for the objdictgen module."""
#
# Copyright (C) 2024  Svein Seldal, Laerdal Medical AS
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

import os
from typing import TYPE_CHECKING, Iterator, Protocol, TypedDict

import deepdiff.model  # type: ignore[import]  # Due to missing typing stubs for deepdiff

if TYPE_CHECKING:
    from objdictgen.maps import ODMapping


#  MAPS
# ======

TODValue = bool|int|float|str
"""Type for storing the value of an object dictionary entry."""

TODSubObj = TypedDict('TODSubObj', {
    "name": str,
    "type": int,
    "access": str,
    "pdo": bool,
    "nbmin": int,
    "nbmax": int,
    "default": TODValue,
}, total=False)
"""Dict-like type for the sub-object dictionary mappings."""

TODObj = TypedDict('TODObj', {
    "name": str,
    "struct": int,
    "size": int,
    "default": TODValue,
    "values": list[TODSubObj],
    "need": bool,
    "callback": bool,
    "incr": int,
    "nbmin": int,
    "nbmax": int,
}, total=False)
"""Dict-like type for the object dictionary mappings."""

# See maps.import_profile
TProfileMenu = list[tuple[str, list[int]]]
"""Type for the profile menu entries."""


#  NODE
# ======

TPath = os.PathLike[str] | str
"""Type for a file path."""

TParamEntry = TypedDict('TParamEntry', {
    "comment": str,
    "buffer_size": int,
    "save": bool,
    # "callback": bool,  # It can exist in the ParamsDictionary dict, but not as subenties
}, total=False)
"""Type for storing a object dictionary parameter entry."""

TIndexEntry = TypedDict('TIndexEntry', {
    'index': int,
    'dictionary': TODValue|list[TODValue],
    'params': TParamEntry|dict[int, TParamEntry],
    'object': TODObj,
    'base': int,
    'basestruct': int,
    'groups': list[str],
}, total=False)
"""Type representing the full entry of an object dictionary index."""


class NodeProtocol(Protocol):
    """Protocol for the Node class."""

    # pylint: disable=unnecessary-ellipsis

    Name: str
    """Name of the node."""

    Type: str
    """Type of the node. Either "master" or "slave"."""

    ID: int
    """Node ID."""

    Description: str
    """Node description."""

    ProfileName: str
    """Name of any loaded profiles. "None" if no profile is loaded."""

    Profile: "ODMapping"
    """Mapping containing the object definitions for the profile."""

    DefaultStringSize: int
    """Setting for the default string size."""

    def __iter__(self) -> Iterator[int]:
        """Iterate over the entries of the node."""
        ...

    def GetEntryName(self, index: int, compute: bool = True) -> str:
        """Get the name of the entry with the given index."""
        ...

    def GetEntry(self, index:int, subindex: int|None = None,
                    compute: bool = True, aslist: bool = False) -> list[TODValue]|TODValue:
        """Get the value of the entry with the given index and subindex."""
        ...

    def GetTypeName(self, index: int) -> str:
        """Get the type name of the entry with the given index."""
        ...

    def GetEntryInfos(self, index: int, compute: bool = True) -> TODObj:
        """Get the dictionary of the entry with the given index."""
        ...

    def GetParamsEntry(self, index: int, subindex: int|None = None,
                        aslist: bool = False) -> TParamEntry|list[TParamEntry]:
        """Get the parameters of the entry with the given index."""
        ...

    def GetSubentryInfos(self, index: int, subindex: int, compute: bool = True) -> TODSubObj:
        """Get the dictionary of the subentry with the given index and subindex."""
        ...

    def GetIndexes(self) -> list[int]:
        """ Return a sorted list of indexes in Object Dictionary """
        ...

    def GetNodeName(self) -> str:
        """Get the name of the node."""
        ...

    def GetNodeID(self) -> int:
        """Get the ID of the node."""
        ...

    def GetNodeType(self) -> str:
        """Get the type of the node."""
        ...

    def GetNodeDescription(self) -> str:
        """Get the description of the node."""
        ...

    def GetDefaultStringSize(self) -> int:
        """Get the default string size setting."""
        ...


#  JSON
# ======
# Keep the TOD*Json types in sync with the JSON schema

# Corresponds to #subitem and #subitem_repeat in json schema
TODSubObjJson = TypedDict('TODSubObjJson', {
    "name": str,
    "comment": str,
    "buffer_size": int|str,
    "type": int|str,
    "access": str,
    "pdo": bool,
    "default": TODValue,
    "save": bool,
    "value": TODValue,

    # Convenience fields
    "__name": str,
    "__type": str,
})
"""JSON object dictionary sub-object type definition."""

# Corresponds to "#each" in json schema
TODEachJson = TypedDict('TODEachJson', {
    "name": str,
    "type": int|str,
    "access": str,
    "pdo": bool,
    "nbmin": int,
    "nbmax": int,
    "default": TODValue,
})
"""JSON object dictionary "each" type definition."""

# Corresponds to "#object" in json schema
TODObjJson = TypedDict('TODObjJson', {
    "index": int|str,
    "name": str,
    "struct": int|str,
    "group": str|None,  # FIXME: Don't really want None here
    "mandatory": bool,
    "unused": bool,
    "default": TODValue,
    "size": int,
    "incr": int,
    "nbmax": int,
    "repeat": bool,
    "profile_callback": bool,
    "callback": bool,
    "each": TODEachJson,
    "sub": list[TODSubObjJson],

    # Convenience fields
    "__name": str,
}, total=False)
"""JSON object dictionary object type definition."""

TODJson = TypedDict('TODJson', {
    "$id": str,
    "$version": int|str,
    "$description": str,
    "$tool": str,
    "$date": str,
    "name": str,
    "description": str,
    "type": str,
    "id": int,
    "profile": str,
    "default_string_size": int,
    "dictionary": list[TODObjJson],
})
"""JSON file type definition"""

TDiffEntries = list[tuple[str, deepdiff.model.DiffLevel, str]]
"""Type for the diff entries retunred by diff_nodes"""

TDiffNodes = dict[int|str, TDiffEntries]
"""Type returned from the diff_nodes function."""


#  EDS
# =====

class TEntry(TypedDict):
    """Type definition for ENTRY_TYPES in the EDS file."""
    name: str
    require: list[str]
    optional: list[str]



#  COMMONDIALOGS
# ===============

TGetValues = TypedDict("TGetValues", {
    "slaveName": str,
    "slaveNodeID": int,
    "edsFile": str
}, total=False)
"""Type for the return value of the AddSlaveDialog.GetValues method."""
