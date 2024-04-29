import pytest

from objdictgen import __main__

@pytest.mark.parametrize("file", ['master', 'slave'])
def test_main_open_od(odpath, file):

    od = __main__.open_od(odpath / (file + '.json'))
    assert od is not None
    assert od.Name == 'master' if file == 'master' else 'slave'


@pytest.mark.parametrize("file", ['master', 'slave'])
def test_main_list_od(odpath, file):

    od = __main__.open_od(odpath / (file + '.json'))

    import argparse
    ns = argparse.Namespace(
        no_sort=False, index=[], compact=False, short=False, unused=True,
        all=True, raw=False
    )

    for line in __main__.list_od(od, file, ns):
        print(line)
