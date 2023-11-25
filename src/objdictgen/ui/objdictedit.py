# -*- coding: utf-8 -*-
#
#    This file is based on objdictgen from CanFestival
#
#    Copyright (C) 2022-2023  Svein Seldaleldal, Laerdal Medical AS
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

from objdictgen.ui.exception import AddExceptHook
from objdictgen.ui import nodeeditortemplate as net
from objdictgen.ui import subindextable as sit
from objdictgen.ui import commondialogs as cdia
import objdictgen

if sys.version_info[0] >= 3:
    unicode = str  # pylint: disable=invalid-name

log = logging.getLogger('objdictgen')


def usage():
    print("\nUsage of objdictedit :")
    print("\n   %s [Filepath, ...]\n" % sys.argv[0])


[
    ID_OBJDICTEDIT, ID_OBJDICTEDITFILEOPENED,
    ID_OBJDICTEDITHELPBAR,
] = [wx.NewId() for _init_ctrls in range(3)]

[
    ID_OBJDICTEDITFILEMENUIMPORTEDS, ID_OBJDICTEDITFILEMENUEXPORTEDS,
    ID_OBJDICTEDITFILEMENUEXPORTC,
] = [wx.NewId() for _init_coll_FileMenu_Items in range(3)]

[
    ID_OBJDICTEDITEDITMENUNODEINFOS, ID_OBJDICTEDITEDITMENUDS301PROFILE,
    ID_OBJDICTEDITEDITMENUDS302PROFILE, ID_OBJDICTEDITEDITMENUOTHERPROFILE,
] = [wx.NewId() for _init_coll_EditMenu_Items in range(4)]

[
    ID_OBJDICTEDITADDMENUSDOSERVER, ID_OBJDICTEDITADDMENUSDOCLIENT,
    ID_OBJDICTEDITADDMENUPDOTRANSMIT, ID_OBJDICTEDITADDMENUPDORECEIVE,
    ID_OBJDICTEDITADDMENUMAPVARIABLE, ID_OBJDICTEDITADDMENUUSERTYPE,
] = [wx.NewId() for _init_coll_AddMenu_Items in range(6)]


class ObjdictEdit(wx.Frame, net.NodeEditorTemplate):
    # pylint: disable=attribute-defined-outside-init

    EDITMENU_ID = ID_OBJDICTEDITEDITMENUOTHERPROFILE

    def _init_coll_MenuBar_Menus(self, parent):
        if self.ModeSolo:
            parent.Append(menu=self.FileMenu, title='File')
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
        parent.Append(helpString='', id=wx.ID_SAVEAS,
              kind=wx.ITEM_NORMAL, item='Save As...\tALT+S')
        parent.AppendSeparator()
        parent.Append(helpString='', id=ID_OBJDICTEDITFILEMENUIMPORTEDS,
              kind=wx.ITEM_NORMAL, item='Import EDS file')
        parent.Append(helpString='', id=ID_OBJDICTEDITFILEMENUEXPORTEDS,
              kind=wx.ITEM_NORMAL, item='Export to EDS file')
        parent.Append(helpString='', id=ID_OBJDICTEDITFILEMENUEXPORTC,
              kind=wx.ITEM_NORMAL, item='Build Dictionary\tCTRL+B')
        parent.AppendSeparator()
        parent.Append(helpString='', id=wx.ID_EXIT,
              kind=wx.ITEM_NORMAL, item='Exit')
        self.Bind(wx.EVT_MENU, self.OnNewMenu, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self.OnOpenMenu, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.OnCloseMenu, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_MENU, self.OnSaveMenu, id=wx.ID_SAVE)
        self.Bind(wx.EVT_MENU, self.OnSaveAsMenu, id=wx.ID_SAVEAS)
        self.Bind(wx.EVT_MENU, self.OnImportEDSMenu,
              id=ID_OBJDICTEDITFILEMENUIMPORTEDS)
        self.Bind(wx.EVT_MENU, self.OnExportEDSMenu,
              id=ID_OBJDICTEDITFILEMENUEXPORTEDS)
        self.Bind(wx.EVT_MENU, self.OnExportCMenu,
              id=ID_OBJDICTEDITFILEMENUEXPORTC)
        self.Bind(wx.EVT_MENU, self.OnQuitMenu, id=wx.ID_EXIT)

    def _init_coll_EditMenu_Items(self, parent):
        parent.Append(helpString='', id=wx.ID_REFRESH,
              kind=wx.ITEM_NORMAL, item='Refresh\tCTRL+R')
        parent.AppendSeparator()
        parent.Append(helpString='', id=wx.ID_UNDO,
              kind=wx.ITEM_NORMAL, item='Undo\tCTRL+Z')
        parent.Append(helpString='', id=wx.ID_REDO,
              kind=wx.ITEM_NORMAL, item='Redo\tCTRL+Y')
        parent.AppendSeparator()
        parent.Append(helpString='', id=ID_OBJDICTEDITEDITMENUNODEINFOS,
              kind=wx.ITEM_NORMAL, item='Node infos')
        parent.Append(helpString='', id=ID_OBJDICTEDITEDITMENUDS301PROFILE,
              kind=wx.ITEM_NORMAL, item='DS-301 Profile')
        parent.Append(helpString='', id=ID_OBJDICTEDITEDITMENUDS302PROFILE,
              kind=wx.ITEM_NORMAL, item='DS-302 Profile')
        parent.Append(helpString='', id=ID_OBJDICTEDITEDITMENUOTHERPROFILE,
              kind=wx.ITEM_NORMAL, item='Other Profile')
        self.Bind(wx.EVT_MENU, self.OnRefreshMenu, id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self.OnUndoMenu, id=wx.ID_UNDO)
        self.Bind(wx.EVT_MENU, self.OnRedoMenu, id=wx.ID_REDO)
        self.Bind(wx.EVT_MENU, self.OnNodeInfosMenu,
              id=ID_OBJDICTEDITEDITMENUNODEINFOS)
        self.Bind(wx.EVT_MENU, self.OnCommunicationMenu,
              id=ID_OBJDICTEDITEDITMENUDS301PROFILE)
        self.Bind(wx.EVT_MENU, self.OnOtherCommunicationMenu,
              id=ID_OBJDICTEDITEDITMENUDS302PROFILE)
        self.Bind(wx.EVT_MENU, self.OnEditProfileMenu,
              id=ID_OBJDICTEDITEDITMENUOTHERPROFILE)

    def _init_coll_AddMenu_Items(self, parent):
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUSDOSERVER,
              kind=wx.ITEM_NORMAL, item='SDO Server')
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUSDOCLIENT,
              kind=wx.ITEM_NORMAL, item='SDO Client')
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUPDOTRANSMIT,
              kind=wx.ITEM_NORMAL, item='PDO Transmit')
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUPDORECEIVE,
              kind=wx.ITEM_NORMAL, item='PDO Receive')
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUMAPVARIABLE,
              kind=wx.ITEM_NORMAL, item='Map Variable')
        parent.Append(helpString='', id=ID_OBJDICTEDITADDMENUUSERTYPE,
              kind=wx.ITEM_NORMAL, item='User Type')
        self.Bind(wx.EVT_MENU, self.OnAddSDOServerMenu,
              id=ID_OBJDICTEDITADDMENUSDOSERVER)
        self.Bind(wx.EVT_MENU, self.OnAddSDOClientMenu,
              id=ID_OBJDICTEDITADDMENUSDOCLIENT)
        self.Bind(wx.EVT_MENU, self.OnAddPDOTransmitMenu,
              id=ID_OBJDICTEDITADDMENUPDOTRANSMIT)
        self.Bind(wx.EVT_MENU, self.OnAddPDOReceiveMenu,
              id=ID_OBJDICTEDITADDMENUPDORECEIVE)
        self.Bind(wx.EVT_MENU, self.OnAddMapVariableMenu,
              id=ID_OBJDICTEDITADDMENUMAPVARIABLE)
        self.Bind(wx.EVT_MENU, self.OnAddUserTypeMenu,
              id=ID_OBJDICTEDITADDMENUUSERTYPE)

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
        self.EditMenu = wx.Menu(title='')
        self.AddMenu = wx.Menu(title='')

        self._init_coll_MenuBar_Menus(self.MenuBar)
        if self.ModeSolo:
            self._init_coll_FileMenu_Items(self.FileMenu)
        self._init_coll_EditMenu_Items(self.EditMenu)
        self._init_coll_AddMenu_Items(self.AddMenu)

    def _init_ctrls(self, prnt):
        wx.Frame.__init__(self, id=ID_OBJDICTEDIT, name='objdictedit',
              parent=prnt, pos=wx.Point(149, 178), size=wx.Size(1000, 700),
              style=wx.DEFAULT_FRAME_STYLE, title='Objdictedit')
        self._init_utils()
        self.SetClientSize(wx.Size(1000, 700))
        self.SetMenuBar(self.MenuBar)
        self.Bind(wx.EVT_CLOSE, self.OnCloseFrame)
        if not self.ModeSolo:
            self.Bind(wx.EVT_MENU, self.OnSaveMenu, id=wx.ID_SAVE)
            accel = wx.AcceleratorTable([wx.AcceleratorEntry(wx.ACCEL_CTRL, 83, wx.ID_SAVE)])
            self.SetAcceleratorTable(accel)

        self.FileOpened = wx.Notebook(id=ID_OBJDICTEDITFILEOPENED,
              name='FileOpened', parent=self, pos=wx.Point(0, 0),
              size=wx.Size(0, 0), style=0)
        self.FileOpened.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED,
              self.OnFileSelectedChanged, id=ID_OBJDICTEDITFILEOPENED)

        self.HelpBar = wx.StatusBar(id=ID_OBJDICTEDITHELPBAR, name='HelpBar',
              parent=self, style=wx.STB_SIZEGRIP)
        self._init_coll_HelpBar_Fields(self.HelpBar)
        self.SetStatusBar(self.HelpBar)

    def __init__(self, parent, manager=None, filesopen=None):
        filesopen = filesopen or []
        if manager is None:
            net.NodeEditorTemplate.__init__(self, objdictgen.NodeManager(), self, True)
        else:
            net.NodeEditorTemplate.__init__(self, manager, self, False)
        self._init_ctrls(parent)

        icon = wx.Icon(os.path.join(objdictgen.SCRIPT_DIRECTORY, "ui", "networkedit.ico"), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        if self.ModeSolo:
            for filepath in filesopen:
                try:
                    index = self.Manager.OpenFileInCurrent(os.path.abspath(filepath))
                    new_editingpanel = sit.EditingPanel(self.FileOpened, self, self.Manager)
                    new_editingpanel.SetIndex(index)
                    self.FileOpened.AddPage(new_editingpanel, "")
                except Exception as exc:  # Need this broad exception?
                    log.debug("Swallowed Exception: %s" % (exc, ))
                    raise  # FIXME: Originial code swallows exception
        else:
            for index in self.Manager.GetBufferIndexes():
                new_editingpanel = sit.EditingPanel(self.FileOpened, self, self.Manager)
                new_editingpanel.SetIndex(index)
                self.FileOpened.AddPage(new_editingpanel, "")

        if self.Manager.GetBufferNumber() > 0:
            window = self.FileOpened.GetPage(0)
            if window:
                self.Manager.ChangeCurrentNode(window.GetIndex())
                self.FileOpened.SetSelection(0)

        if self.Manager.CurrentDS302Defined():
            self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, True)
        else:
            self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, False)
        self.RefreshEditMenu()
        self.RefreshBufferState()
        self.RefreshProfileMenu()
        self.RefreshTitle()
        self.RefreshMainMenu()

    def OnFileSelectedChanged(self, event):
        if not self.Closing:
            selected = event.GetSelection()
            # At init selected = -1
            if selected >= 0:
                window = self.FileOpened.GetPage(selected)
                if window:
                    self.Manager.ChangeCurrentNode(window.GetIndex())
                    wx.CallAfter(self.RefreshBufferState)
                    self.RefreshStatusBar()
                    self.RefreshProfileMenu()
        event.Skip()

    def OnQuitMenu(self, event):  # pylint: disable=unused-argument
        self.Close()

    def OnCloseFrame(self, event):
        self.Closing = True
        if not self.ModeSolo:
            if getattr(self, "_onclose", None) is not None:
                self._onclose()
            event.Skip()
        elif self.Manager.OneFileHasChanged():
            dialog = wx.MessageDialog(self, "There are changes, do you want to save?", "Close Application", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            answer = dialog.ShowModal()
            dialog.Destroy()
            if answer == wx.ID_YES:
                for _ in range(self.Manager.GetBufferNumber()):
                    if self.Manager.CurrentIsSaved():
                        self.Manager.CloseCurrent()
                    else:
                        self.Save()
                        self.Manager.CloseCurrent(True)
                event.Skip()
            elif answer == wx.ID_NO:
                event.Skip()
            else:
                event.Veto()
        else:
            event.Skip()

# ------------------------------------------------------------------------------
#                             Refresh Functions
# ------------------------------------------------------------------------------

    def RefreshTitle(self):
        if self.FileOpened.GetPageCount() > 0:
            self.SetTitle("Objdictedit - %s" % self.Manager.GetCurrentFilename())
        else:
            self.SetTitle("Objdictedit")

    def RefreshCurrentIndexList(self):
        selected = self.FileOpened.GetSelection()
        window = self.FileOpened.GetPage(selected)
        window.RefreshIndexList()

    def RefreshStatusBar(self):
        selected = self.FileOpened.GetSelection()
        if selected >= 0:
            window = self.FileOpened.GetPage(selected)
            self.SetStatusBarText(window.GetSelection(), self.Manager)

    def RefreshMainMenu(self):
        if self.FileOpened.GetPageCount() > 0:
            if self.ModeSolo:
                self.MenuBar.EnableTop(1, True)
                self.MenuBar.EnableTop(2, True)
                self.FileMenu.Enable(wx.ID_CLOSE, True)
                self.FileMenu.Enable(wx.ID_SAVE, True)
                self.FileMenu.Enable(wx.ID_SAVEAS, True)
                self.FileMenu.Enable(ID_OBJDICTEDITFILEMENUEXPORTEDS, True)
                self.FileMenu.Enable(ID_OBJDICTEDITFILEMENUEXPORTC, True)
            else:
                self.MenuBar.EnableTop(0, True)
                self.MenuBar.EnableTop(1, True)
        else:
            if self.ModeSolo:
                self.MenuBar.EnableTop(1, False)
                self.MenuBar.EnableTop(2, False)
                self.FileMenu.Enable(wx.ID_CLOSE, False)
                self.FileMenu.Enable(wx.ID_SAVE, False)
                self.FileMenu.Enable(wx.ID_SAVEAS, False)
                self.FileMenu.Enable(ID_OBJDICTEDITFILEMENUEXPORTEDS, False)
                self.FileMenu.Enable(ID_OBJDICTEDITFILEMENUEXPORTC, False)
            else:
                self.MenuBar.EnableTop(0, False)
                self.MenuBar.EnableTop(1, False)

    def RefreshEditMenu(self):
        if self.FileOpened.GetPageCount() > 0:
            undo, redo = self.Manager.GetCurrentBufferState()
            self.EditMenu.Enable(wx.ID_UNDO, undo)
            self.EditMenu.Enable(wx.ID_REDO, redo)
        else:
            self.EditMenu.Enable(wx.ID_UNDO, False)
            self.EditMenu.Enable(wx.ID_REDO, False)

# ------------------------------------------------------------------------------
#                            Buffer Functions
# ------------------------------------------------------------------------------

    def RefreshBufferState(self):
        fileopened = self.Manager.GetAllFilenames()
        for idx, filename in enumerate(fileopened):
            self.FileOpened.SetPageText(idx, filename)
        self.RefreshEditMenu()
        self.RefreshTitle()

# ------------------------------------------------------------------------------
#                         Load and Save Funtions
# ------------------------------------------------------------------------------

    def OnNewMenu(self, event):  # pylint: disable=unused-argument
        # FIXME: Unused. Delete this?
        # self.FilePath = ""
        dialog = cdia.CreateNodeDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            name, id_, nodetype, description = dialog.GetValues()
            profile, filepath = dialog.GetProfile()
            nmt = dialog.GetNMTManagement()
            options = dialog.GetOptions()
            try:
                index = self.Manager.CreateNewNode(name, id_, nodetype, description, profile, filepath, nmt, options)
                new_editingpanel = sit.EditingPanel(self.FileOpened, self, self.Manager)
                new_editingpanel.SetIndex(index)
                self.FileOpened.AddPage(new_editingpanel, "")
                self.FileOpened.SetSelection(self.FileOpened.GetPageCount() - 1)
                self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, False)
                if "DS302" in options:
                    self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, True)
                self.RefreshBufferState()
                self.RefreshProfileMenu()
                self.RefreshMainMenu()
            except Exception as exc:  # pylint: disable=broad-except
                message = wx.MessageDialog(self, str(exc), "ERROR", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()
        dialog.Destroy()

    def OnOpenMenu(self, event):  # pylint: disable=unused-argument
        filepath = self.Manager.GetCurrentFilePath()
        if filepath:
            directory = os.path.dirname(filepath)
        else:
            directory = os.getcwd()
        dialog = wx.FileDialog(self, "Choose a file", directory, "", "OD files (*.json;*.od;*.eds)|*.json;*.od;*.eds|All files|*.*", style=wx.FD_OPEN | wx.FD_CHANGE_DIR)
        if dialog.ShowModal() == wx.ID_OK:
            filepath = dialog.GetPath()
            if os.path.isfile(filepath):
                try:
                    index = self.Manager.OpenFileInCurrent(filepath)
                    new_editingpanel = sit.EditingPanel(self.FileOpened, self, self.Manager)
                    new_editingpanel.SetIndex(index)
                    self.FileOpened.AddPage(new_editingpanel, "")
                    self.FileOpened.SetSelection(self.FileOpened.GetPageCount() - 1)
                    if self.Manager.CurrentDS302Defined():
                        self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, True)
                    else:
                        self.EditMenu.Enable(ID_OBJDICTEDITEDITMENUDS302PROFILE, False)
                    self.RefreshEditMenu()
                    self.RefreshBufferState()
                    self.RefreshProfileMenu()
                    self.RefreshMainMenu()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()
        dialog.Destroy()

    def OnSaveMenu(self, event):  # pylint: disable=unused-argument
        if not self.ModeSolo and getattr(self, "_onsave", None) is not None:
            self._onsave()
            self.RefreshBufferState()
        else:
            self.Save()

    def OnSaveAsMenu(self, event):  # pylint: disable=unused-argument
        self.SaveAs()

    def Save(self):
        try:
            result = self.Manager.SaveCurrentInFile()
            if not result:
                self.SaveAs()
            else:
                self.RefreshBufferState()
        except Exception as exc:  # pylint: disable=broad-except
            message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
            message.ShowModal()
            message.Destroy()

    def SaveAs(self):
        filepath = self.Manager.GetCurrentFilePath()
        if filepath:
            directory, filename = os.path.split(filepath)
        else:
            directory, filename = os.getcwd(), "%s" % self.Manager.GetCurrentNodeInfos()[0]

        with wx.FileDialog(self, "Choose a file", directory, filename, wildcard="OD JSON file (*.json)|*.json;|OD file (*.od)|*.od;|EDS file (*.eds)|*.eds",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            
            log.debug(filepath)
            filepath = dialog.GetPath()

            if not os.path.isdir(os.path.dirname(filepath)):
                message = wx.MessageDialog(self, "%s is not a valid folder!" % os.path.dirname(filepath), "Error", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()
            else:
                try:
                    #Try and save the file and then update the filepath if successfull
                    if self.Manager.SaveCurrentInFile(filepath):
                        self.Manager.SetCurrentFilePath(filepath)
                    self.RefreshBufferState()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()

    def OnCloseMenu(self, event):
        answer = wx.ID_YES
        result = self.Manager.CloseCurrent()
        if not result:
            dialog = wx.MessageDialog(self, "There are changes, do you want to save?", "Close File", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            answer = dialog.ShowModal()
            dialog.Destroy()
            if answer == wx.ID_YES:
                self.OnSaveMenu(event)
                if self.Manager.CurrentIsSaved():
                    self.Manager.CloseCurrent()
            elif answer == wx.ID_NO:
                self.Manager.CloseCurrent(True)
        if self.FileOpened.GetPageCount() > self.Manager.GetBufferNumber():
            current = self.FileOpened.GetSelection()
            self.FileOpened.DeletePage(current)
            if self.FileOpened.GetPageCount() > 0:
                self.FileOpened.SetSelection(min(current, self.FileOpened.GetPageCount() - 1))
            self.RefreshBufferState()
            self.RefreshMainMenu()

    # --------------------------------------------------------------------------
    #                     Import and Export Functions
    # --------------------------------------------------------------------------

    def OnImportEDSMenu(self, event):  # pylint: disable=unused-argument
        dialog = wx.FileDialog(self, "Choose a file", os.getcwd(), "", "EDS files (*.eds)|*.eds|All files|*.*", style=wx.FD_OPEN | wx.FD_CHANGE_DIR)
        if dialog.ShowModal() == wx.ID_OK:
            filepath = dialog.GetPath()
            if os.path.isfile(filepath):
                try:
                    index = self.Manager.OpenFileInCurrent(filepath, load=False)
                    new_editingpanel = sit.EditingPanel(self.FileOpened, self, self.Manager)
                    new_editingpanel.SetIndex(index)
                    self.FileOpened.AddPage(new_editingpanel, "")
                    self.FileOpened.SetSelection(self.FileOpened.GetPageCount() - 1)
                    self.RefreshBufferState()
                    self.RefreshCurrentIndexList()
                    self.RefreshProfileMenu()
                    self.RefreshMainMenu()
                    message = wx.MessageDialog(self, "Import successful", "Information", wx.OK | wx.ICON_INFORMATION)
                    message.ShowModal()
                    message.Destroy()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()
            else:
                message = wx.MessageDialog(self, "'%s' is not a valid file!" % filepath, "Error", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()
        dialog.Destroy()

    def OnExportEDSMenu(self, event):  # pylint: disable=unused-argument
        dialog = wx.FileDialog(self, "Choose a file", os.getcwd(), self.Manager.GetCurrentNodeInfos()[0], "EDS files (*.eds)|*.eds|All files|*.*", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR)
        if dialog.ShowModal() == wx.ID_OK:
            filepath = dialog.GetPath()
            if not os.path.isdir(os.path.dirname(filepath)):
                message = wx.MessageDialog(self, "'%s' is not a valid folder!" % os.path.dirname(filepath), "Error", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()
            else:
                path, extend = os.path.splitext(filepath)
                if extend in ("", "."):
                    filepath = path + ".eds"
                try:
                    self.Manager.SaveCurrentInFile(filepath, filetype='eds')
                    message = wx.MessageDialog(self, "Export successful", "Information", wx.OK | wx.ICON_INFORMATION)
                    message.ShowModal()
                    message.Destroy()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()
        dialog.Destroy()

    def OnExportCMenu(self, event):  # pylint: disable=unused-argument
        dialog = wx.FileDialog(self, "Choose a file", os.getcwd(), self.Manager.GetCurrentNodeInfos()[0], "CANFestival C files (*.c)|*.c|All files|*.*", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR)
        if dialog.ShowModal() == wx.ID_OK:
            filepath = dialog.GetPath()
            if not os.path.isdir(os.path.dirname(filepath)):
                message = wx.MessageDialog(self, "'%s' is not a valid folder!" % os.path.dirname(filepath), "Error", wx.OK | wx.ICON_ERROR)
                message.ShowModal()
                message.Destroy()
            else:
                path, extend = os.path.splitext(filepath)
                if extend in ("", "."):
                    filepath = path + ".c"
                try:
                    self.Manager.SaveCurrentInFile(filepath, filetype='c')
                    message = wx.MessageDialog(self, "Export successful", "Information", wx.OK | wx.ICON_INFORMATION)
                    message.ShowModal()
                    message.Destroy()
                except Exception as exc:  # pylint: disable=broad-except
                    message = wx.MessageDialog(self, str(exc), "Error", wx.OK | wx.ICON_ERROR)
                    message.ShowModal()
                    message.Destroy()
        dialog.Destroy()


def uimain(args):
    app = wx.App()

    wx.InitAllImageHandlers()

    # Install a exception handle for bug reports
    AddExceptHook(os.getcwd(), objdictgen.ODG_VERSION)

    frame = ObjdictEdit(None, filesopen=args)

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

    uimain(args)
