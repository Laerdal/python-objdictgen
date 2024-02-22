import pytest

from objdictgen.__main__ import main


@pytest.mark.parametrize("suffix", ['od', 'json', 'eds'])
def test_odg_list_woprofile(odfile, suffix):

    fname = odfile + '.' + suffix
    if not fname.exists():
        pytest.skip("File not found")

    main((
        'list',
        str(fname)
    ))


@pytest.mark.parametrize("suffix", ['od', 'json', 'eds'])
def test_odg_list_wprofile(odfile, suffix, profile):

    fname = odfile + '.' + suffix
    if not fname.exists():
        pytest.skip("File not found")

    main((
        'list',
        str(fname)
    ))
