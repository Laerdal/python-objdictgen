""" General tests for objdictgen package. """
import re


def test_import():
    """ Test that the package can be imported. """

    import objdictgen

    assert re.match(r"^\d+\.\d+\.\d+([a-z]\d+)?$", objdictgen.__version__), \
        "Version string does not match expected format."
