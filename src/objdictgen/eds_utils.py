"""Handler for EDS files, a standard file format in CANopen."""
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

import logging
import re
from pathlib import Path
from time import localtime, strftime
from typing import TYPE_CHECKING, Any, Callable

# Accessed by node.py, so we need to import module to avoid circular references
from objdictgen import maps
from objdictgen import node as nodelib
from objdictgen.maps import OD
from objdictgen.typing import TEntry, TPath

if TYPE_CHECKING:
    from objdictgen.node import Node
    from objdictgen.nodelist import NodeList

log = logging.getLogger('objdictgen')

# Regular expression for finding index section names
RE_INDEX = re.compile(r'([0-9A-F]{1,4}$)')
# Regular expression for finding subindex section names
RE_SUBINDEX = re.compile(r'([0-9A-F]{1,4})SUB([0-9A-F]{1,2}$)')
# Regular expression for finding index section names
RE_INDEX_OBJECTLINKS = re.compile(r'([0-9A-F]{1,4}OBJECTLINKS$)')

# Regular expression for finding NodeXPresent keynames
RE_NODEPRESENT = re.compile(r'NODE([0-9]{1,3})PRESENT$')
# Regular expression for finding NodeXName keynames
RE_NODENAME = re.compile(r'NODE([0-9]{1,3})NAME$')
# Regular expression for finding NodeXDCFName keynames
RE_NODEDCFNAME = re.compile(r'NODE([0-9]{1,3})DCFNAME$')

# Dictionary for quickly translate boolean into integer value
BOOL_TRANSLATE = {True: "1", False: "0"}

# Dictionary for quickly translate eds access value into canfestival access value
ACCESS_TRANSLATE = {
    "RO": "ro", "WO": "wo", "RW": "rw", "RWR": "rw", "RWW": "rw", "CONST": "ro"
}

# Function for verifying data values
is_integer = lambda x: isinstance(x, int)  # pylint: disable=unnecessary-lambda-assignment
is_string = lambda x: isinstance(x, str)  # pylint: disable=unnecessary-lambda-assignment
is_boolean = lambda x: x in (0, 1)  # pylint: disable=unnecessary-lambda-assignment

# Define checking of value for each attribute
ENTRY_ATTRIBUTES: dict[str, Callable[[Any], bool]] = {
    "SUBNUMBER": is_integer,
    "PARAMETERNAME": is_string,
    "OBJECTTYPE": lambda x: x in (2, 7, 8, 9),
    "DATATYPE": is_integer,
    "LOWLIMIT": is_integer,
    "HIGHLIMIT": is_integer,
    "ACCESSTYPE": lambda x: x.upper() in ACCESS_TRANSLATE,
    "DEFAULTVALUE": lambda x: True,
    "PDOMAPPING": is_boolean,
    "OBJFLAGS": is_integer,
    "PARAMETERVALUE": lambda x: True,
    "UPLOADFILE": is_string,
    "DOWNLOADFILE": is_string,
}

# Define entry parameters by entry ObjectType number
ENTRY_TYPES: dict[int, TEntry] = {
    2: {"name": " DOMAIN",
        "require": ["PARAMETERNAME", "OBJECTTYPE"],
        "optional": ["DATATYPE", "ACCESSTYPE", "DEFAULTVALUE", "OBJFLAGS"]},
    7: {"name": " VAR",
        "require": ["PARAMETERNAME", "DATATYPE", "ACCESSTYPE"],
        "optional": ["OBJECTTYPE", "DEFAULTVALUE", "PDOMAPPING", "LOWLIMIT",
                    "HIGHLIMIT", "OBJFLAGS", "PARAMETERVALUE"]},
    8: {"name": "n ARRAY",
        "require": ["PARAMETERNAME", "OBJECTTYPE", "SUBNUMBER"],
        "optional": ["OBJFLAGS"]},
    9: {"name": " RECORD",
        "require": ["PARAMETERNAME", "OBJECTTYPE", "SUBNUMBER"],
        "optional": ["OBJFLAGS"]},
}


def get_default_value(node: "Node", index: int, subindex: int = -1):
    """Function that search into Node Mappings the informations about an index
    or a subindex and return the default value."""
    infos = node.GetEntryInfos(index)
    if infos["struct"] & OD.MultipleSubindexes:
        # First case entry is a array
        if infos["struct"] & OD.IdenticalSubindexes:
            subentry_infos = node.GetSubentryInfos(index, 1)
        # Second case entry is an record
        else:
            subentry_infos = node.GetSubentryInfos(index, subindex)
        # If a default value is defined for this subindex, returns it
        if "default" in subentry_infos:
            return subentry_infos["default"]
        # If not, returns the default value for the subindex type
        return node.GetTypeDefaultValue(subentry_infos["type"])

    # Third case entry is a var
    subentry_infos = node.GetSubentryInfos(index, 0)
    # If a default value is defined for this subindex, returns it
    if "default" in subentry_infos:
        return subentry_infos["default"]
    # If not, returns the default value for the subindex type
    return node.GetTypeDefaultValue(subentry_infos["type"])


# ------------------------------------------------------------------------------
#                               Parse file
# ------------------------------------------------------------------------------


# List of section names that are not index and subindex and that we can meet in
# an EDS file
SECTION_KEYNAMES = ["FILEINFO", "DEVICEINFO", "DUMMYUSAGE", "COMMENTS",
                    "MANDATORYOBJECTS", "OPTIONALOBJECTS", "MANUFACTUREROBJECTS",
                    "STANDARDDATATYPES", "SUPPORTEDMODULES"]


def extract_sections(data: str) -> list[tuple[str, list[str]]]:
    """Extract sections from a file and returns a dictionary of the informations"""
    return [
        (
            blocktuple[0],                # EntryName : Assignements dict
            blocktuple[-1].splitlines(),  # all the lines
        )
        for blocktuple in [               # Split the eds files into
            block.split("]", 1)           # (EntryName,Assignements) tuple
            for block in                  # for each blocks staring with '['
            ("\n" + data).split("\n[")]
        if blocktuple[0].isalnum()]       # if EntryName exists


def parse_cpj_file(filepath: TPath):
    """Parse a CPJ file and return a list of dictionaries of the informations"""
    networks = []

    # Read file text
    with open(filepath, "r", encoding="utf-8") as f:
        cpj_data = f.read()

    sections = extract_sections(cpj_data)
    # Parse assignments for each section
    for section_name, assignments in sections:

        # Verify that section name is TOPOLOGY
        if section_name.upper() in "TOPOLOGY":

            # Reset values for topology
            topology: dict[str, Any] = {"Name": "", "Nodes": {}}

            for assignment in assignments:
                # Escape any comment
                if assignment.startswith(";"):
                    pass
                # Verify that line is a valid assignment
                elif "=" in assignment:
                    # Split assignment into the two values keyname and value
                    keyname, value = assignment.split("=", 1)

                    # keyname must be immediately followed by the "=" sign, so we
                    # verify that there is no whitespace into keyname
                    if keyname.isalnum():
                        # value can be preceded and followed by whitespaces, so we escape them
                        value = value.strip()
                        computed_value: int|str

                        # First case, value starts with "0x" or "-0x", then it's an hexadecimal value
                        if value.startswith("0x") or value.startswith("-0x"):
                            try:
                                computed_value = int(value, 16)
                            except ValueError:
                                raise ValueError(
                                    f"'{value}' is not a valid value for attribute '{keyname}' "
                                    f"of section '[{section_name}]'"
                                ) from None
                        elif value.isdigit() or value.startswith("-") and value[1:].isdigit():
                            # Second case, value is a number and starts with "0" or "-0", then it's an octal value
                            if value.startswith("0") or value.startswith("-0"):
                                computed_value = int(value, 8)
                            # Third case, value is a number and don't start with "0", then it's a decimal value
                            else:
                                computed_value = int(value)
                        # In any other case, we keep string value
                        else:
                            computed_value = value

                        # Search if the section name match any cpj expression
                        nodepresent_result = RE_NODEPRESENT.match(keyname.upper())
                        nodename_result = RE_NODENAME.match(keyname.upper())
                        nodedcfname_result = RE_NODEDCFNAME.match(keyname.upper())

                        if keyname.upper() == "NETNAME":
                            if not isinstance(computed_value, str):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            topology["Name"] = computed_value

                        elif keyname.upper() == "NODES":
                            if not isinstance(computed_value, int):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            topology["Number"] = computed_value

                        elif keyname.upper() == "EDSBASENAME":
                            if not isinstance(computed_value, str):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            topology["Path"] = computed_value

                        elif nodepresent_result:
                            if not isinstance(computed_value, int):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            nodeid = int(nodepresent_result[1])
                            if nodeid not in topology["Nodes"]:
                                topology["Nodes"][nodeid] = {}
                            topology["Nodes"][nodeid]["Present"] = computed_value

                        elif nodename_result:
                            if not isinstance(computed_value, str):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            nodeid = int(nodename_result[1])
                            if nodeid not in topology["Nodes"]:
                                topology["Nodes"][nodeid] = {}
                            topology["Nodes"][nodeid]["Name"] = computed_value

                        elif nodedcfname_result:
                            if not isinstance(computed_value, str):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' "
                                    f"of section '[{section_name}]'"
                                )
                            nodeid = int(nodedcfname_result[1])
                            if nodeid not in topology["Nodes"]:
                                topology["Nodes"][nodeid] = {}
                            topology["Nodes"][nodeid]["DCFName"] = computed_value

                        else:
                            raise ValueError(f"Keyname '{keyname}' not recognised for section '[{section_name}]'")

                # All lines that are not empty and are neither a comment neither not a valid assignment
                elif assignment.strip():
                    raise ValueError(f"'{assignment.strip()}' is not a valid CPJ line")

            if "Number" not in topology:
                raise ValueError(f"'Nodes' keyname in '[{section_name}]' section is missing")

            if topology["Number"] != len(topology["Nodes"]):
                raise ValueError("'Nodes' value not corresponding to number of nodes defined")

            for nodeid, node in topology["Nodes"].items():
                if "Present" not in node:
                    raise ValueError(f"'Node{nodeid}Present' keyname in '[{section_name}]' section is missing")

            networks.append(topology)

        # In other case, there is a syntax problem into CPJ file
        else:
            raise ValueError(f"Section '[{section_name}]' is unrecognized")

    return networks


def parse_eds_file(filepath: TPath) -> dict[str|int, Any]:
    """Parse an EDS file and returns a dictionary of the informations"""
    eds_dict: dict[str|int, Any] = {}

    # Read file text
    with open(filepath, 'r', encoding="utf-8") as f:
        eds_file = f.read()

    sections = extract_sections(eds_file)

    # Parse assignments for each section
    for section_name, assignments in sections:
        # Reset values of entry
        values: dict[str, Any] = {}

        # Search if the section name match an index or subindex expression
        index_result = RE_INDEX.match(section_name.upper())
        subindex_result = RE_SUBINDEX.match(section_name.upper())
        index_objectlinks_result = RE_INDEX_OBJECTLINKS.match(section_name.upper())

        # Compilation of the EDS information dictionary

        is_entry = False
        # First case, section name is in SECTION_KEYNAMES
        if section_name.upper() in SECTION_KEYNAMES:
            # Verify that entry is not already defined
            if section_name.upper() not in eds_dict:
                eds_dict[section_name.upper()] = values
            else:
                raise ValueError(f"'[{section_name}]' section is defined two times")
        # Second case, section name is an index name
        elif index_result:
            # Extract index number
            index = int(index_result[1], 16)
            # If index hasn't been referenced before, we add an entry into the dictionary
            if index not in eds_dict:
                eds_dict[index] = values
                eds_dict[index]["subindexes"] = {}
            elif list(eds_dict[index]) == ["subindexes"]:
                values["subindexes"] = eds_dict[index]["subindexes"]
                eds_dict[index] = values
            else:
                raise ValueError(f"'[{section_name}]' section is defined two times")
            is_entry = True
        # Third case, section name is a subindex name
        elif subindex_result:
            # Extract index and subindex number
            index, subindex = [int(value, 16) for value in subindex_result.groups()]
            # If index hasn't been referenced before, we add an entry into the dictionary
            # that will be updated later
            if index not in eds_dict:
                eds_dict[index] = {"subindexes": {}}
            if subindex not in eds_dict[index]["subindexes"]:
                eds_dict[index]["subindexes"][subindex] = values
            else:
                raise ValueError(f"'[{section_name}]' section is defined two times")
            is_entry = True
        # Third case, section name is a subindex name
        elif index_objectlinks_result:
            pass
        # In any other case, there is a syntax problem into EDS file
        else:
            raise ValueError(f"Section '[{section_name}]' is unrecognized")

        for assignment in assignments:
            # Escape any comment
            if assignment.startswith(";"):
                pass
            # Verify that line is a valid assignment
            elif "=" in assignment:
                # Split assignment into the two values keyname and value
                keyname, value = assignment.split("=", 1)

                # keyname must be immediately followed by the "=" sign, so we
                # verify that there is no whitespace into keyname
                if keyname.isalnum():
                    # value can be preceded and followed by whitespaces, so we escape them
                    value = value.strip()
                    # First case, value starts with "$NODEID", then it's a formula
                    computed_value: int|str
                    if value.upper().startswith("$NODEID"):
                        try:
                            _ = int(value.upper().replace("$NODEID+", ""), 16)
                            computed_value = f'"{value}"'
                        except ValueError:
                            raise ValueError(
                                f"'{value}' is not a valid formula for attribute '{keyname}' "
                                f"of section '[{section_name}]'"
                            ) from None
                    # Second case, value starts with "0x", then it's an hexadecimal value
                    elif value.startswith("0x") or value.startswith("-0x"):
                        try:
                            computed_value = int(value, 16)
                        except ValueError:
                            raise ValueError(
                                f"'{value}' is not a valid value for attribute '{keyname}' "
                                f"of section '[{section_name}]'"
                            ) from None
                    elif value.isdigit() or value.startswith("-") and value[1:].isdigit():
                        # Third case, value is a number and starts with "0", then it's an octal value
                        if value.startswith("0") or value.startswith("-0"):
                            computed_value = int(value, 8)
                        # Forth case, value is a number and don't start with "0", then it's a decimal value
                        else:
                            computed_value = int(value)
                    # In any other case, we keep string value
                    else:
                        computed_value = value

                    # Add value to values dictionary
                    # NOTE! The value can be 0 that must be added to the output
                    if computed_value != "":
                        # If entry is an index or a subindex
                        if is_entry:
                            # Verify that keyname is a possible attribute
                            if keyname.upper() not in ENTRY_ATTRIBUTES:
                                raise ValueError(
                                    f"Keyname '{keyname}' not recognised for section '[{section_name}]'"
                                )
                            # Verify that value is valid
                            if not ENTRY_ATTRIBUTES[keyname.upper()](computed_value):
                                raise ValueError(
                                    f"Invalid value '{value}' for keyname '{keyname}' of section '[{section_name}]'"
                                )
                            values[keyname.upper()] = computed_value
                        else:
                            values[keyname.upper()] = computed_value
            # All lines that are not empty and are neither a comment neither not a valid assignment
            elif assignment.strip():
                raise ValueError(f"'{assignment.strip()}' is not a valid EDS line")

        # If entry is an index or a subindex
        if is_entry:
            # Verify that entry has an ObjectType
            values["OBJECTTYPE"] = values.get("OBJECTTYPE", 7)
            # Extract parameters defined
            keys = set(values)
            keys.discard("subindexes")
            # Extract possible parameters and parameters required
            possible = set(
                ENTRY_TYPES[values["OBJECTTYPE"]]["require"]
                + ENTRY_TYPES[values["OBJECTTYPE"]]["optional"]
            )
            required = set(ENTRY_TYPES[values["OBJECTTYPE"]]["require"])
            # Verify that parameters defined contains all the parameters required
            if not keys.issuperset(required):
                missing = required.difference(keys)
                if len(missing) > 1:
                    tp = ", ".join([f"'{attribute}'" for attribute in missing])
                    attributes = f"Attributes {tp} are"
                else:
                    attributes = f"Attribute '{missing.pop()}' is"
                raise ValueError(
                    f"Error on section '[{section_name}]': '{attributes}' required "
                    f"for a '{ENTRY_TYPES[values['OBJECTTYPE']]['name']}' entry"
                )
            # Verify that parameters defined are all in the possible parameters
            if not keys.issubset(possible):
                unsupported = keys.difference(possible)
                if len(unsupported) > 1:
                    tp = ", ".join([f"'{attribute}'" for attribute in unsupported])
                    attributes = f"Attributes {tp} are"
                else:
                    attributes = f"Attribute '{unsupported.pop()}' is"
                raise ValueError(
                    f"Error on section '[{section_name}]': '{attributes}' unsupported "
                    f"for a '{ENTRY_TYPES[values['OBJECTTYPE']]['name']}' entry"
                )

            verify_value(values, section_name, "ParameterValue")
            verify_value(values, section_name, "DefaultValue")

    return eds_dict


def verify_value(values: dict[str, Any], section_name: str, param: str):
    """Verify that a value is compatible with the DataType of the entry"""
    uparam = param.upper()
    if uparam in values:
        try:
            if values["DATATYPE"] in (0x09, 0x0A, 0x0B, 0x0F):
                values[uparam] = str(values[uparam])
            elif values["DATATYPE"] in (0x08, 0x11):
                values[uparam] = float(values[uparam])
            elif values["DATATYPE"] == 0x01:
                values[uparam] = {0: False, 1: True}[values[uparam]]
            elif not isinstance(values[uparam], int) and "$NODEID" not in values[uparam].upper():
                raise ValueError()
        except ValueError:
            raise ValueError(f"Error on section '[{section_name}]': '{param}' incompatible with DataType") from None


def generate_eds_content(node: "Node", filepath: TPath):
    """Generate the EDS file content for the current node in the manager."""

    filepath = Path(filepath)

    # Dictionary of each index contents
    indexcontents = {}

    # Extract local time
    current_time = localtime()
    # Extract node informations
    nodename = node.Name
    # nodeid = node.ID
    nodetype = node.Type
    description = node.Description or ""

    # Retreiving lists of indexes defined
    entries = list(node)

    # FIXME: Too many camelCase vars in here
    # pylint: disable=invalid-name

    try:
        value = node.GetEntry(0x1018)
    except ValueError:
        raise ValueError("Missing required Identity (0x1018) object") from None

    # Generate FileInfo section
    fileContent = "[FileInfo]\n"
    fileContent += f"FileName={filepath.name}\n"
    fileContent += "FileVersion=1\n"
    fileContent += "FileRevision=1\n"
    fileContent += "EDSVersion=4.0\n"
    fileContent += f"Description={description}\n"
    fileContent += f"CreationTime={strftime('%I:%M', current_time)}"
    # %p option of strftime seems not working, then generate AM/PM by hands
    if strftime("%I", current_time) == strftime("%H", current_time):
        fileContent += "AM\n"
    else:
        fileContent += "PM\n"
    fileContent += f"CreationDate={strftime('%m-%d-%Y', current_time)}\n"
    fileContent += "CreatedBy=CANFestival\n"
    fileContent += f"ModificationTime={strftime('%I:%M', current_time)}"
    # %p option of strftime seems not working, then generate AM/PM by hands
    if strftime("%I", current_time) == strftime("%H", current_time):
        fileContent += "AM\n"
    else:
        fileContent += "PM\n"
    fileContent += f"ModificationDate={strftime('%m-%d-%Y', current_time)}\n"
    fileContent += "ModifiedBy=CANFestival\n"

    # Generate DeviceInfo section
    fileContent += "\n[DeviceInfo]\n"
    fileContent += "VendorName=CANFestival\n"
    # Use information typed by user in Identity entry
    fileContent += f"VendorNumber=0x{node.GetEntry(0x1018, 1):08X}\n"
    fileContent += f"ProductName={nodename}\n"
    fileContent += f"ProductNumber=0x{node.GetEntry(0x1018, 2):08X}\n"
    fileContent += f"RevisionNumber=0x{node.GetEntry(0x1018, 3):08X}\n"
    # CANFestival support all baudrates as soon as driver choosen support them
    fileContent += "BaudRate_10=1\n"
    fileContent += "BaudRate_20=1\n"
    fileContent += "BaudRate_50=1\n"
    fileContent += "BaudRate_125=1\n"
    fileContent += "BaudRate_250=1\n"
    fileContent += "BaudRate_500=1\n"
    fileContent += "BaudRate_800=1\n"
    fileContent += "BaudRate_1000=1\n"
    # Select BootUp type from the informations given by user
    fileContent += f"SimpleBootUpMaster={BOOL_TRANSLATE[nodetype == 'master']}\n"
    fileContent += f"SimpleBootUpSlave={BOOL_TRANSLATE[nodetype == 'slave']}\n"
    # CANFestival characteristics
    fileContent += "Granularity=8\n"
    fileContent += "DynamicChannelsSupported=0\n"
    fileContent += "CompactPDO=0\n"
    fileContent += "GroupMessaging=0\n"
    # Calculate receive and tranmit PDO numbers with the entry available
    fileContent += f"NrOfRXPDO={len([idx for idx in entries if 0x1400 <= idx <= 0x15FF])}\n"
    fileContent += f"NrOfTXPDO={len([idx for idx in entries if 0x1800 <= idx <= 0x19FF])}\n"
    # LSS not supported as soon as DS-302 was not fully implemented
    fileContent += "LSS_Supported=0\n"

    # Generate Dummy Usage section
    fileContent += "\n[DummyUsage]\n"
    fileContent += "Dummy0001=0\n"
    fileContent += "Dummy0002=1\n"
    fileContent += "Dummy0003=1\n"
    fileContent += "Dummy0004=1\n"
    fileContent += "Dummy0005=1\n"
    fileContent += "Dummy0006=1\n"
    fileContent += "Dummy0007=1\n"

    # Generate Comments section
    fileContent += "\n[Comments]\n"
    fileContent += "Lines=0\n"

    # List of entry by type (Mandatory, Optional or Manufacturer
    mandatories: list[int] = []
    optionals: list[int] = []
    manufacturers: list[int] = []

    # Remove all unused PDO
    # for entry in entries[:]:
    #    if 0x1600 <= entry < 0x1800 or 0x1A00 <= entry < 0x1C00:
    #        subentry_value = node.GetEntry(entry, 1)
    #        if subentry_value is None or subentry_value == 0:
    #            entries.remove(entry)
    #            entries.remove(entry - 0x200)

    # For each entry, we generate the entry section or sections if there is subindexes
    for entry in entries:
        # Extract infos and values for the entry
        entry_infos = node.GetEntryInfos(entry)
        values = node.GetEntry(entry, compute=False)
        # Define section name
        text = f"\n[{entry:X}]\n"
        # If there is only one value, it's a VAR entry
        if not isinstance(values, list):
            # Extract the informations of the first subindex
            subentry_infos = node.GetSubentryInfos(entry, 0)
            # Generate EDS informations for the entry
            text += f"ParameterName={subentry_infos['name']}\n"
            text += "ObjectType=0x7\n"
            text += f"DataType=0x{subentry_infos['type']:04X}\n"
            text += f"AccessType={subentry_infos['access']}\n"
            if subentry_infos["type"] == 1:
                text += f"DefaultValue={BOOL_TRANSLATE[bool(values)]}\n"
            else:
                text += f"DefaultValue={values}\n"
            text += f"PDOMapping={BOOL_TRANSLATE[subentry_infos['pdo']]}\n"
        else:
            # Generate EDS informations for the entry
            text += f"ParameterName={entry_infos['name']}\n"
            if entry_infos["struct"] & OD.IdenticalSubindexes:
                text += "ObjectType=0x8\n"
            else:
                text += "ObjectType=0x9\n"

            # Generate EDS informations for subindexes of the entry in a separate text
            subtext = ""
            # Reset number of subindex defined
            nb_subentry = 0
            for subentry, value in enumerate(values):
                # Extract the informations of each subindex
                subentry_infos = node.GetSubentryInfos(entry, subentry)
                # If entry is not for the compatibility, generate informations for subindex
                if subentry_infos["name"] == "Compatibility Entry":
                    continue
                subtext += f"\n[{entry:X}sub{subentry:X}]\n"
                subtext += f"ParameterName={subentry_infos['name']}\n"
                subtext += "ObjectType=0x7\n"
                subtext += f"DataType=0x{subentry_infos['type']:04X}\n"
                subtext += f"AccessType={subentry_infos['access']}\n"
                if subentry_infos["type"] == 1:
                    subtext += f"DefaultValue={BOOL_TRANSLATE[bool(value)]}\n"
                else:
                    subtext += f"DefaultValue={value}\n"
                subtext += f"PDOMapping={BOOL_TRANSLATE[subentry_infos['pdo']]}\n"
                # Increment number of subindex defined
                nb_subentry += 1
            # Write number of subindex defined for the entry
            text += f"SubNumber={nb_subentry}\n"
            # Write subindex definitions
            text += subtext

        # Then we add the entry in the right list

        # First case, entry is between 0x2000 and 0x5FFF, then it's a manufacturer entry
        if 0x2000 <= entry <= 0x5FFF:
            manufacturers.append(entry)
        # Second case, entry is required, then it's a mandatory entry
        elif entry_infos.get("need"):
            mandatories.append(entry)
        # In any other case, it's an optional entry
        else:
            optionals.append(entry)
        # Save text of the entry in the dictiionary of contents
        indexcontents[entry] = text

    def generate_index_contents(name: str, entries: list[int]):
        """Generate the index section for the index and the subindexes."""
        nonlocal fileContent
        fileContent += f"\n[{name}]\n"
        fileContent += f"SupportedObjects={len(entries)}\n"
        entries.sort()
        for idx, entry in enumerate(entries):
            fileContent += f"{idx + 1}=0x{entry:04X}\n"
        # Write entries
        for entry in entries:
            fileContent += indexcontents[entry]

    generate_index_contents("MandatoryObjects", mandatories)
    generate_index_contents("OptionalObjects", optionals)
    generate_index_contents("ManufacturerObjects", manufacturers)

    # Return File Content
    return fileContent


def generate_cpj_content(nodelist: "NodeList"):
    """Generate the CPJ file content for the nodelist."""
    nodes = nodelist.SlaveNodes

    filecontent = "[TOPOLOGY]\n"
    filecontent += f"NetName={nodelist.NetworkName}\n"
    filecontent += f"Nodes=0x{len(nodes):02X}\n"

    for nodeid in sorted(nodes):
        filecontent += f"Node{nodeid}Present=0x01\n"
        filecontent += f"Node{nodeid}Name={nodes[nodeid].Name}\n"
        filecontent += f"Node{nodeid}DCFName={nodes[nodeid].EDS}\n"

    filecontent += "EDSBaseName=eds\n"
    return filecontent


def generate_node(filepath: TPath, nodeid: int = 0) -> "Node":
    """Generate a Node from an EDS file."""
    # Create a new node
    node = nodelib.Node(id=nodeid)

    # Parse file and extract dictionary of EDS entry
    eds_dict = parse_eds_file(filepath)

    # Extract the common informations for the node
    fileinfo = eds_dict.get("FILEINFO", {})
    node.Description = fileinfo.get("DESCRIPTION", "")

    deviceinfo = eds_dict.get("DEVICEINFO", {})
    node.Name = deviceinfo.get("PRODUCTNAME", "")
    if deviceinfo.get("SIMPLEBOOTUPSLAVE") == 1:
        node.Type = "slave"
    if deviceinfo.get("SIMPLEBOOTUPMASTER") == 1:
        node.Type = "master"

    # Ensure we have the ODs we need
    missing = [f"0x{i:04X}" for i in (
        0x1000,
    ) if i not in eds_dict]
    if missing:
        tp = ",".join(missing)
        raise ValueError(f"EDS file is missing parameter index {tp}")

    # Extract Profile Number from Device Type entry
    # NOTE: Objdictgen does not export the profile number as default value
    #       in index 0x1000, so we can't rely on it to detect the profile.
    profilenb = eds_dict[0x1000].get("DEFAULTVALUE", 0) & 0x0000ffff
    if profilenb not in [0, 301, 302]:
        # Compile Profile name and path to .prf file
        try:
            # Import profile
            profilename = f"DS-{profilenb}"
            mapping, menuentries = maps.import_profile(profilename)
            node.ProfileName = profilename
            node.Profile = mapping
            node.SpecificMenu = menuentries
        except ValueError as exc:
            log.warning("WARNING: Loading profile '%s' failed: %s", profilename, exc)

    # Read all entries in the EDS dictionary
    for entry, values in eds_dict.items():
        # All sections with a name in keynames are escaped
        if entry in SECTION_KEYNAMES:
            continue

        # FIXME: entry should be integer, but can that be guaranteed?
        assert isinstance(entry, int)

        # If no informations are available, then we write them
        if not node.IsMappingEntry(entry):
            # First case, entry is a DOMAIN or VAR
            if values["OBJECTTYPE"] in [2, 7]:
                if values["OBJECTTYPE"] == 2:
                    values["DATATYPE"] = values.get("DATATYPE", 0xF)
                    if values["DATATYPE"] != 0xF:
                        raise ValueError(f"Domain entry 0x{entry:04X} DataType must be 0xF(DOMAIN) if defined")
                # Add mapping for entry
                node.AddMappingEntry(entry, entry={
                    "name": values["PARAMETERNAME"],
                    "struct": OD.VAR,
                })
                # Add mapping for first subindex
                node.AddMappingSubEntry(entry, 0, values={
                    "name": values["PARAMETERNAME"],
                    "type": values["DATATYPE"],
                    "access": ACCESS_TRANSLATE[values["ACCESSTYPE"].upper()],
                    "pdo": values.get("PDOMAPPING", 0) == 1,
                })

            # Second case, entry is an ARRAY or RECORD
            elif values["OBJECTTYPE"] in [8, 9]:
                # Extract maximum subindex number defined
                max_subindex = max(values["subindexes"])
                # Add mapping for entry
                node.AddMappingEntry(entry, entry={
                    "name": values["PARAMETERNAME"],
                    "struct": OD.RECORD
                })
                # Add mapping for first subindex
                node.AddMappingSubEntry(entry, 0, values={
                    "name": "Number of Entries",
                    "type": 0x05,
                    "access": "ro",
                    "pdo": False,
                })
                # Add mapping for other subindexes
                for subindex in range(1, int(max_subindex) + 1):
                    # if subindex is defined
                    if subindex in values["subindexes"]:
                        node.AddMappingSubEntry(entry, subindex, values={
                            "name": values["subindexes"][subindex]["PARAMETERNAME"],
                            "type": values["subindexes"][subindex]["DATATYPE"],
                            "access": ACCESS_TRANSLATE[values["subindexes"][subindex]["ACCESSTYPE"].upper()],
                            "pdo": values["subindexes"][subindex].get("PDOMAPPING", 0) == 1,
                        })
                    # if not, we add a mapping for compatibility
                    else:
                        node.AddMappingSubEntry(entry, subindex, values={
                            "name": "Compatibility Entry",
                            "type": 0x05,
                            "access": "rw",
                            "pdo": False,
                        })

        # First case, entry is a DOMAIN or VAR
        if values["OBJECTTYPE"] in [2, 7]:
            # Take default value if it is defined
            if "PARAMETERVALUE" in values:
                value = values["PARAMETERVALUE"]
            elif "DEFAULTVALUE" in values:
                value = values["DEFAULTVALUE"]
            # Find default value for value type of the entry
            else:
                value = get_default_value(node, entry)
            node.AddEntry(entry, 0, value)

        # Second case, entry is an ARRAY or a RECORD
        elif values["OBJECTTYPE"] in [8, 9]:
            # Verify that "Subnumber" attribute is defined and has a valid value
            if "SUBNUMBER" in values and values["SUBNUMBER"] > 0:
                # Extract maximum subindex number defined
                max_subindex = max(values["subindexes"])
                node.AddEntry(entry, value=[])
                # Define value for all subindexes except the first
                for subindex in range(1, int(max_subindex) + 1):
                    # Take default value if it is defined and entry is defined
                    if subindex in values["subindexes"] and "PARAMETERVALUE" in values["subindexes"][subindex]:
                        value = values["subindexes"][subindex]["PARAMETERVALUE"]
                    elif subindex in values["subindexes"] and "DEFAULTVALUE" in values["subindexes"][subindex]:
                        value = values["subindexes"][subindex]["DEFAULTVALUE"]
                    # Find default value for value type of the subindex
                    else:
                        value = get_default_value(node, entry, subindex)
                    node.AddEntry(entry, subindex, value)
            else:
                raise ValueError(f"Array or Record entry 0x{entry:04X} must have a 'SubNumber' attribute")

    return node
