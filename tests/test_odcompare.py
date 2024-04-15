import copy
import shutil
import re
import os
import pytest

from objdictgen import Node
from objdictgen.nosis import unsafe_string


def shave_dict(a, b):
    """ Recursively remove equal elements from two dictionaries.
        Note: This function modifies the input dictionaries.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a.keys()) | set(b.keys()):
            if k in a and k in b:
                a[k], b[k] = shave_dict(a[k], b[k])
            if k in a and k in b and a[k] == b[k]:
                del a[k]
                del b[k]
    return a, b


def shave_equal(a, b, ignore=None, preprocess=None):
    """ Remove equal elements from two objects and return the remaining elements.
    """
    a = copy.deepcopy(a.__dict__)
    b = copy.deepcopy(b.__dict__)

    for n in ignore or []:
        a.pop(n, None)
        b.pop(n, None)

    if preprocess:
        preprocess(a, b)

    return shave_dict(a, b)


def test_load_compare(odjsoneds):
    """ Tests that the file can be loaded twice without failure and no
        difference.
    """
    od = odjsoneds

    # Load the OD two times
    m1 = Node.LoadFile(od)
    m2 = Node.LoadFile(od)

    a, b = shave_equal(m1, m2)
    assert a == b


def test_odload_py2_compare(py2_pickle, wd):
    """ Load the OD and compare it with the python2 loaded OD to ensure that
        the OD is loaded equally. This is particular important when comparing
        string encoding.
    """
    od, py2data = py2_pickle

    # Load the OD
    m1 = Node.LoadFile(od)

    # Special handling for string handling in py2. Py3 puts everything in OD
    # as value attributes, which py2 reads as strings. A py2 string does not
    # support unicode, so the data will be coming over as raw bytes in the
    # string. If they differ, attempt to convert the py2 string to utf-8
    def convert_to_utf8(index: int):
        """Convert the string to utf-8 if it is different from the py2 data"""
        a = m1.Dictionary[index]
        b = py2data["Dictionary"][index]
        if a != b:
            py2data["Dictionary"][index] = b.encode('latin-1').decode('utf-8')

    # # Convert the known string that are encoded differently in py2
    if od.stem == 'domain':
        convert_to_utf8(8194)

    a, b = shave_dict(py2data, m1.__dict__)
    assert a == b


def test_odexport(odjsoneds, wd, fn):
    """ Test that the od file can be exported to od and that the loaded file
        is equal to the original.
    """
    od = odjsoneds
    tmpod = od.stem

    m0 = Node.LoadFile(od)
    m1 = Node.LoadFile(od)

    # Save the OD
    m1.DumpFile(tmpod + '.od', filetype='od')

    # Assert that the object is unmodified by the export
    a, b = shave_equal(m0, m1)
    assert a == b

    # Modify the od files to remove unique elements
    #  .od.orig  is the original .od file
    #  .od       is the generated .od file
    re_id = re.compile(b'(id|module)="\\w+"')
    with open(od, 'rb') as fi:
        with open(f'{od.name}.orig', 'wb') as fo:
            for line in fi:
                fo.write(re_id.sub(b'', line))
    shutil.move(tmpod + '.od', tmpod + '.tmp')
    with open(tmpod + '.tmp', 'rb') as fi:
        with open(tmpod + '.od', 'wb') as fo:
            for line in fi:
                fo.write(re_id.sub(b'', line))
    os.remove(tmpod + '.tmp')

    # Load the saved OD
    m2 = Node.LoadFile(tmpod + '.od')

    # OD format never contains IndexOrder, so its ok to ignore it
    a, b = shave_equal(m1, m2, ignore=('IndexOrder',))
    assert a == b


def test_jsonexport(odjsoneds, wd):
    """ Test that the file can be exported to json and that the loaded file
        is equal to the first.
    """
    od = odjsoneds
    tmpod = od.stem

    m0 = Node.LoadFile(od)
    m1 = Node.LoadFile(od)

    m1.DumpFile(tmpod + '.json', filetype='json')

    # Assert that the object is unmodified by the export
    a, b = shave_equal(m0, m1)
    assert a == b


def test_cexport(odjsoneds, wd, fn):
    """ Test that the file can be exported to c
    """
    od = odjsoneds
    tmpod = od.stem

    if tmpod in ('strings', 'legacy-strings'):
        pytest.xfail("UNICODE_STRINGS is not supported in C")

    m0 = Node.LoadFile(od)
    m1 = Node.LoadFile(od)

    m1.DumpFile(tmpod + '.c', filetype='c')

    # Assert that the object is unmodified by the export
    a, b = shave_equal(m0, m1)
    assert a == b


def test_cexport_py2_compare(py2_cfile, wd, fn):
    """ Test that the exported c files match the ones generated by python2
    """

    # Extract the path to the OD and the path to the python2 c file
    od, py2od = py2_cfile
    tmpod = od.stem

    if tmpod in ('strings', 'legacy-strings', 'domain'):
        pytest.xfail("UNICODE_STRINGS is not supported in C")

    m0 = Node.LoadFile(od)

    m0.DumpFile(tmpod + '.c', filetype='c')

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

    # Compare the generated c files
    assert fn.diff(tmpod + '.c', py2od + '.c', n=0, postprocess=accept_known_py2_bugs)
    assert fn.diff(tmpod + '.h', py2od + '.h', n=0)
    assert fn.diff(tmpod + '_objectdefines.h', py2od + '_objectdefines.h', n=0)


def test_edsexport(odjsoneds, wd, fn):
    """ Test that the file can be exported to eds """

    od = odjsoneds
    tmpod = od.stem

    m0 = Node.LoadFile(od)
    m1 = Node.LoadFile(od)

    try:
        m1.DumpFile(tmpod + '.eds', filetype='eds')

    except KeyError as e:
        if str(e) in "KeyError: 'Index 0x1018 does not exist'":
            pytest.xfail("Index 0x1018 does not exist, so EDS export will fail")
        raise

    # Assert that the object is unmodified by the export
    a, b = shave_equal(m0, m1)
    assert a == b


def test_edsexport_py2_compare(py2_edsfile, wd, fn):
    """ Test that the exported c files match the ones generated by python2
    """

    # Extract the path to the OD and the path to the python2 eds file
    od, py2od = py2_edsfile
    tmpod = od.stem

    m0 = Node.LoadFile(od)

    m0.DumpFile(tmpod + '.eds', filetype='eds')

    assert fn.diff(tmpod + '.eds', py2od + '.eds')


def test_edsimport(odjsoneds, wd):
    """ Test that EDS files can be exported and imported again.
    """
    od = odjsoneds
    tmpod = od.stem

    m1 = Node.LoadFile(od)

    try:
        m1.DumpFile(tmpod + '.eds', filetype='eds')
    except KeyError as e:
        if str(e) in "KeyError: 'Index 0x1018 does not exist'":
            pytest.xfail("Index 0x1018 does not exist, so EDS export will fail")
        raise

    m2 = Node.LoadFile(tmpod + '.eds')

    def accept_known_eds_limitation(a, b):
        """ This function mitigates a known limitation in the EDS file format
            to make the rest of the file comparison possible.

            In the EDS the Dictionary element contains dynamic code, such
            as "'{True:"$NODEID+0x%X00"%(base+2),False:0x80000000}[base<4]'",
            while in the EDS this is compiled to values such as'"$NODEID+0x500"'

            The fix is to replace the dynamic code with the calculated value
            which is the same as is done in the EDS file generation.
        """
        def num(x):
            if isinstance(x, list):
                return x[1:]
            return x
        a['Dictionary'] = {
            i: num(m1.GetEntry(i, compute=False))
            for i in m1
        }
        b['Dictionary'] = {
            i: num(m2.GetEntry(i, compute=False))
            for i in m2
        }

    # EDS files are does not contain the complete information as OD and JSON
    # files does.
    a, b = shave_equal(
        m1, m2, preprocess=accept_known_eds_limitation,
        ignore=(
            "IndexOrder", "Profile", "ProfileName", "DS302", "UserMapping",
            "ParamsDictionary", "DefaultStringSize"
        )
    )
    assert a == b


def test_jsonimport(odjsoneds, wd):
    """ Test that JSON files can be exported and read back. It will be
        compared with orginal contents.
    """
    od = odjsoneds
    tmpod = od.stem

    m1 = Node.LoadFile(od)

    m1.DumpFile(tmpod + '.json', filetype='json')

    m2 = Node.LoadFile(tmpod + '.json')

    # Only include IndexOrder when comparing json files
    ignore = ('IndexOrder',) if od.suffix != '.json' else None
    a, b = shave_equal(m1, m2, ignore=ignore)
    assert a == b


def test_jsonimport_compact(odjsoneds, wd):
    """ Test that JSON files can be exported and read back. It will be
        compared with orginal contents.
    """
    od = odjsoneds
    tmpod = od.stem

    m1 = Node.LoadFile(od)

    m1.DumpFile(tmpod + '.json', filetype='json', compact=True)

    m2 = Node.LoadFile(tmpod + '.json')

    # Only include IndexOrder when comparing json files
    ignore = ('IndexOrder',) if od.suffix != '.json' else None
    a, b = shave_equal(m1, m2, ignore=ignore)
    assert a == b


def test_od_json_compare(odfile):
    """ Test reading and comparing the od and json with the same filename
    """

    odjson = odfile.with_suffix('.json')

    if not odjson.exists():
        pytest.skip(f"No .json file next to '{odfile.rel_to_wd()}'")

    m1 = Node.LoadFile(odfile)
    m2 = Node.LoadFile(odjson)

    # IndexOrder doesn't make sense in OD file so ignore it
    a, b = shave_equal(m1, m2, ignore=('IndexOrder',))
    assert a == b


PROFILE_ODS = [
    "profile-test",
    "profile-ds302",
    "profile-ds401",
    "profile-ds302-ds401",
    "profile-ds302-test",
    "legacy-profile-test",
    "legacy-profile-ds302",
    "legacy-profile-ds401",
    "legacy-profile-ds302-ds401",
    "legacy-profile-ds302-test",
]


@pytest.mark.parametrize("oddut", PROFILE_ODS)
@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_save_wo_profile(odpath, oddut, suffix, wd):
    """ Test that saving a od that contains a profile creates identical
        results as the original. This test has no access to the profile dir
    """

    fa = odpath / oddut
    fb = oddut + '.' + suffix

    m1 = Node.LoadFile(fa + '.od')
    m1.DumpFile(fb, filetype=suffix)

    m2 = Node.LoadFile(fb)

    # Ignore the IndexOrder when working with json files
    ignore = ('IndexOrder',) if suffix == 'json' else None
    a, b = shave_equal(m1, m2, ignore=ignore)
    assert a == b


@pytest.mark.parametrize("oddut", PROFILE_ODS)
@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_save_with_profile(odpath, oddut, suffix, wd, profile):
    """ Test that saving a od that contains a profile creates identical
        results as the original. This test have access to the profile dir
    """

    # FIXME: Does this work? The test succeeds even if the profile is missing

    fa = odpath / oddut
    fb = oddut + '.' + suffix

    m1 = Node.LoadFile(fa + '.od')
    m1.DumpFile(fb, filetype=suffix)

    m2 = Node.LoadFile(fb)

    # Ignore the IndexOrder when working with json files
    ignore = ('IndexOrder',) if suffix == 'json' else None
    a, b = shave_equal(m1, m2, ignore=ignore)
    assert a == b


@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_equiv_compare(odpath, equiv_files, suffix):
    """ Test reading the od and compare it with the corresponding json file
    """
    a, b = equiv_files

    oda = (odpath / a) + '.' + suffix
    odb = (odpath / b) + '.od'

    if not oda.exists():
        pytest.skip(f"No {oda.rel_to_wd()} file")

    m1 = Node.LoadFile(oda)
    m2 = Node.LoadFile(odb)

    # Special handling for string handling in py2. Py3 puts everything in OD
    # as value attributes, which py2 reads as strings. A py2 string does not
    # support unicode, so the data will be coming over as raw bytes in the
    # string. If they differ, attempt to convert the py2 string to utf-8
    def convert_to_utf8(index: int):
        """Convert the string to utf-8 if it is different from the py2 data"""
        a = m1.Dictionary[index]
        b = m2.Dictionary[index]
        if a != b:
            m2.Dictionary[index] = unsafe_string(b, True)

    # Convert the known string that are encoded differently in py2
    if oda.stem == 'domain':
        convert_to_utf8(8195)

    a, b = shave_equal(m1, m2, ignore=('Description', 'IndexOrder'))
    assert a == b
