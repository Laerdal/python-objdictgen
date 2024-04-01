"""Objectdict Node class containting the object dictionary."""
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
import copy
import logging
import re
import traceback
from pathlib import Path
from typing import Any, Generator, Iterable, Iterator, Self

import colorama

import objdictgen
# The following import needs care when importing node
from objdictgen import eds_utils, gen_cfile, jsonod, maps, nosis
from objdictgen.maps import OD, ODMapping, ODMappingList
from objdictgen.typing import (NodeProtocol, TIndexEntry, TODObj, TODSubObj,
                               TODValue, TParamEntry, TPath, TProfileMenu)

log = logging.getLogger('objdictgen')

Fore = colorama.Fore
Style = colorama.Style

# Used to match strings such as 'Additional Server SDO %d Parameter %d[(idx, sub)]'
# This example matches to two groups
# ['Additional Server SDO %d Parameter %d', 'idx, sub']
RE_NAME_SYNTAX = re.compile(r'(.*)\[[(](.*)[)]\]')

# Regular expression to match $NODEID in a string
RE_NODEID = re.compile(r'\$NODEID\b', re.IGNORECASE)


# ------------------------------------------------------------------------------
#                          Definition of Node Object
# ------------------------------------------------------------------------------

class Node(NodeProtocol):
    """
    A Object Dictionary representation of a CAN node.
    """

    Name: str
    """Name of the node"""

    Type: str
    """Type of the node. Should be 'slave' or 'master'"""

    ID: int
    """Node ID"""

    Description: str
    """Description of the node"""

    Dictionary: dict[int, TODValue|list[TODValue]]
    """Object dictionary of the node. The key is the index and the value is the
    literal value. For objects that have multiple subindexes, the object
    is a list of values."""

    ParamsDictionary: dict[int, TParamEntry|dict[int, TParamEntry]]
    """Dictionary of parameters for the node. The key is the index and the value
    contains the parameter for the index object. It can be a dict of subindexes.
    """
    # FIXME: The type definition on ParamsDictionary is not precisely accurate.
    # When self.Dictionary is not a list, ParamsDictionary is TParamEntry.
    # When self.Dictionary is a list, ParamsDictionary is a dict with
    # int subindexes as keys and "TParamEntryN" (a type without callback) as
    # values. The subindex dict also may contain the "callback" key.

    Profile: ODMapping
    """Profile object dictionary mapping"""

    DS302: ODMapping
    """DS-302 object dictionary mapping"""

    UserMapping: ODMapping
    """Custom user object dictionary mapping"""

    ProfileName: str
    """Name of the loaded profile. If no profile is loaded, it should be 'None'
    """

    SpecificMenu: TProfileMenu
    """Specific menu for the profile"""

    IndexOrder: list[int]
    """Order of the indexes in the object dictionary to preserve the order"""

    DefaultStringSize: int = 10
    """Default string size for the node"""

    def __init__(
            self, name: str = "", type: str = "slave", id: int = 0,
            description: str = "", profilename: str = "None",
            profile: ODMapping | None = None, specificmenu: TProfileMenu | None = None,
    ):
        self.Name: str = name
        self.Type: str = type
        self.ID: int = id
        self.Description: str = description
        self.ProfileName: str = profilename
        self.Profile: ODMapping = profile or ODMapping()
        self.SpecificMenu: TProfileMenu = specificmenu or []
        self.Dictionary: dict[int, TODValue|list[TODValue]] = {}
        self.ParamsDictionary: dict[int, TParamEntry|dict[int, TParamEntry]] = {}
        self.DS302: ODMapping = ODMapping()
        self.UserMapping: ODMapping = ODMapping()
        self.IndexOrder: list[int] = []

    # --------------------------------------------------------------------------
    #                      Node Input/Output
    # --------------------------------------------------------------------------

    @staticmethod
    def isXml(filepath: TPath) -> bool:
        """Check if the file is an XML file"""
        with open(filepath, 'r', encoding="utf-8") as f:
            header = f.read(5)
            return header == "<?xml"

    @staticmethod
    def isEds(filepath: TPath) -> bool:
        """Check if the file is an EDS file"""
        with open(filepath, 'r', encoding="utf-8") as f:
            header = f.readline().rstrip()
            return header == "[FileInfo]"

    @staticmethod
    def LoadFile(filepath: TPath) -> "Node":
        """ Open a file and create a new node """
        if Node.isXml(filepath):
            log.debug("Loading XML OD '%s'", filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                return nosis.xmlload(f)

        if Node.isEds(filepath):
            log.debug("Loading EDS '%s'", filepath)
            return eds_utils.generate_node(filepath)

        log.debug("Loading JSON OD '%s'", filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            return Node.LoadJson(f.read())

    @staticmethod
    def LoadJson(contents: str) -> "Node":
        """ Import a new Node from a JSON string """
        return jsonod.generate_node(contents)

    def DumpFile(self, filepath: TPath, filetype: str = "json", **kwargs):
        """ Save node into file """
        if filetype == 'od':
            log.debug("Writing XML OD '%s'", filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                # Never generate an od with IndexOrder in it
                nosis.xmldump(f, self, omit=('IndexOrder', ))
            return

        if filetype == 'eds':
            log.debug("Writing EDS '%s'", filepath)
            content = eds_utils.generate_eds_content(self, filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return

        if filetype == 'json':
            log.debug("Writing JSON OD '%s'", filepath)
            jdata = self.DumpJson(**kwargs)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(jdata)
            return

        if filetype == 'c':
            log.debug("Writing C files '%s'", filepath)
            gen_cfile.generate_file(filepath, self)
            return

        raise ValueError("Unknown file suffix, unable to write file")

    def DumpJson(self, compact=False, sort=False, internal=False, validate=True) -> str:
        """ Dump the node into a JSON string """
        return jsonod.generate_jsonc(
            self, compact=compact, sort=sort, internal=internal, validate=validate
        )

    # --------------------------------------------------------------------------
    #                      Node Informations Functions
    # --------------------------------------------------------------------------

    def GetMappings(self, userdefinedtoo: bool=True, withmapping=False) -> ODMappingList:
        """Return the different Mappings available for this node"""
        mapping = ODMappingList([self.Profile, self.DS302])
        if userdefinedtoo:
            mapping.append(self.UserMapping)
        if withmapping:
            mapping.append(maps.MAPPING_DICTIONARY)
        return mapping

    def AddEntry(self, index: int, subindex: int|None = None, value: TODValue|list[TODValue]|None = None) -> bool:
        """
        Add a new entry in the Object Dictionary
        """
        if index not in self.Dictionary:
            if not subindex:
                self.Dictionary[index] = value
                return True
            if subindex == 1:
                self.Dictionary[index] = [value]
                return True
        elif (subindex and isinstance(self.Dictionary[index], list)
                and subindex == len(self.Dictionary[index]) + 1):
            self.Dictionary[index].append(value)
            return True
        return False

    def SetEntry(self, index: int, subindex: int|None = None, value: TODValue|None = None) -> bool:
        """Modify an existing entry in the Object Dictionary"""
        if index not in self.Dictionary:
            return False
        if not subindex:
            if value is not None:
                self.Dictionary[index] = value
            return True
        if isinstance(self.Dictionary[index], list) and 0 < subindex <= len(self.Dictionary[index]):
            if value is not None:
                self.Dictionary[index][subindex - 1] = value
            return True
        return False

    def SetParamsEntry(self, index: int, subindex: int|None = None, comment=None, buffer_size=None, save=None, callback=None) -> bool:
        """Set parameter values for an entry in the Object Dictionary."""
        if index not in self.Dictionary:
            return False
        if ((comment is not None or save is not None or callback is not None or buffer_size is not None)
            and index not in self.ParamsDictionary
        ):
            self.ParamsDictionary[index] = {}
        if subindex is None or not isinstance(self.Dictionary[index], list) and subindex == 0:
            if comment is not None:
                self.ParamsDictionary[index]["comment"] = comment
            if buffer_size is not None:
                self.ParamsDictionary[index]["buffer_size"] = buffer_size
            if save is not None:
                self.ParamsDictionary[index]["save"] = save
            if callback is not None:
                self.ParamsDictionary[index]["callback"] = callback
            return True
        if isinstance(self.Dictionary[index], list) and 0 <= subindex <= len(self.Dictionary[index]):
            if ((comment is not None or save is not None or callback is not None or buffer_size is not None)
                and subindex not in self.ParamsDictionary[index]
            ):
                self.ParamsDictionary[index][subindex] = {}
            if comment is not None:
                self.ParamsDictionary[index][subindex]["comment"] = comment
            if buffer_size is not None:
                self.ParamsDictionary[index][subindex]["buffer_size"] = buffer_size
            if save is not None:
                self.ParamsDictionary[index][subindex]["save"] = save
            return True
        return False

    def RemoveEntry(self, index: int, subindex: int|None = None) -> bool:
        """
        Removes an existing entry in the Object Dictionary. If a subindex is specified
        it will remove this subindex only if it's the last of the index. If no subindex
        is specified it removes the whole index and subIndexes from the Object Dictionary.
        """
        if index not in self.Dictionary:
            return False
        if not subindex:
            self.Dictionary.pop(index)
            if index in self.ParamsDictionary:
                self.ParamsDictionary.pop(index)
            return True
        if isinstance(self.Dictionary[index], list) and subindex == len(self.Dictionary[index]):
            self.Dictionary[index].pop(subindex - 1)
            if index in self.ParamsDictionary:
                if subindex in self.ParamsDictionary[index]:
                    self.ParamsDictionary[index].pop(subindex)
                if len(self.ParamsDictionary[index]) == 0:
                    self.ParamsDictionary.pop(index)
            if len(self.Dictionary[index]) == 0:
                self.Dictionary.pop(index)
                if index in self.ParamsDictionary:
                    self.ParamsDictionary.pop(index)
            return True
        return False

    def IsEntry(self, index: int, subindex: int=0) -> bool:
        """
        Check if an entry exists in the Object Dictionary
        """
        if index in self.Dictionary:
            if not subindex:
                return True
            dictval = self.Dictionary[index]
            return isinstance(dictval, list) and subindex <= len(dictval)
        return False

    def GetEntry(self, index: int, subindex: int|None = None, compute=True, aslist=False) -> list[TODValue]|TODValue:
        """
        Returns the value of the entry specified by the index and subindex. If
        subindex is None, it will return the value or the list of values of the
        entire index. If aslist is True, it will always return a list.
        """
        if index not in self.Dictionary:
            raise KeyError(f"Index 0x{index:04x} does not exist")
        base = self.GetBaseIndexNumber(index)
        nodeid = self.ID
        if subindex is None:
            if isinstance(self.Dictionary[index], list):
                return [len(self.Dictionary[index])] + [
                    self.eval_value(value, base, nodeid, compute)
                    for value in self.Dictionary[index]
                ]
            result = self.eval_value(self.Dictionary[index], base, nodeid, compute)
            # This option ensures that the function consistently returns a list
            if aslist:
                return [result]
            return result
        if subindex == 0:
            if isinstance(self.Dictionary[index], list):
                return len(self.Dictionary[index])
            return self.eval_value(self.Dictionary[index], base, nodeid, compute)
        if isinstance(self.Dictionary[index], list) and 0 < subindex <= len(self.Dictionary[index]):
            return self.eval_value(self.Dictionary[index][subindex - 1], base, nodeid, compute)
        raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

    def GetParamsEntry(self, index: int, subindex: int|None = None,
                        aslist: bool = False) -> TParamEntry|list[TParamEntry]:
        """
        Returns the value of the entry asked. If the entry has the value "count", it
        returns the number of subindex in the entry except the first.
        """
        if index not in self.Dictionary:
            raise KeyError(f"Index 0x{index:04x} does not exist")
        if subindex is None:
            if isinstance(self.Dictionary[index], list):
                if index in self.ParamsDictionary:
                    result = []
                    for i in range(len(self.Dictionary[index]) + 1):
                        line = maps.DEFAULT_PARAMS.copy()
                        if i in self.ParamsDictionary[index]:
                            line.update(self.ParamsDictionary[index][i])
                        result.append(line)
                    return result
                return [maps.DEFAULT_PARAMS.copy() for i in range(len(self.Dictionary[index]) + 1)]
            result = maps.DEFAULT_PARAMS.copy()
            if index in self.ParamsDictionary:
                result.update(self.ParamsDictionary[index])
            # This option ensures that the function consistently returns a list
            if aslist:
                return [result]
            return result
        if subindex == 0 and not isinstance(self.Dictionary[index], list):
            result = maps.DEFAULT_PARAMS.copy()
            if index in self.ParamsDictionary:
                result.update(self.ParamsDictionary[index])
            return result
        if isinstance(self.Dictionary[index], list) and 0 <= subindex <= len(self.Dictionary[index]):
            result = maps.DEFAULT_PARAMS.copy()
            if index in self.ParamsDictionary and subindex in self.ParamsDictionary[index]:
                result.update(self.ParamsDictionary[index][subindex])
            return result
        raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

    def HasEntryCallbacks(self, index: int) -> bool:
        """Check if entry has the callback flag defined."""
        entry_infos = self.GetEntryInfos(index)
        if entry_infos and "callback" in entry_infos:
            return entry_infos["callback"]
        if index in self.Dictionary and index in self.ParamsDictionary and "callback" in self.ParamsDictionary[index]:
            return self.ParamsDictionary[index]["callback"]
        return False

    def IsMappingEntry(self, index: int) -> bool:
        """
        Check if an entry exists in the User Mapping Dictionary and returns the answer.
        """
        # FIXME: Is usermapping only used when defining custom objects?
        # Come back to this and test if this is the case. If it is the function
        # should probably be renamed to "IsUserEntry" or somesuch
        return index in self.UserMapping

    def AddMappingEntry(self, index: int, subindex: int|None = None, name="Undefined", struct=0, size=None, nbmax=None,
                        default=None, values=None) -> bool:
        """
        Add a new entry in the User Mapping Dictionary
        """
        if index not in self.UserMapping:
            if values is None:
                values = []
            if subindex is None:
                self.UserMapping[index] = {"name": name, "struct": struct, "need": False, "values": values}
                if size is not None:
                    self.UserMapping[index]["size"] = size
                if nbmax is not None:
                    self.UserMapping[index]["nbmax"] = nbmax
                if default is not None:
                    self.UserMapping[index]["default"] = default
                return True
        elif subindex is not None and subindex == len(self.UserMapping[index]["values"]):
            if values is None:
                values = {}
            self.UserMapping[index]["values"].append(values)
            return True
        return False

    def SetMappingEntry(self, index: int, subindex: int|None = None, name=None, struct=None, size=None, nbmax=None, default=None, values=None) -> bool:
        """
        Modify an existing entry in the User Mapping Dictionary
        """
        if index not in self.UserMapping:
            return False
        if subindex is None:
            if name is not None:
                self.UserMapping[index]["name"] = name
                if self.UserMapping[index]["struct"] & OD.IdenticalSubindexes:
                    self.UserMapping[index]["values"][1]["name"] = name + " %d[(sub)]"
                elif not self.UserMapping[index]["struct"] & OD.MultipleSubindexes:
                    self.UserMapping[index]["values"][0]["name"] = name
            if struct is not None:
                self.UserMapping[index]["struct"] = struct
            if size is not None:
                self.UserMapping[index]["size"] = size
            if nbmax is not None:
                self.UserMapping[index]["nbmax"] = nbmax
            if default is not None:
                self.UserMapping[index]["default"] = default
            if values is not None:
                self.UserMapping[index]["values"] = values
            return True
        if 0 <= subindex < len(self.UserMapping[index]["values"]) and values is not None:
            if "type" in values:
                if self.UserMapping[index]["struct"] & OD.IdenticalSubindexes:
                    if self.IsStringType(self.UserMapping[index]["values"][subindex]["type"]):
                        if self.IsRealType(values["type"]):
                            for i in range(len(self.Dictionary[index])):
                                self.SetEntry(index, i + 1, 0.)
                        elif not self.IsStringType(values["type"]):
                            for i in range(len(self.Dictionary[index])):
                                self.SetEntry(index, i + 1, 0)
                    elif self.IsRealType(self.UserMapping[index]["values"][subindex]["type"]):
                        if self.IsStringType(values["type"]):
                            for i in range(len(self.Dictionary[index])):
                                self.SetEntry(index, i + 1, "")
                        elif not self.IsRealType(values["type"]):
                            for i in range(len(self.Dictionary[index])):
                                self.SetEntry(index, i + 1, 0)
                    elif self.IsStringType(values["type"]):
                        for i in range(len(self.Dictionary[index])):
                            self.SetEntry(index, i + 1, "")
                    elif self.IsRealType(values["type"]):
                        for i in range(len(self.Dictionary[index])):
                            self.SetEntry(index, i + 1, 0.)
                else:
                    if self.IsStringType(self.UserMapping[index]["values"][subindex]["type"]):
                        if self.IsRealType(values["type"]):
                            self.SetEntry(index, subindex, 0.)
                        elif not self.IsStringType(values["type"]):
                            self.SetEntry(index, subindex, 0)
                    elif self.IsRealType(self.UserMapping[index]["values"][subindex]["type"]):
                        if self.IsStringType(values["type"]):
                            self.SetEntry(index, subindex, "")
                        elif not self.IsRealType(values["type"]):
                            self.SetEntry(index, subindex, 0)
                    elif self.IsStringType(values["type"]):
                        self.SetEntry(index, subindex, "")
                    elif self.IsRealType(values["type"]):
                        self.SetEntry(index, subindex, 0.)
            self.UserMapping[index]["values"][subindex].update(values)
            return True
        return False

    def RemoveMappingEntry(self, index: int, subindex: int|None = None) -> bool:
        """
        Removes an existing entry in the User Mapping Dictionary. If a subindex is specified
        it will remove this subindex only if it's the last of the index. If no subindex
        is specified it removes the whole index and subIndexes from the User Mapping Dictionary.
        """
        if index in self.UserMapping:
            if subindex is None:
                self.UserMapping.pop(index)
                return True
            if subindex == len(self.UserMapping[index]["values"]) - 1:
                self.UserMapping[index]["values"].pop(subindex)
                return True
        return False

    def RemoveMapVariable(self, index: int, subindex: int = 0):
        """
        Remove all PDO mappings references to the specificed index and subindex.
        """
        model = index << 16
        mask = 0xFFFF << 16
        if subindex:
            model += subindex << 8
            mask += 0xFF << 8
        for i in self.Dictionary:  # pylint: disable=consider-using-dict-items
            if 0x1600 <= i <= 0x17FF or 0x1A00 <= i <= 0x1BFF:
                for j, value in enumerate(self.Dictionary[i]):
                    if (value & mask) == model:
                        self.Dictionary[i][j] = 0

    def UpdateMapVariable(self, index: int, subindex: int, size: int):
        """
        Update the PDO mappings references to the specificed index and subindex
        and set the size value.
        """
        model = index << 16
        mask = 0xFFFF << 16
        if subindex:
            model += subindex << 8
            mask = 0xFF << 8
        for i in self.Dictionary:  # pylint: disable=consider-using-dict-items
            if 0x1600 <= i <= 0x17FF or 0x1A00 <= i <= 0x1BFF:
                for j, value in enumerate(self.Dictionary[i]):
                    if (value & mask) == model:
                        self.Dictionary[i][j] = model + size

    def RemoveLine(self, index: int, maxval: int, incr: int = 1):
        """ Remove the given index and shift all the following indexes """
        # FIXME: This function is called from NodeManager.RemoveCurrentVariable()
        # but uncertain on how it is used.
        i = index
        while i < maxval and self.IsEntry(i + incr):
            self.Dictionary[i] = self.Dictionary[i + incr]
            i += incr
        self.Dictionary.pop(i)

    def Copy(self) -> Self:
        """
        Return a copy of the node
        """
        return copy.deepcopy(self)

    def GetDict(self) -> dict[str, Any]:
        """ Return the class data as a dict """
        return copy.deepcopy(self.__dict__)

    def GetIndexDict(self, index: int) -> TIndexEntry:
        """ Return a full and raw representation of the index """

        def _mapping_for_index(index: int) -> Generator[tuple[str, TODObj], None, None]:
            for n, o in (
                ('profile', self.Profile),
                ('ds302', self.DS302),
                ('user', self.UserMapping),
                ('built-in', maps.MAPPING_DICTIONARY),
            ):
                if index in o:
                    yield n, o[index]

        objmaps = list(_mapping_for_index(index))
        firstobj: TODObj = objmaps[0][1] if objmaps else {}

        obj: TIndexEntry = {
            "index": index,
            "groups": list(n for n, _ in objmaps),
        }

        if firstobj:   # Safe to assume False here is not just an empty ODObj
            obj['object'] = firstobj
        if index in self.Dictionary:
            obj['dictionary'] = self.Dictionary[index]
        if index in self.ParamsDictionary:
            obj['params'] = self.ParamsDictionary[index]

        baseindex = self.GetBaseIndex(index)
        if index != baseindex:
            obj['base'] = baseindex
            baseobject = next(_mapping_for_index(baseindex))
            obj['basestruct'] = baseobject[1]["struct"]

        # Ensure that the object is safe to mutate
        return copy.deepcopy(obj)

    def GetIndexes(self):
        """
        Return a sorted list of indexes in Object Dictionary
        """
        return list(sorted(self.Dictionary))


    # --------------------------------------------------------------------------
    #                      Node Informations Functions
    # --------------------------------------------------------------------------

    def GetBaseIndex(self, index: int) -> int:
        """ Return the index number of the base object """
        for mapping in self.GetMappings():
            result = self.FindIndex(index, mapping)
            if result:
                return result
        return self.FindIndex(index, maps.MAPPING_DICTIONARY)

    def GetBaseIndexNumber(self, index: int) -> int:
        """ Return the index number from the base object """
        for mapping in self.GetMappings():
            result = self.FindIndex(index, mapping)
            if result is not None:
                return (index - result) // mapping[result].get("incr", 1)
        result = self.FindIndex(index, maps.MAPPING_DICTIONARY)
        if result is not None:
            return (index - result) // maps.MAPPING_DICTIONARY[result].get("incr", 1)
        return 0

    def GetCustomisedTypeValues(self, index: int) -> tuple[list[TODValue], int]:
        """Return the customization struct type from the index. It returns
        a tuple containing the entry value and the int of the type of the object.
        0 indicates numerical value, 1 indicates string value."""
        values = self.GetEntry(index)
        customisabletypes = self.GetCustomisableTypes()
        return values, customisabletypes[values[1]][1]  # type: ignore

    def GetEntryName(self, index: int, compute=True) -> str:
        """Return the entry name for the given index"""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindEntryName(index, mappings[i], compute)
            i += 1
        if result is None:
            result = self.FindEntryName(index, maps.MAPPING_DICTIONARY, compute)
        return result

    def GetEntryInfos(self, index: int, compute=True) -> TODObj:
        """Return the entry infos for the given index"""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindEntryInfos(index, mappings[i], compute)
            i += 1
        r301 = self.FindEntryInfos(index, maps.MAPPING_DICTIONARY, compute)
        if r301:
            if result is not None:
                r301.update(result)
            return r301
        return result

    def GetSubentryInfos(self, index: int, subindex: int, compute: bool = True) -> TODSubObj:
        """Return the subentry infos for the given index and subindex"""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindSubentryInfos(index, subindex, mappings[i], compute)
            if result:
                result["user_defined"] = i == len(mappings) - 1 and index >= 0x1000
            i += 1
        r301 = self.FindSubentryInfos(index, subindex, maps.MAPPING_DICTIONARY, compute)
        if r301:
            if result is not None:
                r301.update(result)
            else:
                r301["user_defined"] = False
            return r301
        return result

    def GetEntryFlags(self, index: int) -> set[str]:
        """Return the flags for the given index"""
        flags: set[str] = set()
        info = self.GetEntryInfos(index)
        if not info:
            return flags

        if info.get('need'):
            flags.add("Mandatory")
        if index in self.UserMapping:
            flags.add("User")
        if index in self.DS302:
            flags.add("DS-302")
        if index in self.Profile:
            flags.add("Profile")
        if self.HasEntryCallbacks(index):
            flags.add('CB')
        if index not in self.Dictionary:
            if index in self.DS302 or index in self.Profile:
                flags.add("Unused")
            else:
                flags.add("Missing")
        return flags

    def GetAllSubentryInfos(self, index, compute=True):
        values = self.GetEntry(index, compute=compute, aslist=True)
        entries = self.GetParamsEntry(index, aslist=True)
        for i, (value, entry) in enumerate(zip(values, entries)):  # type: ignore
            info = {
                'subindex': i,
                'value': value,
            }
            result = self.GetSubentryInfos(index, i)
            if result:
                info.update(result)
            info.update(entry)
            yield info

    def GetTypeIndex(self, typename: str) -> int:
        """Return the type index for the given type name."""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindTypeIndex(typename, mappings[i])
            i += 1
        if result is None:
            result = self.FindTypeIndex(typename, maps.MAPPING_DICTIONARY)
        return result

    def GetTypeName(self, typeindex: int) -> str:
        """Return the type name for the given type index."""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindTypeName(typeindex, mappings[i])
            i += 1
        if result is None:
            result = self.FindTypeName(typeindex, maps.MAPPING_DICTIONARY)
        return result

    def GetTypeDefaultValue(self, typeindex: int) -> TODValue:
        """Return the default value for the given type index."""
        result = None
        mappings = self.GetMappings()
        i = 0
        while not result and i < len(mappings):
            result = self.FindTypeDefaultValue(typeindex, mappings[i])
            i += 1
        if result is None:
            result = self.FindTypeDefaultValue(typeindex, maps.MAPPING_DICTIONARY)
        return result

    def GetMapVariableList(self, compute=True) -> list[tuple[int, int, int, str]]:
        """Return a list of all objects and subobjects available for mapping into
        pdos. Returns a list of tuples with the index, subindex, size and name of the object."""
        list_ = list(self.FindMapVariableList(maps.MAPPING_DICTIONARY, self, compute))
        for mapping in self.GetMappings():
            list_.extend(self.FindMapVariableList(mapping, self, compute))
        list_.sort()
        return list_

    def GetMandatoryIndexes(self, node: "Node|None" = None) -> list[int]:  # pylint: disable=unused-argument
        """Return the mandatory indexes for the node."""
        list_ = self.FindMandatoryIndexes(maps.MAPPING_DICTIONARY)
        for mapping in self.GetMappings():
            list_.extend(self.FindMandatoryIndexes(mapping))
        return list_

    def GetCustomisableTypes(self) -> dict[int, tuple[str, int]]:
        """ Return the customisable types. It returns a dict by the index number.
        The value is a tuple with the type name and the size of the type."""
        return {
            index: (self.GetTypeName(index), valuetype)
            for index, valuetype in maps.CUSTOMISABLE_TYPES
        }

    # --------------------------------------------------------------------------
    #                      Type helper functions
    # --------------------------------------------------------------------------

    def IsStringType(self, index: int) -> bool:
        """Is the object index a string type?"""
        if index in (0x9, 0xA, 0xB, 0xF):  # VISIBLE_STRING, OCTET_STRING, UNICODE_STRING, DOMAIN
            return True
        if 0xA0 <= index < 0x100:  # Custom types
            result = self.GetEntry(index, 1)
            if result in (0x9, 0xA, 0xB):
                return True
        return False

    def IsRealType(self, index: int) -> bool:
        """Is the object index a real (float) type?"""
        if index in (0x8, 0x11):  # REAL32, REAL64
            return True
        if 0xA0 <= index < 0x100:  # Custom types
            result = self.GetEntry(index, 1)
            if result in (0x8, 0x11):
                return True
        return False

    # --------------------------------------------------------------------------
    #                      Type and Map Variable Lists
    # --------------------------------------------------------------------------

    def GetTypeList(self) -> list[str]:
        """Return a list of all object types available for the current node"""
        list_ = self.FindTypeList(maps.MAPPING_DICTIONARY)
        for mapping in self.GetMappings():
            list_.extend(self.FindTypeList(mapping))
        return list_

    @staticmethod
    def GenerateMapName(name: str, index: int, subindex: int) -> str:
        """Return how a mapping object should be named in UI"""
        return f"{name} (0x{index:04X})"

    def GetMapValue(self, mapname: str) -> int:
        """Return the mapping value from the given printable name"""
        if mapname == "None":
            return 0

        list_ = self.GetMapVariableList()
        for index, subindex, size, name in list_:
            if mapname == self.GenerateMapName(name, index, subindex):
                # array type, only look at subindex 1 in UserMapping
                if self.UserMapping[index]["struct"] == OD.ARRAY:
                    if self.IsStringType(self.UserMapping[index]["values"][1]["type"]):
                        try:
                            if int(self.ParamsDictionary[index][subindex]["buffer_size"]) <= 8:
                                return ((index << 16) + (subindex << 8)
                                        + size * int(self.ParamsDictionary[index][subindex]["buffer_size"]))
                            raise ValueError("String size too big to fit in a PDO")
                        except KeyError:
                            raise ValueError(
                                "No string length found and default string size too big to fit in a PDO"
                            ) from None
                else:
                    if self.IsStringType(self.UserMapping[index]["values"][subindex]["type"]):
                        try:
                            if int(self.ParamsDictionary[index][subindex]["buffer_size"]) <= 8:
                                return ((index << 16) + (subindex << 8) +
                                        size * int(self.ParamsDictionary[index][subindex]["buffer_size"]))
                            raise ValueError("String size too big to fit in a PDO")
                        except KeyError:
                            raise ValueError(
                                "No string length found and default string size too big to fit in a PDO"
                            ) from None
                return (index << 16) + (subindex << 8) + size
        return None

    @staticmethod
    def GetMapIndex(value: int) -> tuple[int, int, int]:
        """Return the index, subindex, size from a map value"""
        if value:
            index = value >> 16
            subindex = (value >> 8) % (1 << 8)
            size = (value) % (1 << 8)
            return index, subindex, size
        return 0, 0, 0

    def GetMapName(self, value: int) -> str:
        """Return the printable name for the given map value."""
        index, subindex, _ = self.GetMapIndex(value)
        if value:
            result = self.GetSubentryInfos(index, subindex)
            if result:
                return self.GenerateMapName(result["name"], index, subindex)
        return "None"

    def GetMapList(self) -> list[str]:
        """
        Return the list of variables that can be mapped into pdos for the current node
        """
        return ["None"] + [
            self.GenerateMapName(name, index, subindex)
            for index, subindex, size, name in self.GetMapVariableList()
        ]

    def GetAllParameters(self, sort=False) -> list[int]:
        """ Get a list of all indices. If node maintains a sort order,
            it will be used. Otherwise if sort is False, the order
            will be arbitrary. If sort is True they will be sorted.
        """
        order = list(self.UserMapping)
        order += [k for k in self.Dictionary if k not in order]
        order += [k for k in self.ParamsDictionary if k not in order]
        if self.Profile:
            order += [k for k in self.Profile if k not in order]
        if self.DS302:
            order += [k for k in self.DS302 if k not in order]

        if sort:
            order = sorted(order)

        # Is there a recorded order that should supersede the above sequence?
        # Node might not contain IndexOrder if read from legacy od file
        elif hasattr(self, 'IndexOrder'):
            # Pick k from IndexOrder which is present in order
            keys = [k for k in self.IndexOrder if k in order]
            # Append any missing k from order that is not in IndexOrder
            keys += (k for k in order if k not in keys)
            order = keys

        return order

    def GetUnusedParameters(self):
        """ Return a list of all unused parameter indexes """
        return [
            k for k in self.GetAllParameters()
            if k not in self.Dictionary
        ]

    def RemoveIndex(self, index: int) -> None:
        """ Remove the given index"""
        self.UserMapping.pop(index, None)
        self.Dictionary.pop(index, None)
        self.ParamsDictionary.pop(index, None)
        if self.DS302:
            self.DS302.pop(index, None)
        if self.Profile:
            self.Profile.pop(index, None)
            if not self.Profile:
                self.ProfileName = "None"

    # --------------------------------------------------------------------------
    #                      Validator
    # --------------------------------------------------------------------------

    def Validate(self, fix=False):
        """ Verify any inconsistencies when loading an OD. The function will
            attempt to fix the data if the correct flag is enabled.
        """
        def _warn(text: str):
            name = self.GetEntryName(index)
            log.warning("WARNING: 0x%04x (%d) '%s': %s", index, index, name, text)

        # Iterate over all the values and user parameters
        for index in set(self.Dictionary) | set(self.ParamsDictionary):

            #
            # Test if ParamDictionary exists without Dictionary
            #
            if index not in self.Dictionary:
                _warn("Parameter value without any dictionary entry")
                if fix:
                    del self.ParamsDictionary[index]
                    _warn("FIX: Deleting ParamDictionary entry")
                continue

            base = self.GetEntryInfos(index)
            is_var = base["struct"] in (OD.VAR, OD.NVAR)

            #
            # Test if ParamDictionary matches Dictionary
            #
            dictlen = 1 if is_var else len(self.Dictionary.get(index, []))
            params = {
                k: v
                for k, v in self.ParamsDictionary.get(index, {}).items()
                if isinstance(k, int)
            }
            excessive_params = {k for k in params if k > dictlen}
            if excessive_params:
                log.debug("Excessive params: %s", excessive_params)
                _warn(
                    f"Excessive user parameters ({len(excessive_params)}) "
                    f"or too few dictionary values ({dictlen})"
                )

                if index in self.Dictionary:
                    for idx in excessive_params:
                        del self.ParamsDictionary[index][idx]
                        del params[idx]
                    t_p = ", ".join(str(k) for k in excessive_params)
                    _warn(f"FIX: Deleting ParamDictionary entries {t_p}")

                    # If params have been emptied because of this, remove it altogether
                    if not params:
                        del self.ParamsDictionary[index]
                        _warn("FIX: Deleting ParamDictionary entry")

        # Iterate over all user mappings
        params = set(self.UserMapping)
        for index in params:
            for idx, subvals in enumerate(self.UserMapping[index]['values']):

                #
                # Test that subindexi have a name
                #
                if not subvals["name"]:
                    _warn(f"Sub index {idx}: Missing name")
                    if fix:
                        subvals["name"] = f"Subindex {idx}"
                        _warn(f"FIX: Set name to '{subvals['name']}'")

    # --------------------------------------------------------------------------
    #                      Printing and output
    # --------------------------------------------------------------------------

    def GetPrintLine(self, index: int, unused=False, compact=False):

        obj = self.GetEntryInfos(index)
        if not obj:
            return '', {}

        # Get the node flags
        flags = self.GetEntryFlags(index)
        if 'Unused' in flags and not unused:
            return '', {}

        # Replace flags for formatting
        for _, flag in enumerate(flags.copy()):
            if flag == 'Missing':
                flags.discard('Missing')
                flags.add(Fore.RED + ' *MISSING* ' + Style.RESET_ALL)

        # Print formattings
        t_flags = ', '.join(flags)
        fmt = {
            'key': f"{Fore.GREEN}0x{index:04x} ({index}){Style.RESET_ALL}",
            'name': self.GetEntryName(index),
            'struct': maps.ODStructTypes.to_string(obj.get('struct'), '???').upper(),  # type: ignore
            'flags': f"  {Fore.CYAN}{t_flags}{Style.RESET_ALL}" if flags else '',
            'pre': '    ' if not compact else '',
        }

        # ** PRINT PARAMETER **
        return "{pre}{key}  {name}   [{struct}]{flags}", fmt

    def GetPrintParams(self, keys=None, short=False, compact=False, unused=False, verbose=False, raw=False):
        """
        Generator for printing the dictionary values
        """

        # Get the indexes to print and determine the order
        keys = keys or self.GetAllParameters(sort=True)

        index_range = None
        for k in keys:

            line, fmt = self.GetPrintLine(k, unused=unused, compact=compact)
            if not line:
                continue

            # Print the parameter range header
            ir = self.get_index_range(k)
            if index_range != ir:
                index_range = ir
                if not compact:
                    yield Fore.YELLOW + ir["description"] + Style.RESET_ALL

            # Yield the parameter header
            yield line.format(**fmt)

            # Omit printing sub index data if:
            if short or k not in self.Dictionary:
                continue

            infos = []
            for info in self.GetAllSubentryInfos(k, compute=not raw):

                # Prepare data for printing

                i = info['subindex']
                typename = self.GetTypeName(info['type'])
                value = info['value']

                # Special formatting on value
                if isinstance(value, str):
                    value = '"' + value + '"'
                elif i and index_range and index_range["name"] in ('rpdom', 'tpdom'):
                    index, subindex, _ = self.GetMapIndex(value)
                    pdo = self.GetSubentryInfos(index, subindex)
                    suffix = '???' if value else ''
                    if pdo:
                        suffix = str(pdo["name"])
                    value = f"0x{value:x}  {suffix}"
                elif i and value and (k in (4120, ) or 'COB ID' in info["name"]):
                    value = f"0x{value:x}"
                else:
                    value = str(value)

                comment = info['comment'] or ''
                if comment:
                    comment = f"{Fore.LIGHTBLACK_EX}/* {info.get('comment')} */{Style.RESET_ALL}"

                # Omit printing this subindex if:
                if (not verbose and i == 0
                    and fmt['struct'] in ('RECORD', 'NRECORD', 'ARRAY', 'NARRAY')
                    and not comment
                ):
                    continue

                # Print formatting
                infos.append({
                    'i': f"{i:02d}",
                    'access': info['access'],
                    'pdo': 'P' if info['pdo'] else ' ',
                    'name': info['name'],
                    'type': typename,
                    'value': value,
                    'comment': comment,
                    'pre': fmt['pre'],
                })

            if not infos:
                continue

            # Calculate the max width for each of the columns
            w = {
                col: max(len(str(row[col])) for row in infos) or ''
                for col in infos[0]
            }

            # Generate a format string based on the calculcated column widths
            # Legitimate use of % as this is making a string containing format specifiers
            fmt = "{pre}    {i:%ss}  {access:%ss}  {pdo:%ss}  {name:%ss}  {type:%ss}  {value:%ss}  {comment}" % (
                w["i"],  w["access"],  w["pdo"],  w["name"],  w["type"],  w["value"]  # noqa: E126, E241
            )

            # Print each line using the generated format string
            for info in infos:
                yield fmt.format(**info)

            if not compact and infos:
                yield ""

    # --------------------------------------------------------------------------
    #                      Load mapping
    # --------------------------------------------------------------------------

    @staticmethod
    def ImportProfile(profilename):

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

    # --------------------------------------------------------------------------
    #                      Evaluation of values
    # --------------------------------------------------------------------------

    @staticmethod
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
        value = Node.evaluate_expression(value,
            {   # These are the vars that can be used within the string
                'base': base,
            }
        )

        if compute and isinstance(value, str):
            # Replace $NODEID with 'nodeid' so it can be evaluated.
            value = RE_NODEID.sub("nodeid", value)

            # This will resolve '$NODEID' expressions
            value = Node.evaluate_expression(value,
                {   # These are the vars that can be used within the string
                    'nodeid': nodeid,
                }
            )

        return value

    @staticmethod
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
        return result.group(1) % Node.evaluate_expression(
            result.group(2).strip(),
            {   # These are the vars that can be used in the string
                'idx': idx,
                'sub': sub,
            }
        )

    @staticmethod
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

    @staticmethod
    def get_index_range(index):
        for irange in maps.INDEX_RANGES:
            if irange["min"] <= index <= irange["max"]:
                return irange
        raise ValueError(f"Cannot find index range for value '0x{index:x}'")

    @staticmethod
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

    @staticmethod
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

    # --------------------------------------------------------------------------
    #                      Search in a Mapping Dictionary
    # --------------------------------------------------------------------------

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
    def FindEntryName(index, mappingdictionary, compute=True):
        """
        Return the name of an entry by searching in mappingdictionary
        """
        base_index = Node.FindIndex(index, mappingdictionary)
        if base_index:
            infos = mappingdictionary[base_index]
            if infos["struct"] & OD.IdenticalIndexes and compute:
                return Node.eval_name(
                    infos["name"], idx=(index - base_index) // infos["incr"] + 1, sub=0
                )
            return infos["name"]
        return None

    @staticmethod
    def FindEntryInfos(index, mappingdictionary, compute=True):
        """
        Return the informations of one entry by searching in mappingdictionary
        """
        base_index = Node.FindIndex(index, mappingdictionary)
        if base_index:
            obj = mappingdictionary[base_index].copy()
            if obj["struct"] & OD.IdenticalIndexes and compute:
                obj["name"] = Node.eval_name(
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
        base_index = Node.FindIndex(index, mappingdictionary)
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
                    infos["name"] = Node.eval_name(
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
                                    computed_name = Node.eval_name(computed_name, idx=1, sub=i + 1)
                                yield (index, i + 1, infos["size"], computed_name)
                        else:
                            computed_name = name
                            if compute:
                                computed_name = Node.eval_name(computed_name, idx=1, sub=subindex)
                            yield (index, subindex, infos["size"], computed_name)

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


# Register node with gnosis
nosis.add_class_to_store('Node', Node)
