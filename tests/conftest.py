""" Pytest configuration file for the objdictgen package """
from typing import Generator
import os
import difflib
from dataclasses import dataclass
import subprocess
from pathlib import Path
import pytest

import objdictgen
import objdictgen.node


HERE = Path(__file__).parent

# Location of the test OD files
ODDIR = HERE / 'od'

# Default OD test directories
DEFAULT_ODTESTDIRS = [
    ODDIR / 'legacy-compare',
    ODDIR / 'extra-compare',
]


class ODPath(type(Path())):
    """ Overload on Path to add OD specific methods """

    def __add__(self, other):
        return ODPath(self.parent / (self.name + other))

    def __truediv__(self, other):
        return ODPath(Path.__truediv__(self, other))


class Fn:
    """ Helper class for testing functions """

    @staticmethod
    def diff(a, b, predicate=None, **kw):
        """ Diff two files """
        if predicate is None:
            predicate = lambda x: True
        print(a, b)
        with open(a, 'r') as f:
            da = [n.rstrip() for n in f if predicate(n)]
        with open(b, 'r') as f:
            db = [n.rstrip() for n in f if predicate(n)]
        out = tuple(difflib.unified_diff(da, db, **kw))
        if out:
            print('\n'.join(o.rstrip() for o in out))
        return not out


@dataclass
class Py2:
    """ Class for calling python2 """
    py2: Path | None
    objdictgen: Path | None

    def __post_init__(self):
        print("\n    ****POST****\n")

    def run(self, script, **kwargs):

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

        indata = script.encode('ascii', 'backslashreplace')

        kw = {
            'input': indata,
            'env': env,
            'text': False,
        }
        kw.update(**kwargs)

        return subprocess.check_output([self.py2, '-'], executable=self.py2, **kw)


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
    ''' Special fixture generators '''

    # Collect the list of od test directories
    oddirs = metafunc.config.getoption("oddir")
    if not oddirs:
        oddirs = list(DEFAULT_ODTESTDIRS)

    # Add "odfile" fixture
    if "odfile" in metafunc.fixturenames:

        # Make a list of all .od files in tests/od
        odfiles = []
        for d in oddirs:
            odfiles.extend(
                ODPath(f.with_suffix('').absolute())
                for f in d.glob('*.od')
            )

        metafunc.parametrize("odfile", odfiles,
            ids=[str(o.relative_to(ODDIR).as_posix()) for o in odfiles],
            indirect=False
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

@pytest.fixture
def odfile(request) -> Generator[ODPath, None, None]:
    """ Fixture for each of the od files in the test directory """
    print(type(request.param))
    yield request.param

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
    yield None

@pytest.fixture
def py2(request) -> Generator[Py2, None, None]:
    """ Fixture for each of the od files in the test directory """
    yield request.param

@pytest.fixture
def wd(tmp_path):
    """ Fixture that changes the working directory to a temp location """
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    yield Path(os.getcwd())
    os.chdir(str(cwd))
