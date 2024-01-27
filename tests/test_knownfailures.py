import os
import pytest

from objdictgen import Node


@pytest.mark.parametrize("suffix", ['.od', '.json'])
def test_edsfail_null(wd, oddir, suffix):
    ''' EDS export of null.od fails because it contains no
        data. This is possibly a bug, or EDS does not support empty
        EDS.
    '''

    fa = os.path.join(oddir, 'null')

    m0 = Node.LoadFile(fa + suffix)

    with pytest.raises(KeyError) as exc:
        m0.DumpFile(fa + '.eds', filetype='eds')
    assert "Index 0x1018 does not exist" in str(exc.value)


@pytest.mark.parametrize("suffix", ['.od', '.json'])
def test_cexportfail_unicode(wd, oddir, suffix):
    ''' C-export does not support UNICODE yet. '''

    fa = os.path.join(oddir, 'unicode')

    m0 = Node.LoadFile(fa + suffix)

    cfile_type = {"cfile_type": 0}
    with pytest.raises(ValueError) as exc:
        m0.DumpFile(f"{fa}.c", filetype='c', **cfile_type)
    assert "'UNICODE_STRING' isn't a valid type for CanFestival" in str(exc.value)
