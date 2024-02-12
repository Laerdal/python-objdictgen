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

from objdictgen.ui import commondialogs as cdia
from objdictgen.ui import nodeeditortemplate as net
from objdictgen.ui import subindextable as sit
from objdictgen.ui.exception import display_exception_dialog

[
    ID_NETWORKEDITNETWORKNODES,
] = [wx.NewId() for _init_ctrls in range(1)]


class NetworkEditorTemplate(net.NodeEditorTemplate):
    # pylint: disable=attribute-defined-outside-init

    def _init_ctrls(self, prnt):
        self.NetworkNodes = wx.Notebook(id=ID_NETWORKEDITNETWORKNODES,
              name='NetworkNodes', parent=prnt, pos=wx.Point(0, 0),
              size=wx.Size(0, 0), style=wx.NB_LEFT)
        self.NetworkNodes.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED,
              self.OnNodeSelectedChanged, id=ID_NETWORKEDITNETWORKNODES)

    def __init__(self, manager, frame, mode_solo):
        self.NodeList = manager
        net.NodeEditorTemplate.__init__(self, self.NodeList.Manager, frame, mode_solo)

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
            new_editingpanel = sit.EditingPanel(self.NetworkNodes, self, self.Manager)
            new_editingpanel.SetIndex(self.Manager.GetCurrentNodeID())
            self.NetworkNodes.AddPage(new_editingpanel, "")
            for idx in self.NodeList.GetSlaveIDs():
                new_editingpanel = sit.EditingPanel(self.NetworkNodes, self, self.NodeList, False)
                new_editingpanel.SetIndex(idx)
                self.NetworkNodes.AddPage(new_editingpanel, "")

    def OnNodeSelectedChanged(self, event):
        if not self.Closing:
            selected = event.GetSelection()
            # At init selected = -1
            if selected >= 0:
                window = self.NetworkNodes.GetPage(selected)
                self.NodeList.CurrentSelected = window.GetIndex()
            wx.CallAfter(self.RefreshMainMenu)  # FIXME: Missing symbol. From where?
            wx.CallAfter(self.RefreshStatusBar)
        event.Skip()

# ------------------------------------------------------------------------------
#                              Buffer Functions
# ------------------------------------------------------------------------------

    def RefreshBufferState(self):
        if self.NodeList is not None:
            nodeid = self.Manager.GetCurrentNodeID()
            if nodeid is not None:
                nodename = "0x%2.2X %s" % (nodeid, self.Manager.GetCurrentNodeName())
            else:
                nodename = self.Manager.GetCurrentNodeName()
            self.NetworkNodes.SetPageText(0, nodename)
            for idx, name in enumerate(self.NodeList.GetSlaveNames()):
                self.NetworkNodes.SetPageText(idx + 1, name)

# ------------------------------------------------------------------------------
#                             Slave Nodes Management
# ------------------------------------------------------------------------------

    def OnAddSlaveMenu(self, event):  # pylint: disable=unused-argument
        dialog = cdia.AddSlaveDialog(self.Frame)
        dialog.SetNodeList(self.NodeList)
        if dialog.ShowModal() == wx.ID_OK:
            values = dialog.GetValues()
            try:
                self.NodeList.AddSlaveNode(values["slaveName"], values["slaveNodeID"], values["edsFile"])
                new_editingpanel = sit.EditingPanel(self.NetworkNodes, self, self.NodeList, False)
                new_editingpanel.SetIndex(values["slaveNodeID"])
                idx = self.NodeList.GetOrderNumber(values["slaveNodeID"])
                self.NetworkNodes.InsertPage(idx, new_editingpanel, "")
                self.NodeList.CurrentSelected = idx
                self.NetworkNodes.SetSelection(idx)
                self.RefreshBufferState()
            except Exception as exc:  # pylint: disable=broad-except
                display_exception_dialog(self.Frame)
        dialog.Destroy()

    def OnRemoveSlaveMenu(self, event):  # pylint: disable=unused-argument
        slavenames = self.NodeList.GetSlaveNames()
        slaveids = self.NodeList.GetSlaveIDs()
        dialog = wx.SingleChoiceDialog(self.Frame, "Choose a slave to remove", "Remove slave", slavenames)
        if dialog.ShowModal() == wx.ID_OK:
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
            except Exception as exc:  # pylint: disable=broad-except
                display_exception_dialog(self.Frame)
        dialog.Destroy()

    def OpenMasterDCFDialog(self, node_id):
        self.NetworkNodes.SetSelection(0)
        self.NetworkNodes.GetPage(0).OpenDCFDialog(node_id)
