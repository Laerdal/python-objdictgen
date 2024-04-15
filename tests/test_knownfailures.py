import pytest

from objdictgen import Node


@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_fail_eds_null(wd, odpath, suffix):
    """ EDS export of null.od fails because it contains no
        data. This is possibly a bug, or EDS does not support empty
        EDS.
    """

    fa = odpath / 'null'

    m0 = Node.LoadFile(fa + '.' + suffix)

    with pytest.raises(KeyError) as exc:
        m0.DumpFile(fa + '.eds', filetype='eds')
    assert "Index 0x1018 does not exist" in str(exc.value)


@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_fail_cexport_unicode(wd, odpath, suffix):
    """ C-export does not support UNICODE yet. """

    fa = odpath / 'strings'

    m0 = Node.LoadFile(fa + '.' + suffix)

    with pytest.raises(ValueError) as exc:
        m0.DumpFile(fa + '.c', filetype='c')
    assert "'UNICODE_STRING' isn't a valid type for CanFestival" in str(exc.value)
