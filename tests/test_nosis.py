from dataclasses import dataclass
import pickle
import pytest

from objdictgen import nosis


def test_nosis_aton():

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


def test_nosis_ntoa():

    ntoa = nosis.ntoa
    assert ntoa(1) == "1"
    assert ntoa(0.) == "0."
    assert ntoa(1.5) == "1.5"
    assert ntoa(1+2j) == "1+2j"

    with pytest.raises(ValueError):
        ntoa("foo")


TESTS = [
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

XML_STRINGS = [
    ("'", "'"),
]


def cmp_xml(d):
    out = nosis.xmldump(None, d)
    print(type(out), out)
    data = nosis.xmlload(out)
    assert d == data


def test_nosis_safe_string():

    for s in TESTS:
        assert nosis.safe_string(s[0]) == s[1]

    for s in TESTS + XML_STRINGS:
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


@dataclass
class TypesDut:
    _str: str
    _int: int
    _float: float
    _complex: complex
    _none: None
    _true: bool
    _false: bool
    _list: list
    _tuple: tuple
    _dict: dict


@pytest.fixture()
def types_dut():
    return TypesDut(
        _str="foo",
        _int=1, _float=1.5, _complex=1+2j,
        _none=None, _true=True, _false=False,
        _list=[1, 2, 3], _tuple=(1, 2, 3), _dict={'a': 1, 'b': 2},
    )


def test_nosis_datatypes(types_dut):
    """Test dump and load of all datatypes"""

    xml = nosis.xmldump(None, types_dut)
    # print(xml)

    nosis.add_class_to_store('TypesDut', TypesDut)
    data = nosis.xmlload(xml)
    # print(data)

    assert types_dut == data


def test_nosis_py2_datatypes_load(py2, wd, types_dut):
    """Test that py2 gnosis is able to load a py3 nosis generated XML"""

    nosis.add_class_to_store('TypesDut', TypesDut)

    xml = nosis.xmldump(None, types_dut)

    # Import the XML using the old py2 gnosis and pickle it
    pyapp=f"""
from gnosis.xml.pickle import *
import pickle, sys
a = loads('''{xml}''')
with open("dump.pickle", "wb") as f:
    pickle.dump(a.__dict__, f, protocol=0)
"""
    cmd = py2.run(pyapp, stdout=py2.PIPE)
    out = py2.stdout(cmd)
    print(out)
    py2.check(cmd)

    # Load the pickled data and compare
    with open("dump.pickle", "rb") as f:
        data = pickle.load(f)
        print(data)

    assert types_dut.__dict__ == data


def xtest_nosis_py2_datatypes_dump(py2, wd, types_dut):
    """Test that py3 nosis is able to read py2 generated XML"""

    # Import the XML using the old py2 gnosis and pickle it
    pyapp="""
from gnosis.xml.pickle import *
class TypesDut:
    def __init__(self):
        self._str = "foo"
        self._int = 1
        self._float = 1.5
        self._complex = 1+2j
        self._none = None
        self._true = True
        self._false = False
        self._list = [1, 2, 3]
        self._tuple = (1, 2, 3)
        self._dict = {'a': 1, 'b': 2}
a = TypesDutLegacy()
xml = dumps(a)
with open("dump.xml", "wb") as f:
    f.write(xml)
"""
    cmd = py2.run(pyapp, stdout=py2.PIPE)
    out = py2.stdout(cmd)
    print(out)
    py2.check(cmd)

    # Load the pickled data and compare
    with open("dump.xml", "rb") as f:
        xml = f.read().decode()

    nosis.add_class_to_store('TypesDut', TypesDut)
    data = nosis.xmlload(xml)
    print(data)

    assert types_dut == data
