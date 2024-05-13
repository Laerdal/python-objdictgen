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

import copy
import logging
from pathlib import Path
from typing import Any, Generator, Iterable, Iterator

import colorama

# The following import needs care when importing node
from objdictgen import eds_utils, gen_cfile, jsonod, maps, nosis
from objdictgen.maps import OD, ODMapping, ODMappingList
from objdictgen.typing import (NodeProtocol, TIndexEntry, TODObj, TODSubObj,
                               TODValue, TParamEntry, TPath, TProfileMenu)

log = logging.getLogger('objdictgen')

Fore = colorama.Fore
Style = colorama.Style


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
    #                      Dunders
    # --------------------------------------------------------------------------

    def __iter__(self) -> Iterator[int]:
        """Iterate over all indexes in the dictionary"""
        return iter(sorted(self.Dictionary))

    def __setattr__(self, name: str, value: Any):
        """Ensure that that internal attrs are of the right datatype."""
        if name in ("Profile", "DS302", "UserMapping"):
            if not isinstance(value, ODMapping):
                value = ODMapping(value)
        super().__setattr__(name, value)

    # --------------------------------------------------------------------------
    #                      Legacy access methods
    # --------------------------------------------------------------------------

    def GetNodeName(self) -> str:
        """Get the name of the node"""
        return self.Name

    def GetNodeID(self) -> int:
        """Get the ID of the node"""
        return self.ID

    def GetNodeType(self) -> str:
        """Get the type of the node"""
        return self.Type

    def GetNodeDescription(self) -> str:
        """Get the description of the node"""
        return self.Description

    def GetDefaultStringSize(self) -> int:
        """Get the default string size"""
        return self.DefaultStringSize

    def GetIndexes(self) -> list[int]:
        """ Return a sorted list of indexes in Object Dictionary """
        return list(self)

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

    def DumpFile(self, filepath: TPath, filetype: str|None = "json", **kwargs):
        """ Save node into file """

        # Attempt to determine the filetype from the filepath
        if not filetype:
            filetype = Path(filepath).suffix[1:]
        if not filetype:
            filetype = "json"

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
            # Convert filepath to str because it might be used with legacy code
            gen_cfile.GenerateFile(str(filepath), self)
            return

        raise ValueError("Unknown file suffix, unable to write file")

    def DumpJson(self, compact=False, sort=False, internal=False, validate=True) -> str:
        """ Dump the node into a JSON string """
        return jsonod.generate_jsonc(
            self, compact=compact, sort=sort, internal=internal, validate=validate
        )

    def asdict(self) -> dict[str, Any]:
        """ Return the class data as a dict """
        return copy.deepcopy(self.__dict__)

    def copy(self) -> "Node":
        """
        Return a copy of the node
        """
        return copy.deepcopy(self)

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

    def GetEntry(self, index: int, subindex: int|None = None, compute=True, aslist=False) -> list[TODValue]|TODValue:
        """
        Returns the value of the entry specified by the index and subindex. If
        subindex is None, it will return the value or the list of values of the
        entire index. If aslist is True, it will always return a list.
        """
        if index not in self.Dictionary:
            raise KeyError(f"Index 0x{index:04x} does not exist")
        dictval = self.Dictionary[index]

        # Variables needed by the eval_value function
        base = self.GetBaseIndexNumber(index)
        nodeid = self.ID

        if subindex is None:
            if isinstance(dictval, list):
                out: list[TODValue] = [len(dictval)]
                out.extend(
                    maps.eval_value(value, base, nodeid, compute)
                    for value in dictval
                )
                return out  # Type is list[TValue]

            result = maps.eval_value(dictval, base, nodeid, compute)
            # This option ensures that the function consistently returns a list
            if aslist:
                return [result]  # Type is list[TValue]
            return result  # Type is TValue

        if isinstance(dictval, list):
            if subindex == 0:
                return len(dictval)  # Type is int

            if 0 < subindex <= len(dictval):
                # Type is TValue
                return maps.eval_value(dictval[subindex - 1], base, nodeid, compute)

            raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

        # Special case: If the dictionary value is not a list, subindex 0
        # can be used to retrieve the entry.
        if subindex == 0:
            return maps.eval_value(dictval, base, nodeid, compute)

        raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x} for a non-list entry")

    def GetParamsEntry(self, index: int, subindex: int|None = None,
                        aslist: bool = False) -> TParamEntry|list[TParamEntry]:
        """
        Returns the value of the entry asked. If the entry has the value "count", it
        returns the number of subindex in the entry except the first.
        """
        if index not in self.Dictionary:
            raise KeyError(f"Index 0x{index:04x} does not exist")
        dictval = self.Dictionary[index]
        params = self.ParamsDictionary.get(index)

        def _get_param(v: TParamEntry|None) -> TParamEntry:
            params = maps.DEFAULT_PARAMS.copy()
            if v is not None:
                params.update(v)
            return params

        if subindex is None:
            if isinstance(dictval, list):
                # FIXME: An interesting difference beween GetParamsEntry() and GetEntry() is that
                # the latter returns the number of subindexes in index 0, while the former does not

                # FIXME: There is a programmed assumption here: It checks dictval for a
                # list but it assumes then that param_value is a dict. This is not always the case.

                params = params or {}
                return [_get_param(params.get(i)) for i in range(len(dictval) + 1)]  # type: ignore[call-overload]

            # Dictionary value is not a list
            result = _get_param(params)  # type: ignore[arg-type]

            # This option ensures that the function consistently returns a list
            if aslist:
                return [result]
            return result

        if isinstance(dictval, list):

            if 0 <= subindex <= len(dictval):
                params = params or {}
                return _get_param(params.get(subindex))  # type: ignore[call-overload]

            raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

        # Special case: If the dictionary value is not a list, subindex 0
        # will fetch the parameter.
        if subindex == 0:
            return _get_param(params)# type: ignore[arg-type]

        raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

    def GetIndexEntry(self, index: int, withbase: bool = False) -> TIndexEntry:
        """ Return a full and raw representation of the index """

        def _mapping_for_index(index: int) -> Generator[tuple[str, TODObj], None, None]:
            for name, o in (
                ('profile', self.Profile),
                ('ds302', self.DS302),
                ('user', self.UserMapping),
                ('built-in', maps.MAPPING_DICTIONARY),
            ):
                if index in o:
                    yield name, o[index]

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
            _, baseobject = next(_mapping_for_index(baseindex))
            obj['basestruct'] = baseobject["struct"]
            if withbase:
                # If "object" is not present, add the base object
                obj.setdefault("object", baseobject)

        # FIXME: Add the ability to evaluate the names and the values
        # with the "compute" flag

        # Ensure that the object is safe to mutate
        return copy.deepcopy(obj)

    def GetSubentryLength(self, index: int) -> int:
        """ Return the length of the subindex """
        val = self.Dictionary.get(index, [])
        if not isinstance(val, list):
            return 0
        return len(val)

    def GetBaseIndex(self, index: int) -> int:
        """ Return the index number of the base object """
        return self.GetMappings(withmapping=True).FindBaseIndex(index)

    def GetBaseIndexNumber(self, index: int) -> int:
        """ Return the index number from the base object """
        return self.GetMappings(withmapping=True).FindBaseIndexNumber(index)

    def GetCustomisedTypeValues(self, index: int) -> tuple[list[TODValue], int]:
        """Return the customization struct type from the index. It returns
        a tuple containing the entry value and the int of the type of the object.
        0 indicates numerical value, 1 indicates string value."""
        values = self.GetEntry(index)
        if not isinstance(values, list):
            raise ValueError(f"Index 0x{index:04x} is not an entry with subobjects")
        customisabletypes = self.GetCustomisableTypes()
        # values[1] contains the object type index
        return values, customisabletypes[values[1]][1]  # type: ignore[index]

    def GetEntryName(self, index: int, compute=True) -> str:
        """Return the entry name for the given index"""
        return self.GetMappings(withmapping=True).FindEntryName(index, compute)

    def GetEntryInfos(self, index: int, compute=True) -> TODObj:
        """Return the entry infos for the given index"""
        # FIXME: Add flags. Add the ability to determine the mapping source
        result = self.GetMappings(withmapping=True).FindEntryInfos(index, compute)
        try:
            # If present in built-in dictionary, use the built-in values
            # and update with the user provided values
            r301 = maps.MAPPING_DICTIONARY.FindEntryInfos(index, compute)
            r301.update(result)
            return r301
        except ValueError:
            pass
        return result

    def GetSubentryInfos(self, index: int, subindex: int, compute: bool = True) -> TODSubObj:
        """Return the subentry infos for the given index and subindex"""
        # FIXME: Add flags. Add the ability to determine the mapping source
        result = self.GetMappings(withmapping=True).FindSubentryInfos(index, subindex, compute)
        # FIXME: This will alter objects in the mapping store. This is probably not intended
        result["user_defined"] = index in self.UserMapping
        try:
            r301 = maps.MAPPING_DICTIONARY.FindSubentryInfos(index, subindex, compute)
            r301.update(result)
            return r301
        except ValueError:
            pass
        return result

    def GetTypeIndex(self, typename: str) -> int:
        """Return the type index for the given type name."""
        return self.GetMappings(withmapping=True).FindTypeIndex(typename)

    def GetTypeName(self, index: int) -> str:
        """Return the type name for the given type index."""
        return self.GetMappings(withmapping=True).FindTypeName(index)

    def GetTypeDefaultValue(self, index: int) -> TODValue:
        """Return the default value for the given type index."""
        return self.GetMappings(withmapping=True).FindTypeDefaultValue(index)

    def GetMapVariableList(self, compute=True) -> list[tuple[int, int, int, str]]:
        """Return a list of all objects and subobjects available for mapping into
        pdos. Returns a list of tuples with the index, subindex, size and name of the object."""
        return list(sorted(self.GetMappings(withmapping=True).FindMapVariableList(self, compute)))

    def GetMandatoryIndexes(self) -> list[int]:
        """Return the mandatory indexes for the node."""
        # FIXME: Old code listed MAPPING_DIRECTORY first, this is last. Important?
        return self.GetMappings(withmapping=True).FindMandatoryIndexes()

    def GetCustomisableTypes(self) -> dict[int, tuple[str, int]]:
        """ Return the customisable types. It returns a dict by the index number.
        The value is a tuple with the type name and the size of the type."""
        return {
            index: (self.GetTypeName(index), valuetype)
            for index, valuetype in maps.CUSTOMISABLE_TYPES
        }

    def GetTypeList(self) -> list[str]:
        """Return a list of all object types available for the current node"""
        # FIXME: Old code listed MAPPING_DIRECTORY first, this puts it last. Important?
        return self.GetMappings(withmapping=True).FindTypeList()

    @staticmethod
    def GenerateMapName(name: str, index: int, subindex: int) -> str:
        """Return how a mapping object should be named in UI"""
        return f"{name} (0x{index:04X})"

    def GetMapValue(self, mapname: str) -> int:
        """Return the mapping value from the given printable name"""
        if mapname == "None":
            return 0

        def _get_buffer_size(index: int, subindex: int, size: int, name: str) -> int:
            try:
                params: TParamEntry = self.ParamsDictionary[index][subindex]  # type: ignore[literal-required]
                bs = params["buffer_size"]
                if bs <= 8:
                    return (index << 16) + (subindex << 8) + size * bs
                raise ValueError(f"String size of '{name}' too big to fit in a PDO")
            except KeyError:
                raise ValueError(
                    "No string length found and default string size too big to fit in a PDO"
                ) from None

        varlist = self.GetMapVariableList()
        for index, subindex, size, name in varlist:
            if mapname == self.GenerateMapName(name, index, subindex):
                # array type, only look at subindex 1 in UserMapping
                if self.UserMapping[index]["struct"] == OD.ARRAY:
                    if self.IsStringType(self.UserMapping[index]["values"][1]["type"]):
                        return _get_buffer_size(index, subindex, size, mapname)
                else:
                    if self.IsStringType(self.UserMapping[index]["values"][subindex]["type"]):
                        return _get_buffer_size(index, subindex, size, mapname)
                return (index << 16) + (subindex << 8) + size

        raise ValueError(f"Mapping '{mapname}' not found")

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
            # FIXME: Removed a "if result" check here
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

    def GetAllIndices(self, sort=False) -> list[int]:
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
            k for k in self.GetAllIndices()
            if k not in self.Dictionary
        ]

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

    def IsMappingEntry(self, index: int) -> bool:
        """
        Check if an entry exists in the User Mapping Dictionary and returns the answer.
        """
        # FIXME: Is usermapping only used when defining custom objects?
        # Come back to this and test if this is the case. If it is the function
        # should probably be renamed to "IsUserEntry" or somesuch
        return index in self.UserMapping

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

    def HasEntryCallbacks(self, index: int) -> bool:
        """Check if entry has the callback flag defined."""
        entry_infos = self.GetEntryInfos(index)
        if entry_infos and "callback" in entry_infos:
            return entry_infos["callback"]
        if index in self.Dictionary and index in self.ParamsDictionary:
            params = self.ParamsDictionary[index]
            return params.get("callback", False)  # type: ignore[call-overload, return-value]
        return False

    # --------------------------------------------------------------------------
    #                      Node mutuation functions
    # --------------------------------------------------------------------------

    def AddEntry(self, index: int, subindex: int|None = None, value: TODValue|list[TODValue]|None = None):
        """
        Add a new entry in the Object Dictionary
        """
        # FIXME: It need a value, but the order of fn arguments is placed after an optional arg
        assert value is not None
        if index not in self.Dictionary:
            if not subindex:
                self.Dictionary[index] = value
                return
            if subindex == 1:
                # FIXME: When specifying a subindex, the value should never be a list
                assert not isinstance(value, list)
                self.Dictionary[index] = [value]
                return
            raise ValueError(f"Invalid subindex {subindex} when 0x{index:04x} is not in the dictionary")

        dictval = self.Dictionary[index]
        if subindex and isinstance(dictval, list) and subindex == len(dictval) + 1:
            # FIXME: When specifying a subindex, the value should never be a list
            assert not isinstance(value, list)
            dictval.append(value)
            return
        raise ValueError(f"Unable to add entry 0x{index:04x} subindex {subindex}")

    def SetEntry(self, index: int, subindex: int|None = None, value: TODValue|None = None):
        """Modify an existing entry in the Object Dictionary"""
        # FIXME: Is it permissible to have value as None? The code seems to suggest that it is
        assert value is not None
        if index not in self.Dictionary:
            raise ValueError(f"Index 0x{index:04x} does not exist")
        dictval = self.Dictionary[index]

        if not subindex:
            # if value is not None:  # FIXME: Can this be None?
            self.Dictionary[index] = value
            return

        if isinstance(dictval, list) and 0 < subindex <= len(dictval):
            # if value is not None:  # FIXME: Can this be None?
            dictval[subindex - 1] = value
            return
        raise ValueError(f"Failed to set entry 0x{index:04x} subindex {subindex}")

    def SetParamsEntry(self, index: int, subindex: int|None = None, params: TParamEntry|None = None):
        """Set parameter values for an entry in the Object Dictionary."""
        if index not in self.Dictionary:
            raise ValueError(f"Index 0x{index:04x} does not exist")
        if not params:
            raise ValueError("No parameters to set for index 0x{index:04x}")

        dictval = self.Dictionary[index]
        pardict = self.ParamsDictionary.setdefault(index, {})

        if subindex is None or (not isinstance(dictval, list) and subindex == 0):
            pardict.update(params)  # type: ignore[arg-type]
            return

        if isinstance(dictval, list) and 0 <= subindex <= len(dictval):
            subparam: TParamEntry = pardict.setdefault(subindex, {})  # type: ignore[typeddict-item,misc]
            subparam.update(params)
            return

        raise ValueError(f"Failed to set params entry 0x{index:04x} subindex {subindex}")

    def RemoveEntry(self, index: int, subindex: int|None = None):
        """
        Removes an existing entry in the Object Dictionary. If a subindex is specified
        it will remove this subindex only if it's the last of the index. If no subindex
        is specified it removes the whole index and subIndexes from the Object Dictionary.
        """
        if index not in self.Dictionary:
            raise ValueError(f"Index 0x{index:04x} does not exist")

        if subindex is None:
            self.Dictionary.pop(index)
            self.ParamsDictionary.pop(index, None)
            return

        dictval = self.Dictionary[index]
        if isinstance(dictval, list) and subindex == len(dictval):
            dictval.pop(subindex - 1)
            if index in self.ParamsDictionary:
                self.ParamsDictionary[index].pop(subindex, None)  # type: ignore[typeddict-item,misc]
                if len(self.ParamsDictionary[index]) == 0:
                    self.ParamsDictionary.pop(index)
            if len(dictval) == 0:
                self.Dictionary.pop(index)
                self.ParamsDictionary.pop(index, None)
            return
        raise ValueError(f"Failed to remove entry 0x{index:04x} subindex {subindex}")

    def AddMappingEntry(self, index: int, entry: TODObj):
        """
        Add a new entry in the User Mapping Dictionary
        """
        if index in self.UserMapping:
            raise ValueError(f"Index 0x{index:04x} already exists in UserMapping")
        if not entry:
            raise ValueError("No entry to set for index 0x{index:04x}")
        if index not in self.UserMapping:
            entry.setdefault("values", [])
            self.UserMapping[index] = entry
            return
        raise ValueError(f"Failed to add mapping entry 0x{index:04x}")

    def AddMappingSubEntry(self, index: int, subindex: int, values: TODSubObj):
        """
        Add a new subentry in the User Mapping Dictionary
        """
        if not values:
            raise ValueError("No values to set for index 0x{index:04x} subindex {subindex}")
        if index not in self.UserMapping:
            raise ValueError(f"Index 0x{index:04x} does not exist in User Mapping")
        if subindex == len(self.UserMapping[index]["values"]):
            self.UserMapping[index]["values"].append(values)
            return
        raise ValueError(f"Failed to add mapping entry 0x{index:04x} subindex {subindex}")

    def SetMappingEntry(self, index: int, entry: TODObj):
        """
        Modify an existing entry in the User Mapping Dictionary
        """
        if index not in self.UserMapping:
            raise ValueError(f"Index 0x{index:04x} does not exist in User Mapping")
        if not entry:
            raise ValueError("No entry to set for index 0x{index:04x}")
        usermap = self.UserMapping[index]
        if "name" in entry:
            name = entry["name"]
            if usermap["struct"] & OD.IdenticalSubindexes:
                usermap["values"][1]["name"] = name + " %d[(sub)]"
            elif not usermap["struct"] & OD.MultipleSubindexes:
                usermap["values"][0]["name"] = name
        usermap.update(entry)

    def SetMappingSubEntry(self, index: int, subindex: int, values: TODSubObj):
        """
        Modify an existing subentry in the User Mapping Dictionary
        """
        if index not in self.UserMapping:
            raise ValueError(f"Index 0x{index:04x} subindex {subindex} does not exist in User Mapping")
        if not values:
            raise ValueError(f"No values to set for index 0x{index:04x} subindex {subindex}")
        usermap = self.UserMapping[index]
        if subindex >= len(usermap["values"]):
            raise ValueError(f"Subindex {subindex} for index 0x{index:04x} does not exist in User Mapping")
        submap = usermap["values"][subindex]
        if "type" in values:
            if usermap["struct"] & OD.IdenticalSubindexes:
                if self.IsStringType(submap["type"]):
                    if self.IsRealType(values["type"]):
                        for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                            self.SetEntry(index, i + 1, 0.)
                    elif not self.IsStringType(values["type"]):
                        for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                            self.SetEntry(index, i + 1, 0)
                elif self.IsRealType(submap["type"]):
                    if self.IsStringType(values["type"]):
                        for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                            self.SetEntry(index, i + 1, "")
                    elif not self.IsRealType(values["type"]):
                        for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                            self.SetEntry(index, i + 1, 0)
                elif self.IsStringType(values["type"]):
                    for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                        self.SetEntry(index, i + 1, "")
                elif self.IsRealType(values["type"]):
                    for i in range(len(self.Dictionary[index])):  # type: ignore[arg-type]
                        self.SetEntry(index, i + 1, 0.)
            else:
                if self.IsStringType(submap["type"]):
                    if self.IsRealType(values["type"]):
                        self.SetEntry(index, subindex, 0.)
                    elif not self.IsStringType(values["type"]):
                        self.SetEntry(index, subindex, 0)
                elif self.IsRealType(submap["type"]):
                    if self.IsStringType(values["type"]):
                        self.SetEntry(index, subindex, "")
                    elif not self.IsRealType(values["type"]):
                        self.SetEntry(index, subindex, 0)
                elif self.IsStringType(values["type"]):
                    self.SetEntry(index, subindex, "")
                elif self.IsRealType(values["type"]):
                    self.SetEntry(index, subindex, 0.)
        submap.update(values)

    def RemoveMappingEntry(self, index: int, subindex: int|None = None):
        """
        Removes an existing entry in the User Mapping Dictionary. If a subindex is specified
        it will remove this subindex only if it's the last of the index. If no subindex
        is specified it removes the whole index and subIndexes from the User Mapping Dictionary.
        """
        if index not in self.UserMapping:
            raise ValueError(f"Index 0x{index:04x} does not exist in User Mapping")
        if subindex is None:
            self.UserMapping.pop(index)
            return
        obj = self.UserMapping[index]
        if subindex == len(obj["values"]) - 1:
            obj["values"].pop(subindex)
            return
        if obj['struct'] & OD.IdenticalSubindexes:
            return
        raise ValueError(f"Invalid subindex {subindex} for index 0x{index:04x}")

    def RemoveMapVariable(self, index: int, subindex: int = 0):
        """
        Remove all PDO mappings references to the specificed index and subindex.
        """
        model = index << 16
        mask = 0xFFFF << 16
        if subindex:
            model += subindex << 8
            mask += 0xFF << 8
        # Iterate over all RPDO and TPDO mappings and remove the reference to this variable
        for i, dictval in self.Dictionary.items():
            if 0x1600 <= i <= 0x17FF or 0x1A00 <= i <= 0x1BFF:
                # FIXME: Assumes that PDO mappings are records
                assert isinstance(dictval, list)
                for j, value in enumerate(dictval):
                    # FIXME: Assumes that the data in the records are ints
                    assert isinstance(value, int)
                    if (value & mask) == model:
                        dictval[j] = 0

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
        for i, dictval in self.Dictionary.items():
            if 0x1600 <= i <= 0x17FF or 0x1A00 <= i <= 0x1BFF:
                # FIXME: Assumes that PDO mappings are records
                assert isinstance(dictval, list)
                for j, value in enumerate(dictval):
                    # FIXME: Assumes that the data in the records are ints
                    assert isinstance(value, int)
                    if (value & mask) == model:
                        dictval[j] = model + size

    def RemoveLine(self, index: int, maxval: int, incr: int = 1):
        """ Remove the given index and shift all the following indexes """
        # FIXME: This function is called from NodeManager.RemoveCurrentVariable()
        # but uncertain on how it is used.
        i = index
        while i < maxval and self.IsEntry(i + incr):
            self.Dictionary[i] = self.Dictionary[i + incr]
            i += incr
        self.Dictionary.pop(i)

    def RemoveIndex(self, index: int|Iterable[int]) -> None:
        """ Remove the given index or indexes """
        if isinstance(index, int):
            index = [index]
        for i in index:
            self.UserMapping.pop(i, None)
            self.Dictionary.pop(i, None)
            self.ParamsDictionary.pop(i, None)
            if self.DS302:
                self.DS302.pop(i, None)
            if self.Profile:
                self.Profile.pop(i, None)
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

            # FIXME: This probably needs a revisit. Is this checking that the
            # dimensions of Dictionary and ParamsDictionary match?

            #
            # Test if ParamDictionary matches Dictionary
            #
            # Complile a list of all subindexes
            dictlen = 1 if is_var else len(self.Dictionary.get(index, []))  # type: ignore[arg-type]
            params = {
                k: v
                # This assumes that ParamsDictionary is always a dict with or without subindexes
                for k, v in self.ParamsDictionary.get(index, {}).items()
                if isinstance(k, int)  # Any other key is not a subindex
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
                        del self.ParamsDictionary[index][idx]  # type: ignore[typeddict-item,misc]
                        del params[idx]
                    t_p = ", ".join(str(k) for k in excessive_params)
                    _warn(f"FIX: Deleting ParamDictionary entries {t_p}")

                    # If params have been emptied because of this, remove it altogether
                    if not params:
                        del self.ParamsDictionary[index]
                        _warn("FIX: Deleting ParamDictionary entry")

        # Iterate over all user mappings
        for index in set(self.UserMapping):
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

    def GetPrintEntryHeader(
            self, index: int, unused=False, compact=False, raw=False,
            entry: TIndexEntry|None = None
    ) -> tuple[str, dict[str, str]]:

        # Get the information about the index if it wasn't passed along
        if not entry:
            entry = self.GetIndexEntry(index, withbase=True)
        obj = entry["object"]

        # Get the flags for the entry
        flags: set[str] = set()
        for group in entry["groups"]:
            v = {
                "built-in": None,
                "user": "User",
                "ds302": "DS-302",
                "profile": "Profile",
            }.get(group, group)
            if v:
                flags.add(v)
        if obj.get('need'):
            flags.add("Mandatory")
        if entry.get("params", {}).get("callback"):
            flags.add('CB')
        if "dictionary" not in entry:
            if "ds302" in entry["groups"] or "profile" in entry["groups"]:
                flags.add("Unused")
            else:
                flags.add("Missing")

        # Skip printing if the entry is unused and we are not printing unused
        if 'Unused' in flags and not unused:
            return '', {}

        # Replace flags for formatting
        for _, flag in enumerate(flags.copy()):
            if flag == 'Missing':
                flags.discard('Missing')
                flags.add(Fore.RED + ' *MISSING* ' + Style.RESET_ALL)

        # Print formattings
        idx = (index - entry.get("base", index)) // obj.get("incr", 1) + 1
        t_name = obj['name']
        if not raw:
            t_name = maps.eval_name(t_name, idx=idx, sub=0)
        t_flags = ', '.join(flags)
        t_string = maps.ODStructTypes.to_string(obj['struct']) or '???'

        # ** PRINT PARAMETER **
        return "{pre}{key}  {name}   {struct}{flags}", {
            'key': f"{Fore.LIGHTGREEN_EX}0x{index:04x} ({index}){Style.RESET_ALL}",
            'name': f"{Fore.LIGHTWHITE_EX}{t_name}{Style.RESET_ALL}",
            'struct': f"{Fore.LIGHTYELLOW_EX}[{t_string.upper()}]{Style.RESET_ALL}",
            'flags': f"  {Fore.MAGENTA}{t_flags}{Style.RESET_ALL}" if flags else '',
            'pre': '    ' if not compact else '',
        }

    def GetPrintEntry(
            self, keys: list[int]|None = None, short=False, compact=False,
            unused=False, verbose=False, raw=False,
    ) -> Generator[str, None, None]:
        """
        Generator for printing the dictionary values
        """

        # Get the indexes to print and determine the order
        keys = keys or self.GetAllIndices(sort=True)

        index_range = None
        for k in keys:

            # Get the index entry information
            param = self.GetIndexEntry(k, withbase=True)
            obj = param["object"]

            # Get the header for the entry
            line, fmt = self.GetPrintEntryHeader(
                k, unused=unused, compact=compact, entry=param, raw=raw
            )
            if not line:
                continue

            # Print the parameter range header
            ir = maps.INDEX_RANGES.get_index_range(k)
            if index_range != ir:
                index_range = ir
                if not compact:
                    yield Fore.YELLOW + ir.description + Style.RESET_ALL

            # Yield the parameter header
            yield line.format(**fmt)

            # Omit printing sub index data if:
            if short:
                continue

            # Fetch the dictionary values and the parameters, if present
            if k in self.Dictionary:
                values = self.GetEntry(k, aslist=True, compute=not raw)
            else:
                values = ['__N/A__'] * len(obj["values"])
            if k in self.ParamsDictionary:
                params = self.GetParamsEntry(k, aslist=True)
            else:
                params = [maps.DEFAULT_PARAMS] * len(obj["values"])
            # For mypy to ensure that values and entries are lists
            assert isinstance(values, list) and isinstance(params, list)

            infos = []
            for i, (value, param) in enumerate(zip(values, params)):

                # Prepare data for printing
                info = self.GetSubentryInfos(k, i)
                typename = self.GetTypeName(info['type'])

                # Type specific formatting of the value
                if value == "__N/A__":
                    t_value = f'{Fore.LIGHTBLACK_EX}N/A{Style.RESET_ALL}'
                elif isinstance(value, str):
                    length = len(value)
                    if typename == 'DOMAIN':
                        value = value.encode('unicode_escape').decode()
                    t_value = '"' + value + f'"  ({length})'
                elif i and index_range and index_range.name in ('rpdom', 'tpdom'):
                    # FIXME: In PDO mappings, the value is ints
                    assert isinstance(value, int)
                    index, subindex, _ = self.GetMapIndex(value)
                    try:
                        pdo = self.GetSubentryInfos(index, subindex)
                        t_v = f"{value:x}"
                        t_value = f"0x{t_v[0:4]}_{t_v[4:6]}_{t_v[6:]}  {Fore.LIGHTCYAN_EX}{pdo['name']}{Style.RESET_ALL}"
                    except ValueError:
                        suffix = '   ???' if value else ''
                        t_value = f"0x{value:x}{suffix}"
                elif i and value and (k in (4120, ) or 'COB ID' in info["name"]):
                    t_value = f"0x{value:x}"
                else:
                    t_value = str(value)

                # Add comment if present
                t_comment = param['comment'] or ''
                if t_comment:
                    t_comment = f"{Fore.LIGHTBLACK_EX}/* {t_comment} */{Style.RESET_ALL}"

                # Omit printing the first element unless specifically requested
                if (not verbose and i == 0
                    and obj['struct'] & OD.MultipleSubindexes
                    and not t_comment
                ):
                    continue

                # Print formatting
                infos.append({
                    'i': f"{Fore.GREEN}{i:02d}{Style.RESET_ALL}",
                    'access': info['access'],
                    'pdo': 'P' if info['pdo'] else ' ',
                    'name': info['name'],
                    'type': f"{Fore.LIGHTBLUE_EX}{typename}{Style.RESET_ALL}",
                    'value': t_value,
                    'comment': t_comment,
                    'pre': fmt['pre'],
                })

            # Must skip the next step if list is empty, as the first element is
            # used for the header
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
                w["i"],  w["access"],  w["pdo"],  w["name"],  w["type"],  w["value"]
            )

            # Print each line using the generated format string
            for infoentry in infos:
                yield fmt.format(**infoentry)

            if not compact and infos:
                yield ""


# Register node with gnosis
nosis.add_class_to_store('Node', Node)
