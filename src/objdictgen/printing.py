""" Functions for printing the object dictionary. """
from __future__ import annotations

from typing import Generator

from colorama import Fore, Style

from objdictgen import maps
from objdictgen.maps import OD
from objdictgen.node import Node
from objdictgen.typing import TIndexEntry


def GetPrintEntryHeader(
        node: Node, index: int, unused=False, compact=False, raw=False,
        entry: TIndexEntry|None = None
) -> tuple[str, dict[str, str]]:

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
    return "{pre}{key}  {name}   {struct}{flags}", {
        'key': f"{Fore.LIGHTGREEN_EX}0x{index:04x} ({index}){Style.RESET_ALL}",
        'name': f"{Fore.LIGHTWHITE_EX}{t_name}{Style.RESET_ALL}",
        'struct': f"{Fore.LIGHTYELLOW_EX}[{t_string.upper()}]{Style.RESET_ALL}",
        'flags': f"  {Fore.MAGENTA}{t_flags}{Style.RESET_ALL}" if flags else '',
        'pre': '    ' if not compact else '',
    }


def GetPrintEntry(
        node: Node, keys: list[int]|None = None, short=False, compact=False,
        unused=False, verbose=False, raw=False,
) -> Generator[str, None, None]:
    """
    Generator for printing the dictionary values
    """

    # Get the indexes to print and determine the order
    keys = keys or node.GetAllIndices(sort=True)

    index_range = None
    for k in keys:

        # Get the index entry information
        param = node.GetIndexEntry(k, withbase=True)
        obj = param["object"]

        # Get the header for the entry
        line, fmt = GetPrintEntryHeader(
            node, k, unused=unused, compact=compact, entry=param, raw=raw
        )
        if not line:
            continue

        # Print the parameter range header
        ir = maps.INDEX_RANGES.get_index_range(k)
        if index_range != ir:
            index_range = ir
            if not compact:
                yield Fore.YELLOW + ir.description + Style.RESET_ALL

        # Yield the parameter header
        yield line.format(**fmt)

        # Omit printing sub index data if:
        if short:
            continue

        # Fetch the dictionary values and the parameters, if present
        if k in node.Dictionary:
            values = node.GetEntry(k, aslist=True, compute=not raw)
        else:
            values = ['__N/A__'] * len(obj["values"])
        if k in node.ParamsDictionary:
            params = node.GetParamsEntry(k, aslist=True)
        else:
            params = [maps.DEFAULT_PARAMS] * len(obj["values"])
        # For mypy to ensure that values and entries are lists
        assert isinstance(values, list) and isinstance(params, list)

        infos = []
        for i, (value, param) in enumerate(zip(values, params)):

            # Prepare data for printing
            info = node.GetSubentryInfos(k, i)
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
                index, subindex, _ = node.GetMapIndex(value)
                try:
                    pdo = node.GetSubentryInfos(index, subindex)
                    t_v = f"{value:x}"
                    t_value = f"0x{t_v[0:4]}_{t_v[4:6]}_{t_v[6:]}  {Fore.LIGHTCYAN_EX}{pdo['name']}{Style.RESET_ALL}"
                except ValueError:
                    suffix = '   ???' if value else ''
                    t_value = f"0x{value:x}{suffix}"
            elif i and value and (k in (4120, ) or 'COB ID' in info["name"]):
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
            continue

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

