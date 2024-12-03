"""Test utils module."""

from colorama import Fore, Style
from objdictgen import utils


def test_utils_remove_color():
    """Test remove_color function."""
    assert utils.remove_color("Hello, World!") == "Hello, World!"

    assert utils.remove_color(Fore.RED + "Hello, World!") == "Hello, World!"

    assert utils.remove_color(Fore.RED + "Hello, World!" + Style.RESET_ALL) == "Hello, World!"


def test_utils_strip_brackets():
    """Test strip_brackets function."""
    assert utils.strip_brackets("['Hello']") == "Hello"

    assert utils.strip_brackets("['Hello'] World") == "Hello World"

    assert utils.strip_brackets("['Hello'] World") == "Hello World"

    assert utils.strip_brackets("Hello") == "Hello"


def test_utils_exc_amend():
    """Test exc_amend function."""

    exc = ValueError("Hello")
    exc = utils.exc_amend(exc, "World: ")

    assert str(exc) == "World: Hello"

    exc = ValueError()
    exc = utils.exc_amend(exc, "World: ")

    assert str(exc) == "World: "


def test_utils_str_to_int():
    """Test str_to_int function."""

    assert utils.str_to_int("123") == 123

    assert utils.str_to_int(123) == 123

    assert utils.str_to_int("0x123") == 291

    try:
        utils.str_to_int("Hello")
    except ValueError as e:
        assert str(e) == "Expected integer, got 'Hello'"


def test_utils_maybe_number():
    """Test maybe_number function."""

    assert utils.maybe_number("123") == 123

    assert utils.maybe_number(123) == 123

    assert utils.maybe_number("0x123") == 291

    assert utils.maybe_number("Hello") == "Hello"


def test_utils_copy_in_order():
    """Test copy_in_order function."""

    d = {"a": 1, "b": 2, "c": 3}

    assert utils.copy_in_order(d, ["b", "c", "a"]) == {"b": 2, "c": 3, "a": 1}

    assert utils.copy_in_order(d, ["c", "b"]) == {"c": 3, "b": 2, "a": 1}

    assert utils.copy_in_order(d, ["b", "d"]) == {"b": 2, "a": 1, "c": 3}

    assert utils.copy_in_order(d, []) == d


def test_utils_diff_colored_lines():
    """Test diff_colored_lines function."""

    lines1 = ["Hello", "World"]
    lines2 = ["Hello", "World!"]

    out = list(utils.diff_colored_lines(lines1, lines2))

    assert out == ["  Hello", "- World", "+ World!" ]


    lines1 = [f"{Fore.RED}Hello", f"{Fore.GREEN}World"]
    lines2 = ["Hello", "World!"]

    out = list(utils.diff_colored_lines(lines1, lines2))

    assert out == [f"  {Fore.RED}Hello", f"- {Fore.GREEN}World", "+ World!" ]


    lines1 = ["Hello", "World!"]
    lines2 = [f"{Fore.RED}Hello", f"{Fore.GREEN}World"]

    out = list(utils.diff_colored_lines(lines1, lines2))

    assert out == [f"  {Fore.RED}Hello", "- World!", f"+ {Fore.GREEN}World" ]


def test_utils_diff_highlight_changes():
    """Test highlight_changes function."""

    lines = ["  Hello", "- World", "+ Friend"]

    out = list(utils.highlight_changes(lines))

    assert out == ["  Hello", "- World", "? ^^ ^", "+ Friend", "? ^ ^^^"]
