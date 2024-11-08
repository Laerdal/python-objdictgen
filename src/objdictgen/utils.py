""" Utility functions for objdictgen """
from typing import Mapping, Sequence, TypeVar, cast

T = TypeVar('T')
M = TypeVar('M', bound=Mapping)


def exc_amend(exc: Exception, text: str) -> Exception:
    """ Helper to prefix text to an exception """
    args = list(exc.args)
    if len(args) > 0:
        args[0] = text + str(args[0])
    else:
        args.append(text)
    exc.args = tuple(args)
    return exc


def str_to_int(string: str|int) -> int:
    """ Convert string or int to int. Fail if not possible."""
    i = maybe_number(string)
    if not isinstance(i, int):
        raise ValueError(f"Expected integer, got '{string}'")
    return i


def maybe_number(string: str|int) -> int|str:
    """ Convert string to a number, otherwise pass it through as-is"""
    if isinstance(string, int):
        return string
    s = string.strip()
    if s.startswith('0x') or s.startswith('-0x'):
        return int(s.replace('0x', ''), 16)
    if s.isdigit():
        return int(string)
    return string


def copy_in_order(d: M, order: Sequence[T]) -> M:
    """ Remake dict d with keys in order """
    out = {
        k: d[k]
        for k in order
        if k in d
    }
    out.update({
        k: v
        for k, v in d.items()
        if k not in out
    })
    return cast(M, out)  # FIXME: For mypy

