"""Main entry point for objdictgen / odg."""
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
# USA

import argparse
import functools
import getopt
import logging
import sys
from dataclasses import dataclass, field
from pprint import pformat
from typing import TYPE_CHECKING, Callable, Sequence, TypeVar

from colorama import Fore, Style, init

import objdictgen
from objdictgen import jsonod
from objdictgen.typing import TDiffEntries, TDiffNodes, TPath

T = TypeVar('T')

if TYPE_CHECKING:
    from objdictgen.node import Node

# For colored output
init()

# Initalize the python logger to simply output to stdout
log = logging.getLogger()
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stdout))


@dataclass
class DebugOpts:
    """ Options for main to control the debug_wrapper """
    show_debug: bool = field(default=False)

    def set_debug(self, dbg: bool) -> None:
        """Set debug level"""
        self.show_debug = dbg

        log.setLevel(logging.DEBUG)


def debug_wrapper() -> Callable[[Callable[..., T]], Callable[..., T]]:
    """ Wrapper to catch all exceptions and supress the output unless debug
        is set
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def inner(*args, **kw):
            opts = DebugOpts()
            try:
                return fn(opts, *args, **kw)
            except Exception as exc:  # pylint: disable=broad-except
                if opts.show_debug:
                    raise
                print(f"{objdictgen.ODG_PROGRAM}: {exc.__class__.__name__}: {exc}")
                sys.exit(1)
        return inner
    return decorator


def open_od(fname: TPath|str, validate=True, fix=False) -> "Node":
    """ Open and validate the OD file"""

    try:
        od = objdictgen.LoadFile(fname)

        if validate:
            od.Validate(fix=fix)

        return od
    except Exception as exc:
        jsonod.exc_amend(exc, f"{fname}: ")
        raise


def print_diffs(diffs: TDiffNodes, show=False):
    """ Print the differences between two object dictionaries"""

    def _pprint(text: str):
        for line in pformat(text).splitlines():
            print("       ", line)

    def _printlines(entries: TDiffEntries):
        for chtype, change, path in entries:
            if 'removed' in chtype:
                print(f"<<<     {path} only in LEFT")
                if show:
                    _pprint(change.t1)
            elif 'added' in chtype:
                print(f"    >>> {path} only in RIGHT")
                if show:
                    _pprint(change.t2)
            elif 'changed' in chtype:
                print(f"<< - >> {path} value changed from '{change.t1}' to '{change.t2}'")
            else:
                print(f"{Fore.RED}{chtype} {path} {change}{Style.RESET_ALL}")

    rest = diffs.pop('', None)
    if rest:
        print(f"{Fore.GREEN}Changes:{Style.RESET_ALL}")
        _printlines(rest)

    for index in sorted(diffs):
        print(f"{Fore.GREEN}Index 0x{index:04x} ({index}){Style.RESET_ALL}")
        _printlines(diffs[index])


@debug_wrapper()
def main(debugopts: DebugOpts, args: Sequence[str]|None = None):
    """ Main command dispatcher """

    parser = argparse.ArgumentParser(
        prog=objdictgen.ODG_PROGRAM,
        description="""
            A tool to read and convert object dictionary files for the
            CAN festival library
        """,
        add_help=True,
    )

    # FIXME: New options: new file, add parameter, delete parameter, copy parameter

    subparser = parser.add_subparsers(title="command", dest="command", metavar="command", help="""
        Commands
    """, required=True)


    # -- COMMON --
    opt_debug = dict(action='store_true', help="Debug: enable tracebacks on errors")
    opt_od = dict(metavar='od', default=None, help="Object dictionary")

    parser.add_argument('--version', action='version', version='%(prog)s ' + objdictgen.__version__)
    parser.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- HELP --
    subp = subparser.add_parser('help', help="""
        Show help of all commands
    """)
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- CONVERT --
    subp = subparser.add_parser('convert', help="""
        Generate
    """, aliases=['gen', 'conv'])
    subp.add_argument('od', **opt_od)  # type: ignore[arg-type]
    subp.add_argument('out', default=None, help="Output file")
    subp.add_argument('-i', '--index', action="append",
                        help="OD Index to include. Filter out the rest.")
    subp.add_argument('-x', '--exclude', action="append", help="OD Index to exclude.")
    subp.add_argument('-f', '--fix', action="store_true",
                        help="Fix any inconsistency errors in OD before generate output")
    subp.add_argument('-t', '--type', choices=['od', 'eds', 'json', 'c'],
                        help="Select output file type")
    subp.add_argument('--drop-unused', action="store_true", help="Remove unused parameters")
    subp.add_argument('--internal', action="store_true",
                        help="Store in internal format (json only)")
    subp.add_argument('--nosort', action="store_true",
                        help="Don't order of parameters in output OD")
    subp.add_argument('--novalidate', action="store_true",
                        help="Don't validate files before conversion")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- DIFF --
    subp = subparser.add_parser('diff', help="""
        Compare OD files
    """, aliases=['compare'])
    subp.add_argument('od1', **opt_od)  # type: ignore[arg-type]
    subp.add_argument('od2', **opt_od)  # type: ignore[arg-type]
    subp.add_argument('--internal', action="store_true", help="Diff internal object")
    subp.add_argument('--novalidate', action="store_true",
                        help="Don't validate input files before diff")
    subp.add_argument('--show', action="store_true", help="Show difference data")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- EDIT --
    subp = subparser.add_parser('edit', help="""
        Edit OD (UI)
    """)
    subp.add_argument('od', nargs="*", help="Object dictionary")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- LIST --
    subp = subparser.add_parser('list', help="""
        List
    """)
    subp.add_argument('od', nargs="+", help="Object dictionary")
    subp.add_argument('-i', '--index', action="append", help="Specify parameter index to show")
    subp.add_argument('--all', action="store_true",
                        help="Show all subindexes, including subindex 0")
    subp.add_argument('--asis', action="store_true", help="Do not sort output")
    subp.add_argument('--compact', action="store_true", help="Compact listing")
    subp.add_argument('--header', action="store_true", help="List header only")
    subp.add_argument('--raw', action="store_true", help="Show raw parameter values")
    subp.add_argument('--short', action="store_true", help="Do not list sub-index")
    subp.add_argument('--unused', action="store_true", help="Include unused profile parameters")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- NETWORK --
    subp = subparser.add_parser('network', help="""
        Edit network (UI)
    """)
    subp.add_argument('dir', nargs="?", help="Project directory")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]

    # -- NODELIST --
    subp = subparser.add_parser('nodelist', help="""
        List project nodes
    """)
    subp.add_argument('dir', nargs="?", help="Project directory")
    subp.add_argument('-D', '--debug', **opt_debug)  # type: ignore[arg-type]


    # -- COMMON --

    # Parse command-line arguments
    opts = parser.parse_args(args)

    # Enable debug mode
    if opts.debug:
        debugopts.set_debug(opts.debug)


    # -- HELP command --
    if opts.command == "help":
        parser.print_help()
        print()

        for subparsers_action in (
                a for a in parser._actions  # pylint: disable=protected-access
                if isinstance(a, argparse._SubParsersAction)  # pylint: disable=protected-access
        ):
            for choice, subparser in subparsers_action.choices.items():
                print(f"command '{choice}'")
                # FIXME: Not sure why mypy doesn't know about format_help
                for info in subparser.format_help().split('\n'):  # type: ignore[attr-defined]
                    print("    " + info)


    # -- CONVERT command --
    if opts.command in ("convert", "conv", "gen"):

        od = open_od(opts.od, fix=opts.fix)

        to_remove: set[int] = set()

        # Drop excluded parameters
        if opts.exclude:
            to_remove |= set(jsonod.str_to_int(i) for i in opts.exclude)

        # Drop unused parameters
        if opts.drop_unused:
            to_remove |= set(od.GetUnusedParameters())

        # Drop all other indexes than specified
        if opts.index:
            index = [jsonod.str_to_int(i) for i in opts.index]
            to_remove |= (set(od.GetAllParameters()) - set(index))

        # Have any parameters to delete?
        if to_remove:
            print("Removed parameters:")
            info = [
                od.GetPrintLine(k, unused=True)
                for k in sorted(to_remove)
            ]
            for idx in to_remove:
                od.RemoveIndex(idx)
            for line, fmt in info:
                print(line.format(**fmt))

        # Write the data
        od.DumpFile(opts.out,
            filetype=opts.type, sort=not opts.nosort,
            internal=opts.internal, validate=not opts.novalidate
        )


    # -- DIFF command --
    elif opts.command in ("diff", "compare"):
        od1 = open_od(opts.od1, validate=not opts.novalidate)
        od2 = open_od(opts.od2, validate=not opts.novalidate)

        diffs = jsonod.diff_nodes(
            od1, od2, asdict=not opts.internal,
            validate=not opts.novalidate,
        )

        if diffs:
            errcode = 1
            print(f"{objdictgen.ODG_PROGRAM}: '{opts.od1}' and '{opts.od2}' differ")
        else:
            errcode = 0
            print(f"{objdictgen.ODG_PROGRAM}: '{opts.od1}' and '{opts.od2}' are equal")

        print_diffs(diffs, show=opts.show)
        parser.exit(errcode)


    # -- EDIT command --
    elif opts.command == "edit":

        # Import here to prevent including optional UI components for cmd-line use
        from .ui.objdictedit import \
            uimain  # pylint: disable=import-outside-toplevel
        uimain(opts.od)


    # -- LIST command --
    elif opts.command == "list":

        for n, name in enumerate(opts.od):

            if n > 0:
                print()
            if len(opts.od) > 1:
                print(Fore.LIGHTBLUE_EX + name + '\n' + "=" * len(name) + Style.RESET_ALL)

            od = open_od(name)

            # Get the indexes to print and determine the order
            keys = od.GetAllParameters(sort=not opts.asis)
            if opts.index:
                indexp = [jsonod.str_to_int(i) for i in opts.index]
                keysp = [k for k in keys if k in indexp]
                missing = ", ".join((str(k) for k in indexp if k not in keysp))
                if missing:
                    parser.error(f"Unknown index {missing}")

            profiles = []
            if od.DS302:
                loaded, equal = jsonod.compare_profile("DS-302", od.DS302)
                if equal:
                    extra = "DS-302 (equal)"
                elif loaded:
                    extra = "DS-302 (not equal)"
                else:
                    extra = "DS-302 (not loaded)"
                profiles.append(extra)

            pname = od.ProfileName
            if pname and pname != 'None':
                loaded, equal = jsonod.compare_profile(pname, od.Profile, od.SpecificMenu)
                if equal:
                    extra = f"{pname} (equal)"
                elif loaded:
                    extra = f"{pname} (not equal)"
                else:
                    extra = f"{pname} (not loaded)"
                profiles.append(extra)

            if not opts.compact:
                print(f"File:      {name}")
                print(f"Name:      {od.Name}  [{od.Type.upper()}]  {od.Description}")
                tp = ", ".join(profiles) or None
                print(f"Profiles:  {tp}")
                if od.ID:
                    print(f"ID:        {od.ID}")
                print("")

            if opts.header:
                continue

            # Print the parameters
            for line in od.GetPrintParams(
                keys=keys, short=opts.short, compact=opts.compact, unused=opts.unused,
                verbose=opts.all, raw=opts.raw
            ):
                print(line)


    # -- NETWORK command --
    elif opts.command == "network":

        # Import here to prevent including optional UI components for cmd-line use
        from .ui.networkedit import \
            uimain  # pylint: disable=import-outside-toplevel
        uimain(opts.dir)


    # -- NODELIST command --
    elif opts.command == "nodelist":

        # Import here to prevent including optional UI components for cmd-line use
        from .nodelist import \
            main as _main  # pylint: disable=import-outside-toplevel
        _main(opts.dir)


    else:
        parser.error(f"Programming error: Uknown option '{opts.command}'")


def main_objdictgen():
    """ Legacy objdictgen command """

    def usage():
        print("\nUsage of objdictgen :")
        print(f"\n   {sys.argv[0]} XMLFilePath CFilePath\n")

    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.GetoptError:
        # print help information and exit:
        usage()
        sys.exit(2)

    for opt, _ in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()

    filein = ""
    fileout = ""
    if len(args) == 2:
        filein = args[0]
        fileout = args[1]
    else:
        usage()
        sys.exit()

    if filein != "" and fileout != "":
        print("Parsing input file", filein)
        node = objdictgen.LoadFile(filein)
        print("Writing output file", fileout)
        node.DumpFile(fileout, filetype='c')
        print("All done")


def main_objdictedit():
    """ Legacy objdictedit command """

    # Import here to prevent including optional UI components for cmd-line use
    from .ui.objdictedit import \
        main as _main  # pylint: disable=import-outside-toplevel
    _main()


# To support -m objdictgen
if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    main()
