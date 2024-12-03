""" Utility functions for objdictgen """
import difflib
import os
import re
from typing import Generator, Iterable, Mapping, Sequence, TypeVar, cast

from colorama import Fore, Style

T = TypeVar('T')
M = TypeVar('M', bound=Mapping)

RE_BRACKETS_STRIP = re.compile(r"^\['(.*?)'\](.*)")

try:
    TERMINAL = os.get_terminal_size()
    TERM_COLS = TERMINAL.columns
except OSError:
    TERM_COLS = 80


def remove_color(text: str) -> str:
    """ Remove color codes from text """
    for color in Fore.__dict__.values():
        text = text.replace(color, '')
    text = text.replace(Style.RESET_ALL, '')
    return text


def strip_brackets(s: str) -> str:
    """ Strip surrounding brackets and quotes from a string """
    # Convert any ['<name>'] to <name>
    m = RE_BRACKETS_STRIP.match(s)
    if m:
        return m[1] + m[2]
    return s


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


def diff_colored_lines(lines1: list[str], lines2: list[str]) -> Generator[str, None, None]:
    """Diff two lists of lines and return the differences."""

    nocolor1 = [remove_color(line).rstrip() for line in lines1]
    nocolor2 = [remove_color(line).rstrip() for line in lines2]

    for line in difflib.ndiff(nocolor1, nocolor2):
        if line.startswith('? '):
            continue
        try:
            # Find the index of the line in the uncolored list
            # and replace the line with the colored line
            index = nocolor1.index(line[2:])
            line = line[0:2] + lines1[index]
        except ValueError:
            pass
        try:
            # Find the index of the line in the uncolored list
            # and replace the line with the colored line
            index = nocolor2.index(line[2:])
            line = line[0:2] + lines2[index]
        except ValueError:
            pass
        yield line


def highlight_changes(lines: Iterable[str]) -> Generator[str, None, None]:
    """Highlight changes in a list of lines."""

    lines = list(lines)
    linecount = len(lines)

    delay = None
    for i, line in enumerate(lines, start=1):

        yield line

        if delay:
            yield delay
            delay = None
            continue

        if line.startswith('- '):
            if i < linecount and lines[i].startswith('+ '):
                nextline = lines[i]

                l1 = remove_color(line[2:]).rstrip()
                l2 = remove_color(nextline[2:]).rstrip()

                s = difflib.SequenceMatcher(None, l1, l2, autojunk=False)
                s1 = ['^'] * len(l1)
                s2 = ['^'] * len(l2)
                for a, b, n in s.get_matching_blocks():
                    for c in range(a, a+n, 1):
                        s1[c] = ' '
                    for c in range(b, b+n, 1):
                        s2[c] = ' '
                d1 = ''.join(s1).rstrip()
                d2 = ''.join(s2).rstrip()
                if d1:
                    yield '? ' + d1
                if d2:
                    delay = '? ' + d2
