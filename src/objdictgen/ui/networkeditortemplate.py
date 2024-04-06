"""Network Editor Template."""
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

from typing import cast

import wx

from objdictgen.nodelist import NodeList
from objdictgen.ui.commondialogs import AddSlaveDialog
from objdictgen.ui.exception import display_exception_dialog
from objdictgen.ui.nodeeditortemplate import NodeEditorTemplate
from objdictgen.ui.subindextable import EditingPanel, EditingPanelNotebook

[
    ID_NETWORKEDITNETWORKNODES,
] = [wx.NewId() for _ in range(1)]


class NetworkEditorTemplate(NodeEditorTemplate):
    """Network Editor Template."""
    # pylint: disable=attribute-defined-outside-init

    def _init_ctrls(self, parent):
        # FIXME: This cast is to define right type hints of attributes for this specific instance
        self.NetworkNodes = cast(EditingPanelNotebook, wx.Notebook(
            id=ID_NETWORKEDITNETWORKNODES,
            name='NetworkNodes', parent=parent, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.NB_LEFT,
        ))
        self.NetworkNodes.Bind(
            wx.EVT_NOTEBOOK_PAGE_CHANGED,
            self.OnNodeSelectedChanged, id=ID_NETWORKEDITNETWORKNODES
        )

    def __init__(self, nodelist: NodeList, mode_solo: bool):
        self.NodeList = nodelist
        NodeEditorTemplate.__init__(self, self.NodeList.Manager, mode_solo)

    def GetCurrentNodeId(self):
        selected = self.NetworkNodes.GetSelection()
        # At init selected = -1
        if selected > 0:
            window = self.NetworkNodes.GetPage(selected)
            return window.GetIndex()
        return 0

    def RefreshCurrentIndexList(self):
        selected = self.NetworkNodes.GetSelection()
        if selected == 0:
            window = self.NetworkNodes.GetPage(selected)
            window.RefreshIndexList()

    def RefreshNetworkNodes(self):
        if self.NetworkNodes.GetPageCount() > 0:
            self.NetworkNodes.DeleteAllPages()
        if self.NodeList:
            new_editingpanel = EditingPanel(self.NetworkNodes, self, self.Manager)
            new_editingpanel.SetIndex(self.Manager.current.ID)
            self.NetworkNodes.AddPage(new_editingpanel, "")
            for idx in self.NodeList.GetSlaveIDs():
                # FIXME: Why is NodeList used where NodeManager is expected?
                new_editingpanel = EditingPanel(self.NetworkNodes, self, self.NodeList, False)
                new_editingpanel.SetIndex(idx)
                self.NetworkNodes.AddPage(new_editingpanel, "")

    def OnNodeSelectedChanged(self, event):
        if not self.Closing:
            selected = event.GetSelection()
            # At init selected = -1
            if selected >= 0:
                window = self.NetworkNodes.GetPage(selected)
                self.NodeList.CurrentSelected = window.GetIndex()
            raise NotImplementedError("Unimplemented symbol.")
            # FIXME: Missing symbol in the original code. Delete?
            # wx.CallAfter(self.RefreshMainMenu)
            # wx.CallAfter(self.RefreshStatusBar)
        event.Skip()

    # --------------------------------------------------------------------------
    #                          Buffer Functions
    # --------------------------------------------------------------------------

    def RefreshBufferState(self):
        if self.NodeList is not None:
            nodeid = self.Manager.current.ID
            if nodeid is not None:
                nodename = f"0x{nodeid:02X} {self.Manager.current.Name}"
            else:
                nodename = self.Manager.current.Name
            self.NetworkNodes.SetPageText(0, nodename)
            for idx, name in enumerate(self.NodeList.GetSlaveNames()):
                self.NetworkNodes.SetPageText(idx + 1, name)

    # --------------------------------------------------------------------------
    #                         Slave Nodes Management
    # --------------------------------------------------------------------------

    def OnAddSlaveMenu(self, event):  # pylint: disable=unused-argument
        with AddSlaveDialog(self.Frame) as dialog:
            dialog.SetNodeList(self.NodeList)
            if dialog.ShowModal() != wx.ID_OK:
                return
            values = dialog.GetValues()

        try:
            self.NodeList.AddSlaveNode(
                values["slaveName"], values["slaveNodeID"], values["edsFile"],
            )
            # FIXME: Why is NodeList used where NodeManager is expected?
            new_editingpanel = EditingPanel(self.NetworkNodes, self, self.NodeList, False)
            new_editingpanel.SetIndex(values["slaveNodeID"])
            idx = self.NodeList.GetOrderNumber(values["slaveNodeID"])
            self.NetworkNodes.InsertPage(idx, new_editingpanel, "")
            self.NodeList.CurrentSelected = idx
            self.NetworkNodes.SetSelection(idx)
            self.RefreshBufferState()
        except Exception:  # pylint: disable=broad-except
            display_exception_dialog(self.Frame)

    def OnRemoveSlaveMenu(self, event):  # pylint: disable=unused-argument
        slavenames = self.NodeList.GetSlaveNames()
        slaveids = self.NodeList.GetSlaveIDs()
        with wx.SingleChoiceDialog(
            self.Frame, "Choose a slave to remove", "Remove slave", slavenames,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            choice = dialog.GetSelection()

        try:
            self.NodeList.RemoveSlaveNode(slaveids[choice])
            slaveids.pop(choice)
            current = self.NetworkNodes.GetSelection()
            self.NetworkNodes.DeletePage(choice + 1)
            if self.NetworkNodes.GetPageCount() > 0:
                new_selection = min(current, self.NetworkNodes.GetPageCount() - 1)
                self.NetworkNodes.SetSelection(new_selection)
                if new_selection > 0:
                    self.NodeList.CurrentSelected = slaveids[new_selection - 1]
            self.RefreshBufferState()
        except Exception:  # pylint: disable=broad-except
            display_exception_dialog(self.Frame)

    def OpenMasterDCFDialog(self, node_id: int):
        self.NetworkNodes.SetSelection(0)
        self.NetworkNodes.GetPage(0).OpenDCFDialog(node_id)
