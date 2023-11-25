import pytest

from objdictgen.node import EvaluateExpression

def test_evaluate_expression():

    assert EvaluateExpression('4+3') == 7
    assert EvaluateExpression('4-3') == 1
    assert EvaluateExpression('11') == 11

    with pytest.raises(SyntaxError):
        EvaluateExpression('4+3+2')
        EvaluateExpression('4+3')
        EvaluateExpression('str')

