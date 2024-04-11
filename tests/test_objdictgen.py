
import pytest
import objdictgen.__main__


def test_objdictgen_run(odjsoneds, mocker, wd):
    """Test that we're able to run objdictgen on our od files"""

    od = odjsoneds
    tmpod = od.stem

    if tmpod in ('legacy-strings', 'strings', 'unicode'):
        pytest.xfail("UNICODE_STRINGS is not supported in C")

    mocker.patch("sys.argv", [
        "objdictgen",
        str(od),
        od.stem + '.c',
    ])

    objdictgen.__main__.main_objdictgen()


def test_objdictgen_py2_compare(py2_cfile, mocker, wd, fn):
    """Test that comparing objectdictgen output from python2 and python3 is the same."""

    # Extract the path to the OD and the path to the python2 c file
    od, py2od = py2_cfile
    tmpod = od.stem

    if tmpod in ('legacy-strings'):
        pytest.xfail("UNICODE_STRINGS is not supported in C")

    mocker.patch("sys.argv", [
        "objdictgen",
        str(od),
        tmpod + '.c',
    ])

    objdictgen.__main__.main_objdictgen()

    def accept_known_py2_bugs(lines):
        """ Python2 outputs floats differently than python3, but the
            change is expected. This function attempts to find if the diff
            output only contains these expected differences."""
        for line in lines:
            if line in ("---", "+++"):
                continue
            if any(line.startswith(s) for s in (
                "@@ ", "-REAL32 ", "+REAL32 ", "-REAL64 ", "+REAL64 ",
            )):
                continue
            # No match, so there is some other difference. Report as error
            return lines
        pytest.xfail("Py2 prints floats differently than py3 which is expected")

    assert fn.diff(tmpod + '.c', py2od + '.c', n=0, postprocess=accept_known_py2_bugs)
    assert fn.diff(tmpod + '.h', py2od + '.h', n=0)
    assert fn.diff(tmpod + '_objectdefines.h', py2od + '_objectdefines.h', n=0)
