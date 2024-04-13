import pytest
from pprint import pprint
from objdictgen import Node
from objdictgen.jsonod import generate_jsonc, generate_node, remove_jsonc
from .test_odcompare import shave_equal


def test_jsonod_remove_jsonc():
    """ Test that the remove_jsonc function works as expected. """

    out = remove_jsonc("""{
"a": "abc",  // remove
"b": 42
}""")
    assert out == """{
"a": "abc",
"b": 42
}"""

    # This was a bug where there quoted string made jsonc parsing fail
    out = remove_jsonc("""{
"a": "a\\"bc",  // remove
"b": 42
}""")
    assert out == """{
"a": "a\\"bc",
"b": 42
}"""

    out = remove_jsonc("""{
"a": "a\\"bc",  /* remove it */ "c": 42,
"b": 42
}""")
    assert out == """{
"a": "a\\"bc","c": 42,
"b": 42
}"""

    out = remove_jsonc("""{
"a": "a'bc",  // remove
"b": 42
}""")
    assert out == """{
"a": "a'bc",
"b": 42
}"""


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
