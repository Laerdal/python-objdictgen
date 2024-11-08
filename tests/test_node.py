"""Tests for node.py"""
import pytest

from objdictgen.node import Node

@pytest.mark.parametrize("file", ['master', 'slave'])
def test_node_LoadFile(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))
    assert isinstance(od, Node)
    assert od.Name == 'master' if file == 'master' else 'slave'
