import pytest

from objdictgen.node import StringFormat, EvaluateExpression

def test_string_format():
    assert StringFormat('Additional Server SDO %d Parameter[(idx)]', 5, 0) == 'Additional Server SDO 5 Parameter'
    assert StringFormat('Restore Manufacturer Defined Default Parameters %d[(sub - 3)]', 1, 5) == 'Restore Manufacturer Defined Default Parameters 2'
    assert StringFormat('This doesn\'t match the regex', 1, 2) == 'This doesn\'t match the regex'

    assert StringFormat('%s %.3f[(idx,sub)]', 1, 2) == '1 2.000'
    assert StringFormat('%s %.3f[( idx ,  sub  )]', 1, 2) == '1 2.000'

    with pytest.raises(TypeError): 
        StringFormat('What are these %s[("tests")]', 0, 1)

    with pytest.raises(TypeError):
        StringFormat('There is nothing to format[(idx, sub)]', 1, 2)

    with pytest.raises(Exception):
        StringFormat('Unhandled arithmatic[(idx*sub)]', 2, 4)


def test_evaluate_expression():

    assert EvaluateExpression('4+3') == 7
    assert EvaluateExpression('4-3') == 1
    assert EvaluateExpression('11') == 11
    assert EvaluateExpression('4+3+2') == 9
    assert EvaluateExpression('4+3-2') == 5

    with pytest.raises(TypeError):
        EvaluateExpression('3-"tests"')

    with pytest.raises(SyntaxError):
        EvaluateExpression('4*3')

    with pytest.raises(TypeError):
        EvaluateExpression('str')

    with pytest.raises(TypeError):
        EvaluateExpression('"str"')

    with pytest.raises(SyntaxError):
        EvaluateExpression('$NODEID+12')