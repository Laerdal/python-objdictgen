from dataclasses import dataclass
import pytest

from objdictgen import nosis


def test_aton():

    aton = nosis.aton
    assert aton("(1)") == 1
    assert aton("0") == 0
    assert aton("3") == 3
    assert aton("1.") == 1.
    assert aton("2l") == 2
    assert aton("0x10") == 16
    assert aton("-0x04") == -4
    assert aton("010") == 8
    assert aton("-07") == -7
    assert aton("1+2j") == 1+2j
    assert aton("1:2") == 1+2j

    with pytest.raises(ValueError):
        aton("1.2.3")


def test_ntoa():

    ntoa = nosis.ntoa
    assert ntoa(1) == "1"
    assert ntoa(0.) == "0."
    assert ntoa(1.5) == "1.5"
    assert ntoa(1+2j) == "1+2j"

    with pytest.raises(ValueError):
        ntoa("foo")


SAFE_TESTS = [
    ("", ""),
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', '&quot;'),
    ("'", "&apos;"),
    ("\x3f", "?"),
    ("\x00", "\\x00"),
    ("foo", "foo"),
    ("fu's", "fu&apos;s"),
    ("fu<s", "fu&lt;s"),
]

UNSAFE_TESTS = [
    ("", ""),
    # ("'", "'"),
    ("\x3f", "?"),
    # ("\x00", "\\x00"),
    ("foo", "foo"),
    # ("fu's", "fu&apos;s"),
    # ("fu<s", "fu&lt;s"),
]


def cmp_xml(d):
    out = nosis.xmldump(None, d)
    print(out)
    data = nosis.xmlload(out)
    assert d == data


def test_safe_string():

    for s in SAFE_TESTS:
        assert nosis.safe_string(s[0]) == s[1]


def test_unsafe_string():

    for s in UNSAFE_TESTS:
        assert nosis.unsafe_string(s[1]) == s[0]


def test_nosis_dump_load():

    @dataclass
    class Dut:
        s: str

    nosis.add_class_to_store('Dut', Dut)

    cmp_xml(Dut("foo"))
    cmp_xml(Dut("fu's"))
    cmp_xml(Dut("f<u>s"))
    cmp_xml(Dut("m&m"))
    # cmp_xml(Data("\x00\x00\x00\x00"))


def test_nosis_xml_variants():

    @dataclass
    class Dut:
        s: str

    nosis.add_class_to_store('Dut', Dut)

    # Attribute in body
    xml = """<?xml version="1.0"?>
<!DOCTYPE PyObject SYSTEM "PyObjects.dtd">
<PyObject module="tests.test_nosis" class="Dut" id="2045276382864">
<attr name="s" type="string">hello</attr>
</PyObject>"""

    data = nosis.xmlload(xml)
    assert data.s == "hello"

    # Attribute in tag
    xml = """<?xml version="1.0"?>
<!DOCTYPE PyObject SYSTEM "PyObjects.dtd">
<PyObject module="tests.test_nosis" class="Dut" id="1430208232144">
<attr name="s" type="string" value="world" />
</PyObject>"""

    data = nosis.xmlload(xml)
    assert data.s == "world"


def test_nosis_all_datatypes():
    '''Test all datatypes'''

    # @dataclass
    # class C:
    #     s: str

    @dataclass
    class Dut:
        s: str
        i: int
        l: list
        d: dict
        t: tuple
        n: None
        f: float
        c: complex
        T: bool
        F: bool
        # o: C
        # b: bytes

    nosis.add_class_to_store('Dut', Dut)
    # nosis.add_class_to_store('C', C)

    cmp_xml(Dut(
        s="foo", i=1, l=[1, 2, 3], d={'a': 1, 'b': 2}, t=(1, 2, 3),
        n=None, f=1.5, c=1+2j, T=True, F=False #, o=C("foo"), b=b'\x00\x01\x02'
    ))
