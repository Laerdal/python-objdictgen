
import pytest
from unittest import mock
import os
import sys

@pytest.fixture
def setenvvar(monkeypatch):
    with mock.patch.dict(os.environ, {"TEST": "foobar"}):
        yield


def test_filereplacer(basepath, wd, setenvvar):

    sys.path.append(str(basepath / "packaging"))
    os.chdir(basepath)
    from filereplacer import convert

    tests = [
        (1, "Test data", "Test data"),
        (2, "@@{name}", "objdictgen"),
        (3, "@@{TEST}", "foobar"),  # Read from the mocked environment variable
        (4, "@@{nonexisting}", "non-existing"),
    ]

    for i, data, result in tests:
        infile = wd / "test.txt"
        outfile = wd / "out.txt"
        with open(infile, "w", encoding="utf-8") as f:
            f.write(data)
        if i == 4:
            with pytest.raises(KeyError):
                convert(infile, outfile)
            continue
        else:
            convert(infile, outfile)
            with open(outfile, "r", encoding="utf-8") as f:
                assert f.read() == result
