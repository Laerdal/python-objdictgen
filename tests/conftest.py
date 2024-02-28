""" Pytest configuration file for the objdictgen package """
import shutil
from typing import Generator
import os
import sys
import difflib
from dataclasses import dataclass
import subprocess
from pathlib import Path
import pytest

import objdictgen
import objdictgen.node


# The path to this directory
HERE = Path(__file__).parent

# Where are pytest started from?
CWD = Path(os.getcwd())

# Location of the test OD files
ODDIR = HERE / 'od'

# Default OD test directories
DEFAULT_ODTESTDIRS = [
    ODDIR,
    ODDIR / 'legacy-compare',
    ODDIR / 'extra-compare',
]

# Files to exclude from py2 legacy testing
PY2_OD_EXCLUDE = [
    ODDIR / "unicode.json",
    ODDIR / "unicode.od",
]


class ODPath(type(Path())):
    """ Overload on Path to add OD specific methods """

    @classmethod
    def nfactory(cls, iterable):
        for p in iterable:
            obj = cls(p.absolute())
            if p not in PY2_OD_EXCLUDE:
                yield obj

    def __add__(self, other):
        return ODPath(self.parent / (self.name + other))

    def __truediv__(self, other):
        return ODPath(Path.__truediv__(self, other))

    def rel_to_odpath(self):
        return self.relative_to(ODDIR.absolute())

    def rel_to_wd(self):
        return self.relative_to(CWD)

    @classmethod
    def n(cls, *args, **kwargs):
        return cls(*args, **kwargs)


class Fn:
    """ Helper class for testing functions """

    @staticmethod
    def diff(a, b, predicate=None, postprocess=None, **kw):
        """ Diff two files """
        if predicate is None:
            predicate = lambda x: True
        with open(a, 'r') as f:
            da = [n.rstrip() for n in f if predicate(n)]
        with open(b, 'r') as f:
            db = [n.rstrip() for n in f if predicate(n)]
        out = list(d.rstrip() for d in difflib.unified_diff(da, db, **kw))
        if out and postprocess:
            out = list(postprocess(out))
        if out:
            print('\n'.join(out))
            pytest.fail(f"Files {a} and {b} differ")
        return not out


@dataclass
class Py2:
    """ Class for calling python2 """
    py2: Path | None
    objdictgen: Path | None

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT

    def run(self, script=None, *, cmd='-', **kwargs):

        if not self.py2:
            pytest.skip("--py2 configuration option not set")
        if not self.py2.exists():
            pytest.fail(f"--py2 executable {self.py2} cannot be found")
        if not self.objdictgen:
            pytest.skip("--objdictgen configuation option not set")
        if not self.objdictgen.exists():
            pytest.fail(f"--objdictgen directory {self.objdictgen} cannot be found")

        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.objdictgen)

        if script is not None:
            indata = script.encode('ascii', 'backslashreplace')
        else:
            indata = None

        args = kwargs.pop('args', [])
        kw = {
            'input': indata,
            'env': env,
            'text': False,
        }
        kw.update(**kwargs)

        return subprocess.run([self.py2, cmd] + args, executable=self.py2, **kw)

    def stdout(self, proc):
        if not proc.stdout:
            return ''
        return proc.stdout.decode('utf-8')

    def stderr(self, proc):
        if not proc.stderr:
            return ''
        return proc.stderr.decode('utf-8')

    def check(self, proc):
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, proc.args, self.stdout(proc))
        return proc


def pytest_addoption(parser):
    """ Add options to the pytest command line """
    parser.addoption(
        "--py2", action="store", default=None, type=Path, help="Path to python2 executable",
    )
    parser.addoption(
        "--objdictgen", action="store", default=None, type=Path, help="Path to legacy objdictgen directory",
    )
    parser.addoption(
        "--oddir", action="append", default = None, type=Path, help="Path to OD test directories",
    )


def pytest_generate_tests(metafunc):
    """ Special fixture generators """

    # Collect the list of od test directories
    oddirs = metafunc.config.getoption("oddir")
    if not oddirs:
        oddirs = list(DEFAULT_ODTESTDIRS)

    # Add "_suffix" fixture
    if "_suffix" in metafunc.fixturenames:
        metafunc.parametrize(
            "_suffix", ['od', 'json', 'eds'], indirect=False, scope="session"
        )

    # Make a list of all .od files in tests/od
    odfiles = []
    for d in oddirs:
        odfiles += ODPath.nfactory(d.glob('*.od'))

    jsonfiles = []
    for d in oddirs:
        jsonfiles += ODPath.nfactory(d.glob('*.json'))

    edsfiles = []
    for d in oddirs:
        edsfiles += ODPath.nfactory(d.glob('*.eds'))

    def odids(odlist):
        return [str(o.relative_to(ODDIR).as_posix()) for o in odlist]

    # Add "odfile" fixture
    if "odfile" in metafunc.fixturenames:
        data = sorted(odfiles)
        metafunc.parametrize(
            "odfile", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "odjson" fixture
    if "odjson" in metafunc.fixturenames:
        data = sorted(odfiles + jsonfiles)
        metafunc.parametrize(
            "odjson", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "odjsoneds" fixture
    if "odjsoneds" in metafunc.fixturenames:
        data = sorted(odfiles + jsonfiles + edsfiles)
        metafunc.parametrize(
            "odjsoneds", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "py2" fixture
    if "py2" in metafunc.fixturenames:
        py2_path = metafunc.config.getoption("py2")
        objdictgen_dir = metafunc.config.getoption("objdictgen")

        if py2_path:
            py2_path = py2_path.absolute()
        if objdictgen_dir:
            objdictgen_dir = objdictgen_dir.absolute()

        metafunc.parametrize("py2", [Py2(py2_path, objdictgen_dir)],
                                indirect=False, scope="session")


def pytest_collection_modifyitems(items):
    """Modifies test items in place to ensure test modules run in a given order."""
    # Somewhat of a hack to run test cases ub in sorted order
    items[:] = list(sorted(items, key=lambda k: (k.module.__name__, k.name)))


#
#  FIXTURES
# ========================================
#

@pytest.fixture
def basepath():
    """ Fixture returning the base of the project """
    return (HERE / '..').resolve()


@pytest.fixture
def fn():
    """ Fixture providing a helper class for testing functions """
    return Fn()


@pytest.fixture(scope="session")
def odfile(request) -> Generator[ODPath, None, None]:
    """ Fixture for each of the od files in the test directory """
    return request.param


@pytest.fixture
def odpath():
    """ Fixture returning the path for the od test directory """
    return ODPath(ODDIR.absolute())


@pytest.fixture
def profile(monkeypatch):
    """ Fixture that monkeypatches the profile load directory to include the OD directory
        for testing
    """
    newdirs = []
    newdirs.extend(objdictgen.PROFILE_DIRECTORIES)
    newdirs.append(ODDIR)
    monkeypatch.setattr(objdictgen, 'PROFILE_DIRECTORIES', newdirs)
    return None


@pytest.fixture
def py2(request) -> Generator[Py2, None, None]:
    """ Fixture for each of the od files in the test directory """
    return request.param


@pytest.fixture(scope="session")
def py2_cfile(odfile, py2, wd_session):
    """Fixture for making the cfiles generated by python2 objdictgen"""

    if not odfile.exists():
        pytest.skip(f"File not found: {odfile.rel_to_wd()}")

    tmpod = odfile.stem

    shutil.copy(odfile, tmpod + '.od')

    pyapp = f"""
from nodemanager import *
manager = NodeManager()
manager.OpenFileInCurrent(r'{tmpod}.od')
manager.ExportCurrentToCFile(r'{tmpod}.c')
"""
    cmd = py2.run(script=pyapp, stderr=py2.PIPE)
    stderr = py2.stderr(cmd)
    print(stderr, file=sys.stderr)
    if cmd.returncode:
        lines = stderr.splitlines()
        pytest.xfail(f"Py2 failed: {lines[-1]}")

    return odfile, ODPath(tmpod).absolute()


@pytest.fixture(scope="session")
def py2_edsfile(odfile, py2, wd_session):
    """Fixture for making the cfiles generated by python2 objdictgen"""

    if not odfile.exists():
        pytest.skip(f"File not found: {odfile.rel_to_wd()}")

    tmpod = odfile.stem

    shutil.copy(odfile, tmpod + '.od')

    pyapp = f"""
from nodemanager import *
manager = NodeManager()
manager.OpenFileInCurrent(r'{tmpod}.od')
manager.ExportCurrentToEDSFile(r'{tmpod}.eds')
"""
    cmd = py2.run(script=pyapp, stderr=py2.PIPE)
    stderr = py2.stderr(cmd)
    print(stderr, file=sys.stderr)
    if cmd.returncode:
        lines = stderr.splitlines()
        pytest.xfail(f"Py2 failed: {lines[-1]}")

    return odfile, ODPath(tmpod).absolute()


@pytest.fixture
def wd(tmp_path):
    """ Fixture that changes the working directory to a temp location """
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    yield Path(os.getcwd())
    os.chdir(str(cwd))


@pytest.fixture(scope="session")
def wd_session(tmp_path_factory):
    """ Fixture that changes the working directory to a temp location """
    cwd = os.getcwd()
    tmp_path = tmp_path_factory.mktemp("session")
    os.chdir(str(tmp_path))
    yield Path(os.getcwd())
    os.chdir(str(cwd))
