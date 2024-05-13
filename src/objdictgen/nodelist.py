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
from dataclasses import dataclass

from objdictgen import eds_utils
from objdictgen.node import Node
from objdictgen.nodemanager import NodeManager
from objdictgen.typing import TODObj, TODSubObj, TPath

# ------------------------------------------------------------------------------
#                          Definition of NodeList Object
# ------------------------------------------------------------------------------

@dataclass
class SlaveNode:
    """SlaveNodes in NodeList."""
    Name: str
    EDS: str
    Node: Node


class NodeList:
    """
    Class recording a node list for a CANOpen network.
    """

    def __init__(self, manager: NodeManager, netname=""):
        self.Root: Path = Path("")
        self.Manager: NodeManager = manager
        self.NetworkName: str = netname
        self.SlaveNodes: dict[int, SlaveNode] = {}
        self.EDSNodes: dict[str, Node] = {}
        self.CurrentSelected: int|None = None
        self.Changed = False

    def HasChanged(self) -> bool:
        return self.Changed or not self.Manager.CurrentIsSaved()

    def GetEDSFolder(self, root_path: TPath|None = None) -> Path:
        if root_path is None:
            root_path = self.Root
        return Path(root_path, "eds")

    def GetMasterNodeID(self) -> int:
        return self.Manager.current.ID

    def GetSlaveName(self, idx: int) -> str:
        return self.SlaveNodes[idx].Name

    def GetSlaveNames(self) -> list[str]:
        return [
            f"0x{idx:02X} {self.SlaveNodes[idx].Name}"
            for idx in sorted(self.SlaveNodes)
        ]

    def GetSlaveIDs(self) -> list[int]:
        return list(sorted(self.SlaveNodes))

    def LoadProject(self, root: TPath, netname: str = ""):
        self.SlaveNodes = {}
        self.EDSNodes = {}

        self.Root = Path(root)
        if not self.Root.exists():
            raise OSError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), self.Root)

        eds_folder = self.GetEDSFolder()
        if not eds_folder.exists():
            eds_folder.mkdir(parents=True, exist_ok=True)
            # raise ValueError(f"'{self.Root}' folder doesn't contain a 'eds' folder")

        for file in eds_folder.iterdir():
            if file.is_file() and file.suffix == ".eds":
                self.LoadEDS(file)

        self.LoadMasterNode(netname)
        self.LoadSlaveNodes(netname)
        self.NetworkName = netname

    def SaveProject(self, netname: str = ""):
        self.SaveMasterNode(netname)
        self.SaveNodeList(netname)

    def GetEDSFilePath(self, edspath: TPath) -> Path:
        return self.GetEDSFolder() / Path(edspath).name

    def ImportEDSFile(self, edspath: TPath):
        edsfolder = self.GetEDSFolder()
        shutil.copy(edspath, edsfolder)
        self.LoadEDS(edsfolder / Path(edspath).name)

    def LoadEDS(self, eds: TPath):
        eds = Path(eds)
        node = eds_utils.generate_node(eds)
        self.EDSNodes[eds.name] = node

    def AddSlaveNode(self, nodename: str, nodeid: int, eds: str):
        if eds not in self.EDSNodes:
            raise ValueError(f"'{eds}' EDS file is not available")
        slave = SlaveNode(Name=nodename, EDS=eds, Node=self.EDSNodes[eds])
        self.SlaveNodes[nodeid] = slave
        self.Changed = True

    def RemoveSlaveNode(self, index: int):
        if index not in self.SlaveNodes:
            raise ValueError(f"Node with '0x{index:02X}' ID doesn't exist")
        self.SlaveNodes.pop(index)
        self.Changed = True

    def LoadMasterNode(self, netname: str = "") -> int:
        if netname:
            masterpath = self.Root / f"{netname}_master.od"
        else:
            masterpath = self.Root / "master.od"
        if masterpath.is_file():
            index = self.Manager.OpenFileInCurrent(masterpath)
        else:
            index = self.Manager.CreateNewNode(
                name="MasterNode", id=0x00, type="master", description="",
                profile="None", filepath="", nmt="Heartbeat", options=["DS302"],
            )
        return index

    def SaveMasterNode(self, netname: str = ""):
        if netname:
            masterpath = self.Root / f"{netname}_master.od"
        else:
            masterpath = self.Root / "master.od"
        try:
            self.Manager.SaveCurrentInFile(masterpath)
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError(f"Fail to save master node in '{masterpath}'") from exc

    def LoadSlaveNodes(self, netname: str = ""):
        cpjpath = self.Root / "nodelist.cpj"
        if cpjpath.is_file():
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
                            self.LoadEDS(node["DCFName"])
                            self.AddSlaveNode(node["Name"], nodeid, node["DCFName"])
                self.Changed = False
            except Exception as exc:  # pylint: disable=broad-except
                raise ValueError(f"Unable to load CPJ file '{cpjpath}'") from exc

    def SaveNodeList(self, netname: str = ""):
        cpjpath = self.Root / "nodelist.cpj"
        try:
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
                return self.Manager.current.IsEntry(index)
            node = self.SlaveNodes[self.CurrentSelected].Node
            if node:
                node.ID = self.CurrentSelected
                return node.IsEntry(index)
            raise ValueError("Can't find node")
        raise ValueError("No Node selected")

    def GetEntryInfos(self, index: int) -> TODObj:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.current.GetEntryInfos(index)
            node = self.SlaveNodes[self.CurrentSelected].Node
            if node:
                node.ID = self.CurrentSelected
                return node.GetEntryInfos(index)
            raise ValueError("Can't find node")
        raise ValueError("No Node selected")

    def GetSubentryInfos(self, index: int, subindex: int) -> TODSubObj:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.current.GetSubentryInfos(index, subindex)
            node = self.SlaveNodes[self.CurrentSelected].Node
            if node:
                node.ID = self.CurrentSelected
                return node.GetSubentryInfos(index, subindex)
            raise ValueError("Can't find node")
        raise ValueError("No Node selected")

    def GetCurrentValidIndexes(self, minval: int, maxval: int) -> list[tuple[str, int]]:
        if self.CurrentSelected is not None:
            if self.CurrentSelected == 0:
                return self.Manager.GetCurrentValidIndexes(minval, maxval)
            node = self.SlaveNodes[self.CurrentSelected].Node
            if node:
                node.ID = self.CurrentSelected
                return [
                    (node.GetEntryName(index), index)
                    for index in node
                    if minval <= index <= maxval
                ]
            raise ValueError("Can't find node")
        raise ValueError("No Node selected")

    def GetCurrentEntryValues(self, index: int):
        if self.CurrentSelected is not None:
            node = self.SlaveNodes[self.CurrentSelected].Node
            if node:
                node.ID = self.CurrentSelected
                return self.Manager.GetNodeEntryValues(node, index)
            raise ValueError("Can't find node")
        raise ValueError("No Node selected")

    def AddToMasterDCF(self, node_id: int, index: int, subindex: int, size: int, value: int):
        # Adding DCF entry into Master node
        if not self.Manager.current.IsEntry(0x1F22):
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
        for line in node.GetPrintEntry(raw=True):
            print(line)
    print()
    for nodeid, nodeinfo in nodelist.SlaveNodes.items():
        print(f"SlaveNode name={nodeinfo.Name} id=0x{nodeid:02X} :")
        for line in nodeinfo.Node.GetPrintEntry():
            print(line)
        print()
