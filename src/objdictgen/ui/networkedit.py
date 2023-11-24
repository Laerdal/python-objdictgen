# -*- coding: utf-8 -*-
#
#    This file is based on objdictgen from CanFestival
#
#    Copyright (C) 2022-2023  Svein Seldal, Laerdal Medical AS
#    Copyright (C): Edouard TISSERANT, Francis DUPIN and Laurent BESSARD
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
#    USA

from __future__ import print_function
from __future__ import absolute_import
from builtins import range

import os
import sys
import getopt
import logging

import wx

import objdictgen
from objdictgen.nodelist import NodeList
from objdictgen.nodemanager import NodeManager
from objdictgen.ui.exception import AddExceptHook
from objdictgen.ui.networkeditortemplate import NetworkEditorTemplate

log = logging.getLogger('objdictgen')


def usage():
    print("\nUsage of networkedit.py :")
    print("\n   %s [Projectpath]\n" % sys.argv[0])


[
    ID_NETWORKEDIT, ID_NETWORKEDITNETWORKNODES,
    ID_NETWORKEDITHELPBAR,
] = [wx.NewId() for _init_ctrls in range(3)]

[
    ID_NETWORKEDITNETWORKMENUBUILDMASTER,
] = [wx.NewId() for _init_coll_AddMenu_Items in range(1)]

[
    ID_NETWORKEDITEDITMENUNODEINFOS, ID_NETWORKEDITEDITMENUDS301PROFILE,
    ID_NETWORKEDITEDITMENUDS302PROFILE, ID_NETWORKEDITEDITMENUOTHERPROFILE,
] = [wx.NewId() for _init_coll_EditMenu_Items in range(4)]

[
    ID_NETWORKEDITADDMENUSDOSERVER, ID_NETWORKEDITADDMENUSDOCLIENT,
    ID_NETWORKEDITADDMENUPDOTRANSMIT, ID_NETWORKEDITADDMENUPDORECEIVE,
    ID_NETWORKEDITADDMENUMAPVARIABLE, ID_NETWORKEDITADDMENUUSERTYPE,
] = [wx.NewId() for _init_coll_AddMenu_Items in range(6)]


class NetworkEdit(wx.Frame, NetworkEditorTemplate):
    # pylint: disable=attribute-defined-outside-init

    EDITMENU_ID = ID_NETWORKEDITEDITMENUOTHERPROFILE

    def _init_coll_MenuBar_Menus(self, parent):
        if self.ModeSolo:
            parent.Append(menu=self.FileMenu, title='File')
        parent.Append(menu=self.NetworkMenu, title='Network')
        parent.Append(menu=self.EditMenu, title='Edit')
        parent.Append(menu=self.AddMenu, title='Add')

    def _init_coll_FileMenu_Items(self, parent):
        parent.Append(helpString='', id=wx.ID_NEW,
              kind=wx.ITEM_NORMAL, item='New\tCTRL+N')
        parent.Append(helpString='', id=wx.ID_OPEN,
              kind=wx.ITEM_NORMAL, item='Open\tCTRL+O')
        parent.Append(helpString='', id=wx.ID_CLOSE,
              kind=wx.ITEM_NORMAL, item='Close\tCTRL+W')
        parent.AppendSeparator()
        parent.Append(helpString='', id=wx.ID_SAVE,
              kind=wx.ITEM_NORMAL, item='Save\tCTRL+S')
        parent.AppendSeparator()
        parent.Append(helpString='', id=wx.ID_EXIT,
              kind=wx.ITEM_NORMAL, item='Exit')
        self.Bind(wx.EVT_MENU, self.OnNewProjectMenu, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self.OnOpenProjectMenu, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.OnCloseProjectMenu, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_MENU, self.OnSaveProjectMenu, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.OnQuitMenu, id=wx.ID_EXIT)

    def _init_coll_NetworkMenu_Items(self, parent):
        parent.Append(helpString='', id=wx.ID_ADD,
              kind=wx.ITEM_NORMAL, item='Add Slave Node')
        parent.Append(helpString='', id=wx.ID_DELETE,
              kind=wx.ITEM_NORMAL, item='Remove Slave Node')
        parent.AppendSeparator()
        parent.Append(helpString='', id=ID_NETWORKEDITNETWORKMENUBUILDMASTER,
              kind=wx.ITEM_NORMAL, item='Build Master Dictionary')
        self.Bind(wx.EVT_MENU, self.OnAddSlaveMenu, id=wx.ID_ADD)
        self.Bind(wx.EVT_MENU, self.OnRemoveSlaveMenu, id=wx.ID_DELETE)
        # self.Bind(wx.EVT_MENU, self.OnBuildMasterMenu,
        #       id=ID_NETWORKEDITNETWORKMENUBUILDMASTER)

    def _init_coll_EditMenu_Items(self, parent):
        parent.Append(helpString='', id=wx.ID_REFRESH,
              kind=wx.ITEM_NORMAL, item='Refresh\tCTRL+R')
        parent.AppendSeparator()
        parent.Append(helpString='', id=wx.ID_UNDO,
              kind=wx.ITEM_NORMAL, item='Undo\tCTRL+Z')
        parent.Append(helpString='', id=wx.ID_REDO,
              kind=wx.ITEM_NORMAL, item='Redo\tCTRL+Y')
        parent.AppendSeparator()
        parent.Append(helpString='', id=ID_NETWORKEDITEDITMENUNODEINFOS,
              kind=wx.ITEM_NORMAL, item='Node infos')
        parent.Append(helpString='', id=ID_NETWORKEDITEDITMENUDS301PROFILE,
              kind=wx.ITEM_NORMAL, item='DS-301 Profile')
        parent.Append(helpString='', id=ID_NETWORKEDITEDITMENUDS302PROFILE,
              kind=wx.ITEM_NORMAL, item='DS-302 Profile')
        parent.Append(helpString='', id=ID_NETWORKEDITEDITMENUOTHERPROFILE,
              kind=wx.ITEM_NORMAL, item='Other Profile')
        self.Bind(wx.EVT_MENU, self.OnRefreshMenu, id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self.OnUndoMenu, id=wx.ID_UNDO)
        self.Bind(wx.EVT_MENU, self.OnRedoMenu, id=wx.ID_REDO)
        self.Bind(wx.EVT_MENU, self.OnNodeInfosMenu,
              id=ID_NETWORKEDITEDITMENUNODEINFOS)
        self.Bind(wx.EVT_MENU, self.OnCommunicationMenu,
              id=ID_NETWORKEDITEDITMENUDS301PROFILE)
        self.Bind(wx.EVT_MENU, self.OnOtherCommunicationMenu,
              id=ID_NETWORKEDITEDITMENUDS302PROFILE)
        self.Bind(wx.EVT_MENU, self.OnEditProfileMenu,
              id=ID_NETWORKEDITEDITMENUOTHERPROFILE)

    def _init_coll_AddMenu_Items(self, parent):
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUSDOSERVER,
              kind=wx.ITEM_NORMAL, item='SDO Server')
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUSDOCLIENT,
              kind=wx.ITEM_NORMAL, item='SDO Client')
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUPDOTRANSMIT,
              kind=wx.ITEM_NORMAL, item='PDO Transmit')
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUPDORECEIVE,
              kind=wx.ITEM_NORMAL, item='PDO Receive')
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUMAPVARIABLE,
              kind=wx.ITEM_NORMAL, item='Map Variable')
        parent.Append(helpString='', id=ID_NETWORKEDITADDMENUUSERTYPE,
              kind=wx.ITEM_NORMAL, item='User Type')
        self.Bind(wx.EVT_MENU, self.OnAddSDOServerMenu,
              id=ID_NETWORKEDITADDMENUSDOSERVER)
        self.Bind(wx.EVT_MENU, self.OnAddSDOClientMenu,
              id=ID_NETWORKEDITADDMENUSDOCLIENT)
        self.Bind(wx.EVT_MENU, self.OnAddPDOTransmitMenu,
              id=ID_NETWORKEDITADDMENUPDOTRANSMIT)
        self.Bind(wx.EVT_MENU, self.OnAddPDOReceiveMenu,
              id=ID_NETWORKEDITADDMENUPDORECEIVE)
        self.Bind(wx.EVT_MENU, self.OnAddMapVariableMenu,
              id=ID_NETWORKEDITADDMENUMAPVARIABLE)
        self.Bind(wx.EVT_MENU, self.OnAddUserTypeMenu,
              id=ID_NETWORKEDITADDMENUUSERTYPE)

    def _init_coll_HelpBar_Fields(self, parent):
        parent.SetFieldsCount(3)

        parent.SetStatusText(i=0, text='')
        parent.SetStatusText(i=1, text='')
        parent.SetStatusText(i=2, text='')

        parent.SetStatusWidths([100, 110, -1])

    def _init_utils(self):
        self.MenuBar = wx.MenuBar()
        self.MenuBar.SetEvtHandlerEnabled(True)

        if self.ModeSolo:
            self.FileMenu = wx.Menu(title='')
        self.NetworkMenu = wx.Menu(title='')
        self.EditMenu = wx.Menu(title='')
        self.AddMenu = wx.Menu(title='')
        # FIXME: Unused. Delete this?
        # self.HelpMenu = wx.Menu(title='')

        self._init_coll_MenuBar_Menus(self.MenuBar)
        if self.ModeSolo:
            self._init_coll_FileMenu_Items(self.FileMenu)
        self._init_coll_NetworkMenu_Items(self.NetworkMenu)
        self._init_coll_EditMenu_Items(self.EditMenu)
        self._init_coll_AddMenu_Items(self.AddMenu)

    def _init_ctrls(self, prnt):
        wx.Frame.__init__(self, id=ID_NETWORKEDIT, name='networkedit',
              parent=prnt, pos=wx.Point(149, 178), size=wx.Size(1000, 700),
              style=wx.DEFAULT_FRAME_STYLE, title='Networkedit')
        self._init_utils()
        self.SetClientSize(wx.Size(1000, 700))
        self.SetMenuBar(self.MenuBar)
        self.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        if not self.ModeSolo:
            self.Bind(wx.EVT_MENU, self.OnSaveProjectMenu, id=wx.ID_SAVE)
            accel = wx.AcceleratorTable([wx.AcceleratorEntry(wx.ACCEL_CTRL, 83, wx.ID_SAVE)])
            self.SetAcceleratorTable(accel)

        NetworkEditorTemplate._init_ctrls(self, self)

        self.HelpBar = wx.StatusBar(id=ID_NETWORKEDITHELPBAR, name='HelpBar',
              parent=self, style=wx.STB_SIZEGRIP)
        self._init_coll_HelpBar_Fields(self.HelpBar)
        self.SetStatusBar(self.HelpBar)

    def __init__(self, parent, nodelist=None, projectOpen=None):
        if nodelist is None:
            NetworkEditorTemplate.__init__(self, NodeList(NodeManager()), self, True)
        else:
            NetworkEditorTemplate.__init__(self, nodelist, self, False)
        self._init_ctrls(parent)
        # FIXME: Unused. Delete this?
        # self.HtmlFrameOpened = []

        icon = wx.Icon(os.path.join(objdictgen.SCRIPT_DIRECTORY, "ui", "networkedit.ico"), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        if self.ModeSolo:
            if projectOpen:
                try:
                    self.NodeList.LoadProject(projectOpen)
                    self.NodeList.CurrentSelected = 0
                    self.RefreshNetworkNodes()
                    self.RefreshProfileMenu()
                except Exception as exc:
                    log.debug("Exception: %s" % exc)
                    raise  # FIXME: Temporary. Orginal code swallows exception
            else:
                self.NodeList = None
        else:
            self.NodeList.CurrentSelected = 0
            self.RefreshNetworkNodes()
            self.RefreshProfileMenu()
        self.NetworkNodes.SetFocus()

        self.RefreshBufferState()
        self.RefreshTitle()
        self.RefreshMainMenu()

    def OnCloseFrame(self, event):
        self.Closing = True
        if not self.ModeSolo and getattr(self, "_onclose", None) is not None:
            self._onclose()
        event.Skip()

    def OnQuitMenu(self, event):  # pylint: disable=unused-argument
        self.Close()

# ------------------------------------------------------------------------------
#                         Load and Save Funtions
# ------------------------------------------------------------------------------

    def OnNewProjectMenu(self, event):  # pylint: disable=unused-argument
        if self.NodeList:
            defaultpath = os.path.dirname(self.NodeList.Root)
        else:
            defaultpath = os.getcwd()
        dialog = wx.DirDialog(self, "Choose a project", defaultpath, wx.DD_NEW_DIR_BUTTON)
        if dialog.ShowModal() == wx.ID_OK:
            projectpath = dialog.GetPath()
            if os.path.isdir(projectpath) and len(os.listdir(projectpath)) == 0:
                manager = NodeManager()
                nodelist = NodeList(manager)
                try:
                    nodelist.LoadProject(projectpath)

                    self.Manager = manager
                    self.NodeList = nodelist
                    self.NodeList.CurrentSelected = 0

                    self.RefreshNetworkNodes()
                    self.RefreshBufferState()
                    self.RefreshTitle()
                    self.RefreshProfileMenu()
                    self.RefreshMainMenu()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "ERROR", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()

    def OnOpenProjectMenu(self, event):  # pylint: disable=unused-argument
        if self.NodeList:
            defaultpath = os.path.dirname(self.NodeList.Root)
        else:
            defaultpath = os.getcwd()
        dialog = wx.DirDialog(self, "Choose a project", defaultpath, 0)
        if dialog.ShowModal() == wx.ID_OK:
            projectpath = dialog.GetPath()
            if os.path.isdir(projectpath):
                manager = NodeManager()
                nodelist = NodeList(manager)
                try:
                    nodelist.LoadProject(projectpath)

                    self.Manager = manager
                    self.NodeList = nodelist
                    self.NodeList.CurrentSelected = 0

                    self.RefreshNetworkNodes()
                    self.RefreshBufferState()
                    self.RefreshTitle()
                    self.RefreshProfileMenu()
                    self.RefreshMainMenu()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()
        dialog.Destroy()

    def OnSaveProjectMenu(self, event):  # pylint: disable=unused-argument
        if not self.ModeSolo and getattr(self, "_onsave", None) is not None:
            self._onsave()
        else:
            try:
                self.NodeList.SaveProject()
            except Exception as exc:  # pylint: disable=broad-except
                message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()

    def OnCloseProjectMenu(self, event):  # pylint: disable=unused-argument
        if self.NodeList:
            if self.NodeList.HasChanged():
                dialog = wx.MessageDialog(self, "There are changes, do you want to save?", "Close Project", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
                answer = dialog.ShowModal()
                dialog.Destroy()
                if answer == wx.ID_YES:
                    try:
                        self.NodeList.SaveProject()
                    except Exception as exc:  # pylint: disable=broad-except
                        message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                        message.ShowModal()
                        message.Destroy()
                elif answer == wx.ID_NO:
                    self.NodeList.Changed = False
            if not self.NodeList.HasChanged():
                self.Manager = None
                self.NodeList = None
                self.RefreshNetworkNodes()
                self.RefreshTitle()
                self.RefreshMainMenu()

# ------------------------------------------------------------------------------
#                             Refresh Functions
# ------------------------------------------------------------------------------

    def RefreshTitle(self):
        if self.NodeList is not None:
            self.SetTitle("Networkedit - %s" % self.NodeList.NetworkName)
        else:
            self.SetTitle("Networkedit")

    def RefreshStatusBar(self):
        selected = self.NetworkNodes.GetSelection()
        if self.HelpBar and selected >= 0:
            window = self.NetworkNodes.GetPage(selected)
            self.SetStatusBarText(window.GetSelection(), self.NodeList)

    def RefreshMainMenu(self):
        self.NetworkMenu.Enable(ID_NETWORKEDITNETWORKMENUBUILDMASTER, False)
        if self.NodeList is None:
            if self.ModeSolo:
                self.MenuBar.EnableTop(1, False)
                self.MenuBar.EnableTop(2, False)
                self.MenuBar.EnableTop(3, False)
                if self.FileMenu:
                    self.FileMenu.Enable(wx.ID_CLOSE, False)
                    self.FileMenu.Enable(wx.ID_SAVE, False)
            else:
                self.MenuBar.EnableTop(0, False)
                self.MenuBar.EnableTop(1, False)
                self.MenuBar.EnableTop(2, False)
        else:
            if self.ModeSolo:
                self.MenuBar.EnableTop(1, True)
                if self.FileMenu:
                    self.FileMenu.Enable(wx.ID_CLOSE, True)
                    self.FileMenu.Enable(wx.ID_SAVE, True)
                if self.NetworkNodes.GetSelection() == 0:
                    self.MenuBar.EnableTop(2, True)
                    self.MenuBar.EnableTop(3, True)
                else:
                    self.MenuBar.EnableTop(2, False)
                    self.MenuBar.EnableTop(3, False)
            else:
                self.MenuBar.EnableTop(0, True)
                if self.NetworkNodes.GetSelection() == 0:
                    self.MenuBar.EnableTop(1, True)
                    self.MenuBar.EnableTop(2, True)
                else:
                    self.MenuBar.EnableTop(1, False)
                    self.MenuBar.EnableTop(2, False)

# ------------------------------------------------------------------------------
#                              Buffer Functions
# ------------------------------------------------------------------------------

    def RefreshBufferState(self):
        NetworkEditorTemplate.RefreshBufferState(self)
        if self.NodeList is not None:
            self.RefreshTitle()


def uimain(project):
    app = wx.PySimpleApp()

    wx.InitAllImageHandlers()

    # Install a exception handle for bug reports
    AddExceptHook(os.getcwd(), objdictgen.ODG_VERSION)

    frame = NetworkEdit(None, projectOpen=project)

    frame.Show()
    app.MainLoop()


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)

    for opt, _ in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()

    if len(args) == 0:
        project = None
    elif len(args) == 1:
        project = args[0]
    else:
        usage()
        sys.exit(2)

    uimain(project)
