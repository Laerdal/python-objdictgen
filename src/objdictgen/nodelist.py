"""Module to manage a list of nodes for a CANOpen network."""
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

import errno
import os
from pathlib import Path
import shutil

from objdictgen import eds_utils
from objdictgen.node import Node
from objdictgen.nodemanager import NodeManager
from objdictgen.typing import TODObj, TODSubObj, TPath

# ------------------------------------------------------------------------------
#                          Definition of NodeList Object
# ------------------------------------------------------------------------------


class NodeList:
    """
    Class recording a node list for a CANOpen network.
    """

    def __init__(self, manager: NodeManager, netname=""):
        self.Root: Path = Path("")
        self.Manager: NodeManager = manager
        self.NetworkName: str = netname
        self.SlaveNodes: dict[int, dict] = {}
        self.EDSNodes: dict[str, Node] = {}
        self.CurrentSelected: int|None = None
        self.Changed = False

    def HasChanged(self) -> bool:
        return self.Changed or not self.Manager.CurrentIsSaved()

    def GetEDSFolder(self, root_path: TPath|None = None) -> Path:
        if root_path is None:
            root_path = self.Root
        return os.path.join(root_path, "eds")

    def GetMasterNodeID(self) -> int:
        return self.Manager.GetCurrentNodeID()

    def GetSlaveName(self, idx: int) -> str:
        return self.SlaveNodes[idx]["Name"]

    def GetSlaveNames(self) -> list[str]:
        return [
            f"0x{idx:02X} {self.SlaveNodes[idx]['Name']}"
            for idx in sorted(self.SlaveNodes)
        ]

    def GetSlaveIDs(self) -> list[int]:
        return list(sorted(self.SlaveNodes))

    def LoadProject(self, root: TPath, netname: str = ""):
        self.SlaveNodes = {}
        self.EDSNodes = {}

        self.Root = root
        if not os.path.exists(self.Root):
            raise OSError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), self.Root)

        eds_folder = self.GetEDSFolder()
        if not os.path.exists(eds_folder):
            os.mkdir(eds_folder)
            # raise ValueError(f"'{self.Root}' folder doesn't contain a 'eds' folder")

        files = os.listdir(eds_folder)
        for file in files:
            filepath = os.path.join(eds_folder, file)
            if os.path.isfile(filepath) and os.path.splitext(filepath)[-1] == ".eds":
                self.LoadEDS(file)

        self.LoadMasterNode(netname)
        self.LoadSlaveNodes(netname)
        self.NetworkName = netname

    def SaveProject(self, netname: str = ""):
        self.SaveMasterNode(netname)
        self.SaveNodeList(netname)

    def GetEDSFilePath(self, edspath: TPath) -> Path:
        _, file = os.path.split(edspath)
        eds_folder = self.GetEDSFolder()
        return os.path.join(eds_folder, file)

    def ImportEDSFile(self, edspath: TPath):
        _, file = os.path.split(edspath)
        shutil.copy(edspath, self.GetEDSFolder())
        self.LoadEDS(file)

    def LoadEDS(self, eds: TPath):
        edspath = os.path.join(self.GetEDSFolder(), eds)
        node = eds_utils.generate_node(edspath)
        self.EDSNodes[eds] = node

    def AddSlaveNode(self, nodename: str, nodeid: int, eds: str):
        if eds not in self.EDSNodes:
            raise ValueError(f"'{eds}' EDS file is not available")
        slave = {"Name": nodename, "EDS": eds, "Node": self.EDSNodes[eds]}
        self.SlaveNodes[nodeid] = slave
        self.Changed = True

    def RemoveSlaveNode(self, index: int):
        if index not in self.SlaveNodes:
            raise ValueError(f"Node with '0x{index:02X}' ID doesn't exist")
        self.SlaveNodes.pop(index)
        self.Changed = True

    def LoadMasterNode(self, netname: str = "") -> int:
        if netname:
            masterpath = os.path.join(self.Root, f"{netname}_master.od")
        else:
            masterpath = os.path.join(self.Root, "master.od")
        if os.path.isfile(masterpath):
            index = self.Manager.OpenFileInCurrent(masterpath)
        else:
            index = self.Manager.CreateNewNode(
                name="MasterNode", id=0x00, type="master", description="",
                profile="None", filepath="", nmt="Heartbeat", options=["DS302"],
            )
        return index

    def SaveMasterNode(self, netname: str = ""):
        if netname:
            masterpath = os.path.join(self.Root, f"{netname}_master.od")
        else:
            masterpath = os.path.join(self.Root, "master.od")
        try:
            self.Manager.SaveCurrentInFile(masterpath)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Fail to save master node in '{masterpath}'") from exc

    def LoadSlaveNodes(self, netname: str = ""):
        cpjpath = os.path.join(self.Root, "nodelist.cpj")
        if os.path.isfile(cpjpath):
            try:
                networks = eds_utils.parse_cpj_file(cpjpath)
                network = None
                if netname:
                    for net in networks:
                        if net["Name"] == netname:
                            network = net
                    self.NetworkName = netname
                elif len(networks) > 0:
                    network = networks[0]
                    self.NetworkName = network["Name"]
                if network:
                    for nodeid, node in network["Nodes"].items():
                        if node["Present"] == 1:
                            self.AddSlaveNode(node["Name"], nodeid, node["DCFName"])
                self.Changed = False
            except Exception as exc:  # pylint: disable=broad-except
                raise ValueError(f"Unable to load CPJ file '{cpjpath}'") from exc

    def SaveNodeList(self, netname: str = ""):
        cpjpath = ''  # For linting
        try:
            cpjpath = os.path.join(self.Root, "nodelist.cpj")
            content = eds_utils.generate_cpj_content(self)
            if netname:
                mode = "a"
            else:
                mode = "w"
            with open(cpjpath, mode=mode, encoding="utf-8") as f:
                f.write(content)
            self.Changed = False
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Fail to save node list in '{cpjpath}'") from exc

    def GetOrderNumber(self, nodeid: int) -> int:
        nodeindexes = list(sorted(self.SlaveNodes))
        return nodeindexes.index(nodeid) + 1

    def IsCurrentEntry(self, index: int) -> bool:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.IsCurrentEntry(index)
            node = self.SlaveNodes[self.CurrentSelected]["Node"]
            if node:
                node.ID = self.CurrentSelected
                return node.IsEntry(index)
        return False

    def GetEntryInfos(self, index: int) -> TODObj:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.GetEntryInfos(index)
            node = self.SlaveNodes[self.CurrentSelected]["Node"]
            if node:
                node.ID = self.CurrentSelected
                return node.GetEntryInfos(index)
        return None

    def GetSubentryInfos(self, index: int, subindex: int) -> TODSubObj:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.GetSubentryInfos(index, subindex)
            node = self.SlaveNodes[self.CurrentSelected]["Node"]
            if node:
                node.ID = self.CurrentSelected
                return node.GetSubentryInfos(index, subindex)
        return None

    def GetCurrentValidIndexes(self, min_: int, max_: int) -> list[tuple[str, int]]:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.GetCurrentValidIndexes(min_, max_)
            node = self.SlaveNodes[self.CurrentSelected]["Node"]
            if node:
                node.ID = self.CurrentSelected
                return [
                    (node.GetEntryName(index), index)
                    for index in node.GetIndexes()
                    if min_ <= index <= max_
                ]
            raise ValueError("Can't find node")
        return []

    def GetCurrentEntryValues(self, index: int):
        if self.CurrentSelected is not None:
            node = self.SlaveNodes[self.CurrentSelected]["Node"]
            if node:
                node.ID = self.CurrentSelected
                return self.Manager.GetNodeEntryValues(node, index)
            raise ValueError("Can't find node")
        return [], []

    def AddToMasterDCF(self, node_id: int, index: int, subindex: int, size: int, value: int):
        # Adding DCF entry into Master node
        if not self.Manager.IsCurrentEntry(0x1F22):
            self.Manager.ManageEntriesOfCurrent([0x1F22], [])
        self.Manager.AddSubentriesToCurrent(0x1F22, 127)
        self.Manager.AddToDCF(node_id, index, subindex, size, value)


def main(projectdir):

    manager = NodeManager()

    nodelist = NodeList(manager)

    nodelist.LoadProject(projectdir)
    print("MasterNode :")
    node = manager.CurrentNode
    if node:
        for line in node.GetPrintParams(raw=True):
            print(line)
    print()
    for nodeid, node in nodelist.SlaveNodes.items():
        print(f"SlaveNode name={node['Name']} id=0x{nodeid:02X} :")
        for line in node["Node"].GetPrintParams():
            print(line)
        print()
