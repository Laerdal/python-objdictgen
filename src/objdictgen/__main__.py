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
from __future__ import annotations

import argparse
import functools
import logging
import sys
from dataclasses import dataclass, field
from typing import Callable, Sequence, TypeVar

from colorama import Fore, Style, init

from objdictgen import ODG_PROGRAM, __version__, jsonod
from objdictgen.node import Node
from objdictgen.printing import format_diff_nodes, format_node
from objdictgen.typing import TPath
from objdictgen.utils import exc_amend

T = TypeVar('T')

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
            except Exception as exc:
                if opts.show_debug:
                    raise
                print(f"{ODG_PROGRAM}: {exc.__class__.__name__}: {exc}")
                sys.exit(1)
        return inner
    return decorator


def open_od(fname: TPath|str, validate=True, fix=False) -> Node:
    """ Open and validate the OD file"""

    try:
        od = Node.LoadFile(fname, validate=validate)

        if validate:
            od.Validate(fix=fix)

        return od
    except Exception as exc:
        exc_amend(exc, f"{fname}: ")
        raise


@debug_wrapper()
def main(debugopts: DebugOpts, args: Sequence[str]|None = None):
    """ Main command dispatcher """

    # -- COMMON OPTIONS --
    common_opts = argparse.ArgumentParser(add_help=False)
    common_opts.add_argument('-D', '--debug', action='store_true',
                               help="Debug: enable tracebacks on errors")
    common_opts.add_argument('--no-color', action='store_true',
                               help="Disable colored output")
    common_opts.add_argument('--novalidate', action='store_true',
                               help="Don't validate input files")

    # -- MAIN PARSER --
    parser = argparse.ArgumentParser(
        prog=ODG_PROGRAM,
        description="""
            A tool to read and convert object dictionary files for the
            CAN festival library
        """,
        add_help=True,
        parents=[common_opts],
    )
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    subparser = parser.add_subparsers(title="command", dest="command", metavar="command", help="""
        Commands
    """, required=True)

    # FIXME: New options: new file, add parameter, delete parameter, copy parameter

    # -- HELP --
    subp = subparser.add_parser('help', parents=[common_opts], help="""
        Show help of all commands
    """)
    subp.add_argument('subcommand', nargs='?', help="Show help of specific command")

    # -- CONVERT --
    subp = subparser.add_parser('convert', parents=[common_opts], help="""
        Generate
    """, aliases=['gen', 'conv'])
    subp.add_argument('od', help="Object dictionary")
    subp.add_argument('out', help="Output file")
    subp.add_argument('-i', '--index', action="append",
                        help="OD Index to include. Filter out the rest.")
    subp.add_argument('-x', '--exclude', action="append", help="OD Index to exclude.")
    subp.add_argument('-f', '--fix', action="store_true",
                        help="Fix any inconsistency errors in OD before generate output")
    subp.add_argument('-t', '--type', choices=['od', 'eds', 'json', 'jsonc', 'c'],
                        help="Select output file type")
    subp.add_argument('--drop-unused', action="store_true", help="Remove unused parameters")
    subp.add_argument('--internal', action="store_true",
                        help="Store in internal format (json only)")
    subp.add_argument('--no-sort', action="store_true",
                        help="Don't order of parameters in output OD")
    subp.add_argument('--generate-with', type=str, help="Pass a .py file for custom code generation")

    # -- DIFF --
    subp = subparser.add_parser('diff', parents=[common_opts], help="""
        Compare OD files
    """, aliases=['compare'])
    subp.add_argument('od1', help="Object dictionary")
    subp.add_argument('od2', help="Object dictionary")
    subp.add_argument('--show', action="store_true", help="Show difference data")
    subp.add_argument('--internal', action="store_true", help="Diff internal object")
    subp.add_argument('--data', action="store_true", help="Show difference as data")
    subp.add_argument('--raw', action="store_true", help="Show raw difference")

    # -- EDIT --
    subp = subparser.add_parser('edit', parents=[common_opts], help="""
        Edit OD (UI)
    """)
    subp.add_argument('od', nargs="*", help="Object dictionary")

    # -- LIST --
    subp = subparser.add_parser('list', parents=[common_opts], help="""
        List
    """, aliases=['cat'])
    subp.add_argument('od', nargs="+", help="Object dictionary")
    subp.add_argument('-i', '--index', action="append", help="Specify parameter index to show")
    subp.add_argument('--all', action="store_true",
                        help="Show all subindexes, including subindex 0")
    subp.add_argument('--compact', action="store_true", help="Compact listing")
    subp.add_argument('--raw', action="store_true", help="Show raw parameter values")
    subp.add_argument('--short', action="store_true", help="Do not list sub-index")
    subp.add_argument('--unused', action="store_true", help="Include unused profile parameters")
    subp.add_argument('--internal', action="store_true", help="Show internal data")
    subp.add_argument('--minus', help="Show only parameters that are not in this OD")

    # -- NETWORK --
    subp = subparser.add_parser('network', parents=[common_opts], help="""
        Edit network (UI)
    """)
    subp.add_argument('dir', nargs="?", help="Project directory")

    # -- NODELIST --
    subp = subparser.add_parser('nodelist', parents=[common_opts], help="""
        List project nodes
    """)
    subp.add_argument('dir', nargs="?", help="Project directory")


    # -- COMMON --

    # Parse command-line arguments
    common = common_opts.parse_known_args(args)[0]
    opts = parser.parse_args(args)
    # Copy any options prior to the command into the final opts
    for k, v in vars(common).items():
        setattr(opts, k, v)

    # Enable debug mode
    if opts.debug:
        debugopts.set_debug(opts.debug)

    # Enable colored output
    if opts.no_color:
        init(strip=True)
    else:
        init()


    # -- HELP command --
    if opts.command == "help":
        if opts.subcommand:
            for subparsers_action in (
                    a for a in parser._actions
                    if isinstance(a, argparse._SubParsersAction)
            ):
                for choice, subparser in subparsers_action.choices.items():
                    if choice != opts.subcommand:
                        continue
                    # FIXME: Not sure why mypy doesn't know about format_help
                    print(subparser.format_help(), end="")  # type: ignore[attr-defined]

        else:
            parser.print_help()
            print()
            print("""For detailed help for each command:
    odg <command> --help
""")


    # -- CONVERT command --
    elif opts.command in ("convert", "conv", "gen"):

        od = open_od(opts.od, fix=opts.fix, validate=not opts.novalidate)

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
            to_remove |= (set(od.GetAllIndices()) - set(index))

        # Have any parameters to delete?
        if to_remove:
            print("Removed parameters:")
            info = [
                od.GetPrintEntryHeader(k, unused=True)
                for k in sorted(to_remove)
            ]
            od.RemoveIndex(to_remove)
            for line, fmt in info:
                print(line.format(**fmt))

        # Write the data
        od.DumpFile(opts.out,
            filetype=opts.type,
            # These additional options are only used for JSON output
            sort=not opts.no_sort, internal=opts.internal, validate=not opts.novalidate, custom_genfile=opts.generate_with
        )


    # -- DIFF command --
    elif opts.command in ("diff", "compare"):

        od1 = open_od(opts.od1, validate=not opts.novalidate)
        od2 = open_od(opts.od2, validate=not opts.novalidate)

        lines = list(format_diff_nodes(od1, od2, data=opts.data, raw=opts.raw,
                             internal=opts.internal, show=opts.show))

        for line in lines:
            print(line)

        errcode = 1 if lines else 0
        if errcode:
            print(f"{ODG_PROGRAM}: '{opts.od1}' and '{opts.od2}' differ")
        else:
            print(f"{ODG_PROGRAM}: '{opts.od1}' and '{opts.od2}' are equal")

        if errcode:
            parser.exit(errcode)


    # -- EDIT command --
    elif opts.command == "edit":

        # Import here to prevent including optional UI components for cmd-line use
        from .ui.objdictedit import uimain
        uimain(opts.od)


    # -- LIST command --
    elif opts.command in ("list", "cat"):

        minus = None
        if opts.minus:
            minus = open_od(opts.minus, validate=not opts.novalidate)

        for n, name in enumerate(opts.od):

            if n > 0:
                print()
            if len(opts.od) > 1:
                print(Fore.LIGHTBLUE_EX + name + '\n' + "=" * len(name) + Style.RESET_ALL)

            od = open_od(name, validate=not opts.novalidate)
            for line in format_node(od, name, index=opts.index, minus=minus, opts=opts):
                print(line)


    # -- NETWORK command --
    elif opts.command == "network":

        # Import here to prevent including optional UI components for cmd-line use
        from .ui.networkedit import uimain
        uimain(opts.dir)


    # -- NODELIST command --
    elif opts.command == "nodelist":

        # Import here to prevent including optional UI components for cmd-line use
        from .nodelist import main as _main
        _main(opts.dir)


    else:
        parser.error(f"Programming error: Uknown option '{opts.command}'")


# To support -m objdictgen
if __name__ == '__main__':
    main()
