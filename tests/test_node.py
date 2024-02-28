import pytest

from objdictgen.node import Node


def test_string_format():
    assert Node.string_format('Additional Server SDO %d Parameter[(idx)]', 5, 0) == 'Additional Server SDO 5 Parameter'
    assert Node.string_format('Restore Manufacturer Defined Default Parameters %d[(sub - 3)]', 1, 5) == 'Restore Manufacturer Defined Default Parameters 2'
    assert Node.string_format('This doesn\'t match the regex', 1, 2) == 'This doesn\'t match the regex'

    assert Node.string_format('%s %.3f[(idx,sub)]', 1, 2) == '1 2.000'
    assert Node.string_format('%s %.3f[( idx ,  sub  )]', 1, 2) == '1 2.000'

    assert Node.string_format('This is a %s[(sub*8-7)]', 1, 2) == 'This is a 9'

    with pytest.raises(TypeError):
        Node.string_format('What are these %s[("tests")]', 0, 1)

    with pytest.raises(TypeError):
        Node.string_format('There is nothing to format[(idx, sub)]', 1, 2)

    with pytest.raises(Exception):
        Node.string_format('Unhandled arithmatic[(idx*sub)]', 2, 4)


def test_evaluate_expression():

    assert Node.evaluate_expression('4+3') == 7
    assert Node.evaluate_expression('4-3') == 1
    assert Node.evaluate_expression('11') == 11
    assert Node.evaluate_expression('4+3+2') == 9
    assert Node.evaluate_expression('4+3-2') == 5
    assert Node.evaluate_expression('4*3') == 12

    with pytest.raises(TypeError):
        Node.evaluate_expression('3-"tests"')

    with pytest.raises(TypeError):
        Node.evaluate_expression('3-"tests"')

    with pytest.raises(TypeError):
        Node.evaluate_expression('not 5')

    with pytest.raises(TypeError):
        Node.evaluate_expression('str')

    with pytest.raises(TypeError):
        Node.evaluate_expression('"str"')

    with pytest.raises(SyntaxError):
        Node.evaluate_expression('$NODEID+12')