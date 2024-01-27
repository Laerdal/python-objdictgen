# -*- coding: utf-8 -*-
#
#    This file is based on objdictgen from CanFestival
#
#    Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
#    Copyright (C): Edouard TISSERANT, Francis DUPIN
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
import sys
from objdictgen.gen_cfile.standard import GenerateStandardFileContent
from objdictgen.gen_cfile.legacy import GenerateLegacyFileContent


def write_file(file_path: str, buffer: str):
    print(f"Writing file: {file_path}")
    try:
        with open(file_path, "wb") as f:
            f.write(buffer.encode('utf-8'))
    except (OSError, IsADirectoryError) as err:
        sys.stderr.write(f"Could not write file: {file_path}: {str(err)}")
        sys.exit(-1)


def GenerateCFile(cfilepath, node, pointers_dict=None, **kwargs):
    generate_file_content_methods = [GenerateStandardFileContent, GenerateLegacyFileContent]
    generate_file_content = generate_file_content_methods[kwargs.get("cfile_type")]
    pointers_dict = pointers_dict or {}
    filebase = os.path.splitext(cfilepath)[0]
    headerfilepath = f"{filebase}.h"
    content, header, header_defs = generate_file_content(node, os.path.basename(headerfilepath), pointers_dict)

    write_file(cfilepath, content)
    write_file(headerfilepath, header)
    write_file(f"{filebase}_objectdefines.h", header_defs)
