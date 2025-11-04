"""Test functions for printing.py"""
import types

import pytest

from objdictgen.node import Node
from objdictgen.printing import FormatNodeOpts, format_diff_nodes, format_node, format_od_header, format_od_object


@pytest.mark.parametrize("file", [
    'master', 'slave',
    'profile-ds302', 'profile-ds302-modified',
    'profile-ds401', 'profile-ds401-modified',
])
def test_printing_format_node(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))
    od.ID = 1

    opts = FormatNodeOpts(
        compact=False, short=False, unused=True, all=True, raw=False
    )

    lines = format_node(od, file, opts=opts)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)

    opts = FormatNodeOpts(
        compact=False, short=False, unused=True, all=True, raw=False
    )

    lines = format_node(od, file, index=[0x1000], opts=opts)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)

    opts = FormatNodeOpts(
        compact=False, short=False, unused=True, all=True, raw=False
    )

    with pytest.raises(ValueError) as exc:
        lines = list(format_node(od, file, index=[0x5000], opts=opts))
    assert "Unknown index 20480" in str(exc.value)


@pytest.mark.parametrize("file", [
    'master', 'slave',
])
def test_printing_format_od_header(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))

    fmt, info = format_od_header(od, 0x1000)
    assert isinstance(fmt, str)
    assert isinstance(info, dict)
    out = fmt.format(**info)
    assert isinstance(out, str)


@pytest.mark.parametrize("file", [
    'master', 'slave',
])
def test_printing_format_od_object(odpath, file):

    od = Node.LoadFile(odpath / (file + '.json'))

    lines = format_od_object(od, 0x1000)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)


@pytest.mark.parametrize("filepair", [
    ("slave-emcy.json", "slave-heartbeat.json"),
    ("diff-a.json", "diff-b.json"),
])
def test_printing_diff_nodes(odpath, filepair):

    print(filepair)

    m1 = Node.LoadFile(odpath / filepair[0])
    m2 = Node.LoadFile(odpath / filepair[1])

    lines = format_diff_nodes(m1, m2)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)

    lines = format_diff_nodes(m1, m2, data=True, show=True)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)

    lines = format_diff_nodes(m1, m2, raw=True)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)

    lines = format_diff_nodes(m1, m2, internal=True)
    assert isinstance(lines, types.GeneratorType)
    for line in lines:
        assert isinstance(line, str)
