"""Tests for node.py"""
import pytest

from objdictgen.node import Node, NodeProtocol, executeCustomGenerator

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