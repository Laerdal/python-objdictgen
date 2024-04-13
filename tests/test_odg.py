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

    # Due to well-known differences between py2 and p3 handling
    # we skip the domain comparison
    excludes = ('legacy-domain',)
    if oda.stem in excludes or odb.stem in excludes:
        pytest.skip("py2 and py3 are by design different and can't be compared with this OD")

    main((
        'compare', '-D',
        str(oda),
        str(odb),
    ))
