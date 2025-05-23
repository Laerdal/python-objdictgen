"""Shared dialog classes for the Object Dictionary Editor."""
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
from __future__ import annotations

import logging
import os

import wx
import wx.grid

import objdictgen
from objdictgen import maps
from objdictgen.maps import OD
from objdictgen.typing import TGetValues
from objdictgen.ui.exception import (display_error_dialog,
                                     display_exception_dialog)

log = logging.getLogger('objdictgen')


# ------------------------------------------------------------------------------
#                          Editing Communication Dialog
# ------------------------------------------------------------------------------


[
    ID_COMMUNICATIONDIALOG, ID_COMMUNICATIONDIALOGPOSSIBLEINDEXES,
    ID_COMMUNICATIONDIALOGCURRENTINDEXES, ID_COMMUNICATIONDIALOGSELECT,
    ID_COMMUNICATIONDIALOGUNSELECT, ID_COMMUNICATIONDIALOGSTATICTEXT1,
    ID_COMMUNICATIONDIALOGSTATICTEXT2
] = [wx.NewId() for _ in range(7)]


class CommunicationDialog(wx.Dialog):
    """Edit Communication Profile Dialog."""
    # pylint: disable=attribute-defined-outside-init

    IndexDictionary: dict[int, tuple[str, bool]]
    CurrentList: list[int]
    AllList: list[int]

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.LeftGridSizer, 0, border=0, flag=wx.GROW)
        parent.Add(self.MiddleGridSizer, 0, border=0, flag=wx.GROW)
        parent.Add(self.RightGridSizer, 0, border=0, flag=wx.GROW)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableCol(2)
        parent.AddGrowableRow(0)

    def _init_coll_LeftGridSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=0, flag=wx.GROW)
        parent.Add(self.PossibleIndexes, 0, border=0, flag=wx.GROW)

    def _init_coll_LeftGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(1)

    def _init_coll_MiddleGridSizer_Items(self, parent):
        parent.Add(self.Select, 0, border=0, flag=wx.ALIGN_BOTTOM)
        parent.Add(self.Unselect, 0, border=0, flag=wx.ALIGN_TOP)

    def _init_coll_MiddleGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)
        parent.AddGrowableRow(1)

    def _init_coll_RightGridSizer_Items(self, parent):
        parent.Add(self.staticText2, 0, border=0, flag=wx.GROW)
        parent.Add(self.CurrentIndexes, 0, border=0, flag=wx.GROW)

    def _init_coll_RightGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(1)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.FlexGridSizer(cols=3, hgap=15, rows=1, vgap=0)
        self.LeftGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=5)
        self.MiddleGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=40)
        self.RightGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=5)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)
        self._init_coll_LeftGridSizer_Items(self.LeftGridSizer)
        self._init_coll_LeftGridSizer_Growables(self.LeftGridSizer)
        self._init_coll_MiddleGridSizer_Items(self.MiddleGridSizer)
        self._init_coll_MiddleGridSizer_Growables(self.MiddleGridSizer)
        self._init_coll_RightGridSizer_Items(self.RightGridSizer)
        self._init_coll_RightGridSizer_Growables(self.RightGridSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_COMMUNICATIONDIALOG,
            name='CommunicationDialog', parent=parent, pos=wx.Point(234, 216),
            size=wx.Size(726, 437), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            title='Edit Communication Profile')
        self.SetClientSize(wx.Size(726, 437))

        self.staticText1 = wx.StaticText(id=ID_COMMUNICATIONDIALOGSTATICTEXT1,
            label='Possible Profile Indexes:', name='staticText1',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0,
            17), style=0)

        self.PossibleIndexes = wx.ListBox(choices=[],
            id=ID_COMMUNICATIONDIALOGPOSSIBLEINDEXES,
            name='PossibleIndexes', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.LB_EXTENDED)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnPossibleIndexesDClick,
            id=ID_COMMUNICATIONDIALOGPOSSIBLEINDEXES)

        self.Select = wx.Button(id=ID_COMMUNICATIONDIALOGSELECT, label='>>',
            name='Select', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(32, 32), style=0)
        self.Select.Bind(wx.EVT_BUTTON, self.OnSelectButton,
            id=ID_COMMUNICATIONDIALOGSELECT)

        self.Unselect = wx.Button(id=ID_COMMUNICATIONDIALOGUNSELECT,
            label='<<', name='Unselect', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(32, 32), style=0)
        self.Unselect.Bind(wx.EVT_BUTTON, self.OnUnselectButton,
            id=ID_COMMUNICATIONDIALOGUNSELECT)

        self.staticText2 = wx.StaticText(id=ID_COMMUNICATIONDIALOGSTATICTEXT2,
            label='Current Profile Indexes:', name='staticText2',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0,
            17), style=0)

        self.CurrentIndexes = wx.ListBox(choices=[],
            id=ID_COMMUNICATIONDIALOGCURRENTINDEXES, name='CurrentIndexes',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 0),
            style=wx.LB_EXTENDED)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnCurrentIndexesDClick,
            id=ID_COMMUNICATIONDIALOGCURRENTINDEXES)

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)

        self._init_sizers()

    def __init__(self, parent):
        self._init_ctrls(parent)
        self.AllList = []
        self.CurrentList = []
        self.IndexDictionary = {}

    def SetIndexDictionary(self, dictionary: dict[int, tuple[str, bool]]):
        self.IndexDictionary = dictionary

    def SetCurrentList(self, currentlist: list[int]):
        self.CurrentList = []
        self.CurrentList.extend(currentlist)
        self.CurrentList.sort()

    def GetCurrentList(self) -> list[int]:
        return self.CurrentList

    def RefreshLists(self):
        self.PossibleIndexes.Clear()
        self.CurrentIndexes.Clear()
        self.AllList = []
        for index in self.IndexDictionary:
            if index not in self.CurrentList:
                self.AllList.append(index)
        self.AllList.sort()
        for index in self.AllList:
            self.PossibleIndexes.Append(f"0x{index:04X}   {self.IndexDictionary[index][0]}")
        for index in self.CurrentList:
            if index in self.IndexDictionary:
                self.CurrentIndexes.Append(f"0x{index:04X}   {self.IndexDictionary[index][0]}")

    def OnPossibleIndexesDClick(self, event):
        self.SelectPossible()
        event.Skip()

    def OnCurrentIndexesDClick(self, event):
        self.UnselectCurrent()
        event.Skip()

    def OnSelectButton(self, event):
        self.SelectPossible()
        event.Skip()

    def OnUnselectButton(self, event):
        self.UnselectCurrent()
        event.Skip()

    def SelectPossible(self):
        selected = self.PossibleIndexes.GetSelections()
        for i in selected:
            self.CurrentList.append(self.AllList[i])
        self.CurrentList.sort()
        self.RefreshLists()

    def UnselectCurrent(self):
        selected = self.CurrentIndexes.GetSelections()
        for i in selected:
            if not self.IndexDictionary[self.CurrentList[i]][1]:
                self.CurrentList.pop(i)
        self.CurrentList.sort()
        self.RefreshLists()


# ------------------------------------------------------------------------------
#                          Create Map Variable Dialog
# ------------------------------------------------------------------------------


[
    ID_MAPVARIABLEDIALOG, ID_MAPVARIABLEDIALOGINDEX,
    ID_MAPVARIABLEDIALOGINDEXNAME, ID_MAPVARIABLEDIALOGSPACER,
    ID_MAPVARIABLEDIALOGSPACER2, ID_MAPVARIABLEDIALOGNUMBER,
    ID_MAPVARIABLEDIALOGRADIOBUTTON1, ID_MAPVARIABLEDIALOGRADIOBUTTON2,
    ID_MAPVARIABLEDIALOGRADIOBUTTON3, ID_MAPVARIABLEDIALOGSTATICTEXT1,
    ID_MAPVARIABLEDIALOGSTATICTEXT2, ID_MAPVARIABLEDIALOGSTATICTEXT3,
    ID_MAPVARIABLEDIALOGSTATICTEXT4,
] = [wx.NewId() for _ in range(13)]


class MapVariableDialog(wx.Dialog):
    """Create Map Variable Dialog."""
    # pylint: disable=attribute-defined-outside-init

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText2, 0, border=0, flag=wx.GROW)
        parent.Add(self.Spacer, 0, border=0, flag=wx.GROW)
        parent.Add(self.Index, 0, border=0, flag=wx.GROW)
        parent.Add(self.radioButton1, 0, border=0, flag=wx.GROW)
        parent.Add(self.Spacer2, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText3, 0, border=0, flag=wx.GROW)
        parent.Add(self.radioButton2, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText4, 0, border=0, flag=wx.GROW)
        parent.Add(self.IndexName, 0, border=0, flag=wx.GROW)
        parent.Add(self.radioButton3, 0, border=0, flag=wx.GROW)
        parent.Add(self.Number, 0, border=0, flag=wx.GROW)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableCol(2)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.FlexGridSizer(cols=3, hgap=30, rows=4, vgap=5)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_MAPVARIABLEDIALOG,
            name='CommunicationDialog', parent=parent, pos=wx.Point(376, 223),
            size=wx.Size(444, 186), style=wx.DEFAULT_DIALOG_STYLE,
            title='Add Map Variable',
        )
        self.SetClientSize(wx.Size(444, 186))

        self.staticText1 = wx.StaticText(id=ID_MAPVARIABLEDIALOGSTATICTEXT1,
            label='Index:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText2 = wx.StaticText(id=ID_MAPVARIABLEDIALOGSTATICTEXT2,
            label='Type:', name='staticText2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText3 = wx.StaticText(id=ID_MAPVARIABLEDIALOGSTATICTEXT3,
            label='Name:', name='staticText3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText4 = wx.StaticText(id=ID_MAPVARIABLEDIALOGSTATICTEXT4,
            label='Number:', name='staticText4', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 16), style=0,
        )

        self.radioButton1 = wx.RadioButton(id=ID_MAPVARIABLEDIALOGRADIOBUTTON1,
            label='VAR', name='radioButton1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 24), style=wx.RB_GROUP,
        )
        self.radioButton1.SetValue(True)
        self.radioButton1.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton1Click,
            id=ID_MAPVARIABLEDIALOGRADIOBUTTON1,
        )

        self.radioButton2 = wx.RadioButton(id=ID_MAPVARIABLEDIALOGRADIOBUTTON2,
            label='ARRAY', name='radioButton2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 24), style=0,
        )
        self.radioButton2.SetValue(False)
        self.radioButton2.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton2Click,
            id=ID_MAPVARIABLEDIALOGRADIOBUTTON2,
        )

        self.radioButton3 = wx.RadioButton(id=ID_MAPVARIABLEDIALOGRADIOBUTTON3,
            label='RECORD', name='radioButton3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 24), style=0,
        )
        self.radioButton3.SetValue(False)
        self.radioButton3.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton3Click,
            id=ID_MAPVARIABLEDIALOGRADIOBUTTON3,
        )

        self.Index = wx.TextCtrl(id=ID_MAPVARIABLEDIALOGINDEX, name='Index',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 25),
            style=0, value='0x2000',
        )

        self.IndexName = wx.TextCtrl(id=ID_MAPVARIABLEDIALOGINDEXNAME,
            name='IndexName', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=0, value='Undefined',
        )

        self.Number = wx.TextCtrl(id=ID_MAPVARIABLEDIALOGNUMBER,
            name='Number', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=wx.TE_RIGHT, value='1',
        )

        self.Spacer = wx.Panel(id=ID_MAPVARIABLEDIALOGSPACER,
            name='Spacer', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.TAB_TRAVERSAL,
        )

        self.Spacer2 = wx.Panel(id=ID_MAPVARIABLEDIALOGSPACER2,
            name='Spacer2', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.TAB_TRAVERSAL,
        )

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

        self._init_sizers()

    def __init__(self, parent):
        self._init_ctrls(parent)
        self.staticText4.Enable(False)
        self.Number.Enable(False)

    def SetIndex(self, index):
        self.Index.SetValue(f"0x{index:04X}")

    def OnOK(self, event):  # pylint: disable=unused-argument
        error = []
        try:
            int(self.Index.GetValue(), 16)
        except ValueError as exc:
            log.debug("ValueError: '%s': %s", self.Index.GetValue(), exc)
            error.append("Index")
        if self.radioButton2.GetValue() or self.radioButton3.GetValue():
            try:
                int(self.Number.GetValue())
                if int(self.Number.GetValue()) < 1:
                    raise ValueError("Number out of range, must be >0")
            except ValueError as exc:
                log.debug("ValueError: '%s': %s", self.Index.GetValue(), exc)
                error.append("Number")
        if len(error) > 0:
            text = ""
            for i, item in enumerate(error):
                if i == 0:
                    text += item
                elif i == len(error) - 1:
                    text += f" and {item} must be integers!"
                else:
                    text += f", {item} must be integer!"
            display_error_dialog(self, f"Form isn't valid. {text}")
        else:
            self.EndModal(wx.ID_OK)

    def GetValues(self):
        name = self.IndexName.GetValue()
        index = int(self.Index.GetValue(), 16)
        if self.radioButton1.GetValue():
            struct = OD.VAR
            number = None
        elif self.radioButton2.GetValue():
            struct = OD.ARRAY
            number = int(self.Number.GetValue())
        elif self.radioButton3.GetValue():
            struct = OD.RECORD
            number = int(self.Number.GetValue())
        return index, name, struct, number

    def OnRadioButton1Click(self, event):
        self.EnableNumberTyping(False)
        event.Skip()

    def OnRadioButton2Click(self, event):
        self.EnableNumberTyping(True)
        event.Skip()

    def OnRadioButton3Click(self, event):
        self.EnableNumberTyping(True)
        event.Skip()

    def EnableNumberTyping(self, enable):
        self.staticText4.Enable(enable)
        self.Number.Enable(enable)


# ------------------------------------------------------------------------------
#                          Create User Type Dialog
# ------------------------------------------------------------------------------


[
    ID_USERTYPEDIALOG, ID_USERTYPEDIALOGSPACER,
    ID_USERTYPEDIALOGTYPE, ID_USERTYPEDIALOGMAX,
    ID_USERTYPEDIALOGMIN, ID_USERTYPEDIALOGLENGTH,
    ID_USERTYPEDIALOGSTATICBOX1, ID_USERTYPEDIALOGSTATICTEXT1,
    ID_USERTYPEDIALOGSTATICTEXT2, ID_USERTYPEDIALOGSTATICTEXT3,
    ID_USERTYPEDIALOGSTATICTEXT4,
] = [wx.NewId() for _ in range(11)]


class UserTypeDialog(wx.Dialog):
    """Create User Type Dialog."""
    # pylint: disable=attribute-defined-outside-init

    # Helpers for typing
    RightBoxSizer: wx.StaticBoxSizer
    RightBoxGridSizer: wx.FlexGridSizer
    TypeDictionary: dict[str, tuple[int, int]]
    # Index: wx.TextCtrl

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.LeftGridSizer, 2, border=5, flag=wx.GROW | wx.RIGHT)
        parent.Add(self.RightBoxSizer, 3, border=5, flag=wx.GROW | wx.LEFT)

    def _init_coll_LeftGridSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=0, flag=wx.GROW)
        parent.Add(self.Type, 0, border=0, flag=wx.GROW)
        parent.Add(self.Spacer, 0, border=0, flag=wx.GROW)

    def _init_coll_LeftGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(2)

    def _init_coll_RightBoxSizer_Items(self, parent):
        parent.Add(self.RightBoxGridSizer, 0, border=10, flag=wx.GROW | wx.ALL)

    def _init_coll_RightBoxGridSizer_Items(self, parent):
        parent.Add(self.staticText2, 0, border=0, flag=wx.GROW)
        parent.Add(self.Min, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText3, 0, border=0, flag=wx.GROW)
        parent.Add(self.Max, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText4, 0, border=0, flag=wx.GROW)
        parent.Add(self.Length, 0, border=0, flag=wx.GROW)

    def _init_coll_RightBoxGridSizer_Growables(self, parent):
        parent.AddGrowableCol(1)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.LeftGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=3, vgap=5)
        self.RightBoxSizer = wx.StaticBoxSizer(self.staticBox1, wx.VERTICAL)
        self.RightBoxGridSizer = wx.FlexGridSizer(cols=2, hgap=5, rows=3, vgap=10)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_LeftGridSizer_Items(self.LeftGridSizer)
        self._init_coll_LeftGridSizer_Growables(self.LeftGridSizer)
        self._init_coll_RightBoxSizer_Items(self.RightBoxSizer)
        self._init_coll_RightBoxGridSizer_Items(self.RightBoxGridSizer)
        self._init_coll_RightBoxGridSizer_Growables(self.RightBoxGridSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_USERTYPEDIALOG, name='UserTypeDialog',
            parent=parent, pos=wx.Point(376, 223), size=wx.Size(444, 210),
            style=wx.DEFAULT_DIALOG_STYLE, title='Add User Type',
        )
        self.SetClientSize(wx.Size(444, 210))

        self.staticText1 = wx.StaticText(id=ID_USERTYPEDIALOGSTATICTEXT1,
            label='Type:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.Type = wx.ComboBox(choices=[], id=ID_USERTYPEDIALOGTYPE,
            name='Type', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 28), style=wx.CB_READONLY,
        )
        self.Type.Bind(wx.EVT_COMBOBOX, self.OnTypeChoice,
            id=ID_USERTYPEDIALOGTYPE,
        )

        self.Spacer = wx.Panel(id=ID_MAPVARIABLEDIALOGSPACER,
            name='Spacer', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.TAB_TRAVERSAL,
        )

        self.staticBox1 = wx.StaticBox(id=ID_USERTYPEDIALOGSTATICBOX1,
            label='Values', name='staticBox1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 0), style=0,
        )

        self.staticText2 = wx.StaticText(id=ID_USERTYPEDIALOGSTATICTEXT2,
            label='Minimum:', name='staticText2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 17), style=0,
        )

        self.Min = wx.TextCtrl(id=ID_USERTYPEDIALOGMIN, name='Min',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=wx.TE_RIGHT, value='0',
        )

        self.staticText3 = wx.StaticText(id=ID_USERTYPEDIALOGSTATICTEXT3,
            label='Maximum:', name='staticText3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 17), style=0,
        )

        self.Max = wx.TextCtrl(id=ID_USERTYPEDIALOGMAX, name='Max',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=wx.TE_RIGHT, value='0',
        )

        self.staticText4 = wx.StaticText(id=ID_USERTYPEDIALOGSTATICTEXT4,
            label='Length:', name='staticText4', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(80, 17), style=0,
        )

        self.Length = wx.TextCtrl(id=ID_USERTYPEDIALOGLENGTH, name='Length',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=wx.TE_RIGHT, value='0',
        )

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

        self._init_sizers()

    def __init__(self, parent):
        self._init_ctrls(parent)

        self.TypeDictionary: dict[str, tuple[int, int]] = {}

    def OnOK(self, event):  # pylint: disable=unused-argument
        error = []
        message = None
        name = self.Type.GetStringSelection()
        if name:
            valuetype = self.TypeDictionary[name][1]
            if valuetype == 0:
                try:
                    int(self.Min.GetValue(), 16)
                except ValueError as exc:
                    log.debug("ValueError: '%s': %s", self.Index.GetValue(), exc)  # FIXME: What is self.Index?
                    error.append("Minimum")
                try:
                    int(self.Max.GetValue(), 16)
                except ValueError as exc:
                    log.debug("ValueError: '%s': %s", self.Index.GetValue(), exc)
                    error.append("Maximum")
            elif valuetype == 1:
                try:
                    int(self.Length.GetValue(), 16)
                except ValueError as exc:
                    log.debug("ValueError: '%s': %s", self.Index.GetValue(), exc)
                    error.append("Length")
            if len(error) > 0:
                message = ""
                for i, item in enumerate(error):
                    if i == 0:
                        message += item
                    elif i == len(error) - 1:
                        message += f" and {item} must be integers!"
                    else:
                        message += f", {item} must be integer!"
        else:
            message = "A type must be selected!"
        if message is not None:
            display_error_dialog(self, f"Form isn't valid. {message}")
        else:
            self.EndModal(wx.ID_OK)

    def SetValues(self, min=None, max=None, length=None):
        if min is not None:
            self.Min.SetValue(str(min))
        if max is not None:
            self.Max.SetValue(str(max))
        if length is not None:
            self.Length.SetValue(str(length))

    def SetTypeList(self, typedic, objtype=None):
        self.Type.Clear()
        typelist = []
        for index, (name, valuetype) in typedic.items():
            self.TypeDictionary[name] = (index, valuetype)
            typelist.append((index, name))
        for index, name in sorted(typelist):
            self.Type.Append(name)
        if objtype is not None:
            self.Type.SetStringSelection(typedic[objtype][0])
        self.RefreshValues()

    def OnTypeChoice(self, event):
        self.RefreshValues()
        event.Skip()

    def RefreshValues(self):
        name = self.Type.GetStringSelection()
        if name:
            valuetype = self.TypeDictionary[name][1]
            if valuetype == 0:
                self.staticText2.Enable(True)
                self.staticText3.Enable(True)
                self.staticText4.Enable(False)
                self.Min.Enable(True)
                self.Max.Enable(True)
                self.Length.Enable(False)
            elif valuetype == 1:
                self.staticText2.Enable(False)
                self.staticText3.Enable(False)
                self.staticText4.Enable(True)
                self.Min.Enable(False)
                self.Max.Enable(False)
                self.Length.Enable(True)
        else:
            self.staticText2.Enable(False)
            self.staticText3.Enable(False)
            self.staticText4.Enable(False)
            self.Min.Enable(False)
            self.Max.Enable(False)
            self.Length.Enable(False)

    def GetValues(self):
        name = self.Type.GetStringSelection()
        objtype = self.TypeDictionary[name][0]
        minval = int(self.Min.GetValue())
        maxval = int(self.Max.GetValue())
        length = int(self.Length.GetValue())
        return objtype, minval, maxval, length


# ------------------------------------------------------------------------------
#                          Editing Node Infos Dialog
# ------------------------------------------------------------------------------


[
    ID_NODEINFOSDIALOG, ID_NODEINFOSDIALOGNAME,
    ID_NODEINFOSDIALOGNODEID, ID_NODEINFOSDIALOGTYPE,
    ID_NODEINFOSDIALOGDEFAULTSTRINGSIZE, ID_NODEINFOSDIALOGDESCRIPTION,
    ID_NODEINFOSDIALOGSTATICTEXT1, ID_NODEINFOSDIALOGSTATICTEXT2,
    ID_NODEINFOSDIALOGSTATICTEXT3, ID_NODEINFOSDIALOGSTATICTEXT4,
    ID_NODEINFOSDIALOGSTATICTEXT5,
] = [wx.NewId() for _ in range(11)]


NODE_TYPES = ["master", "slave"]
NODE_TYPES_DICT = {node_type: node_type for node_type in NODE_TYPES}


class NodeInfosDialog(wx.Dialog):
    """Dialog for editing node infos."""
    # pylint: disable=attribute-defined-outside-init

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=0, flag=wx.GROW)
        parent.Add(self.NodeName, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText2, 0, border=0, flag=wx.GROW)
        parent.Add(self.NodeID, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText3, 0, border=0, flag=wx.GROW)
        parent.Add(self.Type, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText4, 0, border=0, flag=wx.GROW)
        parent.Add(self.DefaultStringSize, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText5, 0, border=0, flag=wx.GROW)
        parent.Add(self.Description, 0, border=0, flag=wx.GROW)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=10, vgap=5)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_NODEINFOSDIALOG,
            name='NodeInfosDialog', parent=parent, pos=wx.Point(376, 223),
            size=wx.Size(300, 280), style=wx.DEFAULT_DIALOG_STYLE,
            title='Node infos',
        )
        self.SetClientSize(wx.Size(300, 280))

        self.staticText1 = wx.StaticText(id=ID_NODEINFOSDIALOGSTATICTEXT1,
            label='Name:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.NodeName = wx.TextCtrl(id=ID_NODEINFOSDIALOGNAME, name='NodeName',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=0, value='',
        )

        self.staticText2 = wx.StaticText(id=ID_NODEINFOSDIALOGSTATICTEXT2,
            label='Node ID:', name='staticText2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.NodeID = wx.TextCtrl(id=ID_NODEINFOSDIALOGNODEID, name='NodeID',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 25),
            style=wx.TE_RIGHT, value='',
        )

        self.staticText3 = wx.StaticText(id=ID_NODEINFOSDIALOGSTATICTEXT3,
            label='Type:', name='staticText3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.Type = wx.ComboBox(choices=[], id=ID_NODEINFOSDIALOGTYPE,
            name='Type', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 28), style=wx.CB_READONLY,
        )

        self.staticText4 = wx.StaticText(id=ID_NODEINFOSDIALOGSTATICTEXT4,
            label='Default String Size:', name='staticText4', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.DefaultStringSize = wx.SpinCtrl(id=ID_NODEINFOSDIALOGDEFAULTSTRINGSIZE,
            name='DefaultStringSize', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 25), style=wx.TE_RIGHT,
        )

        self.staticText5 = wx.StaticText(id=ID_NODEINFOSDIALOGSTATICTEXT5,
            label='Description:', name='staticText5', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.Description = wx.TextCtrl(id=ID_NODEINFOSDIALOGDESCRIPTION,
            name='Description', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=0, value='',
        )

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

        self._init_sizers()

    def __init__(self, parent):
        self._init_ctrls(parent)

        self.staticText2.Hide()
        self.NodeID.Hide()

        for node_type in NODE_TYPES:
            self.Type.Append(node_type)

    def OnOK(self, event):  # pylint: disable=unused-argument
        name = self.NodeName.GetValue()
        message = ""
        if name:
            good = not name[0].isdigit()
            for item in name.split("_"):
                good &= item.isalnum()
            if not good:
                message = (
                    "Node name can't be undefined or start with a digit and "
                    "must be composed of alphanumerical characters or underscore!"
                )
        if message:
            try:
                _ = int(self.NodeID.GetValue(), 16)
            except ValueError as exc:
                log.debug("ValueError: '%s': %s", self.NodeID.GetValue(), exc)
                message = "Node ID must be integer!"
        if message:
            display_error_dialog(self, message)
            self.NodeName.SetFocus()
        else:
            self.EndModal(wx.ID_OK)

    def SetValues(self, name, nodeid, nodetype, description, defaultstringsize):
        self.NodeName.SetValue(name)
        self.NodeID.SetValue(f"0x{nodeid:02X}")
        self.Type.SetStringSelection(nodetype)
        self.Description.SetValue(description)
        self.DefaultStringSize.SetValue(defaultstringsize)

    def GetValues(self):
        name = self.NodeName.GetValue()
        nodeid = int(self.NodeID.GetValue(), 16)
        nodetype = NODE_TYPES_DICT[self.Type.GetStringSelection()]
        description = self.Description.GetValue()
        defaultstringsize = self.DefaultStringSize.GetValue()
        return name, nodeid, nodetype, description, defaultstringsize


# ------------------------------------------------------------------------------
#                          Create New Node Dialog
# ------------------------------------------------------------------------------


[
    ID_CREATENODEDIALOG, ID_CREATENODEDIALOGEMERGENCY,
    ID_CREATENODEDIALOGGENSYNC, ID_CREATENODEDIALOGSPACER,
    ID_CREATENODEDIALOGNAME, ID_CREATENODEDIALOGNMT_HEARTBEAT,
    ID_CREATENODEDIALOGNMT_NODEGUARDING, ID_CREATENODEDIALOGNMT_NONE,
    ID_CREATENODEDIALOGNODEID, ID_CREATENODEDIALOGPROFILE,
    ID_CREATENODEDIALOGSAVECONFIG, ID_CREATENODEDIALOGSTATICTEXT1,
    ID_CREATENODEDIALOGSTATICTEXT2, ID_CREATENODEDIALOGSTATICTEXT3,
    ID_CREATENODEDIALOGSTATICTEXT4, ID_CREATENODEDIALOGSTATICTEXT5,
    ID_CREATENODEDIALOGSTATICTEXT6, ID_CREATENODEDIALOGSTATICTEXT7,
    ID_CREATENODEDIALOGSTOREEDS, ID_CREATENODEDIALOGDESCRIPTION,
    ID_CREATENODEDIALOGTYPE,
] = [wx.NewId() for _ in range(21)]


class CreateNodeDialog(wx.Dialog):
    """Dialog for creating new node."""
    # pylint: disable=attribute-defined-outside-init

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.TopBoxSizer, 0, border=0, flag=wx.GROW)
        parent.Add(self.staticText7, 0, border=0, flag=wx.GROW)
        parent.Add(self.Description, 0, border=0, flag=wx.GROW)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)

    def _init_coll_TopBoxSizer_Items(self, parent):
        parent.Add(self.LeftBoxSizer, 1, border=10, flag=wx.GROW | wx.RIGHT)
        parent.Add(self.RightGridSizer, 1, border=10, flag=wx.GROW | wx.LEFT)

    def _init_coll_LeftBoxSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.Type, 0, border=10, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.staticText2, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.NodeName, 0, border=10, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.staticText3, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.NodeID, 0, border=10, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.staticText4, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.Profile, 0, border=20, flag=wx.GROW | wx.BOTTOM)

    def _init_coll_RightGridSizer_Items(self, parent):
        parent.Add(self.RightTopGridSizer, 0, border=0, flag=wx.GROW)
        parent.Add(self.Spacer, 0, border=0, flag=wx.GROW)
        parent.Add(self.RightBottomGridSizer, 0, border=0, flag=wx.GROW)

    def _init_coll_RightGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(1)

    def _init_coll_RightTopGridSizer_Items(self, parent):
        parent.Add(self.staticText5, 0, border=0, flag=wx.GROW)
        parent.Add(self.NMT_None, 0, border=0, flag=wx.GROW)
        parent.Add(self.NMT_NodeGuarding, 0, border=0, flag=wx.GROW)
        parent.Add(self.NMT_Heartbeat, 0, border=0, flag=wx.GROW)

    def _init_coll_RightTopGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)

    def _init_coll_RightBottomGridSizer_Items(self, parent):
        parent.Add(self.staticText6, 0, border=0, flag=wx.GROW)
        parent.Add(self.DS302, 0, border=0, flag=wx.GROW)
        parent.Add(self.GenSYNC, 0, border=0, flag=wx.GROW)
        parent.Add(self.Emergency, 0, border=0, flag=wx.GROW)
        parent.Add(self.SaveConfig, 0, border=0, flag=wx.GROW)
        parent.Add(self.StoreEDS, 0, border=0, flag=wx.GROW)

    def _init_coll_RightBottomGridSizer_Growables(self, parent):
        parent.AddGrowableCol(0)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.FlexGridSizer(cols=1, hgap=5, rows=3, vgap=0)
        self.TopBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.LeftBoxSizer = wx.BoxSizer(wx.VERTICAL)
        self.RightGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=3, vgap=5)
        self.RightTopGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=4, vgap=0)
        self.RightBottomGridSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=6, vgap=0)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)
        self._init_coll_TopBoxSizer_Items(self.TopBoxSizer)
        self._init_coll_LeftBoxSizer_Items(self.LeftBoxSizer)
        self._init_coll_RightGridSizer_Items(self.RightGridSizer)
        self._init_coll_RightGridSizer_Growables(self.RightGridSizer)
        self._init_coll_RightTopGridSizer_Items(self.RightTopGridSizer)
        self._init_coll_RightTopGridSizer_Growables(self.RightTopGridSizer)
        self._init_coll_RightBottomGridSizer_Items(self.RightBottomGridSizer)
        self._init_coll_RightBottomGridSizer_Growables(self.RightBottomGridSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent, buttons):
        wx.Dialog.__init__(self, id=ID_CREATENODEDIALOG,
            name='CreateNodeDialog', parent=parent, pos=wx.Point(376, 223),
            size=wx.Size(450, 350), style=wx.DEFAULT_DIALOG_STYLE,
            title='Create a new Node',
        )
        self.SetClientSize(wx.Size(450, 350))

        self.staticText1 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT1,
            label='Type:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText2 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT2,
            label='Name:', name='staticText2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText3 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT3,
            label='Node ID:', name='staticText3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.staticText4 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT4,
            label='Profile:', name='staticText4', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.Type = wx.ComboBox(choices=[], id=ID_CREATENODEDIALOGTYPE,
            name='Type', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 28), style=wx.CB_READONLY,
        )

        self.NodeName = wx.TextCtrl(id=ID_CREATENODEDIALOGNAME, name='NodeName',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=0, value='',
        )

        self.NodeID = wx.TextCtrl(id=ID_CREATENODEDIALOGNODEID, name='NodeID',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24),
            style=wx.TE_RIGHT, value='',
        )

        self.Profile = wx.ComboBox(choices=[], id=ID_CREATENODEDIALOGPROFILE,
            name='Profile', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 28), style=wx.CB_READONLY,
        )
        self.Profile.Bind(wx.EVT_COMBOBOX, self.OnProfileChoice,
            id=ID_CREATENODEDIALOGPROFILE,
        )

        self.staticText5 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT5,
            label='Network Management:', name='staticText5',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.NMT_None = wx.RadioButton(id=ID_CREATENODEDIALOGNMT_NONE,
            label='None', name='NMT_None', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=wx.RB_GROUP,
        )
        self.NMT_None.SetValue(True)

        self.NMT_NodeGuarding = wx.RadioButton(id=ID_CREATENODEDIALOGNMT_NODEGUARDING,
            label='Node Guarding', name='NMT_NodeGuarding', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.NMT_NodeGuarding.SetValue(False)

        self.NMT_Heartbeat = wx.RadioButton(id=ID_CREATENODEDIALOGNMT_HEARTBEAT,
            label='Heartbeat', name='NMT_Heartbeat', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.NMT_Heartbeat.SetValue(False)

        self.staticText6 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT6,
            label='Options:', name='staticText6', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.DS302 = wx.CheckBox(id=ID_CREATENODEDIALOGGENSYNC,
            label='DS-302 Profile', name='DS302', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.DS302.SetValue(False)
        # self.DS302.Enable(False)

        self.GenSYNC = wx.CheckBox(id=ID_CREATENODEDIALOGGENSYNC,
            label='Generate SYNC', name='GenSYNC', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.GenSYNC.SetValue(False)

        self.Emergency = wx.CheckBox(id=ID_CREATENODEDIALOGEMERGENCY,
            label='Emergency support', name='Emergency',
            parent=self, pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.Emergency.SetValue(False)

        self.SaveConfig = wx.CheckBox(id=ID_CREATENODEDIALOGSAVECONFIG,
            label='Save Configuration', name='SaveConfig', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.SaveConfig.SetValue(False)
        self.SaveConfig.Enable(False)

        self.StoreEDS = wx.CheckBox(id=ID_CREATENODEDIALOGSTOREEDS,
            label='Store EDS', name='StoreEDS', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 24), style=0,
        )
        self.StoreEDS.SetValue(False)
        self.StoreEDS.Hide()

        self.staticText7 = wx.StaticText(id=ID_CREATENODEDIALOGSTATICTEXT7,
            label='Description:', name='staticText7', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.Description = wx.TextCtrl(id=ID_CREATENODEDIALOGDESCRIPTION,
            name='Description', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=0, value='',
        )

        self.Spacer = wx.Panel(id=ID_CREATENODEDIALOGSPACER,
            name='Spacer', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 0), style=wx.TAB_TRAVERSAL,
        )

        self.ButtonSizer = self.CreateButtonSizer(buttons)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

        self._init_sizers()

    def __init__(self, parent, buttons=wx.OK | wx.CANCEL):
        self._init_ctrls(parent, buttons)

        self.staticText3.Hide()
        self.NodeID.Hide()

        self.NodeID.SetValue("0x00")
        for node_type in NODE_TYPES:
            self.Type.Append(node_type)
        self.Type.SetStringSelection("slave")
        self.Description.SetValue("")
        self.ListProfile = {"None": ""}
        self.Profile.Append("None")
        self.Directory = str(objdictgen.PROFILE_DIRECTORIES[-1])
        for p in objdictgen.PROFILES:
            self.ListProfile[p.stem] = str(p)
            self.Profile.Append(p.stem)
        self.Profile.Append("Other")
        self.Profile.SetStringSelection("None")
        self.NodeName.SetFocus()

    def OnOK(self, event):  # pylint: disable=unused-argument
        name = self.NodeName.GetValue()
        message = ""
        if name:
            if not ((not name[0].isdigit())
                    and all(item.isalnum() for item in name.split("_"))
            ):
                message = (
                    "Node name can't be undefined or start with a digit "
                    "and must be composed of alphanumerical characters or underscore!"
                )
        if message:
            try:
                _ = int(self.NodeID.GetValue(), 16)
            except ValueError as exc:
                log.debug("ValueError: '%s': %s", self.NodeID.GetValue(), exc)
                message = "Node ID must be integer!"
        if message:
            display_error_dialog(self, message)
            self.NodeName.SetFocus()
        else:
            self.EndModal(wx.ID_OK)

    def GetValues(self):
        name = self.NodeName.GetValue()
        nodeid = 0
        if self.NodeID.GetValue():
            nodeid = int(self.NodeID.GetValue(), 16)
        nodetype = NODE_TYPES_DICT[self.Type.GetStringSelection()]
        description = self.Description.GetValue()
        return name, nodeid, nodetype, description

    def GetProfile(self):
        name = self.Profile.GetStringSelection()
        return name, self.ListProfile[name]

    def GetNMTManagement(self) -> str:
        if self.NMT_None.GetValue():
            return "None"
        if self.NMT_NodeGuarding.GetValue():
            return "NodeGuarding"
        if self.NMT_Heartbeat.GetValue():
            return "Heartbeat"
        return ""

    def GetOptions(self) -> list[str]:
        options: list[str] = []
        if self.DS302.GetValue():
            options.append("DS302")
        if self.GenSYNC.GetValue():
            options.append("GenSYNC")
        if self.Emergency.GetValue():
            options.append("Emergency")
        if self.SaveConfig.GetValue():
            options.append("SaveConfig")
        if self.StoreEDS.GetValue():
            options.append("StoreEDS")
        return options

    def OnProfileChoice(self, event):
        if self.Profile.GetStringSelection() == "Other":
            with wx.FileDialog(
                self, "Choose a file", self.Directory, "",
                "OD Profile files (*.prf)|*.prf|All files|*.*",
            ) as dialog:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                filepath = dialog.GetPath()

            if os.path.isfile(filepath):
                name = os.path.splitext(os.path.basename(filepath))[0]
                self.ListProfile[name] = filepath
                length = self.Profile.GetCount()
                self.Profile.Insert(name, length - 2)
                self.Profile.SetStringSelection(name)
            else:
                self.Profile.SetStringSelection("None")
        event.Skip()


# ------------------------------------------------------------------------------
#                            ADD Slave to NodeList Dialog
# ------------------------------------------------------------------------------

[
    ID_ADDSLAVEDIALOG, ID_ADDSLAVEDIALOGSLAVENAME,
    ID_ADDSLAVEDIALOGSLAVENODEID, ID_ADDSLAVEDIALOGEDSFILE,
    ID_ADDSLAVEDIALOGIMPORTEDS, ID_ADDSLAVEDIALOGSTATICTEXT1,
    ID_ADDSLAVEDIALOGSTATICTEXT2, ID_ADDSLAVEDIALOGSTATICTEXT3,
] = [wx.NewId() for _ in range(8)]


class AddSlaveDialog(wx.Dialog):
    """UI for adding a slave to the nodelist."""
    # pylint: disable=attribute-defined-outside-init

    def _init_coll_flexGridSizer1_Items(self, parent):
        parent.Add(self.MainSizer, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_flexGridSizer1_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.SlaveName, 0, border=10, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.staticText2, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.SlaveNodeID, 0, border=10, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.staticText3, 0, border=5, flag=wx.GROW | wx.BOTTOM)
        parent.Add(self.BottomSizer, 0, border=0, flag=wx.GROW)

    def _init_coll_BottomSizer_Items(self, parent):
        parent.Add(self.EDSFile, 0, border=4, flag=wx.GROW | wx.TOP | wx.BOTTOM)
        parent.Add(self.ImportEDS, 0, border=0, flag=0)

    def _init_coll_BottomSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(0)

    def _init_sizers(self):
        self.flexGridSizer1 = wx.FlexGridSizer(cols=1, hgap=0, rows=2, vgap=10)
        self.MainSizer = wx.BoxSizer(wx.VERTICAL)
        self.BottomSizer = wx.FlexGridSizer(cols=2, hgap=5, rows=1, vgap=0)

        self._init_coll_flexGridSizer1_Items(self.flexGridSizer1)
        self._init_coll_flexGridSizer1_Growables(self.flexGridSizer1)
        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_BottomSizer_Items(self.BottomSizer)
        self._init_coll_BottomSizer_Growables(self.BottomSizer)

        self.SetSizer(self.flexGridSizer1)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_ADDSLAVEDIALOG,
            name='AddSlaveDialog', parent=parent, pos=wx.Point(376, 223),
            size=wx.Size(300, 250), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            title='Add a slave to nodelist',
        )
        self.SetClientSize(wx.Size(300, 250))

        self.staticText1 = wx.StaticText(id=ID_ADDSLAVEDIALOGSTATICTEXT1,
            label='Slave Name:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.SlaveName = wx.TextCtrl(id=ID_ADDSLAVEDIALOGSLAVENAME,
            name='SlaveName', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=0,
        )

        self.staticText2 = wx.StaticText(id=ID_ADDSLAVEDIALOGSTATICTEXT2,
            label='Slave Node ID:', name='staticText2', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.SlaveNodeID = wx.TextCtrl(id=ID_ADDSLAVEDIALOGSLAVENODEID,
            name='SlaveName', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 24), style=wx.ALIGN_RIGHT
        )

        self.staticText3 = wx.StaticText(id=ID_ADDSLAVEDIALOGSTATICTEXT3,
            label='EDS File:', name='staticText3', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(0, 17), style=0,
        )

        self.EDSFile = wx.ComboBox(id=ID_ADDSLAVEDIALOGEDSFILE,
            name='EDSFile', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 28), style=wx.CB_READONLY,
        )

        self.ImportEDS = wx.Button(id=ID_ADDSLAVEDIALOGIMPORTEDS, label='Import EDS',
            name='ImportEDS', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(100, 32), style=0,
        )
        self.ImportEDS.Bind(wx.EVT_BUTTON, self.OnImportEDSButton,
            id=ID_ADDSLAVEDIALOGIMPORTEDS,
        )

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL | wx.CENTRE)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

        self._init_sizers()

    def __init__(self, parent):
        self._init_ctrls(parent)

        self.SlaveNodeID.SetValue("0x00")

    def OnOK(self, event):  # pylint: disable=unused-argument
        error = []
        if not self.SlaveName.GetValue():
            error.append("Slave Name")
        if not self.SlaveNodeID.GetValue():
            error.append("Slave Node ID")
        if not self.EDSFile.GetStringSelection():
            error.append("EDS File")
        if len(error) > 0:
            text = ""
            for i, item in enumerate(error):
                if i == 0:
                    text += item
                elif i == len(error) - 1:
                    text += f" and {item}"
                else:
                    text += f", {item}"
            display_error_dialog(self, f"Form isn't complete. {text} must be filled!")
        else:
            try:
                nodestr = self.SlaveNodeID.GetValue()
                if "x" in nodestr:
                    nodeid = int(nodestr, 16)
                else:
                    nodeid = int(nodestr)
            except ValueError as exc:
                log.debug("ValueError: '%s': %s", self.SlaveNodeID.GetValue(), exc)
                display_error_dialog(self, "Slave Node ID must be a value in decimal or hexadecimal!")
                return
            if not 0 <= nodeid <= 127:
                display_error_dialog(self, "Slave Node ID must be between 0 and 127!")
            elif nodeid == self.NodeList.GetMasterNodeID() or nodeid in self.NodeList.GetSlaveIDs():
                display_error_dialog(self, "A Node with this ID already exist in the network!")
            else:
                self.EndModal(wx.ID_OK)

    def OnImportEDSButton(self, event):
        with wx.FileDialog(
            self, "Choose an EDS file", os.path.expanduser("~"), "",
            "EDS files (*.eds)|*.eds|All files|*.*",
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            filepath = dialog.GetPath()

        if os.path.isfile(filepath):
            edsfile = self.NodeList.GetEDSFilePath(filepath)
            if os.path.isfile(edsfile):
                with wx.MessageDialog(self,
                    "EDS file already imported\nWould you like to replace it ?",
                    "Question", wx.YES_NO | wx.ICON_QUESTION,
                ) as dialog:
                    if dialog.ShowModal() == wx.ID_YES:
                        try:
                            self.NodeList.ImportEDSFile(filepath)
                        except Exception:  # pylint: disable=broad-except
                            display_exception_dialog(self)

        self.RefreshEDSFile()
        event.Skip()

    def RefreshEDSFile(self):
        selection = self.EDSFile.GetStringSelection()
        self.EDSFile.Clear()
        for option in self.NodeList.EDSNodes:
            self.EDSFile.Append(option)
        if self.EDSFile.FindString(selection) != wx.NOT_FOUND:
            self.EDSFile.SetStringSelection(selection)

    def SetNodeList(self, nodelist):
        self.NodeList = nodelist
        self.RefreshEDSFile()

    def GetValues(self) -> TGetValues:
        values: TGetValues = {}
        values["slaveName"] = self.SlaveName.GetValue()
        nodestr = self.SlaveNodeID.GetValue()
        if "x" in nodestr:
            values["slaveNodeID"] = int(nodestr, 16)
        else:
            values["slaveNodeID"] = int(nodestr)
        values["edsFile"] = self.EDSFile.GetStringSelection()
        return values

# ------------------------------------------------------------------------------
#                            Editing DCF Entry Dialog
# ------------------------------------------------------------------------------


DCF_ENTRY_TABLE_COLNAMES = ["Index", "Subindex", "Size", "Value"]


class DCFEntryValuesTable(wx.grid.GridTableBase):
    # pylint: disable=attribute-defined-outside-init

    """
    A custom wxGrid Table using user supplied data
    """
    def __init__(self, parent: DCFEntryValuesDialog, data, colnames):
        # The base class must be initialized *first*
        wx.grid.GridTableBase.__init__(self)
        self.data = data
        self.colnames = colnames
        self.Parent = parent
        # NOTE
        # we need to store the row length and col length to
        # see if the table has changed size
        self._rows = self.GetNumberRows()
        self._cols = self.GetNumberCols()

    def GetNumberCols(self):
        return len(self.colnames)

    def GetNumberRows(self):
        return len(self.data)

    def GetColLabelValue(self, col, translate=True):
        if col < len(self.colnames):
            if translate:
                return self.colnames[col]
            return self.colnames[col]
        return None

    def GetValue(self, row, col):
        if row < self.GetNumberRows():
            return str(self.data[row].get(self.GetColLabelValue(col, False), ""))
        return None

    def GetEditor(self, row, col):
        if row < self.GetNumberRows():
            return self.editors[row].get(self.GetColLabelValue(col, False), "")
        return None

    def GetValueByName(self, row, colname):
        return self.data[row].get(colname)

    def SetValue(self, row, col, value):
        if col < len(self.colnames):
            self.data[row][self.GetColLabelValue(col, False)] = value

    def ResetView(self, grid):
        """
        (wx.grid.Grid) -> Reset the grid view.   Call this to
        update the grid if rows and columns have been added or deleted
        """
        grid.BeginBatch()
        for current, new, delmsg, addmsg in [
            (
                self._rows, self.GetNumberRows(),
                wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED
            ),(
                self._cols, self.GetNumberCols(), wx.grid.GRIDTABLE_NOTIFY_COLS_DELETED,
                wx.grid.GRIDTABLE_NOTIFY_COLS_APPENDED
            ),
        ]:
            if new < current:
                msg = wx.grid.GridTableMessage(self, delmsg, new, current - new)
                grid.ProcessTableMessage(msg)
            elif new > current:
                msg = wx.grid.GridTableMessage(self, addmsg, new - current)
                grid.ProcessTableMessage(msg)
                self.UpdateValues(grid)
        grid.EndBatch()

        self._rows = self.GetNumberRows()
        self._cols = self.GetNumberCols()
        # update the column rendering scheme
        self._updateColAttrs(grid)

        # update the scrollbars and the displayed part of the grid
        grid.AdjustScrollbars()
        grid.ForceRefresh()

    def UpdateValues(self, grid):
        """Update all displayed values"""
        # This sends an event to the grid table to update all of the values
        # FIXME: This symbol has probably been removed from wx. Needs more investigation
        msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        grid.ProcessTableMessage(msg)

    def _updateColAttrs(self, grid):
        """
        wx.grid.Grid -> update the column attributes to add the
        appropriate renderer given the column name.

        Otherwise default to the default renderer.
        """

        for row in range(self.GetNumberRows()):
            for col in range(self.GetNumberCols()):
                editor = wx.grid.GridCellTextEditor()
                renderer = wx.grid.GridCellStringRenderer()

                grid.SetReadOnly(row, col, self.Parent.Editable)
                grid.SetCellEditor(row, col, editor)
                grid.SetCellRenderer(row, col, renderer)

                grid.SetCellBackgroundColour(row, col, wx.WHITE)

    def SetData(self, data):
        self.data = data

    def Empty(self):
        self.data = []
        self.editors = []


[
    ID_DCFENTRYVALUESDIALOG, ID_DCFENTRYVALUESDIALOGVALUESGRID,
    ID_DCFENTRYVALUESDIALOGADDBUTTON, ID_DCFENTRYVALUESDIALOGDELETEBUTTON,
    ID_DCFENTRYVALUESDIALOGUPBUTTON, ID_DCFENTRYVALUESDIALOGDOWNBUTTON,
    ID_VARIABLEEDITORPANELSTATICTEXT1,
] = [wx.NewId() for _ in range(7)]


class DCFEntryValuesDialog(wx.Dialog):
    """Dialog to edit DCF Entry values."""
    # pylint: disable=attribute-defined-outside-init

    def _init_coll_MainSizer_Items(self, parent):
        parent.Add(self.staticText1, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ValuesGrid, 0, border=20,
            flag=wx.GROW | wx.TOP | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonPanelSizer, 0,
            border=20, flag=wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT)
        parent.Add(self.ButtonSizer, 0, border=20,
            flag=wx.ALIGN_RIGHT | wx.BOTTOM | wx.LEFT | wx.RIGHT)

    def _init_coll_MainSizer_Growables(self, parent):
        parent.AddGrowableCol(0)
        parent.AddGrowableRow(1)

    def _init_coll_ButtonPanelSizer_Items(self, parent):
        parent.Add(self.UpButton, 0, border=5, flag=wx.ALL)
        parent.Add(self.AddButton, 0, border=5, flag=wx.ALL)
        parent.Add(self.DownButton, 0, border=5, flag=wx.ALL)
        parent.Add(self.DeleteButton, 0, border=5, flag=wx.ALL)

    def _init_sizers(self):
        self.MainSizer = wx.FlexGridSizer(cols=1, hgap=0, rows=3, vgap=0)
        self.ButtonPanelSizer = wx.BoxSizer(wx.HORIZONTAL)

        self._init_coll_MainSizer_Items(self.MainSizer)
        self._init_coll_MainSizer_Growables(self.MainSizer)
        self._init_coll_ButtonPanelSizer_Items(self.ButtonPanelSizer)

        self.SetSizer(self.MainSizer)

    def _init_ctrls(self, parent):
        wx.Dialog.__init__(self, id=ID_DCFENTRYVALUESDIALOG,
            name='DCFEntryValuesDialog', parent=parent, pos=wx.Point(376, 223),
            size=wx.Size(400, 300), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            title='Edit DCF Entry Values',
        )
        self.SetClientSize(wx.Size(400, 300))

        self.staticText1 = wx.StaticText(id=ID_VARIABLEEDITORPANELSTATICTEXT1,
            label='Entry Values:', name='staticText1', parent=self,
            pos=wx.Point(0, 0), size=wx.Size(95, 17), style=0,
        )

        self.ValuesGrid = wx.grid.Grid(id=ID_DCFENTRYVALUESDIALOGVALUESGRID,
            name='ValuesGrid', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(0, 150), style=wx.VSCROLL,
        )
        self.ValuesGrid.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL, False,
            'Sans'))
        self.ValuesGrid.SetLabelFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.NORMAL,
            False, 'Sans'))
        self.ValuesGrid.SetRowLabelSize(0)
        self.ValuesGrid.SetSelectionBackground(wx.WHITE)
        self.ValuesGrid.SetSelectionForeground(wx.BLACK)
        self.ValuesGrid.Bind(wx.grid.EVT_GRID_CELL_CHANGING, self.OnValuesGridCellChange)
        self.ValuesGrid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnValuesGridSelectCell)

        self.AddButton = wx.Button(id=ID_DCFENTRYVALUESDIALOGADDBUTTON, label='Add',
            name='AddButton', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(72, 32), style=0,
        )
        self.Bind(wx.EVT_BUTTON, self.OnAddButton, id=ID_DCFENTRYVALUESDIALOGADDBUTTON)

        self.DeleteButton = wx.Button(id=ID_DCFENTRYVALUESDIALOGDELETEBUTTON, label='Delete',
            name='DeleteButton', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(72, 32), style=0,
        )
        self.Bind(wx.EVT_BUTTON, self.OnDeleteButton, id=ID_DCFENTRYVALUESDIALOGDELETEBUTTON)

        self.UpButton = wx.Button(id=ID_DCFENTRYVALUESDIALOGUPBUTTON, label='^',
            name='UpButton', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(32, 32), style=0,
        )
        self.Bind(wx.EVT_BUTTON, self.OnUpButton, id=ID_DCFENTRYVALUESDIALOGUPBUTTON)

        self.DownButton = wx.Button(id=ID_DCFENTRYVALUESDIALOGDOWNBUTTON, label='v',
            name='DownButton', parent=self, pos=wx.Point(0, 0),
            size=wx.Size(32, 32), style=0,
        )
        self.Bind(wx.EVT_BUTTON, self.OnDownButton, id=ID_DCFENTRYVALUESDIALOGDOWNBUTTON)

        self.ButtonSizer = self.CreateButtonSizer(wx.OK | wx.CANCEL | wx.CENTRE)

        self._init_sizers()

    def __init__(self, parent, editable=True):
        self._init_ctrls(parent)

        self.Values = []
        self.DefaultValue = {"Index": 0, "Subindex": 0, "Size": 1, "Value": 0}
        self.Editable = editable

        self.Table = DCFEntryValuesTable(self, [], DCF_ENTRY_TABLE_COLNAMES)
        self.ValuesGrid.SetTable(self.Table)

    def OnValuesGridCellChange(self, event):
        row, col = event.GetRow(), event.GetCol()
        colname = self.Table.GetColLabelValue(col)
        value = self.Table.GetValue(row, col)
        try:
            self.Values[row][colname] = int(value, 16)  # pyright: ignore[reportArgumentType]
        except ValueError:
            display_error_dialog(self, f"'{value}' is not a valid value!")
        wx.CallAfter(self.RefreshValues)
        event.Skip()

    def OnValuesGridSelectCell(self, event):
        wx.CallAfter(self.RefreshButtons)
        event.Skip()

    def RefreshButtons(self):
        row = self.ValuesGrid.GetGridCursorRow()
        length = len(self.Table.data)
        self.AddButton.Enable(self.Editable)
        self.DeleteButton.Enable(self.Editable and length > 0)
        self.UpButton.Enable(self.Editable and row > 0)
        self.DownButton.Enable(self.Editable and row < length - 1)

    def OnAddButton(self, event):
        new_row = self.DefaultValue.copy()
        self.Values.append(new_row)
        self.RefreshValues()
        event.Skip()

    def OnDeleteButton(self, event):
        row = self.ValuesGrid.GetGridCursorRow()
        self.Values.pop(row)
        self.RefreshValues()
        event.Skip()

    def OnUpButton(self, event):
        self.MoveValue(self.ValuesGrid.GetGridCursorRow(), -1)
        event.Skip()

    def OnDownButton(self, event):
        self.MoveValue(self.ValuesGrid.GetGridCursorRow(), 1)
        event.Skip()

    def MoveValue(self, value_index, move):
        new_index = max(0, min(value_index + move, len(self.Values) - 1))
        if new_index != value_index:
            self.Values.insert(new_index, self.Values.pop(value_index))
            col = self.ValuesGrid.GetGridCursorCol()
            self.RefreshValues()
            self.ValuesGrid.SetGridCursor(new_index, col)
            self.RefreshButtons()
        else:
            self.RefreshValues()

    def SetValues(self, values):
        # FIXME: THis function needs rewrite, as the map.be_to_le is not ported properly to py3
        self.Values = []
        if values:
            data = values[4:]
            current = 0
            for _ in range(maps.be_to_le(values[:4])):
                value = {}
                value["Index"] = maps.be_to_le(data[current:current + 2])
                value["Subindex"] = maps.be_to_le(data[current + 2:current + 3])
                size = maps.be_to_le(data[current + 3:current + 7])
                value["Size"] = size
                value["Value"] = maps.be_to_le(data[current + 7:current + 7 + size])
                current += 7 + size
                self.Values.append(value)
        self.RefreshValues()

    def GetValues(self):
        # FIXME: THis function needs rewrite, as the map.be_to_le is not ported properly to py3
        if len(self.Values) <= 0:
            return ""
        value = maps.le_to_be(len(self.Values), 4)
        for row in self.Values:
            value += maps.le_to_be(row["Index"], 2)
            value += maps.le_to_be(row["Subindex"], 1)
            value += maps.le_to_be(row["Size"], 4)
            value += maps.le_to_be(row["Value"], row["Size"])
        return value

    def RefreshValues(self):
        if len(self.Table.data) > 0:
            self.ValuesGrid.SetGridCursor(0, 0)
        data = []
        for value in self.Values:
            row = {}
            row["Index"] = f"{value['Index']:04X}"
            row["Subindex"] = f"{value['Subindex']:02X}"
            row["Size"] = f"{value['Size']:08X}"
            row["Value"] = ("{:0" + str(value['Size'] * 2) + "X}").format(value["Value"])
            data.append(row)
        self.Table.SetData(data)
        self.Table.ResetView(self.ValuesGrid)
        self.RefreshButtons()
