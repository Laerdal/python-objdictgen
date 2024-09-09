import re
from pprint import pprint
import datetime
from freezegun import freeze_time
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


def test_jsonod_timezone():
    """ Test timezone handling in the jsonod module. """

    for now, offset, cmp in [
        ("2020-01-01 12:00:00", None, "2020-01-01T12:00:00"),
        ("2020-01-01 12:00:00", 5, "2020-01-01T17:00:00"),
        ("2020-01-01 12:00:00", -5, "2020-01-01T07:00:00"),
    ]:
        kw = {}
        if offset is not None:
            kw["tz_offset"] = offset
        with freeze_time(now, **kw):
            # The tzoffset is dependent on the current time, so we need to calculate it
            tzoffset = datetime.datetime.now().astimezone().utcoffset()
            tz = f"{tzoffset.seconds//3600:02}:{tzoffset.seconds%60:02}"
            print(f"tzoffset: {tzoffset}, {type(tzoffset)} {tz}")

            od = Node()
            out = generate_jsonc(od, compact=False, sort=False, internal=False, validate=True)
            m = re.search(r'^\s+"\$date": "(.*?)",$', out, re.M)
            if m:
                print(m[1])
                assert m[1] == cmp + "+" + tz


def test_jsonod_comments(odpath):
    """ Test that the json file exports comments correctly. """

    fname_jsonc = odpath / "jsonod-comments.jsonc"
    fname_json = odpath / "jsonod-comments.json"

    m1 = Node.LoadFile(fname_jsonc)

    with open(fname_jsonc, "r") as f:
        jsonc_data = f.read()
    with open(fname_json, "r") as f:
        json_data = f.read()

    out = generate_jsonc(m1, compact=False, sort=False, internal=False, validate=True, jsonc=True)

    # Compare the jsonc data with the generated data
    for a, b in zip(jsonc_data.splitlines(), out.splitlines()):
        if '"$date"' in a or '"$tool"' in a:
            continue
        assert a == b

    out = generate_jsonc(m1, compact=False, sort=False, internal=False, validate=True, jsonc=False)

    # Compare the json data with the generated data
    for a, b in zip(json_data.splitlines(), out.splitlines()):
        if '"$date"' in a or '"$tool"' in a:
            continue
        assert a == b
