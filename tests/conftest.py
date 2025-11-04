""" Pytest configuration file for the objdictgen package """
import difflib
import os
import pickle
import shutil
import subprocess
import sys
from dataclasses import dataclass
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
ODTESTDIRS = [
    ODDIR,
]

# Files to exclude from testing all ODs
OD_EXCLUDE: list[Path] = [
    ODDIR / 'fail-validation.od',
    ODDIR / 'schema-error.json',
]

# Files to exclude from py2 legacy testing
PY2_OD_EXCLUDE: list[Path] = [
]

# Files to exclude in EDS testing
PY2_EDS_EXCLUDE: list[Path] = [
]

# Files to exclude in pickle testing
PY2_PICKLE_EXCLUDE: list[Path] = [
]

# Equivalent files that should compare as equal
COMPARE_EQUIVS = [
    ('alltypes',             'legacy-alltypes'),
    ('master',               'legacy-master'),
    ('slave',                'legacy-slave'),
    #( "profile-test",        "legacy-profile-test"),
    ( "profile-ds302",       "legacy-profile-ds302"),
    ( "profile-ds401",       "legacy-profile-ds401"),
    ( "profile-ds302-ds401", "legacy-profile-ds302-ds401"),
    #( "profile-ds302-test",  "legacy-profile-ds302-test"),
    ( "slave-ds302",         "legacy-slave-ds302"),
    ( "slave-emcy",          "legacy-slave-emcy"),
    ( "slave-heartbeat",     "legacy-slave-heartbeat"),
    ( "slave-nodeguarding",  "legacy-slave-nodeguarding"),
    ( "slave-sync",          "legacy-slave-sync"),
    ( "strings",             "legacy-strings"),
    ( "domain",              "legacy-domain"),
]


class ODPath(type(Path())):
    """ Overload on Path to add OD specific methods """

    @classmethod
    def nfactory(cls, iterable):
        excl = [p.absolute() for p in OD_EXCLUDE]
        return [
            cls(p.absolute()) for p in iterable
            if p.absolute() not in excl
        ]

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
            predicate = lambda x: True  # noqa: E731
        with open(a, 'r', encoding="utf-8") as f:
            da = [n.rstrip() for n in f if predicate(n)]
        with open(b, 'r', encoding="utf-8") as f:
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
    parser.addoption(
        "--extra", action="store_true", default=False, help=f"Run extra tests in {(ODDIR / 'extra-compare').relative_to(CWD)}"
    )


def pytest_generate_tests(metafunc):
    """ Special fixture generators """

    # Collect the list of od test directories
    oddirs = metafunc.config.getoption("oddir")
    if not oddirs:
        oddirs = list(ODTESTDIRS)

    # Add the extra directory if requested
    extra = metafunc.config.getoption("extra")
    if extra:
        oddirs.append(ODDIR / 'extra-compare')

    # Add "_suffix" fixture
    if "_suffix" in metafunc.fixturenames:
        metafunc.parametrize(
            "_suffix", ['od', 'jsonc', 'json', 'eds'], indirect=False, scope="session"
        )

    # Make a list of all .od files in tests/od
    odfiles = []
    for d in oddirs:
        odfiles += ODPath.nfactory(d.glob('*.od'))

    jsonfiles = []
    for d in oddirs:
        jsonfiles += ODPath.nfactory(d.glob('*.json'))
        jsonfiles += ODPath.nfactory(d.glob('*.jsonc'))

    edsfiles = []
    for d in oddirs:
        edsfiles += ODPath.nfactory(d.glob('*.eds'))

    def odids(odlist):
        return [str(o.relative_to(ODDIR).as_posix()) for o in odlist]

    # Add "odfile" fixture
    # Fixture for each of the .od files in the test directory
    if "odfile" in metafunc.fixturenames:
        data = sorted(odfiles)
        metafunc.parametrize(
            "odfile", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "odjson" fixture
    # Fixture for each of the .od and .json[c] files in the test directory
    if "odjson" in metafunc.fixturenames:
        data = sorted(odfiles + jsonfiles)
        metafunc.parametrize(
            "odjson", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "odjsoneds" fixture
    # Fixture for each of the .od, .json[c], and .eds files in the test directory
    if "odjsoneds" in metafunc.fixturenames:
        data = sorted(odfiles + jsonfiles + edsfiles)
        metafunc.parametrize(
            "odjsoneds", data, ids=odids(data), indirect=False, scope="session"
        )

    # Add "py2" fixture
    # Fixture for a python2 interpreter
    if "py2" in metafunc.fixturenames:
        py2_path = metafunc.config.getoption("py2")
        objdictgen_dir = metafunc.config.getoption("objdictgen")

        if py2_path:
            py2_path = py2_path.absolute()
        if objdictgen_dir:
            objdictgen_dir = objdictgen_dir.absolute()

        metafunc.parametrize("py2", [Py2(py2_path, objdictgen_dir)],
                                indirect=False, scope="session")

    # Add "equiv_files" fixture
    # Fixture for equivalent files that should compare as equal
    if "equiv_files" in metafunc.fixturenames:
        metafunc.parametrize("equiv_files", COMPARE_EQUIVS, ids=(e[0] for e in COMPARE_EQUIVS),
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
def testspath():
    """ Fixture returning the path to the tests directory """
    return (HERE).resolve()


@pytest.fixture
def fn():
    """ Fixture providing a helper class for testing functions """
    return Fn()


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


@pytest.fixture(scope="session")
def py2_cfile(odfile, py2, wd_session):
    """Fixture for making the cfiles generated by python2 objdictgen"""

    if not odfile.exists():
        pytest.skip(f"File not found: {odfile.rel_to_wd()}")

    if odfile in PY2_OD_EXCLUDE:
        pytest.skip(f"File {odfile.rel_to_wd()} is excluded from py2 testing")

    tmpod = odfile.stem

    shutil.copy(odfile, tmpod + '.od')

    pyapp = f"""
from nodemanager import *
import eds_utils, gen_cfile
eds_utils._ = lambda x: x
gen_cfile._ = lambda x: x
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

    if odfile in PY2_EDS_EXCLUDE:
        pytest.skip(f"File {odfile.rel_to_wd()} is excluded from py2 testing")

    tmpod = odfile.stem

    shutil.copy(odfile, tmpod + '.od')

    pyapp = f"""
from nodemanager import *
import eds_utils, gen_cfile
eds_utils._ = lambda x: x
gen_cfile._ = lambda x: x
manager = NodeManager()
manager.OpenFileInCurrent(r'{tmpod}.od')
if manager.CurrentNode.GetEntry(0x1018, 1) is None:
    raise Exception("Missing ID 0x1018 which won't work with EDS")
manager.ExportCurrentToEDSFile(r'{tmpod}.eds')
"""
    cmd = py2.run(script=pyapp, stderr=py2.PIPE)
    stderr = py2.stderr(cmd)
    print(stderr, file=sys.stderr)
    if cmd.returncode:
        lines = stderr.splitlines()
        pytest.xfail(f"Py2 failed: {lines[-1]}")

    return odfile, ODPath(tmpod).absolute()


@pytest.fixture(scope="session")
def py2_pickle(odfile, py2, wd_session):
    """Fixture for making the cfiles generated by python2 objdictgen"""

    if not odfile.exists():
        pytest.skip(f"File not found: {odfile.rel_to_wd()}")

    if odfile in PY2_PICKLE_EXCLUDE:
        pytest.skip(f"File {odfile.rel_to_wd()} is excluded from py2 testing")

    tmpod = odfile.stem

    shutil.copy(odfile, tmpod + '.od')

    pyapp = f"""
import pickle
from nodemanager import *
manager = NodeManager()
manager.OpenFileInCurrent(r'{tmpod}.od')
with open(r'{tmpod}.pickle', 'wb') as f:
    pickle.dump(manager.CurrentNode.__dict__, f, protocol=1)
"""
    cmd = py2.run(script=pyapp, stderr=py2.PIPE)
    stderr = py2.stderr(cmd)
    print(stderr, file=sys.stderr)
    if cmd.returncode:
        lines = stderr.splitlines()
        pytest.xfail(f"Py2 failed: {lines[-1]}")

    # Load the pickled data
    with open(tmpod + '.pickle', 'rb') as f:
        # It seems unicode_escape is needed to be able to encode low and high
        # ascii characters as well as unicode characters
        data = pickle.load(f, encoding='unicode_escape')

    return odfile, data


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
