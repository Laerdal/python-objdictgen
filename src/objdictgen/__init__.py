#
#    Copyright (C) 2022-2023  Svein Seldal, Laerdal Medical AS
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

import os

from objdictgen.node import Node, ImportProfile, Find
from objdictgen.nodemanager import NodeManager
from objdictgen.maps import OD

# Shortcuts
LoadFile = Node.LoadFile
LoadJson = Node.LoadJson

ODG_PROGRAM = "odg"
ODG_VERSION = "3.4"

SCRIPT_DIRECTORY = os.path.split(__file__)[0]

PROFILE_DIRECTORIES = [os.path.join(SCRIPT_DIRECTORY, 'config')]
odgdir = os.environ.get('ODG_PROFILE_DIR')
if odgdir:
    PROFILE_DIRECTORIES.append(odgdir)

JSON_SCHEMA = os.path.join(SCRIPT_DIRECTORY, 'schema', 'od.schema.json')

__all__ = [
    "Node",
    "ImportProfile",
    "Find",
    "LoadFile",
    "LoadJson",
    "NodeManager",
    "OD",
]
