""" Functions for printing the object dictionary. """
from __future__ import annotations

from dataclasses import dataclass
from pprint import pformat
from typing import Generator

from colorama import Fore, Style

from objdictgen import jsonod, maps
from objdictgen.maps import OD
from objdictgen.node import Node
from objdictgen.typing import TDiffNodes, TIndexEntry
from objdictgen.utils import (TERM_COLS, diff_colored_lines, highlight_changes,
                              remove_color, str_to_int)


@dataclass
class FormatNodeOpts:
    """ Options for formatting the node """
    compact: bool = False
    short: bool = False
    unused: bool = False
    all: bool = False
    raw: bool = False
    internal: bool = False

    @classmethod
    def from_args(cls, opts: FormatNodeOpts|None, kwargs) -> FormatNodeOpts:
        """ Create a FormatNodeOpts object from the arguments or kwargs. """
        obj = opts or cls()
        for key, value in kwargs.items():
            setattr(obj, key, value)
        return obj


def format_node(
        node: Node,
        name: str, *,
        index: list[str]|None = None,
        minus: Node|None = None,
        opts: FormatNodeOpts|None = None,
        **kwargs: FormatNodeOpts,
) -> Generator[str, None, None]:
    """Generator for producing the print formatting of a node."""

    # Get the options for the function
    opts = FormatNodeOpts.from_args(opts, kwargs)

    # Get the indexes to print and determine the order
    keys = node.GetAllIndices(sort=True)
    if index:
        indexp = [str_to_int(i) for i in index]
        keys = [k for k in keys if k in indexp]
        missing = ", ".join((str(k) for k in indexp if k not in keys))
        if missing:
            raise ValueError(f"Unknown index {missing}")

    profiles = []
    if node.DS302:
        loaded, equal = jsonod.compare_profile("DS-302", node.DS302)
        if equal:
            extra = "DS-302 (equal)"
        elif loaded:
            extra = "DS-302 (not equal)"
        else:
            extra = "DS-302 (not loaded)"
        profiles.append(extra)

    pname = node.ProfileName
    if pname and pname != 'None':
        loaded, equal = jsonod.compare_profile(pname, node.Profile, node.SpecificMenu)
        if equal:
            extra = f"{pname} (equal)"
        elif loaded:
            extra = f"{pname} (not equal)"
        else:
            extra = f"{pname} (not loaded)"
        profiles.append(extra)

    if not kwargs.get("compact"):
        yield f"{Fore.CYAN}File:{Style.RESET_ALL}      {name}"
        yield f"{Fore.CYAN}Name:{Style.RESET_ALL}      {node.Name}  [{node.Type.upper()}]  {node.Description}"
        tp = ", ".join(profiles) or None
        yield f"{Fore.CYAN}Profiles:{Style.RESET_ALL}  {tp}"
        if node.ID:
            yield f"{Fore.CYAN}ID:{Style.RESET_ALL}        {node.ID}"
        yield ""

    index_range = None
    header = ''

    for k in keys:

        # Get the index range title
        ir = maps.INDEX_RANGES.get_index_range(k)
        if index_range != ir:
            index_range = ir
            if not opts.compact:
                header = Fore.YELLOW + ir.description + Style.RESET_ALL

        obj = node.GetIndexEntry(k)

        if minus and k in minus:
            minusobj = minus.GetIndexEntry(k)

            if obj == minusobj:
                linegen = format_od_object(node, k, short=True)
                lines = [remove_color(line) for line in linegen]
                lines[0] = Fore.LIGHTBLACK_EX + lines[0] + f"   {Fore.LIGHTRED_EX}<EQUAL>{Style.RESET_ALL}"
                yield from lines
                continue

        # Yield the text for the index
        lines = list(format_od_object(
            node, k, short=opts.short, compact=opts.compact, unused=opts.unused,
            verbose=opts.all, raw=opts.raw
        ))

        if opts.internal and lines[-1] == "":
            lines.pop()

        for line in lines:
            # Print the header if it exists
            if header:
                yield header
                header = ''

            # Output the line
            yield line

        if opts.internal:
            obj = node.GetIndexEntry(k)
            lines = pformat(obj, width=TERM_COLS).splitlines()
            yield from lines
            if not opts.compact:
                yield ""


def format_od_header(
        node: Node, index: int, *, unused=False, compact=False, raw=False,
        entry: TIndexEntry|None = None
) -> tuple[str, dict[str, str]]:
    """Get the print output for a dictionary entry header"""

    # Get the information about the index if it wasn't passed along
    if not entry:
        entry = node.GetIndexEntry(index, withbase=True)
    obj = entry["object"]

    # Get the flags for the entry
    flags: set[str] = set()
    for group in entry["groups"]:
        v = {
            "built-in": None,
            "user": "User",
            "ds302": "DS-302",
            "profile": "Profile",
        }.get(group, group)
        if v:
            flags.add(v)
    if obj.get('need'):
        flags.add("Mandatory")
    if entry.get("params", {}).get("callback"):
        flags.add('CB')
    if "dictionary" not in entry:
        if "ds302" in entry["groups"] or "profile" in entry["groups"]:
            flags.add("Unused")
        else:
            flags.add("Missing")

    # Skip printing if the entry is unused and we are not printing unused
    if 'Unused' in flags and not unused:
        return '', {}

    # Replace flags for formatting
    for _, flag in enumerate(flags.copy()):
        if flag == 'Missing':
            flags.discard('Missing')
            flags.add(Fore.RED + ' *MISSING* ' + Style.RESET_ALL)

    # Print formattings
    idx = (index - entry.get("base", index)) // obj.get("incr", 1) + 1
    t_name = obj['name']
    if not raw:
        t_name = maps.eval_name(t_name, idx=idx, sub=0)
    t_flags = ', '.join(flags)
    t_string = maps.ODStructTypes.to_string(obj['struct']) or '???'

    # ** PRINT PARAMETER **
    # Returned as a tuple to allow for futher usage
    return "{pre}{key}  {name}   {struct}{flags}", {
        'key': f"{Fore.LIGHTGREEN_EX}0x{index:04x} ({index}){Style.RESET_ALL}",
        'name': f"{Fore.LIGHTWHITE_EX}{t_name}{Style.RESET_ALL}",
        'struct': f"{Fore.LIGHTYELLOW_EX}[{t_string.upper()}]{Style.RESET_ALL}",
        'flags': f"  {Fore.MAGENTA}{t_flags}{Style.RESET_ALL}" if flags else '',
        'pre': '    ' if not compact else '',
    }


def format_od_object(
        node: Node, index: int, *, short=False, compact=False,
        unused=False, verbose=False, raw=False,
) -> Generator[str, None, None]:
    """Return the print formatting for an object dictionary entry."""

    # Get the index entry information
    param = node.GetIndexEntry(index, withbase=True)
    obj = param["object"]

    # Get the header for the entry and output it unless it is empty
    line, fmt = format_od_header(
        node, index, unused=unused, compact=compact, entry=param, raw=raw
    )
    if not line:
        return
    yield line.format(**fmt)

    # Get the index range title
    index_range = maps.INDEX_RANGES.get_index_range(index)

    # Omit printing sub index data if short is requested
    if short:
        return

    # Fetch the dictionary values and the parameters, if present
    if index in node.Dictionary:
        values = node.GetEntry(index, aslist=True, compute=not raw)
    else:
        # Fill the values with N/A if the entry is not present
        values = ['__N/A__'] * len(obj["values"])

    if index in node.ParamsDictionary:
        # FIXME: Is there a risk that this return less than the length of
        #        dictionary values?
        params = node.GetParamsEntry(index, aslist=True)
    else:
        params = [maps.DEFAULT_PARAMS] * len(values)

    # For mypy to ensure that values and entries are lists
    assert isinstance(values, list) and isinstance(params, list)

    infos = []
    # The strict=True will capture if the values and params are not the same
    for i, (value, param) in enumerate(zip(values, params, strict=True)):

        # Prepare data for printing
        info = node.GetSubentryInfos(index, i)
        typename = node.GetTypeName(info['type'])

        # Type specific formatting of the value
        if value == "__N/A__":
            t_value = f'{Fore.LIGHTBLACK_EX}N/A{Style.RESET_ALL}'
        elif isinstance(value, str):
            length = len(value)
            if typename == 'DOMAIN':
                value = value.encode('unicode_escape').decode()
            t_value = '"' + value + f'"  ({length})'
        elif i and index_range and index_range.name in ('rpdom', 'tpdom'):
            # FIXME: In PDO mappings, the value is ints
            assert isinstance(value, int)
            mapindex, submapindex, _ = node.GetMapIndex(value)
            try:
                pdo = node.GetSubentryInfos(mapindex, submapindex)
                t_v = f"{value:x}"
                t_value = f"0x{t_v[0:4]}_{t_v[4:6]}_{t_v[6:]}  {Fore.LIGHTCYAN_EX}{pdo['name']}{Style.RESET_ALL}"
            except ValueError:
                suffix = '   ???' if value else ''
                t_value = f"0x{value:x}{suffix}"
        elif i and value and (index in (4120, ) or 'COB ID' in info["name"]):
            t_value = f"0x{value:x}"
        else:
            t_value = str(value)

        # Add comment if present
        t_comment = param['comment'] or ''
        if t_comment:
            t_comment = f"{Fore.LIGHTBLACK_EX}/* {t_comment} */{Style.RESET_ALL}"

        # Omit printing the first element unless specifically requested
        if (not verbose and i == 0
            and obj['struct'] & OD.MultipleSubindexes
            and not t_comment
        ):
            continue

        # Print formatting
        infos.append({
            'i': f"{Fore.GREEN}{i:02d}{Style.RESET_ALL}",
            'access': info['access'],
            'pdo': 'P' if info['pdo'] else ' ',
            'name': info['name'],
            'type': f"{Fore.LIGHTBLUE_EX}{typename}{Style.RESET_ALL}",
            'value': t_value,
            'comment': t_comment,
            'pre': fmt['pre'],
        })

    # Must skip the next step if list is empty, as the first element is
    # used for the header
    if not infos:
        return

    # Calculate the max width for each of the columns
    w = {
        col: max(len(str(row[col])) for row in infos) or ''
        for col in infos[0]
    }

    # Generate a format string based on the calculcated column widths
    # Legitimate use of % as this is making a string containing format specifiers
    fmt = "{pre}    {i:%ss}  {access:%ss}  {pdo:%ss}  {name:%ss}  {type:%ss}  {value:%ss}  {comment}" % (
        w["i"],  w["access"],  w["pdo"],  w["name"],  w["type"],  w["value"]
    )

    # Print each line using the generated format string
    for infoentry in infos:
        yield fmt.format(**infoentry)

    if not compact and infos:
        yield ""


def format_diff_nodes(
        od1: Node, od2: Node, *, data=False, raw=False,
        internal=False, show=False
) -> Generator[str, None, None]:
    """ Compare two object dictionaries and return the formatted differences. """

    if internal or data:
        diffs = jsonod.diff(od1, od2, internal=internal)
    else:
        diffs = text_diff(od1, od2, data_mode=raw)

    rst = Style.RESET_ALL

    def _pprint(text: str, prefix: str = '        '):
        for line in pformat(text, width=TERM_COLS).splitlines():
            yield prefix + line

    for index, entries in diffs.items():
        if data or raw or internal:
            yield f"{Fore.LIGHTYELLOW_EX}{index}{rst}"
        for chtype, change, path in entries:

            # Prepare the path for printing
            ppath = path
            if ppath:
                if ppath[0] != "'":
                    ppath = "'" + ppath + "'"
                ppath = ppath + ' '
            ppath = f"{Fore.CYAN}{ppath}{rst}"

            if 'removed' in chtype:
                yield f"<<      {ppath}only in {Fore.MAGENTA}LEFT{rst}"
                if show:
                    yield from _pprint(change.t1, "        <   ")

            elif 'added' in chtype:
                yield f"     >> {ppath}only in {Fore.BLUE}RIGHT{rst}"
                if show:
                    yield from _pprint(change.t2, "        >   ")

            elif 'changed' in chtype:
                yield f"<< - >> {ppath}changed value from '{Fore.GREEN}{change.t1}{rst}' to '{Fore.GREEN}{change.t2}{rst}'"
                if show:
                    yield from _pprint(change.t1, "        <   ")
                    yield from _pprint(change.t2, "        >   ")

            elif 'type_changes' in chtype:
                yield f"<< - >> {ppath}changed type and value from '{Fore.GREEN}{change.t1}{rst}' to '{Fore.GREEN}{change.t2}{rst}'"
                if show:
                    yield from _pprint(change.t1, "        <   ")
                    yield from _pprint(change.t2, "        >   ")

            elif 'diff' in chtype:
                start = path[0:2]
                if start == '  ':
                    ppath = '      ' + path
                elif start == '+ ':
                    ppath = path.replace('+ ', '     >> ')
                    if ppath == '     >> ':
                        ppath = ''
                elif start == '- ':
                    ppath = path.replace('- ', '<<      ')
                    if ppath == '<<      ':
                        ppath = ''
                elif start == '? ':
                    ppath = path.replace('? ', '        ')
                    ppath = f"{Fore.RED}{ppath}{rst}"
                else:
                    ppath = f"{Fore.RED}{chtype} {ppath} {change}{rst}"
                yield ppath
            else:
                yield f"{Fore.RED}{chtype} {ppath} {change}{rst}"


def text_diff(od1: Node, od2: Node, data_mode: bool=False) -> TDiffNodes:
    """ Compare two object dictionaries as text and return the differences. """

    # Get all indices for the nodes
    keys1 = set(od1.GetAllIndices())
    keys2 = set(od2.GetAllIndices())

    diffs: dict[int|str, list] = {}

    for index in sorted(keys1 | keys2):
        changes = []

        # Get the object print entries
        text1 = text2 = []
        entry1: TIndexEntry = {}
        entry2: TIndexEntry = {}
        if index in keys1:
            text1 = list(format_od_object(od1, index, unused=True))
            entry1 = od1.GetIndexEntry(index)
        if index in keys2:
            text2 = list(format_od_object(od2, index, unused=True))
            entry2 = od2.GetIndexEntry(index)

        if data_mode:
            text1 = text2 = []
            if entry1:
                text1 = pformat(entry1, width=TERM_COLS-10, indent=2).splitlines()
            if entry2:
                text2 = pformat(entry2, width=TERM_COLS-10, indent=2).splitlines()

        if entry1 == entry2:
            continue

        for line in highlight_changes(diff_colored_lines(text1, text2)):
            changes.append(('diff', '', line))
        diffs[f"Index {index}"] = changes

    return diffs
