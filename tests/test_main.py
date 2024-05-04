import pytest

from objdictgen import __main__
from objdictgen.__main__ import main


@pytest.mark.parametrize("file", ['master', 'slave'])
def test_main_open_od(odpath, file):

    od = __main__.open_od(odpath / (file + '.json'))
    assert od is not None
    assert od.Name == 'master' if file == 'master' else 'slave'

    with pytest.raises(ValueError) as exc:
        __main__.open_od(odpath / 'fail-validation.od')
    assert "not found in mapping dictionary" in str(exc.value)


@pytest.mark.parametrize("file", [
    'master', 'slave',
    'profile-ds302', 'profile-ds302-modified',
    'profile-ds401', 'profile-ds401-modified',
])
def test_main_list_od(odpath, file):

    od = __main__.open_od(odpath / (file + '.json'))
    od.ID = 1

    import argparse
    ns = argparse.Namespace(
        no_sort=False, index=[], compact=False, short=False, unused=True,
        all=True, raw=False
    )

    lines = list(__main__.list_od(od, file, ns))

    ns = argparse.Namespace(
        no_sort=False, index=[0x1000], compact=False, short=False, unused=True,
        all=True, raw=False
    )

    lines = list(__main__.list_od(od, file, ns))

    ns = argparse.Namespace(
        no_sort=False, index=[0x5000], compact=False, short=False, unused=True,
        all=True, raw=False
    )

    with pytest.raises(ValueError) as exc:
        lines = list(__main__.list_od(od, file, ns))
    assert "Unknown index 20480" in str(exc.value)


def test_main_odg_help():

    main((
        'help',
    ))

    main((
        'help', 'list',
    ))

    with pytest.raises(SystemExit) as exc:
        main((
            'list', '--help',
        ))
    assert exc.value.code == 0


def test_main_odg_list_woprofile(odjsoneds):

    od = odjsoneds

    main((
        'list', '-D',
        str(od)
    ))


def test_main_odg_list_wprofile(odjsoneds, profile):

    od = odjsoneds

    main((
        'list', '-D',
        str(od)
    ))


@pytest.mark.parametrize("suffix", ['od', 'json'])
def test_main_odg_compare(odpath, equiv_files, suffix):
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
