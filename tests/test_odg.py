import pytest

from objdictgen.__main__ import main


def test_odg_list_woprofile(odjsoneds):

    od = odjsoneds

    main((
        'list',
        str(od)
    ))


def test_odg_list_wprofile(odjsoneds, profile):

    od = odjsoneds

    main((
        'list',
        str(od)
    ))
