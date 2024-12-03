"""Generate C file from a object dictionary node for canfestival."""
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
# Copyright (C): Edouard TISSERANT, Francis DUPIN
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

import re
from collections import UserDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from objdictgen.maps import OD
from objdictgen.typing import NodeProtocol, TODValue, TPath

RE_WORD = re.compile(r'([a-zA-Z_0-9]*)')
RE_TYPE = re.compile(r'([\_A-Z]*)([0-9]*)')
RE_RANGE = re.compile(r'([\_A-Z]*)([0-9]*)\[([\-0-9]*)-([\-0-9]*)\]')
RE_STARTS_WITH_DIGIT = re.compile(r'^(\d.*)')
RE_NOTW = re.compile(r"[^\w]")

CATEGORIES: list[tuple[str, int, int]] = [
    ("SDO_SVR", 0x1200, 0x127F), ("SDO_CLT", 0x1280, 0x12FF),
    ("PDO_RCV", 0x1400, 0x15FF), ("PDO_RCV_MAP", 0x1600, 0x17FF),
    ("PDO_TRS", 0x1800, 0x19FF), ("PDO_TRS_MAP", 0x1A00, 0x1BFF)
]
INDEX_CATEGORIES = ["firstIndex", "lastIndex"]

FILE_HEADER = """
/* File generated by gen_cfile.py. Should not be modified. */
"""


@dataclass
class TypeInfos:
    """Type infos for a type."""
    type: str
    size: int|None
    ctype: str
    is_unsigned: bool


class Text:
    """Helper class for formatting text. The class store a string and supports
    concatenation and formatting. Operators '+' and '+=' can be used to add
    strings without formatting and '%=' can be used to add strings with
    formatting. The string is formatted with varaibled from the context 
    dictionary.

    This exists as a workaround until the strings have been converted to
    proper f-strings.
    """

    # FIXME: Remove all %= entries, use f-strings instead, and delete this class

    def __init__(self, context: CFileContext, text: str):
        self.text: str = text
        self.context: CFileContext = context

    def __iadd__(self, other: str|Text) -> Text:
        """Add a string to the text without formatting."""
        self.text += str(other)
        return self

    def __add__(self, other: str|Text) -> Text:
        """Add a string to the text without formatting."""
        return Text(self.context, self.text + str(other))

    def __imod__(self, other: str) -> Text:
        """Add a string to the text with formatting."""
        self.text += other.format(**self.context)
        return self

    def __str__(self) -> str:
        """Return the text."""
        return self.text


class CFileContext(UserDict):
    """Context for generating C file. It serves as a dictionary to store data
    and as a helper for formatting text.
    """
    internal_types: dict[str, TypeInfos]
    default_string_size: int = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.internal_types = {}

    def __getattr__(self, name: str) -> Any:
        """Look up unknown attributes in the data dictionary."""
        return self.data[name]

    # FIXME: Delete this method when everything is converted to f-strings
    def text(self, s: str = "") -> Text:
        """Start a new text object"""
        return Text(self, s)

    # FIXME: Delete this method when everything is converted to f-strings
    def ftext(self, s: str) -> Text:
        """Format a text string."""
        return Text(self, "").__imod__(s)  # pylint: disable=unnecessary-dunder-call

    def get_valid_type_infos(self, typename: str, items=None) -> TypeInfos:
        """Get valid type infos from a typename.
        """

        # Return cached typeinfos
        if typename in self.internal_types:
            return self.internal_types[typename]

        items = items or []
        result = RE_TYPE.match(typename)
        if not result:
            # FIXME: The !!! is for special UI handling
            raise ValueError(f"!!! '{typename}' isn't a valid type for CanFestival.")

        if result[1] == "UNSIGNED" and int(result[2]) in [i * 8 for i in range(1, 9)]:
            typeinfos = TypeInfos(f"UNS{result[2]}", None, f"uint{result[2]}", True)
        elif result[1] == "INTEGER" and int(result[2]) in [i * 8 for i in range(1, 9)]:
            typeinfos = TypeInfos(f"INTEGER{result[2]}", None, f"int{result[2]}", False)
        elif result[1] == "REAL" and int(result[2]) in (32, 64):
            typeinfos = TypeInfos(f"{result[1]}{result[2]}", None, f"real{result[2]}", False)
        elif result[1] in ["VISIBLE_STRING", "OCTET_STRING"]:
            size = self.default_string_size
            for item in items:
                size = max(size, len(item))
            if result[2]:
                size = max(size, int(result[2]))
            typeinfos = TypeInfos("UNS8", size, "visible_string", False)
        elif result[1] == "DOMAIN":
            size = 0
            for item in items:
                size = max(size, len(item))
            typeinfos = TypeInfos("UNS8", size, "domain", False)
        elif result[1] == "BOOLEAN":
            typeinfos = TypeInfos("UNS8", None, "boolean", False)
        else:
            # FIXME: The !!! is for special UI handling
            raise ValueError(f"!!! '{typename}' isn't a valid type for CanFestival.")

        # Cache the typeinfos
        if typeinfos.ctype not in ["visible_string", "domain"]:
            self.internal_types[typename] = typeinfos
        return typeinfos


def format_name(name: str) -> str:
    """Format a string for making a C++ variable."""
    wordlist = [word for word in RE_WORD.findall(name) if word]
    return "_".join(wordlist)


def compute_value(value: TODValue, ctype: str) -> tuple[str, str]:
    """Compute value for C file."""
    if ctype == "visible_string":
        return f'"{value}"', ""
    if ctype == "domain":
        # FIXME: This ctype assumes the value type
        assert isinstance(value, str)
        tp = ''.join([f"\\x{ord(char):02x}" for char in value])
        return f'"{tp}"', ""
    if ctype.startswith("real"):
        return str(value), ""
    # FIXME: Assume value is an integer
    assert not isinstance(value, str)
    # Make sure to handle negative numbers correctly
    if value < 0:
        return f"-0x{-value:X}", f"\t/* {value} */"
    return f"0x{value:X}", f"\t/* {value} */"


def generate_file_content(node: NodeProtocol, headerfile: str, pointers_dict=None) -> tuple[str, str, str]:
    """
    pointers_dict = {(Idx,Sidx):"VariableName",...}
    """

    # FIXME: Too many camelCase vars in here
    # pylint: disable=invalid-name

    # Setup the main context to store the data
    ctx = CFileContext()

    pointers_dict = pointers_dict or {}
    ctx["maxPDOtransmit"] = 0
    ctx["NodeName"] = node.Name
    ctx["NodeID"] = node.ID
    ctx["NodeType"] = node.Type
    ctx["Description"] = node.Description or ""
    ctx["iam_a_slave"] = 1 if node.Type == "slave" else 0

    ctx.default_string_size = node.DefaultStringSize

    # Compiling lists of indexes
    rangelist = [idx for idx in node.GetIndexes() if 0 <= idx <= 0x260]
    listindex = [idx for idx in node.GetIndexes() if 0x1000 <= idx <= 0xFFFF]
    communicationlist = [idx for idx in node.GetIndexes() if 0x1000 <= idx <= 0x11FF]
    # sdolist = [idx for idx in node.GetIndexes() if 0x1200 <= idx <= 0x12FF]
    # pdolist = [idx for idx in node.GetIndexes() if 0x1400 <= idx <= 0x1BFF]
    variablelist = [idx for idx in node.GetIndexes() if 0x2000 <= idx <= 0xBFFF]

    # --------------------------------------------------------------------------
    #                   Declaration of the value range types
    # --------------------------------------------------------------------------

    valueRangeContent = ctx.text()
    strDefine = ctx.text(
        "\n#define valueRange_EMC 0x9F "
        "/* Type for index 0x1003 subindex 0x00 (only set of value 0 is possible) */"
    )
    strSwitch = ctx.text("""    case valueRange_EMC:
      if (*(UNS8*)value != (UNS8)0) return OD_VALUE_RANGE_EXCEEDED;
      break;
""")
    ctx.internal_types["valueRange_EMC"] = TypeInfos("UNS8", 0, "valueRange_EMC", True)
    num = 0
    for index in rangelist:
        rangename = node.GetEntryName(index)
        result = RE_RANGE.match(rangename)
        if result:
            num += 1
            typeindex = node.GetEntry(index, 1)
            # FIXME: It is assumed that rangelist contains propery formatted entries
            #        where index 1 is the object type as int
            assert isinstance(typeindex, int)
            typename = node.GetTypeName(typeindex)
            typeinfos = ctx.get_valid_type_infos(typename)
            ctx.internal_types[rangename] = TypeInfos(
                typeinfos.type, typeinfos.size, f"valueRange_{num}", typeinfos.is_unsigned
            )
            minvalue = node.GetEntry(index, 2)
            maxvalue = node.GetEntry(index, 3)
            # FIXME: It assumed the data is properly formatted
            assert isinstance(minvalue, int)
            assert isinstance(maxvalue, int)
            strDefine += (
                f"\n#define valueRange_{num} 0x{index:02X} "
                f"/* Type {typeinfos.type}, {minvalue} < value < {maxvalue} */"
            )
            strSwitch += f"    case valueRange_{num}:\n"
            if typeinfos.is_unsigned and minvalue <= 0:
                strSwitch += "      /* Negative or null low limit ignored because of unsigned type */;\n"
            else:
                strSwitch += (
                    f"      if (*({typeinfos.type}*)value < ({typeinfos.type}){minvalue}) return OD_VALUE_TOO_LOW;\n"
                )
            strSwitch += (
                f"      if (*({typeinfos.type}*)value > ({typeinfos.type}){maxvalue}) return OD_VALUE_TOO_HIGH;\n"
            )
            strSwitch += "    break;\n"

    valueRangeContent += strDefine
    valueRangeContent %= "\nUNS32 {NodeName}_valueRangeTest (UNS8 typeValue, void * value)\n{{"
    valueRangeContent += "\n  switch (typeValue) {\n"
    valueRangeContent += strSwitch
    valueRangeContent += "  }\n  return 0;\n}\n"

    # --------------------------------------------------------------------------
    #        Creation of the mapped variables and object dictionary
    # --------------------------------------------------------------------------

    mappedVariableContent = ctx.text()
    pointedVariableContent = ctx.text()
    strDeclareHeader = ctx.text()
    indexContents: dict[int, str|Text] = {}
    headerObjDefinitionContent = ctx.text()
    for index in listindex:
        ctx["index"] = index
        entry_infos = node.GetEntryInfos(index)
        params_infos = node.GetParamsEntry(index)
        ctx["EntryName"] = entry_infos["name"]
        values = node.GetEntry(index)

        strindex = ctx.text()
        if index in variablelist:
            strindex %= "\n/* index 0x{index:04X} :   Mapped variable {EntryName} */\n"
        else:
            strindex %= "\n/* index 0x{index:04X} :   {EntryName}. */\n"

        # Entry type is VAR
        if not isinstance(values, list):
            # FIXME: It is assumed that the type of GetParamsEntry() follows the object type
            #        of GetEntry()
            assert not isinstance(params_infos, list)
            subentry_infos = node.GetSubentryInfos(index, 0)
            typename = node.GetTypeName(subentry_infos["type"])
            typeinfos = ctx.get_valid_type_infos(typename, [values])
            if typename == "DOMAIN" and index in variablelist:
                if not typeinfos.size:
                    raise ValueError(f"Domain variable not initialized, index: 0x{index:04X}, subindex: 0x00")
            ctx["subIndexType"] = typeinfos.type
            if typeinfos.size is not None:
                if params_infos["buffer_size"]:
                    ctx["suffix"] = f"[{params_infos['buffer_size']}]"
                else:
                    ctx["suffix"] = f"[{typeinfos.size}]"
            else:
                ctx["suffix"] = ""
            ctx["value"], ctx["comment"] = compute_value(values, typeinfos.ctype)
            if index in variablelist:
                ctx["name"] = RE_STARTS_WITH_DIGIT.sub(r'_\1', format_name(subentry_infos["name"]))
                strDeclareHeader %= (
                    "extern {subIndexType} {name}{suffix};"
                    "\t\t/* Mapped at index 0x{index:04X}, subindex 0x00*/\n"
                )
                mappedVariableContent %= (
                    "{subIndexType} {name}{suffix} = {value};"
                    "\t\t/* Mapped at index 0x{index:04X}, subindex 0x00 */\n"
                )
            else:
                strindex %= (
                    "                    "
                    "{subIndexType} {NodeName}_obj{index:04X}{suffix} = {value};{comment}\n"
                )
            values = [values]
        else:
            subentry_infos = node.GetSubentryInfos(index, 0)
            typename = node.GetTypeName(subentry_infos["type"])
            typeinfos = ctx.get_valid_type_infos(typename)
            ctx["value"] = values[0] if index != 0x1003 else 0
            ctx["subIndexType"] = typeinfos.type
            strindex %= (
                "                    "
                "{subIndexType} {NodeName}_highestSubIndex_obj{index:04X} = {value}; "
                "/* number of subindex - 1*/\n"
            )

            # Entry type is ARRAY
            if entry_infos["struct"] & OD.IdenticalSubindexes:
                subentry_infos = node.GetSubentryInfos(index, 1)
                typename = node.GetTypeName(subentry_infos["type"])
                typeinfos = ctx.get_valid_type_infos(typename, values[1:])
                ctx["subIndexType"] = typeinfos.type
                if typeinfos.size is not None:
                    ctx["suffix"] = f"[{typeinfos.size}]"
                    ctx["type_suffix"] = "*"
                else:
                    ctx["suffix"] = ""
                    ctx["type_suffix"] = ""
                ctx["length"] = values[0]
                if index in variablelist:
                    ctx["name"] = RE_STARTS_WITH_DIGIT.sub(r'_\1', format_name(entry_infos["name"]))
                    ctx["values_count"] = str(len(values) - 1)
                    strDeclareHeader %= (
                        "extern {subIndexType} {name}[{values_count}]{suffix};\t\t"
                        "/* Mapped at index 0x{index:04X}, subindex 0x01 - 0x{length:02X} */\n"
                    )
                    mappedVariableContent %= (
                        "{subIndexType} {name}[]{suffix} =\t\t"
                        "/* Mapped at index 0x{index:04X}, subindex 0x01 - 0x{length:02X} */\n  {{\n"
                    )
                    for subindex, value in enumerate(values):
                        sep = ","
                        if subindex > 0:
                            if subindex == len(values) - 1:
                                sep = ""
                            value, comment = compute_value(value, typeinfos.ctype)
                            if len(value) == 2 and typename == "DOMAIN":
                                raise ValueError(
                                    "Domain variable not initialized, "
                                    f"index: 0x{index:04X}, subindex: 0x{subindex:02X}"
                                )
                            mappedVariableContent += f"    {value}{sep}{comment}\n"
                    mappedVariableContent += "  };\n"
                else:
                    strindex %= (
                        "                    "
                        "{subIndexType}{type_suffix} {NodeName}_obj{index:04X}[] = \n"
                        "                    {{\n"
                    )
                    for subindex, value in enumerate(values):
                        sep = ","
                        if subindex > 0:
                            if subindex == len(values) - 1:
                                sep = ""
                            value, comment = compute_value(value, typeinfos.ctype)
                            strindex += f"                      {value}{sep}{comment}\n"
                    strindex += "                    };\n"
            else:

                ctx["parent"] = RE_STARTS_WITH_DIGIT.sub(r'_\1', format_name(entry_infos["name"]))
                # Entry type is RECORD
                for subindex, value in enumerate(values):
                    ctx["subindex"] = subindex
                    # FIXME: Are there any point in calling this for subindex 0?
                    params_infos = node.GetParamsEntry(index, subindex)
                    # FIXME: Assumed params_info type is coherent with entry_infos["struct"]
                    assert not isinstance(params_infos, list)
                    if subindex > 0:
                        subentry_infos = node.GetSubentryInfos(index, subindex)
                        typename = node.GetTypeName(subentry_infos["type"])
                        typeinfos = ctx.get_valid_type_infos(typename, [values[subindex]])
                        ctx["subIndexType"] = typeinfos.type
                        if typeinfos.size is not None:
                            if params_infos["buffer_size"]:
                                ctx["suffix"] = f"[{params_infos['buffer_size']}]"
                            else:
                                ctx["suffix"] = f"[{typeinfos.size}]"
                        else:
                            ctx["suffix"] = ""
                        ctx["value"], ctx["comment"] = compute_value(value, typeinfos.ctype)
                        ctx["name"] = format_name(subentry_infos["name"])
                        if index in variablelist:
                            strDeclareHeader %= (
                                "extern {subIndexType} {parent}_{name}{suffix};\t\t"
                                "/* Mapped at index 0x{index:04X}, subindex 0x{subindex:02X} */\n"
                            )
                            mappedVariableContent %= (
                                "{subIndexType} {parent}_{name}{suffix} = {value};\t\t"
                                "/* Mapped at index 0x{index:04X}, subindex 0x{subindex:02X} */\n"
                            )
                        else:
                            strindex %= (
                                "                    "
                                "{subIndexType} {NodeName}"
                                "_obj{index:04X}_{name}{suffix} = "
                                "{value};{comment}\n"
                            )

        headerObjDefinitionContent += (
            f"\n#define {RE_NOTW.sub('_', ctx['NodeName'])}"
            f"_{RE_NOTW.sub('_', ctx['EntryName'])}_Idx {ctx['index']:#04x}\n"
        )

        # Generating Dictionary C++ entry
        strindex %= (
            "                    "
            "subindex {NodeName}_Index{index:04X}[] = \n"
            "                     {{\n"
        )
        generateSubIndexArrayComment = True
        for subindex, _ in enumerate(values):
            subentry_infos = node.GetSubentryInfos(index, subindex)
            params_infos = node.GetParamsEntry(index, subindex)
            # FIXME: As subindex is non-zero, params can't be a list
            assert not isinstance(params_infos, list)
            if subindex < len(values) - 1:
                sep = ","
            else:
                sep = ""
            typename = node.GetTypeName(subentry_infos["type"])
            if entry_infos["struct"] & OD.IdenticalSubindexes:
                typeinfos = ctx.get_valid_type_infos(typename, values[1:])
            else:
                typeinfos = ctx.get_valid_type_infos(typename, [values[subindex]])
            if subindex == 0:
                if index == 0x1003:
                    typeinfos = ctx.get_valid_type_infos("valueRange_EMC")
                if entry_infos["struct"] & OD.MultipleSubindexes:
                    name = f"{ctx['NodeName']}_highestSubIndex_obj{ctx['index']:04X}"
                elif index in variablelist:
                    name = format_name(subentry_infos["name"])
                else:
                    name = format_name(f"{ctx['NodeName']}_obj{ctx['index']:04X}")
            elif entry_infos["struct"] & OD.IdenticalSubindexes:
                if index in variablelist:
                    name = f"{format_name(entry_infos['name'])}[{subindex - 1}]"
                else:
                    name = f"{ctx['NodeName']}_obj{ctx['index']:04X}[{subindex - 1}]"
            else:
                if index in variablelist:
                    name = format_name(f"{entry_infos['name']}_{subentry_infos['name']}")
                else:
                    name = (
                        f"{ctx['NodeName']}_obj{ctx['index']:04X}_"
                        f"{format_name(subentry_infos['name'])}"
                    )
            if typeinfos.ctype == "visible_string":
                if params_infos["buffer_size"]:
                    sizeof = str(params_infos["buffer_size"])
                else:
                    value = values[subindex]
                    # FIXME: It should be a str type with visible_string
                    assert isinstance(value, str)
                    sizeof = str(max(len(value), ctx.default_string_size))
            elif typeinfos.ctype == "domain":
                value = values[subindex]
                # FIXME: Value should be string
                assert isinstance(value, str)
                sizeof = str(len(value))
            else:
                sizeof = f"sizeof ({typeinfos.type})"
            params = node.GetParamsEntry(index, subindex)
            # FIXME: As subindex is non-zero, params can't be a list
            assert not isinstance(params, list)
            if params["save"]:
                save = "|TO_BE_SAVE"
            else:
                save = ""
            start_digit = RE_STARTS_WITH_DIGIT.sub(r'_\1', name)
            strindex += (
                f"                       {{ "
                f"{subentry_infos['access'].upper()}{save}, "
                f"{typeinfos.ctype}, {sizeof}, (void*)&{start_digit}, NULL "
                f"}}{sep}\n"
            )
            pointer_name = pointers_dict.get((index, subindex), None)
            if pointer_name is not None:
                pointedVariableContent += f"{typeinfos.type}* {pointer_name} = &{name};\n"
            if not entry_infos["struct"] & OD.IdenticalSubindexes:
                generateSubIndexArrayComment = True
                headerObjDefinitionContent += (
                    f"#define {RE_NOTW.sub('_', ctx['NodeName'])}"
                    f"_{RE_NOTW.sub('_', ctx['EntryName'])}"
                    f"_{RE_NOTW.sub('_', subentry_infos['name'])}"
                    f"_sIdx {subindex:#04x}"
                )
                if params_infos["comment"]:
                    headerObjDefinitionContent += "    /* " + params_infos["comment"] + " */\n"
                else:
                    headerObjDefinitionContent += "\n"
            elif generateSubIndexArrayComment:
                generateSubIndexArrayComment = False
                # Generate Number_of_Entries_sIdx define and write comment
                # about not generating defines for the rest of the array objects
                headerObjDefinitionContent += (
                    f"#define {RE_NOTW.sub('_', ctx['NodeName'])}"
                    f"_{RE_NOTW.sub('_', ctx['EntryName'])}"
                    f"_{RE_NOTW.sub('_', subentry_infos['name'])}"
                    f"_sIdx {subindex:#04x}\n"
                )
                headerObjDefinitionContent += "/* subindex define not generated for array objects */\n"
        strindex += "                     };\n"
        indexContents[index] = strindex

    # --------------------------------------------------------------------------
    #                 Declaration of Particular Parameters
    # --------------------------------------------------------------------------

    if 0x1003 not in communicationlist:
        entry_infos = node.GetEntryInfos(0x1003)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1003] = ctx.ftext("""
/* index 0x1003 :   {EntryName} */
                    UNS8 {NodeName}_highestSubIndex_obj1003 = 0; /* number of subindex - 1*/
                    UNS32 {NodeName}_obj1003[] =
                    {{
                      0x0	/* 0 */
                    }};
                    subindex {NodeName}_Index1003[] =
                     {{
                       {{ RW, valueRange_EMC, sizeof (UNS8), (void*)&{NodeName}_highestSubIndex_obj1003, NULL }},
                       {{ RO, uint32, sizeof (UNS32), (void*)&{NodeName}_obj1003[0], NULL }}
                     }};
""")

    if 0x1005 not in communicationlist:
        entry_infos = node.GetEntryInfos(0x1005)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1005] = ctx.ftext("""
/* index 0x1005 :   {EntryName} */
                    UNS32 {NodeName}_obj1005 = 0x0;   /* 0 */
""")

    if 0x1006 not in communicationlist:
        entry_infos = node.GetEntryInfos(0x1006)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1006] = ctx.ftext("""
/* index 0x1006 :   {EntryName} */
                    UNS32 {NodeName}_obj1006 = 0x0;   /* 0 */
""")

    if 0x1014 not in communicationlist:
        entry_infos = node.GetEntryInfos(0x1014)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1014] = ctx.ftext("""
/* index 0x1014 :   {EntryName} */
                    UNS32 {NodeName}_obj1014 = 0x80 + 0x{NodeID:02X};   /* 128 + NodeID */
""")

    if 0x1016 in communicationlist:
        hbn = node.GetEntry(0x1016, 0)
        # FIXME: Hardcoded assumption on data-type?
        assert isinstance(hbn, int)
        ctx["heartBeatTimers_number"] = hbn
    else:
        ctx["heartBeatTimers_number"] = 0
        entry_infos = node.GetEntryInfos(0x1016)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1016] = ctx.ftext("""
/* index 0x1016 :   {EntryName} */
                    UNS8 {NodeName}_highestSubIndex_obj1016 = 0;
                    UNS32 {NodeName}_obj1016[]={{0}};
""")

    if 0x1017 not in communicationlist:
        entry_infos = node.GetEntryInfos(0x1017)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x1017] = ctx.ftext("""
/* index 0x1017 :   {EntryName} */
                    UNS16 {NodeName}_obj1017 = 0x0;   /* 0 */
""")

    if 0x100C not in communicationlist:
        entry_infos = node.GetEntryInfos(0x100C)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x100C] = ctx.ftext("""
/* index 0x100C :   {EntryName} */
                    UNS16 {NodeName}_obj100C = 0x0;   /* 0 */
""")

    if 0x100D not in communicationlist:
        entry_infos = node.GetEntryInfos(0x100D)
        ctx["EntryName"] = entry_infos["name"]
        indexContents[0x100D] = ctx.ftext("""
/* index 0x100D :   {EntryName} */
                    UNS8 {NodeName}_obj100D = 0x0;   /* 0 */
""")

    # --------------------------------------------------------------------------
    #           Declaration of navigation in the Object Dictionary
    # --------------------------------------------------------------------------

    strDeclareIndex = ctx.text()
    strDeclareSwitch = ""
    strQuickIndex = ""

    quick_index: dict[str, dict[str, int]] = {}
    for index_cat in INDEX_CATEGORIES:
        quick_index[index_cat] = {}
        for cat, idx_min, idx_max in CATEGORIES:
            quick_index[index_cat][cat] = 0

    maxPDOtransmit = 0
    for i, index in enumerate(listindex):
        ctx["index"] = index
        strDeclareIndex %= (
            "  {{ (subindex*){NodeName}_Index{index:04X},"
            "sizeof({NodeName}_Index{index:04X})/"
            "sizeof({NodeName}_Index{index:04X}[0]), 0x{index:04X}}},\n"
        )
        strDeclareSwitch += f"       case 0x{index:04X}: i = {i};break;\n"
        for cat, idx_min, idx_max in CATEGORIES:
            if idx_min <= index <= idx_max:
                quick_index["lastIndex"][cat] = i
                if quick_index["firstIndex"][cat] == 0:
                    quick_index["firstIndex"][cat] = i
                if cat == "PDO_TRS":
                    maxPDOtransmit += 1

    ctx["maxPDOtransmit"] = max(1, maxPDOtransmit)
    for index_cat in INDEX_CATEGORIES:
        strQuickIndex += f"\nconst quick_index {ctx['NodeName']}_{index_cat} = {{\n"
        sep = ","
        for i, (cat, idx_min, idx_max) in enumerate(CATEGORIES):
            if i == len(CATEGORIES) - 1:
                sep = ""
            strQuickIndex += f"  {quick_index[index_cat][cat]}{sep} /* {cat} */\n"
        strQuickIndex += "};\n"

    # --------------------------------------------------------------------------
    #                        Write File Content
    # --------------------------------------------------------------------------

    fileContent = ctx.text(FILE_HEADER)
    fileContent += f"""
#include "{headerfile}"
"""

    fileContent += """
/**************************************************************************/
/* Declaration of mapped variables                                        */
/**************************************************************************/
"""
    fileContent += mappedVariableContent
    fileContent += """
/**************************************************************************/
/* Declaration of value range types                                       */
/**************************************************************************/
"""
    fileContent += valueRangeContent
    fileContent %= """
/**************************************************************************/
/* The node id                                                            */
/**************************************************************************/
/* node_id default value.*/
UNS8 {NodeName}_bDeviceNodeId = 0x{NodeID:02X};

/**************************************************************************/
/* Array of message processing information */

const UNS8 {NodeName}_iam_a_slave = {iam_a_slave};

"""
    if ctx["heartBeatTimers_number"] > 0:
        declaration = ctx.ftext(
            "TIMER_HANDLE {NodeName}_heartBeatTimers[{heartBeatTimers_number}]"
        )
        initializer = "{TIMER_NONE" + ",TIMER_NONE" * (ctx["heartBeatTimers_number"] - 1) + "}"
        fileContent += declaration + " = " + initializer + ";\n"
    else:
        fileContent += f"TIMER_HANDLE {ctx['NodeName']}_heartBeatTimers[1];\n"

    fileContent += """
/*
$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

                               OBJECT DICTIONARY

$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
*/
"""
    for index in sorted(indexContents):
        fileContent += indexContents[index]

    fileContent += """
/**************************************************************************/
/* Declaration of pointed variables                                       */
/**************************************************************************/
"""
    fileContent += pointedVariableContent
    fileContent %= """
const indextable {NodeName}_objdict[] =
{{
"""
    fileContent += strDeclareIndex
    fileContent %= """}};

const indextable * {NodeName}_scanIndexOD (CO_Data *d, UNS16 wIndex, UNS32 * errorCode)
{{
    int i;
    (void)d; /* unused parameter */
    switch(wIndex){{
"""
    fileContent += strDeclareSwitch
    fileContent %= """       default:
            *errorCode = OD_NO_SUCH_OBJECT;
            return NULL;
    }}
    *errorCode = OD_SUCCESSFUL;
    return &{NodeName}_objdict[i];
}}

/*
 * To count at which received SYNC a PDO must be sent.
 * Even if no pdoTransmit are defined, at least one entry is computed
 * for compilations issues.
 */
s_PDO_status {NodeName}_PDO_status[{maxPDOtransmit}] = {{"""

    fileContent += ",".join(["s_PDO_status_Initializer"] * ctx["maxPDOtransmit"]) + "};\n"
    fileContent += strQuickIndex
    fileContent %= """
const UNS16 {NodeName}_ObjdictSize = sizeof({NodeName}_objdict)/sizeof({NodeName}_objdict[0]);

CO_Data {NodeName}_Data = CANOPEN_NODE_DATA_INITIALIZER({NodeName});

"""

    # --------------------------------------------------------------------------
    #                      Write Header File Content
    # --------------------------------------------------------------------------

    ctx["file_include_name"] = headerfile.replace(".", "_").upper()
    headerFileContent = ctx.text(FILE_HEADER)
    headerFileContent %= """
#ifndef {file_include_name}
#define {file_include_name}

#include "data.h"

/* Prototypes of function provided by object dictionnary */
UNS32 {NodeName}_valueRangeTest (UNS8 typeValue, void * value);
const indextable * {NodeName}_scanIndexOD (CO_Data *d, UNS16 wIndex, UNS32 * errorCode);

/* Master node data struct */
extern CO_Data {NodeName}_Data;
"""
    headerFileContent += strDeclareHeader
    headerFileContent %= "\n#endif // {file_include_name}\n"

    # --------------------------------------------------------------------------
    #                      Write Header Object Defintions Content
    # --------------------------------------------------------------------------
    file_include_objdef_name = headerfile.replace(".", "_OBJECTDEFINES_").upper()
    headerObjectDefinitionContent = ctx.text(FILE_HEADER)
    headerObjectDefinitionContent += f"""
#ifndef {file_include_objdef_name}
#define {file_include_objdef_name}

/*
    Object defines naming convention:
    General:
        * All characters in object names that does not match [a-zA-Z0-9_] will be replaced by '_'.
        * Case of object dictionary names will be kept as is.
    Index : Node object dictionary name +_+ index name +_+ Idx
    SubIndex : Node object dictionary name +_+ index name +_+ subIndex name +_+ sIdx
*/
"""
    headerObjectDefinitionContent += headerObjDefinitionContent
    headerObjectDefinitionContent += f"""
#endif /* {file_include_objdef_name} */
"""

    return str(fileContent), str(headerFileContent), str(headerObjectDefinitionContent)


# ------------------------------------------------------------------------------
#                             Main Function
# ------------------------------------------------------------------------------

def GenerateFile(filepath: TPath, node: NodeProtocol, pointers_dict=None):
    """Main function to generate the C file from a object dictionary node."""
    filepath = Path(filepath)
    headerpath = filepath.with_suffix(".h")
    headerdefspath = Path(headerpath.parent / (headerpath.stem + "_objectdefines.h"))
    content, header, header_defs = generate_file_content(
        node, headerpath.name, pointers_dict,
    )

    # Write main .c contents
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Write header file
    with open(headerpath, "w", encoding="utf-8") as f:
        f.write(header)

    # Write object definitions header
    with open(headerdefspath, "w", encoding="utf-8") as f:
        f.write(header_defs)
