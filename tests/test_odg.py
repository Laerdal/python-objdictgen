import pytest

from objdictgen.__main__ import main


def test_odg_list_woprofile(odjsoneds):

    od = odjsoneds

    main((
        'list', '-D',
        str(od)
    ))


def test_odg_list_wprofile(odjsoneds, profile):

    od = odjsoneds

    main((
        'list', '-D',
        str(od)
    ))


@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_odg_compare(odpath, equiv_files, suffix):
    """ Test reading the od and compare it with the corresponding json file
    """
    a, b = equiv_files

    oda = (odpath / a) + '.' + suffix
    odb = (odpath / b) + '.od'

    if not oda.exists():
        pytest.skip(f"No {oda.rel_to_wd()} file")

    main((
        'compare', '-D',
        str(oda),
        str(odb),
    ))
