import pytest
from pprint import pprint
from objdictgen import Node
from objdictgen.jsonod import generate_jsonc, generate_node
from .test_odcompare import shave_equal

def test_jsonod_roundtrip(odjsoneds):
    """ Test that the file can be exported to json and that the loaded file
        is equal to the first.
    """
    od = odjsoneds

    m1 = Node.LoadFile(od)

    out = generate_jsonc(m1, compact=False, sort=False, internal=False, validate=True)

    m2 = generate_node(out)

    a, b = shave_equal(m1, m2, ignore=["IndexOrder", "DefaultStringSize"])
    try:
        # pprint(out)
        pprint(a)
        pprint(b)
        # pprint(a.keys())
        # pprint(b.keys())
        # pprint(a.keys() == b.keys())
        # pprint(a["UserMapping"][8193])
        # pprint(b["UserMapping"][8193])
    except KeyError:
        pass
    assert a == b


def test_jsonod_roundtrip_compact(odjsoneds):
    """ Test that the file can be exported to json and that the loaded file
        is equal to the first.
    """
    od = odjsoneds

    m1 = Node.LoadFile(od)

    out = generate_jsonc(m1, compact=True, sort=False, internal=False, validate=True)

    m2 = generate_node(out)

    a, b = shave_equal(m1, m2, ignore=["IndexOrder", "DefaultStringSize"])
    assert a == b


def test_jsonod_roundtrip_internal(odjsoneds):
    """ Test that the file can be exported to json and that the loaded file
        is equal to the first.
    """
    od = odjsoneds

    m1 = Node.LoadFile(od)

    out = generate_jsonc(m1, compact=False, sort=False, internal=True, validate=True)

    m2 = generate_node(out)

    a, b = shave_equal(m1, m2, ignore=["IndexOrder", "DefaultStringSize"])
    assert a == b
