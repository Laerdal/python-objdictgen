"""Template for the NodeEditor class."""
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

import wx

from objdictgen.maps import OD
from objdictgen.node import Node
from objdictgen.nodemanager import NodeManager
from objdictgen.ui import commondialogs as common
from objdictgen.ui.exception import (display_error_dialog,
                                     display_exception_dialog)


class NodeEditorTemplate(wx.Frame):
    """Template for the NodeEditor class."""

    EDITMENU_ID: int|None = None

    # Hints for typing
    HelpBar: wx.StatusBar
    EditMenu: wx.Menu
    AddMenu: wx.Menu

    def __init__(self, manager: NodeManager, mode_solo: bool):
        self.Manager: NodeManager = manager
        self.Frame = self
        self.ModeSolo = mode_solo
        self.BusId = None  # FIXME: Is this used? EditingPanel.OnSubindexGridCellLeftClick can seem to indicate it is iterable
        self.Closing = False

    def OnAddSDOServerMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.AddSDOServerToCurrent()
        self.RefreshBufferState()
        self.RefreshCurrentIndexList()

    def OnAddSDOClientMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.AddSDOClientToCurrent()
        self.RefreshBufferState()
        self.RefreshCurrentIndexList()

    def OnAddPDOTransmitMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.AddPDOTransmitToCurrent()
        self.RefreshBufferState()
        self.RefreshCurrentIndexList()

    def OnAddPDOReceiveMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.AddPDOReceiveToCurrent()
        self.RefreshBufferState()
        self.RefreshCurrentIndexList()

    def OnAddMapVariableMenu(self, event):  # pylint: disable=unused-argument
        self.AddMapVariable()

    def OnAddUserTypeMenu(self, event):  # pylint: disable=unused-argument
        self.AddUserType()

    def OnRefreshMenu(self, event):  # pylint: disable=unused-argument
        self.RefreshCurrentIndexList()

    def RefreshCurrentIndexList(self):
        pass

    def RefreshStatusBar(self):
        pass

    def SetStatusBarText(self, selection, node: Node):
        if selection:
            index, subindex = selection
            if node.IsEntry(index):
                self.Frame.HelpBar.SetStatusText(f"Index: 0x{index:04X}", 0)
                self.Frame.HelpBar.SetStatusText(f"Subindex: 0x{subindex:02X}", 1)
                entryinfos = node.GetEntryInfos(index)
                name = entryinfos["name"]
                category = "Optional"
                if entryinfos.get("need"):
                    category = "Mandatory"
                struct = "VAR"
                number = ""
                if entryinfos["struct"] & OD.IdenticalIndexes:
                    number = f" possibly defined {entryinfos['nbmax']} times"
                if entryinfos["struct"] & OD.IdenticalSubindexes:
                    struct = "ARRAY"
                elif entryinfos["struct"] & OD.MultipleSubindexes:
                    struct = "RECORD"
                text = f"{name}: {category} entry of struct {struct}{number}."
                self.Frame.HelpBar.SetStatusText(text, 2)
            else:
                for i in range(3):
                    self.Frame.HelpBar.SetStatusText("", i)
        else:
            for i in range(3):
                self.Frame.HelpBar.SetStatusText("", i)

    def RefreshProfileMenu(self):
        node = self.Manager.current_default  # Need a default to start UI
        if self.EDITMENU_ID is not None:
            profile = node.ProfileName
            edititem = self.Frame.EditMenu.FindItemById(self.EDITMENU_ID)
            if edititem:
                length = self.Frame.AddMenu.GetMenuItemCount()
                for _ in range(length - 6):
                    additem = self.Frame.AddMenu.FindItemByPosition(6)
                    self.Frame.AddMenu.Delete(additem.GetId())
                if profile not in ("None", "DS-301"):
                    edititem.SetItemLabel(f"{profile} Profile")
                    edititem.Enable(True)
                    self.Frame.AddMenu.AppendSeparator()
                    for text, _ in node.SpecificMenu:
                        new_id = wx.NewId()
                        self.Frame.AddMenu.Append(
                            helpString='', id=new_id,kind=wx.ITEM_NORMAL, item=text,
                        )
                        self.Frame.Bind(wx.EVT_MENU, self.GetProfileCallBack(text), id=new_id)
                else:
                    edititem.SetItemLabel("Other Profile")
                    edititem.Enable(False)

    # --------------------------------------------------------------------------
    #                        Buffer Functions
    # --------------------------------------------------------------------------

    def RefreshBufferState(self):
        pass

    def OnUndoMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.LoadCurrentPrevious()
        self.RefreshCurrentIndexList()
        self.RefreshBufferState()

    def OnRedoMenu(self, event):  # pylint: disable=unused-argument
        self.Manager.LoadCurrentNext()
        self.RefreshCurrentIndexList()
        self.RefreshBufferState()

    # --------------------------------------------------------------------------
    #                      Editing Profiles functions
    # --------------------------------------------------------------------------

    def OnCommunicationMenu(self, event):  # pylint: disable=unused-argument
        dictionary, current = self.Manager.GetCurrentCommunicationLists()
        self.EditProfile("Edit DS-301 Profile", dictionary, current)

    def OnOtherCommunicationMenu(self, event):  # pylint: disable=unused-argument
        dictionary, current = self.Manager.GetCurrentDS302Lists()
        self.EditProfile("Edit DS-302 Profile", dictionary, current)

    def OnEditProfileMenu(self, event):  # pylint: disable=unused-argument
        title = f"Edit {self.Manager.current.ProfileName} Profile"
        dictionary, current = self.Manager.GetCurrentProfileLists()
        self.EditProfile(title, dictionary, current)

    def EditProfile(self, title: str, dictionary: dict[int, tuple[str, bool]], current: list[int]):
        with common.CommunicationDialog(self.Frame) as dialog:
            dialog.SetTitle(title)
            dialog.SetIndexDictionary(dictionary)
            dialog.SetCurrentList(current)
            dialog.RefreshLists()
            if dialog.ShowModal() == wx.ID_OK:
                new_profile = dialog.GetCurrentList()
                addinglist = []
                removinglist = []
                for index in new_profile:
                    if index not in current:
                        addinglist.append(index)
                for index in current:
                    if index not in new_profile:
                        removinglist.append(index)
                self.Manager.ManageEntriesOfCurrent(addinglist, removinglist)
                self.Manager.BufferCurrentNode()
                self.RefreshBufferState()

    def GetProfileCallBack(self, text):
        def profile_cb(event):  # pylint: disable=unused-argument
            self.Manager.AddSpecificEntryToCurrent(text)
            self.RefreshBufferState()
            self.RefreshCurrentIndexList()
        return profile_cb

    # --------------------------------------------------------------------------
    #                     Edit Node informations function
    # --------------------------------------------------------------------------

    def OnNodeInfosMenu(self, event):  # pylint: disable=unused-argument
        dialog = common.NodeInfosDialog(self.Frame)
        name, nodeid, nodetype, description = self.Manager.GetCurrentNodeInfos()
        defaultstringsize = self.Manager.current.DefaultStringSize
        dialog.SetValues(name, nodeid, nodetype, description, defaultstringsize)
        if dialog.ShowModal() == wx.ID_OK:
            name, nodeid, nodetype, description, defaultstringsize = dialog.GetValues()
            self.Manager.SetCurrentNodeInfos(name, nodeid, nodetype, description)
            self.Manager.current.DefaultStringSize = defaultstringsize
            self.RefreshBufferState()
            self.RefreshCurrentIndexList()
            self.RefreshProfileMenu()

    # --------------------------------------------------------------------------
    #                       Add User Types and Variables
    # --------------------------------------------------------------------------

    def AddMapVariable(self):
        index = self.Manager.GetCurrentNextMapIndex()
        if index:
            with common.MapVariableDialog(self.Frame) as dialog:
                dialog.SetIndex(index)
                if dialog.ShowModal() == wx.ID_OK:
                    try:
                        self.Manager.AddMapVariableToCurrent(*dialog.GetValues())
                        self.RefreshBufferState()
                        self.RefreshCurrentIndexList()
                    except Exception:  # pylint: disable=broad-except
                        display_exception_dialog(self.Frame)
        else:
            display_error_dialog(self.Frame, "No map variable index left!")

    def AddUserType(self):
        with common.UserTypeDialog(self) as dialog:
            dialog.SetTypeList(self.Manager.current.GetCustomisableTypes())
            if dialog.ShowModal() == wx.ID_OK:
                try:
                    self.Manager.AddUserTypeToCurrent(*dialog.GetValues())
                    self.RefreshBufferState()
                    self.RefreshCurrentIndexList()
                except Exception:  # pylint: disable=broad-except
                    display_exception_dialog(self.Frame)
