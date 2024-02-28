"""Object Dictionary tool for Canfestival, a CanOpen stack."""
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
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

import os
from pathlib import Path

from objdictgen.node import Node
from objdictgen.nodemanager import NodeManager

__version__ = "3.4"

# Shortcuts
LoadFile = Node.LoadFile
LoadJson = Node.LoadJson

ODG_PROGRAM = "odg"

SCRIPT_DIRECTORY = Path(__file__).parent

PROFILE_DIRECTORIES: list[Path] = [
    SCRIPT_DIRECTORY / 'config'
]

# Append the ODG_PROFILE_PATH to the PROFILE_DIRECTORIES
odgdir = os.environ.get('ODG_PROFILE_PATH', '')
for d in odgdir.split(";" if os.name == "nt" else ":;"):
    if d:
        PROFILE_DIRECTORIES.append(Path(d))

# Make list of all discoverable profiles
PROFILES: list[Path] = []
for p in PROFILE_DIRECTORIES:
    if p.is_dir():
        PROFILES.extend(p.glob('*.prf'))

JSON_SCHEMA = SCRIPT_DIRECTORY / 'schema' / 'od.schema.json'

__all__ = [
    "LoadFile",
    "LoadJson",
    "Node",
    "NodeManager",
]
