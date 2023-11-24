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

import traceback

import os
import sys
import platform
import time

import wx


# ------------------------------------------------------------------------------
#                               Exception Handler
# ------------------------------------------------------------------------------

def Display_Exception_Dialog(e_type, e_value, e_tb):
    trcbck_lst = []
    for i, line in enumerate(traceback.extract_tb(e_tb)):
        trcbck = " " + str(i + 1) + ". "
        if os.getcwd() not in line[0]:
            trcbck += "file : " + str(line[0]) + ",   "
        else:
            trcbck += "file : " + str(line[0][len(os.getcwd()):]) + ",   "
        trcbck += "line : " + str(line[1]) + ",   " + "function : " + str(line[2])
        trcbck_lst.append(trcbck)

    # Allow clicking....
    cap = wx.Window.GetCapture()
    if cap:
        cap.ReleaseMouse()

    dlg = wx.SingleChoiceDialog(None,
        ("""
            An error has occured.
            Click on OK for saving an error report.
            If appropriate please add an issue to the project on GitHub.
            Error:
        """
        + str(e_type) + " : " + str(e_value)),
        "Error",
        trcbck_lst)
    try:
        res = (dlg.ShowModal() == wx.ID_OK)
    finally:
        dlg.Destroy()

    return res


def Display_Error_Dialog(e_value):
    message = wx.MessageDialog(None, str(e_value), "Error", wx.OK | wx.ICON_ERROR)
    message.ShowModal()
    message.Destroy()


def get_last_traceback(tb):
    while tb.tb_next:
        tb = tb.tb_next
    return tb


def format_namespace(dic, indent='    '):
    return '\n'.join(['%s%s: %s' % (indent, k, repr(v)[:10000]) for k, v in dic.items()])


IGNORED_EXCEPTIONS = []  # a problem with a line in a module is only reported once per session


def AddExceptHook(path, app_version='[No version]'):  # , ignored_exceptions=[]):

    def handle_exception(e_type, e_value, e_traceback):
        traceback.print_exception(e_type, e_value, e_traceback)  # this is very helpful when there's an exception in the rest of this func
        last_tb = get_last_traceback(e_traceback)
        ex = (last_tb.tb_frame.f_code.co_filename, last_tb.tb_frame.f_lineno)
        if str(e_value).startswith("!!!"):  # FIXME: Special exception handling
            Display_Error_Dialog(e_value)
        elif ex not in IGNORED_EXCEPTIONS:
            IGNORED_EXCEPTIONS.append(ex)
            result = Display_Exception_Dialog(e_type, e_value, e_traceback)
            if result:
                info = {
                    'app-title': wx.GetApp().GetAppName(),  # app_title
                    'app-version': app_version,
                    'wx-version': wx.VERSION_STRING,
                    'wx-platform': wx.Platform,
                    'python-version': platform.python_version(),  # sys.version.split()[0],
                    'platform': platform.platform(),
                    'e-type': e_type,
                    'e-value': e_value,
                    'date': time.ctime(),
                    'cwd': os.getcwd(),
                }
                if e_traceback:
                    info['traceback'] = ''.join(traceback.format_tb(e_traceback)) + '%s: %s' % (e_type, e_value)
                    last_tb = get_last_traceback(e_traceback)
                    exception_locals = last_tb.tb_frame.f_locals  # the locals at the level of the stack trace where the exception actually occurred
                    info['locals'] = format_namespace(exception_locals)
                    if 'self' in exception_locals:
                        info['self'] = format_namespace(exception_locals['self'].__dict__)

                with open(path + os.sep + "bug_report_" + info['date'].replace(':', '-').replace(' ', '_') + ".txt", 'w') as output:
                    for a in sorted(info):
                        output.write(a + ":\n" + str(info[a]) + "\n\n")

    # sys.excepthook = lambda *args: wx.CallAfter(handle_exception, *args)
    sys.excepthook = handle_exception
