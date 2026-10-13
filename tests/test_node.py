"""Tests for node.py"""
import pytest

from objdictgen.maps import OD
from objdictgen.node import Node, NodeProtocol, executeCustomGenerator

@pytest.mark.parametrize("index, name, size", [
    (0x1001, "Error Register", 8),
    (0x1002, "Manufacturer Status Register", 32),
])
def test_node_builtin_pdo_mapping_choices(index, name, size):
    node = Node()
    node.AddEntry(index, value=0)
    mapname = node.GenerateMapName(name, index, 0)

    assert mapname in node.GetMapList()
    assert (index, 0, size, name) in node.GetMapVariableList()
    assert node.GetMapValue(mapname) == (index << 16) + size
    assert node.GetMapName((index << 16) + size) == mapname


def test_node_pdo_mapping_choices():
    node = Node()
    assert node.GetMapList() == ["None"]

    node.AddEntry(0x1000, value=0)
    assert node.GetMapList() == ["None"]


def test_node_pdo_mapping_string_buffer_size_as_text():
    node = Node()
    node.UserMapping[0x2000] = {
        "name": "Mapped object",
        "struct": OD.RECORD,
        "need": False,
        "values": [
            {"name": "Count", "type": 0x05, "access": "ro", "pdo": False},
            {"name": "Payload", "type": 0x09, "access": "rw", "pdo": True},
        ],
    }
    node.AddEntry(0x2000, value=["abc"])
    node.SetParamsEntry(0x2000, 1, params={"buffer_size": "3"})

    mapname = node.GenerateMapName("Payload", 0x2000, 1)
    assert node.GetMapValue(mapname) == (0x2000 << 16) + (1 << 8) + 24


@pytest.mark.parametrize("source", ["UserMapping", "Profile", "DS302"])
@pytest.mark.parametrize("struct", [OD.ARRAY, OD.RECORD])
@pytest.mark.parametrize("objtype, value, size", [(0x05, 0, 8), (0x09, "abc", 24)])
def test_node_pdo_mapping_subentry_choices(source, struct, objtype, value, size):
    node = Node()
    subentries = [{"name": "Count", "type": 0x05, "access": "ro", "pdo": False}]
    if struct == OD.ARRAY:
        subentries.append({
            "name": "Value %d[(sub)]", "type": objtype, "access": "rw", "pdo": True, "nbmax": 2,
        })
    else:
        subentries.extend([
            {"name": "First", "type": objtype, "access": "rw", "pdo": True},
            {"name": "Second", "type": objtype, "access": "rw", "pdo": True},
        ])
    getattr(node, source)[0x2000] = {
        "name": "Mapped object", "struct": struct, "need": False, "values": subentries,
    }
    node.AddEntry(0x2000, value=[value, value])
    for subindex in (1, 2):
        if objtype == 0x09:
            node.SetParamsEntry(0x2000, subindex, params={"buffer_size": 3})
        name = node.GetSubentryInfos(0x2000, subindex)["name"]
        mapname = node.GenerateMapName(name, 0x2000, subindex)
        mapvalue = (0x2000 << 16) + (subindex << 8) + size

        assert mapname in node.GetMapList()
        assert (0x2000, subindex, 8, name) in node.GetMapVariableList()
        assert node.GetMapValue(mapname) == mapvalue
        assert node.GetMapName(mapvalue) == mapname

@pytest.mark.parametrize("file", ['master', 'slave'])
def test_node_LoadFile(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))
    assert isinstance(od, Node)
    assert od.Name == 'master' if file == 'master' else 'slave'

@pytest.mark.parametrize("filename", ["this_file_does_not_exist.py", "bad_generator.py", "generator.py"])
def test_node_execute_custom_generator(filename: str, testspath):
    full_path = testspath.joinpath("test_generators").joinpath(filename)
    mock_path = "/mock"
    if filename == "bad_generator.py":
        with pytest.raises(AttributeError):
            executeCustomGenerator(full_path, mock_path, NodeProtocol)
    elif filename == "this_file_does_not_exist.py":
        executeCustomGenerator(full_path, mock_path, NodeProtocol)
    elif filename == "generator.py":
        try:
            executeCustomGenerator(full_path, mock_path, NodeProtocol) == "success"
        except Exception:
            pytest.fail("failed to execute generator.py")