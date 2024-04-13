"""Manage the node and the undo buffer."""
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

import codecs
import logging
import re
from pathlib import Path
from typing import Container, Generic, TypeVar, cast

import colorama

from objdictgen import maps
from objdictgen.maps import OD, ODMapping
from objdictgen.node import Node
from objdictgen.typing import TODSubObj, TPath

T = TypeVar("T")

log = logging.getLogger('objdictgen')

Fore = colorama.Fore
Style = colorama.Style

UNDO_BUFFER_LENGTH = 20

type_model = re.compile(r'([\_A-Z]*)([0-9]*)')
range_model = re.compile(r'([\_A-Z]*)([0-9]*)\[([\-0-9]*)-([\-0-9]*)\]')

# ID for the file viewed
CURRENTID = 0


# Returns a new id
def get_new_id():
    global CURRENTID  # pylint: disable=global-statement
    CURRENTID += 1
    return CURRENTID


class UndoBuffer(Generic[T]):
    """
    Class implementing a buffer of changes made on the current editing Object Dictionary
    """

    def __init__(self, state: T|None = None, issaved: bool = False):
        """
        Constructor initialising buffer
        """
        self.Buffer: list[T|None] = [state if not i else None for i in range(UNDO_BUFFER_LENGTH)]
        self.CurrentIndex: int = -1
        self.MinIndex: int = -1
        self.MaxIndex: int = -1
        # if current state is defined
        if state is not None:
            self.CurrentIndex = 0
            self.MinIndex = 0
            self.MaxIndex = 0
        # Initialising index of state saved
        if issaved:
            self.LastSave = 0
        else:
            self.LastSave = -1

    def Add(self, state: T):
        """
        Add a new state in buffer
        """
        self.CurrentIndex = (self.CurrentIndex + 1) % UNDO_BUFFER_LENGTH
        self.Buffer[self.CurrentIndex] = state
        # Actualising buffer limits
        self.MaxIndex = self.CurrentIndex
        if self.MinIndex == self.CurrentIndex:
            # If the removed state was the state saved, there is no state saved in the buffer
            if self.LastSave == self.MinIndex:
                self.LastSave = -1
            self.MinIndex = (self.MinIndex + 1) % UNDO_BUFFER_LENGTH
        self.MinIndex = max(self.MinIndex, 0)

    def Current(self) -> T:
        """
        Return current state of buffer
        """
        if self.CurrentIndex == -1:
            raise AttributeError("No current state in buffer")
        current = self.Buffer[self.CurrentIndex]
        # FIXME: By design the buffer should not contain None values
        assert current is not None
        return current

    def Previous(self) -> T:
        """
        Change current state to previous in buffer and return new current state
        """
        if self.CurrentIndex != -1 and self.CurrentIndex != self.MinIndex:
            self.CurrentIndex = (self.CurrentIndex - 1) % UNDO_BUFFER_LENGTH
            current = self.Buffer[self.CurrentIndex]
            # FIXME: By design the buffer should not contain None values
            assert current is not None
            return current
        raise AttributeError("No previous buffer available")

    def Next(self) -> T:
        """
        Change current state to next in buffer and return new current state
        """
        if self.CurrentIndex != -1 and self.CurrentIndex != self.MaxIndex:
            self.CurrentIndex = (self.CurrentIndex + 1) % UNDO_BUFFER_LENGTH
            current = self.Buffer[self.CurrentIndex]
            # FIXME: By design the buffer should not contain None values
            assert current is not None
            return current
        raise AttributeError("No next buffer available")

    def IsFirst(self) -> bool:
        """
        Return True if current state is the first in buffer
        """
        return self.CurrentIndex == self.MinIndex

    def IsLast(self) -> bool:
        """
        Return True if current state is the last in buffer
        """
        return self.CurrentIndex == self.MaxIndex

    def CurrentSaved(self):
        """
        Save current state
        """
        self.LastSave = self.CurrentIndex

    def IsCurrentSaved(self) -> bool:
        """
        Return True if current state is saved
        """
        return self.LastSave == self.CurrentIndex


class NodeManager:
    """
    Class which control the operations made on the node and answer to view requests
    """

    def __init__(self):
        """
        Constructor
        """
        self.LastNewIndex = 0
        self.FilePaths: dict[int, Path|None] = {}
        self.FileNames: dict[int, str] = {}
        self.CurrentNodeIndex: int|None = None
        self.CurrentNode: Node|None = None
        self.UndoBuffers: dict[int, UndoBuffer[Node]] = {}

    # --------------------------------------------------------------------------
    #                         Properties
    # --------------------------------------------------------------------------

    @property
    def nodeindex(self) -> int:
        """The current node index."""
        if self.CurrentNodeIndex is None:
            raise AttributeError("No node is currently selected")
        return self.CurrentNodeIndex

    @property
    def current(self) -> Node:
        """The current selected node. It will raise an error if no node is selected."""
        if not self.CurrentNode:
            raise AttributeError("No node is currently selected")
        return self.CurrentNode

    @property
    def current_default(self) -> Node:
        """Return the current node or the default node if no current node is selected."""
        return self.CurrentNode if self.CurrentNode else Node()

    # --------------------------------------------------------------------------
    #                        Create Load and Save Functions
    # --------------------------------------------------------------------------

    # FIXME: Change to not mask the builtins
    def CreateNewNode(self, name: str, id: int, type: str, description: str,
                        profile: str, filepath: TPath, nmt: str,
                        options: Container[str]):
        """
        Create a new node and add a new buffer for storing it
        """
        # Create a new node
        node = Node()
        # Load profile given
        if profile != "None":
            # Import profile
            mapping, menuentries = maps.import_profile(filepath)
            node.ProfileName = profile
            node.Profile = mapping
            node.SpecificMenu = menuentries
        else:
            # Default profile
            node.ProfileName = "None"
            node.Profile = ODMapping()
            node.SpecificMenu = []
        # Initialising node
        self.CurrentNode = node
        node.Name = name
        node.ID = id
        node.Type = type
        node.Description = description
        addindexlist = node.GetMandatoryIndexes()
        addsubindexlist = []
        if nmt == "NodeGuarding":
            addindexlist.extend([0x100C, 0x100D])
        elif nmt == "Heartbeat":
            addindexlist.append(0x1017)
        if "DS302" in options:
            # Import profile
            mapping, menuentries = maps.import_profile("DS-302")
            node.DS302 = mapping
            node.SpecificMenu.extend(menuentries)
        if "GenSYNC" in options:
            addindexlist.extend([0x1005, 0x1006])
        if "Emergency" in options:
            addindexlist.append(0x1014)
        if "SaveConfig" in options:
            addindexlist.extend([0x1010, 0x1011, 0x1020])
        if "StoreEDS" in options:
            addindexlist.extend([0x1021, 0x1022])
        if type == "slave":
            # add default SDO server
            addindexlist.append(0x1200)
            # add default 4 receive and 4 transmit PDO
            for paramindex, mapindex in [(0x1400, 0x1600), (0x1800, 0x1A00)]:
                firstparamindex = self.GetLineFromIndex(paramindex)
                firstmappingindex = self.GetLineFromIndex(mapindex)
                addindexlist.extend(list(range(firstparamindex, firstparamindex + 4)))
                for idx in range(firstmappingindex, firstmappingindex + 4):
                    addindexlist.append(idx)
                    addsubindexlist.append((idx, 8))

        # Add a new buffer
        index = self.AddNodeBuffer(node.copy(), False)
        self.SetCurrentFilePath(None)
        # Add Mandatory indexes
        self.ManageEntriesOfCurrent(addindexlist, [])
        for idx, num in addsubindexlist:
            self.AddSubentriesToCurrent(idx, num)
        return index

    def OpenFileInCurrent(self, filepath: TPath, load=True) -> int:
        """
        Open a file and store it in a new buffer
        """
        node = Node.LoadFile(filepath)

        self.CurrentNode = node
        node.ID = 0

        index = self.AddNodeBuffer(node.copy(), load)
        self.SetCurrentFilePath(filepath if load else None)
        return index

    def SaveCurrentInFile(self, filepath: TPath|None = None, filetype='', **kwargs) -> bool:
        """
        Save current node in a file
        """
        # if no filepath given, verify if current node has a filepath defined
        if not filepath:
            filepath = self.GetCurrentFilePath()
            if not filepath:
                return False

        node = self.CurrentNode
        if not node:
            return False

        # Save node in file
        filepath = Path(filepath)
        ext = filepath.suffix.lstrip('.').lower()

        # Save the data
        node.DumpFile(filepath, filetype=ext, **kwargs)

        # Update saved state in buffer
        if ext not in ('c', 'eds') and self.nodeindex in self.UndoBuffers:
            self.UndoBuffers[self.nodeindex].CurrentSaved()
        return True

    def CloseCurrent(self, ignore=False) -> bool:
        """
        Close current state
        """
        # Verify if it's not forced that the current node is saved before closing it
        if (self.CurrentNodeIndex in self.UndoBuffers
            and (self.UndoBuffers[self.CurrentNodeIndex].IsCurrentSaved() or ignore)
        ):
            self.RemoveNodeBuffer(self.CurrentNodeIndex)
            if len(self.UndoBuffers) > 0:
                previousindexes = [idx for idx in self.UndoBuffers if idx < self.CurrentNodeIndex]
                nextindexes = [idx for idx in self.UndoBuffers if idx > self.CurrentNodeIndex]
                if len(previousindexes) > 0:
                    previousindexes.sort()
                    self.CurrentNodeIndex = previousindexes[-1]
                elif len(nextindexes) > 0:
                    nextindexes.sort()
                    self.CurrentNodeIndex = nextindexes[0]
                else:
                    self.CurrentNodeIndex = None
            else:
                self.CurrentNodeIndex = None
            return True
        return False

    # --------------------------------------------------------------------------
    #                        Add Entries to Current Functions
    # --------------------------------------------------------------------------

    def AddSubentriesToCurrent(self, index: int, number: int, node: Node|None = None):
        """
        Add the specified number of subentry for the given entry. Verify that total
        number of subentry (except 0) doesn't exceed nbmax defined
        """
        disable_buffer = node is not None
        if node is None:
            node = self.current
        # Informations about entry
        length = node.GetEntry(index, 0)
        # FIXME: This code assumes that subindex 0 is the length of the entry
        assert isinstance(length, int)
        infos = node.GetEntryInfos(index)
        subentry_infos = node.GetSubentryInfos(index, 1)
        # Get default value for subindex
        if "default" in subentry_infos:
            default = subentry_infos["default"]
        else:
            default = node.GetTypeDefaultValue(subentry_infos["type"])
        # First case entry is array
        if infos["struct"] & OD.IdenticalSubindexes:
            for i in range(1, min(number, subentry_infos["nbmax"] - length) + 1):
                node.AddEntry(index, length + i, default)
            if not disable_buffer:
                self.BufferCurrentNode()
            return
        # Second case entry is record (and array), only possible for manufacturer specific
        if infos["struct"] & OD.MultipleSubindexes and 0x2000 <= index <= 0x5FFF:
            values: TODSubObj = {"name": "Undefined", "type": 5, "access": "rw", "pdo": True}
            for i in range(1, min(number, 0xFE - length) + 1):
                node.AddMappingSubEntry(index, length + i, values=values.copy())
                node.AddEntry(index, length + i, 0)
            if not disable_buffer:
                self.BufferCurrentNode()

    def RemoveSubentriesFromCurrent(self, index: int, number: int):
        """
        Remove the specified number of subentry for the given entry. Verify that total
        number of subentry (except 0) isn't less than 1
        """
        # Informations about entry
        node = self.current
        infos = node.GetEntryInfos(index)
        length = node.GetEntry(index, 0)
        # FIXME: This code assumes that subindex 0 is the length of the entry
        assert isinstance(length, int)
        nbmin = infos.get("nbmin", 1)
        # Entry is an array, or is an array/record of manufacturer specific
        # FIXME: What is the intended order of the conditions? or-and on same level
        if (infos["struct"] & OD.IdenticalSubindexes or 0x2000 <= index <= 0x5FFF
            and infos["struct"] & OD.MultipleSubindexes
        ):
            for i in range(min(number, length - nbmin)):
                self.RemoveCurrentVariable(index, length - i)
            self.BufferCurrentNode()

    def AddSDOServerToCurrent(self):
        """
        Add a SDO Server to current node
        """
        # An SDO Server is already defined at index 0x1200
        if self.current.IsEntry(0x1200):
            indexlist = [self.GetLineFromIndex(0x1201)]
            if None not in indexlist:
                self.ManageEntriesOfCurrent(indexlist, [])
        # Add an SDO Server at index 0x1200
        else:
            self.ManageEntriesOfCurrent([0x1200], [])

    def AddSDOClientToCurrent(self):
        """
        Add a SDO Server to current node
        """
        indexlist = [self.GetLineFromIndex(0x1280)]
        if None not in indexlist:
            self.ManageEntriesOfCurrent(indexlist, [])

    def AddPDOTransmitToCurrent(self):
        """
        Add a Transmit PDO to current node
        """
        indexlist = [self.GetLineFromIndex(0x1800), self.GetLineFromIndex(0x1A00)]
        if None not in indexlist:
            self.ManageEntriesOfCurrent(indexlist, [])

    def AddPDOReceiveToCurrent(self):
        """
        Add a Receive PDO to current node
        """
        indexlist = [self.GetLineFromIndex(0x1400), self.GetLineFromIndex(0x1600)]
        if None not in indexlist:
            self.ManageEntriesOfCurrent(indexlist, [])

    def AddSpecificEntryToCurrent(self, menuitem: str):
        """
        Add a list of entries defined in profile for menu item selected to current node
        """
        node = self.current
        indexlist: list[int] = []
        for menu, indexes in node.SpecificMenu:
            if menuitem == menu:
                indexlist.extend(
                    self.GetLineFromIndex(index)
                    for index in indexes
                )
        if None not in indexlist:
            self.ManageEntriesOfCurrent(indexlist, [])

    def GetLineFromIndex(self, base_index: int) -> int:
        """
        Search the first index available for a pluri entry from base_index
        """
        node = self.current
        found = False
        index = base_index
        infos = node.GetEntryInfos(base_index)
        while index < base_index + infos["incr"] * infos["nbmax"] and not found:
            if not node.IsEntry(index):
                found = True
            else:
                index += infos["incr"]
        if found:
            return index
        raise ValueError(f"No available index found for 0x{base_index:04X}")

    def ManageEntriesOfCurrent(self, addinglist: list[int], removinglist: list[int], node: Node|None = None):
        """
        Add entries specified in addinglist and remove entries specified in removinglist
        """
        disable_buffer = node is not None
        if node is None:
            node = self.current
        # Add all the entries in addinglist
        for index in addinglist:
            infos = node.GetEntryInfos(index)
            if infos["struct"] & OD.MultipleSubindexes:
                # First case entry is an array
                if infos["struct"] & OD.IdenticalSubindexes:
                    subentry_infos = node.GetSubentryInfos(index, 1)
                    if "default" in subentry_infos:
                        default = subentry_infos["default"]
                    else:
                        default = node.GetTypeDefaultValue(subentry_infos["type"])
                    node.AddEntry(index, value=[])
                    if "nbmin" in subentry_infos:
                        for i in range(subentry_infos["nbmin"]):
                            node.AddEntry(index, i + 1, default)
                    else:
                        node.AddEntry(index, 1, default)
                # Second case entry is a record
                else:
                    # FIXME: How to retrieve the number of subentries?
                    for i in range(1, node.GetSubentryLength(index) + 1):
                        subentry_infos = node.GetSubentryInfos(index, i)
                        if "default" in subentry_infos:
                            default = subentry_infos["default"]
                        else:
                            default = node.GetTypeDefaultValue(subentry_infos["type"])
                        node.AddEntry(index, i, default)
            # Third case entry is a var
            else:
                subentry_infos = node.GetSubentryInfos(index, 0)
                if "default" in subentry_infos:
                    default = subentry_infos["default"]
                else:
                    default = node.GetTypeDefaultValue(subentry_infos["type"])
                node.AddEntry(index, 0, default)
        # Remove all the entries in removinglist
        for index in removinglist:
            self.RemoveCurrentVariable(index)
        if not disable_buffer:
            self.BufferCurrentNode()

    def SetCurrentEntryToDefault(self, index: int, subindex:int, node: Node|None = None):
        """
        Reset an subentry from current node to its default value
        """
        disable_buffer = node is not None
        if node is None:
            node = self.current
        if node.IsEntry(index, subindex):
            subentry_infos = node.GetSubentryInfos(index, subindex)
            if "default" in subentry_infos:
                default = subentry_infos["default"]
            else:
                default = node.GetTypeDefaultValue(subentry_infos["type"])
            node.SetEntry(index, subindex, default)
            if not disable_buffer:
                self.BufferCurrentNode()

    def RemoveCurrentVariable(self, index: int, subindex: int|None = None):
        """
        Remove an entry from current node. Analize the index to perform the correct
        method
        """
        node = self.current
        mappings = node.GetMappings()
        if index < 0x1000 and subindex is None:
            entrytype = node.GetEntry(index, 1)
            # FIXME: By design the type of index 1 is the object type in int
            assert isinstance(entrytype, int)
            for i in mappings[-1]:  # FIXME: Hard code to access last (UserMapping)?
                for value in mappings[-1][i]["values"]:
                    if value["type"] == index:
                        value["type"] = entrytype
            node.RemoveMappingEntry(index)
            node.RemoveEntry(index)
        elif index == 0x1200 and subindex is None:
            node.RemoveEntry(0x1200)
        elif 0x1201 <= index <= 0x127F and subindex is None:
            node.RemoveLine(index, 0x127F)
        elif 0x1280 <= index <= 0x12FF and subindex is None:
            node.RemoveLine(index, 0x12FF)
        elif 0x1400 <= index <= 0x15FF or 0x1600 <= index <= 0x17FF and subindex is None:
            if 0x1600 <= index <= 0x17FF and subindex is None:
                index -= 0x200
            node.RemoveLine(index, 0x15FF)
            node.RemoveLine(index + 0x200, 0x17FF)
        elif 0x1800 <= index <= 0x19FF or 0x1A00 <= index <= 0x1BFF and subindex is None:
            if 0x1A00 <= index <= 0x1BFF:
                index -= 0x200
            node.RemoveLine(index, 0x19FF)
            node.RemoveLine(index + 0x200, 0x1BFF)
        else:
            found = False
            for _, menulist in node.SpecificMenu:
                for i in menulist:
                    iinfos = node.GetEntryInfos(i)
                    indexes = [i + incr * iinfos["incr"] for incr in range(iinfos["nbmax"])]
                    if index in indexes:
                        found = True
                        diff = index - i
                        for j in menulist:
                            jinfos = node.GetEntryInfos(j)
                            node.RemoveLine(
                                j + diff, j + jinfos["incr"] * jinfos["nbmax"], jinfos["incr"]
                            )
            node.RemoveMapVariable(index, subindex or 0)
            if not found:
                infos = node.GetEntryInfos(index)
                if not infos.get("need"):
                    node.RemoveEntry(index, subindex)
            if index in mappings[-1]:
                node.RemoveMappingEntry(index, subindex)

    def AddMapVariableToCurrent(self, index: int, name: str, struct: int, number: int, node: Node|None = None):
        if 0x2000 <= index <= 0x5FFF:
            disable_buffer = node is not None
            if node is None:
                node = self.current
            if node.IsEntry(index):
                raise ValueError(f"Index 0x{index:04X} already defined!")
            node.AddMappingEntry(index, entry={"name": name, "struct": struct})
            if struct == OD.VAR:
                values: TODSubObj = {"name": name, "type": 0x05, "access": "rw", "pdo": True}
                node.AddMappingSubEntry(index, 0, values=values)
                node.AddEntry(index, 0, 0)
            else:
                values = {"name": "Number of Entries", "type": 0x05, "access": "ro", "pdo": False}
                node.AddMappingSubEntry(index, 0, values=values)
                if struct == OD.ARRAY:
                    values = {
                        "name": name + " %d[(sub)]", "type": 0x05,
                        "access": "rw", "pdo": True, "nbmax": 0xFE,
                    }
                    node.AddMappingSubEntry(index, 1, values=values)
                    for i in range(number):
                        node.AddEntry(index, i + 1, 0)
                else:
                    for i in range(number):
                        values = {"name": "Undefined", "type": 0x05, "access": "rw", "pdo": True}
                        node.AddMappingSubEntry(index, i + 1, values=values)
                        node.AddEntry(index, i + 1, 0)
            if not disable_buffer:
                self.BufferCurrentNode()
            return
        raise ValueError(f"Index 0x{index:04X} isn't a valid index for Map Variable!")

    def AddUserTypeToCurrent(self, objtype: int, minval: int, maxval: int, length: int):
        node = self.current
        index = 0xA0
        while index < 0x100 and node.IsEntry(index):
            index += 1
        if index >= 0x100:
            raise ValueError("Too many User Types have already been defined!")
        customisabletypes = node.GetCustomisableTypes()
        name, valuetype = customisabletypes[objtype]
        size = node.GetEntryInfos(objtype)["size"]
        default = node.GetTypeDefaultValue(objtype)
        if valuetype == 0:
            node.AddMappingEntry(index, entry={
                "name": f"{name}[{minval}-{maxval}]", "struct": OD.RECORD,
                "size": size, "default": default,
            })
            node.AddMappingSubEntry(index, 0, values={
                "name": "Number of Entries", "type": 0x05, "access": "ro", "pdo": False,
            })
            node.AddMappingSubEntry(index, 1, values={
                "name": "Type", "type": 0x05, "access": "ro", "pdo": False,
            })
            node.AddMappingSubEntry(index, 2, values={
                "name": "Minimum Value", "type": objtype, "access": "ro", "pdo": False,
            })
            node.AddMappingSubEntry(index, 3, values={
                "name": "Maximum Value", "type": objtype, "access": "ro", "pdo": False,
            })
            node.AddEntry(index, 1, objtype)
            node.AddEntry(index, 2, minval)
            node.AddEntry(index, 3, maxval)
        elif valuetype == 1:
            node.AddMappingEntry(index, entry={
                "name": f"{name}{length}", "struct": OD.RECORD,
                "size": length * size, "default": default,
            })
            node.AddMappingSubEntry(index, 0, values={
                "name": "Number of Entries", "type": 0x05, "access": "ro", "pdo": False,
            })
            node.AddMappingSubEntry(index, 1, values={
                "name": "Type", "type": 0x05, "access": "ro", "pdo": False,
            })
            node.AddMappingSubEntry(index, 2, values={
                "name": "Length", "type": 0x05, "access": "ro", "pdo": False,
            })
            node.AddEntry(index, 1, objtype)
            node.AddEntry(index, 2, length)
        self.BufferCurrentNode()

    # --------------------------------------------------------------------------
    #                      Modify Entry and Mapping Functions
    # --------------------------------------------------------------------------

    def SetCurrentEntryCallbacks(self, index: int, value: bool):
        node = self.current
        if node.IsEntry(index):
            entry_infos = node.GetEntryInfos(index)
            if "callback" not in entry_infos:
                # FIXME: This operation adds params directly to the entry
                # regardless if the index object has subindexes. It should be
                # investigated if this is the indended behavior.
                node.SetParamsEntry(index, params={"callback": value})
                self.BufferCurrentNode()

    def SetCurrentEntry(self, index: int, subindex: int, value: str, name: str, editor: str, node: Node|None = None):
        disable_buffer = node is not None
        if node is None:
            node = self.current
        if node and node.IsEntry(index):
            if name == "value":
                if editor == "map":
                    nvalue = node.GetMapValue(value)
                    node.SetEntry(index, subindex, nvalue)
                elif editor == "bool":
                    nvalue = value == "True"
                    node.SetEntry(index, subindex, nvalue)
                elif editor == "time":
                    node.SetEntry(index, subindex, value)
                elif editor == "number":
                    # Might fail with ValueError if number is malformed
                    node.SetEntry(index, subindex, int(value))
                elif editor == "float":
                    # Might fail with ValueError if number is malformed
                    node.SetEntry(index, subindex, float(value))
                elif editor == "domain":
                    # Might fail with binascii.Error if hex is malformed
                    if len(value) % 2 != 0:
                        value = "0" + value
                    # The latin-1 encoding supports using 0x80-0xFF as values
                    # FIXME: Doesn't work with unicode
                    bvalue = codecs.decode(value, 'hex_codec').decode('latin-1')
                    node.SetEntry(index, subindex, bvalue)
                elif editor == "dcf":
                    node.SetEntry(index, subindex, value)
                else:
                    subentry_infos = node.GetSubentryInfos(index, subindex)
                    objtype = subentry_infos["type"]
                    dic = dict(maps.CUSTOMISABLE_TYPES)
                    if objtype not in dic:
                        # FIXME: Subobj 1 is the objtype, which should be int by design
                        objtype = cast(int, node.GetEntry(objtype)[1])  # type: ignore[index]
                    # FIXME: If objtype is not in dic, this will raise a KeyError
                    if dic[objtype] == 0:
                        # Might fail if number is malformed
                        ivalue: int|str
                        if value.startswith("$NODEID"):
                            ivalue = f'"{value}"'
                        elif value.startswith("0x"):
                            ivalue = int(value, 16)
                        else:
                            ivalue = int(value)
                        node.SetEntry(index, subindex, ivalue)
                    else:
                        node.SetEntry(index, subindex, value)
            elif name in ["comment", "save", "buffer_size"]:
                if name == "save":
                    node.SetParamsEntry(index, subindex, params={"save": value == "Yes"})
                elif name == "comment":
                    node.SetParamsEntry(index, subindex, params={"comment": value})
                elif name == "buffer_size":
                    # Might fail with ValueError if number is malformed
                    nvalue = int(value)
                    if nvalue <= 0:
                        raise ValueError("Number must be positive")
                    node.SetParamsEntry(index, subindex, params={"buffer_size": nvalue})
            else:
                nvalue: str|int = value
                if editor == "type":
                    nvalue = node.GetTypeIndex(value)
                    # All type object shall have size
                    size = node.GetEntryInfos(nvalue)["size"]
                    node.UpdateMapVariable(index, subindex, size)
                elif editor in ["access", "raccess"]:
                    nvalue = {  # type: ignore[assignment]
                        access: abbrev
                        for abbrev, access in maps.ACCESS_TYPE.items()
                    }[value]
                    if editor == "raccess" and not node.IsMappingEntry(index):
                        entry_infos = node.GetEntryInfos(index)
                        subindex0_infos = node.GetSubentryInfos(index, 0, False).copy()
                        subindex1_infos = node.GetSubentryInfos(index, 1, False).copy()
                        node.AddMappingEntry(index, entry={"name": entry_infos["name"], "struct": OD.ARRAY})
                        node.AddMappingSubEntry(index, 0, values=subindex0_infos)
                        node.AddMappingSubEntry(index, 1, values=subindex1_infos)
                node.SetMappingSubEntry(index, subindex, values={name: nvalue})  # type: ignore[misc]
            if not disable_buffer:
                self.BufferCurrentNode()

    def SetCurrentEntryName(self, index: int, name: str):
        self.current.SetMappingEntry(index, entry={"name": name})
        self.BufferCurrentNode()

    def SetCurrentUserType(self, index: int, objtype: int, minval: int, maxval: int, length: int):
        node = self.current
        customisabletypes = node.GetCustomisableTypes()
        _, valuetype = node.GetCustomisedTypeValues(index)
        name, new_valuetype = customisabletypes[objtype]
        size = node.GetEntryInfos(objtype)["size"]
        default = node.GetTypeDefaultValue(objtype)
        if new_valuetype == 0:
            node.SetMappingEntry(index, entry={
                "name": f"{name}[{minval}-{maxval}]", "struct": OD.RECORD,
                "size": size, "default": default,
            })
            if valuetype == 1:
                node.SetMappingSubEntry(index, 2, values={
                    "name": "Minimum Value", "type": objtype, "access": "ro", "pdo": False,
                })
                node.AddMappingSubEntry(index, 3, values={
                    "name": "Maximum Value", "type": objtype, "access": "ro", "pdo": False,
                })
            node.SetEntry(index, 1, objtype)
            node.SetEntry(index, 2, minval)
            if valuetype == 1:
                node.AddEntry(index, 3, maxval)
            else:
                node.SetEntry(index, 3, maxval)
        elif new_valuetype == 1:
            node.SetMappingEntry(index, entry={
                "name": f"{name}{length}", "struct": OD.RECORD, "size": size, "default": default,
            })
            if valuetype == 0:
                node.SetMappingSubEntry(index, 2, values={
                    "name": "Length", "type": 0x02, "access": "ro", "pdo": False,
                })
                node.RemoveMappingEntry(index, 3)
            node.SetEntry(index, 1, objtype)
            node.SetEntry(index, 2, length)
            if valuetype == 0:
                node.RemoveEntry(index, 3)
        self.BufferCurrentNode()

    # --------------------------------------------------------------------------
    #                      Current Buffering Management Functions
    # --------------------------------------------------------------------------

    def BufferCurrentNode(self):
        self.UndoBuffers[self.nodeindex].Add(self.current.copy())

    def CurrentIsSaved(self) -> bool:
        return self.UndoBuffers[self.nodeindex].IsCurrentSaved()

    def OneFileHasChanged(self) -> bool:
        return any(
            not buffer
            for buffer in self.UndoBuffers.values()
        )

    def GetBufferNumber(self) -> int:
        return len(self.UndoBuffers)

    def GetBufferIndexes(self) -> list[int]:
        return list(self.UndoBuffers)

    def LoadCurrentPrevious(self):
        self.CurrentNode = self.UndoBuffers[self.nodeindex].Previous().copy()

    def LoadCurrentNext(self):
        self.CurrentNode = self.UndoBuffers[self.nodeindex].Next().copy()

    def AddNodeBuffer(self, currentstate: Node|None = None, issaved=False) -> int:
        nodeindex = get_new_id()
        self.CurrentNodeIndex = nodeindex
        self.UndoBuffers[nodeindex] = UndoBuffer(currentstate, issaved)
        self.FilePaths[nodeindex] = None
        self.FileNames[nodeindex] = ""
        return nodeindex

    def ChangeCurrentNode(self, index: int):
        if index in self.UndoBuffers:
            self.CurrentNodeIndex = index
            self.CurrentNode = self.UndoBuffers[index].Current().copy()

    def RemoveNodeBuffer(self, index: int):
        self.UndoBuffers.pop(index)
        self.FilePaths.pop(index)
        self.FileNames.pop(index)

    def GetCurrentFilename(self) -> str:
        return self.GetFilename(self.nodeindex)

    def GetAllFilenames(self) -> list[str]:
        return [
            self.GetFilename(idx)
            for idx in sorted(self.UndoBuffers)
        ]

    def GetFilename(self, index: int) -> str:
        if self.UndoBuffers[index].IsCurrentSaved():
            return self.FileNames[index]
        return f"~{self.FileNames[index]}~"

    def SetCurrentFilePath(self, filepath: TPath|None):
        nodeindex = self.nodeindex
        if filepath:
            path = Path(filepath)
            self.FilePaths[nodeindex] = path
            self.FileNames[nodeindex] = path.stem
        else:
            self.LastNewIndex += 1
            self.FilePaths[nodeindex] = None
            self.FileNames[nodeindex] = f"Unnamed{self.LastNewIndex}"

    def GetCurrentFilePath(self) -> Path|None:
        if len(self.FilePaths) > 0:
            return self.FilePaths[self.nodeindex]
        return None

    def GetCurrentBufferState(self) -> tuple[bool, bool]:
        first = self.UndoBuffers[self.nodeindex].IsFirst()
        last = self.UndoBuffers[self.nodeindex].IsLast()
        return not first, not last

    # --------------------------------------------------------------------------
    #                         Profiles Management Functions
    # --------------------------------------------------------------------------

    def GetCurrentCommunicationLists(self) -> tuple[dict[int, tuple[str, bool]], list[int]]:
        commlist = []
        for index in maps.MAPPING_DICTIONARY:
            if 0x1000 <= index < 0x1200:
                commlist.append(index)
        return self.GetProfileLists(maps.MAPPING_DICTIONARY, commlist)

    def GetCurrentDS302Lists(self) -> tuple[dict[int, tuple[str, bool]], list[int]]:
        return self.GetSpecificProfileLists(self.current.DS302)

    def GetCurrentProfileLists(self) -> tuple[dict[int, tuple[str, bool]], list[int]]:
        return self.GetSpecificProfileLists(self.current.Profile)

    def GetSpecificProfileLists(self, mappingdictionary: ODMapping) -> tuple[dict[int, tuple[str, bool]], list[int]]:
        validlist = []
        exclusionlist = []
        for _, menulist in self.current.SpecificMenu:
            exclusionlist.extend(menulist)
        for index in mappingdictionary:
            if index not in exclusionlist:
                validlist.append(index)
        return self.GetProfileLists(mappingdictionary, validlist)

    def GetProfileLists(self, mappingdictionary: ODMapping,
                        profilelist: list[int]) -> tuple[dict[int, tuple[str, bool]], list[int]]:
        dictionary: dict[int, tuple[str, bool]] = {}
        current: list[int] = []
        node = self.current
        for index in profilelist:
            dictionary[index] = (mappingdictionary[index]["name"], mappingdictionary[index]["need"])
            if node.IsEntry(index):
                current.append(index)
        return dictionary, current

    def GetCurrentNextMapIndex(self) -> int:
        node = self.current
        for index in range(0x2000, 0x5FFF):
            if not node.IsEntry(index):
                return index
        raise ValueError("No more free index available in the range 0x2000-0x5FFF")

    # --------------------------------------------------------------------------
    #                         Node State and Values Functions
    # --------------------------------------------------------------------------

    def GetCurrentNodeInfos(self) -> tuple[str, int, str, str]:
        node = self.current
        name = node.Name
        nodeid = node.ID
        nodetype = node.Type
        description = node.Description
        return name, nodeid, nodetype, description

    def SetCurrentNodeInfos(self, name: str, nodeid: int, nodetype: str, description: str):
        node = self.current
        node.Name = name
        node.ID = nodeid
        node.Type = nodetype
        node.Description = description
        self.BufferCurrentNode()

    def GetCurrentValidIndexes(self, minval: int, maxval: int) -> list[tuple[str, int]]:
        node = self.current
        return [
            (node.GetEntryName(index), index)
            for index in node
            if minval <= index <= maxval
        ]

    def GetCurrentValidChoices(self, minval: int, maxval: int) -> list[tuple[str, int|None],]:
        node = self.current
        validchoices: list[tuple[str, int|None]] = []
        exclusionlist = []
        for menu, indexes in node.SpecificMenu:
            exclusionlist.extend(indexes)
            good = True
            for index in indexes:
                good &= minval <= index <= maxval
            if good:
                # FIXME: What does the "None" here mean for the index?
                validchoices.append((menu, None))
        indices = [index for index in maps.MAPPING_DICTIONARY if index >= 0x1000]
        profiles = node.GetMappings(False)
        for profile in profiles:
            indices.extend(list(profile))
        for index in sorted(indices):
            if (minval <= index <= maxval and not node.IsEntry(index)
                and index not in exclusionlist
            ):
                validchoices.append((node.GetEntryName(index), index))
        return validchoices

    def GetNodeEntryValues(self, node: Node, index: int) -> tuple[list[dict], list[dict]]|None:
        if node and node.IsEntry(index):
            entry_infos = node.GetEntryInfos(index)
            # FIXME: data and editors must be described better as they are returned from this function
            data: list[dict] = []
            editors: list[dict] = []
            values = node.GetEntry(index, compute=False)
            params = node.GetParamsEntry(index)
            if isinstance(values, list):
                for i, value in enumerate(values):
                    data.append({"value": value})
                    data[-1].update(params[i])  # type: ignore[literal-required]
            else:
                data.append({"value": values})
                data[-1].update(params)  # type: ignore[arg-type]
            for i, dic in enumerate(data):
                dic["comment"] = dic["comment"] or ""
                dic["buffer_size"] = dic["buffer_size"] or ""
                infos = node.GetSubentryInfos(index, i)
                if infos["name"] == "Number of Entries":
                    dic["buffer_size"] = ""
                dic["subindex"] = f"0x{i:02X}"
                dic["name"] = infos["name"]
                dic["type"] = node.GetTypeName(infos["type"])
                if dic["type"] is None:
                    dic["type"] = "Unknown"
                    dic["buffer_size"] = ""
                dic["access"] = maps.ACCESS_TYPE[infos["access"]]
                dic["save"] = maps.OPTION_TYPE[dic["save"]]
                editor = {
                    "subindex": None, "name": None,
                    "type": None, "value": None,
                    "access": None, "save": "option",
                    "callback": "option", "comment": "string",
                    "buffer_size": "number",
                }
                if isinstance(values, list) and i == 0:
                    if 0x1600 <= index <= 0x17FF or 0x1A00 <= index <= 0x1C00:
                        editor["access"] = "raccess"
                else:
                    # FIXME: Currently node.GetSubentryInfos(index, i) incorrectly adds this
                    if infos["user_defined"]:
                        if entry_infos["struct"] & OD.IdenticalSubindexes:
                            if i == 1:
                                editor["type"] = "type"
                                editor["access"] = "access"
                        else:
                            if entry_infos["struct"] & OD.MultipleSubindexes:
                                editor["name"] = "string"
                            editor["type"] = "type"
                            editor["access"] = "access"
                    if index < 0x260:
                        if i == 1:
                            dic["value"] = node.GetTypeName(dic["value"])
                    elif 0x1600 <= index <= 0x17FF or 0x1A00 <= index <= 0x1C00:
                        editor["value"] = "map"
                        dic["value"] = node.GetMapName(dic["value"])
                    else:
                        # FIXME: dic["type"] is a string by design
                        assert isinstance(dic["type"], str)
                        if (dic["type"].startswith("VISIBLE_STRING")
                            or dic["type"].startswith("OCTET_STRING")
                        ):
                            editor["value"] = "string"
                        elif dic["type"] in ["TIME_OF_DAY", "TIME_DIFFERENCE"]:
                            editor["value"] = "time"
                        elif dic["type"] == "DOMAIN":
                            if index == 0x1F22:
                                editor["value"] = "dcf"
                            else:
                                editor["value"] = "domain"
                            # The latin-1 encoding supports using 0x80-0xFF as values
                            # FIXME: Doesn't work with unicode
                            dic["value"] = codecs.encode(dic["value"].encode('latin-1'), 'hex_codec').decode().upper()
                        elif dic["type"] == "BOOLEAN":
                            editor["value"] = "bool"
                            dic["value"] = maps.BOOL_TYPE[dic["value"]]
                            dic["buffer_size"] = ""
                        result = type_model.match(dic["type"])
                        if result:
                            if result[1] == "UNSIGNED":
                                dic["buffer_size"] = ""
                                try:
                                    fmt = "0x{:0" + str(int(result[2]) // 4) + "X}"
                                except ValueError as exc:
                                    log.debug("ValueError: '%s': %s", result[2], exc)
                                    raise  # FIXME: Originial code swallows exception
                                try:
                                    dic["value"] = fmt.format(dic["value"])
                                except ValueError as exc:
                                    log.debug("ValueError: '%s': %s", dic["value"], exc)
                                    # FIXME: dict["value"] can contain $NODEID for PDOs i.e. $NODEID+0x200
                                editor["value"] = "string"
                            if result[1] == "INTEGER":
                                editor["value"] = "number"
                                dic["buffer_size"] = ""
                            elif result[1] == "REAL":
                                editor["value"] = "float"
                                dic["buffer_size"] = ""
                            elif result[1] in ["VISIBLE_STRING", "OCTET_STRING"]:
                                editor["length"] = result[1]
                        result = range_model.match(dic["type"])
                        if result:
                            if result[1] in ["UNSIGNED", "INTEGER", "REAL"]:
                                editor["min"] = result[3]
                                editor["max"] = result[4]
                                dic["buffer_size"] = ""
                editors.append(editor)
            return data, editors
        return None

    def AddToDCF(self, node_id: int, index: int, subindex: int, size: int, value: int):
        node = self.current
        if node.IsEntry(0x1F22, node_id):
            dcf_value = node.GetEntry(0x1F22, node_id)
            # FIXME: This code assumes that the DCF value is a list
            assert isinstance(dcf_value, list)
            if dcf_value:
                nbparams = maps.be_to_le(dcf_value[:4])
            else:
                nbparams = 0
            new_value = maps.le_to_be(nbparams + 1, 4) + dcf_value[4:]
            new_value += (
                maps.le_to_be(index, 2)
                + maps.le_to_be(subindex, 1)
                + maps.le_to_be(size, 4)
                + maps.le_to_be(value, size)
            )
            node.SetEntry(0x1F22, node_id, new_value)
