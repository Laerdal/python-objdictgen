import pytest

from objdictgen import maps


def test_maps_eval_value():

    dut = maps.eval_value

    assert dut("1234", 0, 0, True) == "1234"
    assert dut("'$NODEID+1'", 0, 0, False) == "$NODEID+1"
    assert dut("'$NODEID+1'", 0, 1000, True) == 1001

    assert dut('{True:"$NODEID+0x%X00"%(base+2),False:0x80000000}[base<4]', 0, 0, False) == "$NODEID+0x200"
    assert dut('{True:"$NODEID+0x%X00"%(base+2),False:0x80000000}[base<4]', 0, 0x1000, True) == 0x1200
    assert dut('{True:"$NODEID+0x%X00"%(base+2),False:0x80000000}[base<4]', 4, 0x1000, True) == 0x80000000


def test_maps_eval_name():

    dut = maps.eval_name

    assert dut("Additional Server SDO %d Parameter[(idx)]", 5, 0) == "Additional Server SDO 5 Parameter"
    assert dut("Restore Manufacturer Defined Default Parameters %d[(sub - 3)]", 1, 5) == "Restore Manufacturer Defined Default Parameters 2"
    assert dut("This doesn't match the regex", 1, 2) == "This doesn't match the regex"

    assert dut("%s %.3f[(idx,sub)]", 1, 2) == "1 2.000"
    assert dut("%s %.3f[( idx ,  sub  )]", 1, 2) == "1 2.000"

    assert dut("This is a %s[(sub*8-7)]", 1, 2) == "This is a 9"

    # with pytest.raises(ValueError):
    assert dut("What are these %s[('tests')]", 0, 1) == "What are these tests"
    assert dut('What are these %s[("tests")]', 0, 1) == "What are these tests"

    with pytest.raises(NameError):
        dut("What are these %s[(tests)]", 0, 1)

    with pytest.raises(TypeError):
        dut("There is nothing to format[(idx, sub)]", 1, 2)

    with pytest.raises(Exception):
        dut("Unhandled arithmatic[(idx*sub)]", 2, 4)


def test_maps_evaluate_expression():

    dut = maps.evaluate_expression

    # BinOp
    assert dut("4+3") == 7
    assert dut("4-3") == 1
    assert dut("4*3") == 12
    assert dut("10%8") == 2
    with pytest.raises(SyntaxError):
        dut("1/2")

    assert dut("4+3+2") == 9
    assert dut("4+3-2") == 5

    # Compare
    assert dut("1<2") == True
    with pytest.raises(SyntaxError):
        dut("1<2<3")
    with pytest.raises(SyntaxError):
        dut("1==2")

    # Subscript
    assert dut("'abc'[1]") == 'b'

    # Constant
    assert dut("11") == 11
    assert dut("1.1") == 1.1
    assert dut("1+2j") == 1+2j
    assert dut("'foobar'") == "foobar"
    assert dut('"foobar"') == "foobar"
    assert dut("False") is False
    assert dut("True") is True
    with pytest.raises(TypeError):
        dut("b'abc'")
    with pytest.raises(TypeError):
        dut("None")
    with pytest.raises(TypeError):
        dut("...")

    # Name
    assert dut("foobar", {"foobar": 42}) == 42
    with pytest.raises(NameError):
        dut("foo")

    # Call
    assert dut("f(1)", {"f": lambda x: x + 1}) == 2
    with pytest.raises(NameError):
        dut("f()")
    with pytest.raises(TypeError):
        dut("f()", {"f": lambda x: x})
    with pytest.raises(TypeError):
        assert dut("f(a=2)", {"f": lambda x: x})
    with pytest.raises(TypeError):
        assert dut("f(1, a=2)", {"f": lambda x: x})
    with pytest.raises(TypeError):
        dut("foo()", {"foo": 42})

    # Tuple
    assert dut("()") == tuple()
    assert dut("(1,2)") == (1, 2)

    # Dict
    assert dut("{}") == {}
    assert dut("{1: 2, 3: 4}") == {1: 2, 3: 4}
    with pytest.raises(TypeError):
        dut("{None: 1}")

    # List
    with pytest.raises(TypeError):
        dut("[]")

    # UnaryOp
    with pytest.raises(TypeError):
        dut("not 5")

    # General
    with pytest.raises(SyntaxError):
        dut("1;2")
    with pytest.raises(SyntaxError):
        dut("$NODEID+12")
    with pytest.raises(TypeError):
        dut('3-"tests"')
    with pytest.raises(TypeError):
        dut("3-'tests'")
