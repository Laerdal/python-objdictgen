""" Object mappings """
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

#
# Dictionary of translation between access symbol and their signification
#
from enum import IntEnum
ACCESS_TYPE = {"ro": "Read Only", "wo": "Write Only", "rw": "Read/Write"}
BOOL_TYPE = {True: "True", False: "False"}
OPTION_TYPE = {True: "Yes", False: "No"}
CUSTOMISABLE_TYPES = [
    (0x02, 0), (0x03, 0), (0x04, 0), (0x05, 0), (0x06, 0), (0x07, 0), (0x08, 0),
    (0x09, 1), (0x0A, 1), (0x0B, 1), (0x10, 0), (0x11, 0), (0x12, 0), (0x13, 0),
    (0x14, 0), (0x15, 0), (0x16, 0), (0x18, 0), (0x19, 0), (0x1A, 0), (0x1B, 0),
]
DEFAULT_PARAMS = {"comment": None, "save": False, "buffer_size": None}


# ------------------------------------------------------------------------------
#                      Dictionary Mapping and Organisation
# ------------------------------------------------------------------------------

class ODStructTypes:
    #
    # Properties of entry structure in the Object Dictionary
    #
    Subindex = 1             # Entry has at least one subindex
    MultipleSubindexes = 2   # Entry has more than one subindex
    IdenticalSubindexes = 4  # Subindexes of entry have the same description
    IdenticalIndexes = 8     # Entry has the same description on multiple indexes

    #
    # Structures of entry in the Object Dictionary, sum of the properties described above
    # for all sorts of entries use in CAN Open specification
    #
    NOSUB = 0  # Entry without subindex (only for type declaration)
    VAR = Subindex  # 1
    RECORD = Subindex | MultipleSubindexes  # 3
    ARRAY = Subindex | MultipleSubindexes | IdenticalSubindexes  # 7
    # Entries identical on multiple indexes
    NVAR = Subindex | IdenticalIndexes  # 9
    NRECORD = Subindex | MultipleSubindexes | IdenticalIndexes  # 11, Example : PDO Parameters
    NARRAY = Subindex | MultipleSubindexes | IdenticalSubindexes | IdenticalIndexes  # 15, Example : PDO Mapping

    #
    # Mapping against name and structure number
    #
    STRINGS = {
        NOSUB: None,
        VAR: "var",
        RECORD: "record",
        ARRAY: "array",
        NVAR: "nvar",
        NRECORD: "nrecord",
        NARRAY: "narray",
    }

    @classmethod
    def to_string(cls, val, default=''):
        # type: (type[ODStructTypes], int, str) -> str
        return cls.STRINGS.get(val, default)

    @classmethod
    def from_string(cls, val, default=None):
        # type: (type[ODStructTypes], str, int|None) -> int|None
        try:
            return next(k for k, v in cls.STRINGS.items() if v == val)
        except StopIteration:
            return default


# Convenience shortcut
OD = ODStructTypes


class CFILE_TYPES(IntEnum):
    current = 0,
    legacy = 1


#
# List of the Object Dictionary ranges
#
INDEX_RANGES = [
    {"min": 0x0001, "max": 0x0FFF, "name": "dtd", "description": "Data Type Definitions"},
    {"min": 0x1000, "max": 0x1029, "name": "cp", "description": "Communication Parameters"},
    {"min": 0x1200, "max": 0x12FF, "name": "sdop", "description": "SDO Parameters"},
    {"min": 0x1400, "max": 0x15FF, "name": "rpdop", "description": "Receive PDO Parameters"},
    {"min": 0x1600, "max": 0x17FF, "name": "rpdom", "description": "Receive PDO Mapping"},
    {"min": 0x1800, "max": 0x19FF, "name": "tpdop", "description": "Transmit PDO Parameters"},
    {"min": 0x1A00, "max": 0x1BFF, "name": "tpdom", "description": "Transmit PDO Mapping"},
    {"min": 0x1C00, "max": 0x1FFF, "name": "ocp", "description": "Other Communication Parameters"},
    {"min": 0x2000, "max": 0x5FFF, "name": "ms", "description": "Manufacturer Specific"},
    {"min": 0x6000, "max": 0x9FFF, "name": "sdp", "description": "Standardized Device Profile"},
    {"min": 0xA000, "max": 0xBFFF, "name": "sip", "description": "Standardized Interface Profile"},
]

#
# MAPPING_DICTIONARY is the structure used for writing a good organised Object
# Dictionary. It follows the specifications of the CANOpen standard.
# Change the informations within it if there is a mistake. But don't modify the
# organisation of this object, it will involve in a malfunction of the application.
#
MAPPING_DICTIONARY = {
    # -- Static Data Types
    0x0001: {"name": "BOOLEAN", "struct": OD.NOSUB, "size": 1, "default": False, "values": []},
    0x0002: {"name": "INTEGER8", "struct": OD.NOSUB, "size": 8, "default": 0, "values": []},
    0x0003: {"name": "INTEGER16", "struct": OD.NOSUB, "size": 16, "default": 0, "values": []},
    0x0004: {"name": "INTEGER32", "struct": OD.NOSUB, "size": 32, "default": 0, "values": []},
    0x0005: {"name": "UNSIGNED8", "struct": OD.NOSUB, "size": 8, "default": 0, "values": []},
    0x0006: {"name": "UNSIGNED16", "struct": OD.NOSUB, "size": 16, "default": 0, "values": []},
    0x0007: {"name": "UNSIGNED32", "struct": OD.NOSUB, "size": 32, "default": 0, "values": []},
    0x0008: {"name": "REAL32", "struct": OD.NOSUB, "size": 32, "default": 0.0, "values": []},
    0x0009: {"name": "VISIBLE_STRING", "struct": OD.NOSUB, "size": 8, "default": "", "values": []},
    0x000A: {"name": "OCTET_STRING", "struct": OD.NOSUB, "size": 8, "default": "", "values": []},
    0x000B: {"name": "UNICODE_STRING", "struct": OD.NOSUB, "size": 16, "default": "", "values": []},
    # 0x000C: {"name": "TIME_OF_DAY", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    # 0x000D: {"name": "TIME_DIFFERENCE", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    # 0x000E: RESERVED
    0x000F: {"name": "DOMAIN", "struct": OD.NOSUB, "size": 0, "default": "", "values": []},
    0x0010: {"name": "INTEGER24", "struct": OD.NOSUB, "size": 24, "default": 0, "values": []},
    0x0011: {"name": "REAL64", "struct": OD.NOSUB, "size": 64, "default": 0.0, "values": []},
    0x0012: {"name": "INTEGER40", "struct": OD.NOSUB, "size": 40, "default": 0, "values": []},
    0x0013: {"name": "INTEGER48", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    0x0014: {"name": "INTEGER56", "struct": OD.NOSUB, "size": 56, "default": 0, "values": []},
    0x0015: {"name": "INTEGER64", "struct": OD.NOSUB, "size": 64, "default": 0, "values": []},
    0x0016: {"name": "UNSIGNED24", "struct": OD.NOSUB, "size": 24, "default": 0, "values": []},
    # 0x0017: RESERVED
    0x0018: {"name": "UNSIGNED40", "struct": OD.NOSUB, "size": 40, "default": 0, "values": []},
    0x0019: {"name": "UNSIGNED48", "struct": OD.NOSUB, "size": 48, "default": 0, "values": []},
    0x001A: {"name": "UNSIGNED56", "struct": OD.NOSUB, "size": 56, "default": 0, "values": []},
    0x001B: {"name": "UNSIGNED64", "struct": OD.NOSUB, "size": 64, "default": 0, "values": []},
    # 0x001C-0x001F: RESERVED

    # -- Communication Profile Area
    0x1000: {"name": "Device Type", "struct": OD.VAR, "need": True, "values":
             [{"name": "Device Type", "type": 0x07, "access": 'ro', "pdo": False}]},
    0x1001: {"name": "Error Register", "struct": OD.VAR, "need": True, "values":
             [{"name": "Error Register", "type": 0x05, "access": 'ro', "pdo": True}]},
    0x1002: {"name": "Manufacturer Status Register", "struct": OD.VAR, "need": False, "values":
             [{"name": "Manufacturer Status Register", "type": 0x07, "access": 'ro', "pdo": True}]},
    0x1003: {"name": "Pre-defined Error Field", "struct": OD.ARRAY, "need": False, "callback": True, "values":
             [{"name": "Number of Errors", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Standard Error Field", "type": 0x07, "access": 'ro', "pdo": False, "nbmin": 1, "nbmax": 0xFE}]},
    0x1005: {"name": "SYNC COB ID", "struct": OD.VAR, "need": False, "callback": True, "values":
             [{"name": "SYNC COB ID", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1006: {"name": "Communication / Cycle Period", "struct": OD.VAR, "need": False, "callback": True, "values":
             [{"name": "Communication Cycle Period", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1007: {"name": "Synchronous Window Length", "struct": OD.VAR, "need": False, "values":
             [{"name": "Synchronous Window Length", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1008: {"name": "Manufacturer Device Name", "struct": OD.VAR, "need": False, "values":
             [{"name": "Manufacturer Device Name", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x1009: {"name": "Manufacturer Hardware Version", "struct": OD.VAR, "need": False, "values":
             [{"name": "Manufacturer Hardware Version", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x100A: {"name": "Manufacturer Software Version", "struct": OD.VAR, "need": False, "values":
             [{"name": "Manufacturer Software Version", "type": 0x09, "access": 'ro', "pdo": False}]},
    0x100C: {"name": "Guard Time", "struct": OD.VAR, "need": False, "values":
             [{"name": "Guard Time", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x100D: {"name": "Life Time Factor", "struct": OD.VAR, "need": False, "values":
             [{"name": "Life Time Factor", "type": 0x05, "access": 'rw', "pdo": False}]},
    0x1010: {"name": "Store parameters", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Save All Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Save Communication Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Save Application Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Save Manufacturer Parameters %d[(sub - 3)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmax": 0x7C}]},
    0x1011: {"name": "Restore Default Parameters", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Restore All Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Restore Communication Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Restore Application Default Parameters", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Restore Manufacturer Defined Default Parameters %d[(sub - 3)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmax": 0x7C}]},
    0x1012: {"name": "TIME COB ID", "struct": OD.VAR, "need": False, "values":
             [{"name": "TIME COB ID", "type": 0x07, "access": 'rw', "pdo": False}]},
    0x1013: {"name": "High Resolution Timestamp", "struct": OD.VAR, "need": False, "values":
             [{"name": "High Resolution Time Stamp", "type": 0x07, "access": 'rw', "pdo": True}]},
    0x1014: {"name": "Emergency COB ID", "struct": OD.VAR, "need": False, "values":
             [{"name": "Emergency COB ID", "type": 0x07, "access": 'rw', "pdo": False, "default": '"$NODEID+0x80"'}]},
    0x1015: {"name": "Inhibit Time Emergency", "struct": OD.VAR, "need": False, "values":
             [{"name": "Inhibit Time Emergency", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1016: {"name": "Consumer Heartbeat Time", "struct": OD.ARRAY, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Consumer Heartbeat Time", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 1, "nbmax": 0x7F}]},
    0x1017: {"name": "Producer Heartbeat Time", "struct": OD.VAR, "need": False, "callback": True, "values":
             [{"name": "Producer Heartbeat Time", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1018: {"name": "Identity", "struct": OD.RECORD, "need": True, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Vendor ID", "type": 0x07, "access": 'ro', "pdo": False},
              {"name": "Product Code", "type": 0x07, "access": 'ro', "pdo": False},
              {"name": "Revision Number", "type": 0x07, "access": 'ro', "pdo": False},
              {"name": "Serial Number", "type": 0x07, "access": 'ro', "pdo": False}]},
    0x1019: {"name": "Synchronous counter overflow value", "struct": OD.VAR, "need": False, "values":
             [{"name": "Synchronous counter overflow value", "type": 0x05, "access": 'rw', "pdo": False}]},
    0x1020: {"name": "Verify Configuration", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Configuration Date", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Configuration Time", "type": 0x07, "access": 'rw', "pdo": False}]},
    # 0x1021: {"name": "Store EDS", "struct": OD.VAR, "need": False, "values":
    #          [{"name": "Store EDS", "type": 0x0F, "access": 'rw', "pdo": False}]},
    # 0x1022: {"name": "Storage Format", "struct": OD.VAR, "need": False, "values":
    #          [{"name": "Storage Format", "type": 0x06, "access": 'rw', "pdo": False}]},
    0x1023: {"name": "OS Command", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Command", "type": 0x0A, "access": 'rw', "pdo": False},
              {"name": "Status", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Reply", "type": 0x0A, "access": 'ro', "pdo": False}]},
    0x1024: {"name": "OS Command Mode", "struct": OD.VAR, "need": False, "values":
             [{"name": "OS Command Mode", "type": 0x05, "access": 'wo', "pdo": False}]},
    0x1025: {"name": "OS Debugger Interface", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Command", "type": 0x0A, "access": 'rw', "pdo": False},
              {"name": "Status", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Reply", "type": 0x0A, "access": 'ro', "pdo": False}]},
    0x1026: {"name": "OS Prompt", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "StdIn", "type": 0x05, "access": 'wo', "pdo": True},
              {"name": "StdOut", "type": 0x05, "access": 'ro', "pdo": True},
              {"name": "StdErr", "type": 0x05, "access": 'ro', "pdo": True}]},
    0x1027: {"name": "Module List", "struct": OD.ARRAY, "need": False, "values":
             [{"name": "Number of Connected Modules", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Module %d[(sub)]", "type": 0x06, "access": 'ro', "pdo": False, "nbmin": 1, "nbmax": 0xFE}]},
    0x1028: {"name": "Emergency Consumer", "struct": OD.ARRAY, "need": False, "values":
             [{"name": "Number of Consumed Emergency Objects", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Emergency Consumer", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 1, "nbmax": 0x7F}]},
    0x1029: {"name": "Error Behavior", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Error Classes", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "Communication Error", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Device Profile", "type": 0x05, "access": 'rw', "pdo": False, "nbmax": 0xFE}]},

    # -- Server SDO Parameters
    0x1200: {"name": "Server SDO Parameter", "struct": OD.RECORD, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "COB ID Client to Server (Receive SDO)", "type": 0x07, "access": 'ro', "pdo": False, "default": '"$NODEID+0x600"'},
              {"name": "COB ID Server to Client (Transmit SDO)", "type": 0x07, "access": 'ro', "pdo": False, "default": '"$NODEID+0x580"'}]},
    0x1201: {"name": "Additional Server SDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x7F, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "COB ID Client to Server (Receive SDO)", "type": 0x07, "access": 'ro', "pdo": False},
              {"name": "COB ID Server to Client (Transmit SDO)", "type": 0x07, "access": 'ro', "pdo": False},
              {"name": "Node ID of the SDO Client", "type": 0x05, "access": 'ro', "pdo": False}]},

    # -- Client SDO Parameters
    0x1280: {"name": "Client SDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x100, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "COB ID Client to Server (Transmit SDO)", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "COB ID Server to Client (Receive SDO)", "type": 0x07, "access": 'rw', "pdo": False},
              {"name": "Node ID of the SDO Server", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Receive PDO Communication Parameters
    0x1400: {"name": "Receive PDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x200, "need": False, "values":
             [{"name": "Highest SubIndex Supported", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "COB ID used by PDO", "type": 0x07, "access": 'rw', "pdo": False, "default": "{True:\"$NODEID+0x%X00\"%(base+2),False:0x80000000}[base<4]"},
              {"name": "Transmission Type", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Inhibit Time", "type": 0x06, "access": 'rw', "pdo": False},
              {"name": "Compatibility Entry", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Event Timer", "type": 0x06, "access": 'rw', "pdo": False},
              {"name": "SYNC start value", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Receive PDO Mapping Parameters
    0x1600: {"name": "Receive PDO %d Mapping[(idx)]", "struct": OD.NARRAY, "incr": 1, "nbmax": 0x200, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "PDO %d Mapping for an application object %d[(idx,sub)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 0, "nbmax": 0x40}]},

    # -- Transmit PDO Communication Parameters
    0x1800: {"name": "Transmit PDO %d Parameter[(idx)]", "struct": OD.NRECORD, "incr": 1, "nbmax": 0x200, "need": False, "callback": True, "values":
             [{"name": "Highest SubIndex Supported", "type": 0x05, "access": 'ro', "pdo": False},
              {"name": "COB ID used by PDO", "type": 0x07, "access": 'rw', "pdo": False, "default": "{True:\"$NODEID+0x%X80\"%(base+1),False:0x80000000}[base<4]"},
              {"name": "Transmission Type", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Inhibit Time", "type": 0x06, "access": 'rw', "pdo": False},
              {"name": "Compatibility Entry", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "Event Timer", "type": 0x06, "access": 'rw', "pdo": False},
              {"name": "SYNC start value", "type": 0x05, "access": 'rw', "pdo": False}]},

    # -- Transmit PDO Mapping Parameters
    0x1A00: {"name": "Transmit PDO %d Mapping[(idx)]", "struct": OD.NARRAY, "incr": 1, "nbmax": 0x200, "need": False, "values":
             [{"name": "Number of Entries", "type": 0x05, "access": 'rw', "pdo": False},
              {"name": "PDO %d Mapping for a process data variable %d[(idx,sub)]", "type": 0x07, "access": 'rw', "pdo": False, "nbmin": 0, "nbmax": 0x40}]},
}
