"""Test functions for printing.py"""
import pytest

from objdictgen.printing import GetPrintEntry
from objdictgen.node import Node


@pytest.mark.parametrize("file", ['master', 'slave'])
def test_printing_GetPrintEntry(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))

    out = list(GetPrintEntry(od))
    assert isinstance(out, list)
    for line in out:
        assert isinstance(line, str)

