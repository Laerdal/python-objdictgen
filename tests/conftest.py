import os
import glob
import difflib
from dataclasses import dataclass
import pytest

import objdictgen
import objdictgen.node


HERE = os.path.split(__file__)[0]

# Location of the test OD files
ODDIR = os.path.join(HERE, 'od')

# Make a list of all .od files in tests/od
_ODFILES = list(glob.glob(os.path.join(ODDIR, 'legacy-compare', '*.od')))
_ODFILES.extend(glob.glob(os.path.join(ODDIR, 'extra-compare', '*.od')))


@dataclass
class ODFile:
    """ Class representing an OD file """
    filename: str

    def __str__(self):
        return self.filename

    def __add__(self, other):
        return self.filename + other

    @property
    def name(self):
        return os.path.split(self.filename)[1]

    @property
    def relpath(self):
        return os.path.relpath(self.filename, ODDIR)


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


# List of all OD files
ODFILES = [ODFile(os.path.abspath(x.replace('.od', ''))) for x in _ODFILES]

def pytest_generate_tests(metafunc):
    ''' Special fixture generators '''
    if "odfile" in metafunc.fixturenames:
        metafunc.parametrize("odfile", ODFILES, ids=[
            o.relpath for o in ODFILES
        ], indirect=True)


#
#  FIXTURES
# ========================================
#

@pytest.fixture
def oddir():
    """ Fixture returning the path for the od test directory """
    return os.path.abspath(os.path.join(ODDIR))

@pytest.fixture
def basepath():
    """ Fixture returning the base of the project """
    return os.path.abspath(os.path.join(HERE, '..'))

@pytest.fixture
def wd(tmp_path):
    """ Fixture that changes the working directory to a temp location """
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    yield os.getcwd()
    os.chdir(str(cwd))

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
def odfile(request, profile):
    """ Fixture for each of the od files in the test directory """
    yield request.param

@pytest.fixture
def fn():
    """ Fixture providing a helper class for testing functions """
    return Fn()
