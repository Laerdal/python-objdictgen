"""Nosis - XML Pickling."""
# This a stripped down version of legacy tool "gnosis", which is
# central to the "OD" format. This is basically a XML pickler for
# python objects. # The original tool was written for very old
# python and this is an updated extract of the original to be able
# to use it with python 3
#
# Copyright (C) 2022-2024  Svein Seldal, Laerdal Medical AS
# Copyright (C): <Unknown Author(s)>
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

import ast
import io
import logging
import re
import sys
from collections import UserDict, UserList
from typing import TYPE_CHECKING, Any, Container, TypeVar
from xml.dom import minidom

if TYPE_CHECKING:
    from _typeshed import SupportsRead

T = TypeVar("T")

log = logging.getLogger('objdictgen.nosis')


class _EmptyClass:
    """ Do-nohting empty class """


# Define how the values for built-ins are stored in the XML file. If True,
# the value is stored in the body of the tag, otherwise it's stored in the
# value= attribute.
TYPE_IN_BODY = {
    int: False,
    float: False,
    complex: False,
    str: False,
}

#
# This doesn't fit in any one place particularly well, but
# it needs to be documented somewhere. The following are the family
# types currently defined:
#
#   obj - thing with attributes and possibly coredata
#
#   uniq - unique thing, its type gives its value, and vice versa
#
#   map - thing that maps objects to other objects
#
#   seq - thing that holds a series of objects
#
#         Note - Py2.3 maybe the new 'Set' type should go here?
#
#   atom - non-unique thing without attributes (e.g. only coredata)
#
#   lang - thing that likely has meaning only in the
#          host language (functions, classes).
#
#          [Note that in Gnosis-1.0.6 and earlier, these were
#           mistakenly placed under 'uniq'. Those encodings are
#           still accepted by the parsers for compatibility.]
#

# Encodings for builtin types.
TYPE_NAMES = {
    'None': 'none',
    'dict': 'map',
    'list': 'seq',
    'tuple': 'seq',
    'numeric': 'atom',
    'string': 'atom',
    'bytes': 'atom',
    # 'PyObject': 'obj',
    # 'function': 'lang',
    # 'class': 'lang',
    'True': 'uniq',
    'False': 'uniq',
}

# Regexp patterns
PAT_FL = r'[-+]?(((((\d+)?[.]\d+|\d+[.])|\d+)[eE][+-]?\d+)|((\d+)?[.]\d+|\d+[.]))'
PAT_INT = r'[-+]?[1-9]\d*'
PAT_FLINT = f'({PAT_FL}|{PAT_INT})'    # float or int
PAT_COMPLEX = f'({PAT_FLINT})?[-+]{PAT_FLINT}[jJ]'
PAT_COMPLEX2 = f'({PAT_FLINT}):({PAT_FLINT})'

# Regexps for parsing numbers
RE_FLOAT = re.compile(PAT_FL + r'$')
RE_ZERO = re.compile(r'[+-]?0$')
RE_INT = re.compile(PAT_INT + r'$')
RE_LONG = re.compile(r'[-+]?\d+[lL]$')
RE_HEX = re.compile(r'([-+]?)(0[xX])([0-9a-fA-F]+)$')
RE_OCT = re.compile(r'([-+]?)(0)([0-7]+)$')
RE_COMPLEX = re.compile(PAT_COMPLEX + r'$')
RE_COMPLEX2 = re.compile(PAT_COMPLEX2 + r'$')


def aton(s: str) -> int|float|complex:
    """Convert a string to a number"""
    # -- massage the string slightly
    s = s.strip()
    while s[0] == '(' and s[-1] == ')':  # remove optional parens
        s = s[1:-1]

    # -- test for cases
    if RE_ZERO.match(s):
        return 0

    if RE_FLOAT.match(s):
        return float(s)

    if RE_LONG.match(s):
        return int(s.rstrip('lL'))

    if RE_INT.match(s):
        return int(s)

    m = RE_HEX.match(s)
    if m:
        n = int(m.group(3), 16)
        if n < sys.maxsize:
            n = int(n)
        if m.group(1) == '-':
            n = n * (-1)
        return n

    m = RE_OCT.match(s)
    if m:
        n = int(m.group(3), 8)
        if n < sys.maxsize:
            n = int(n)
        if m.group(1) == '-':
            n = n * (-1)
        return n

    if RE_COMPLEX.match(s):
        return complex(s)

    if RE_COMPLEX2.match(s):
        r, i = s.split(':')
        return complex(float(r), float(i))

    raise ValueError(f"Invalid string '{s}'")


# we use ntoa() instead of repr() to ensure we have a known output format
def ntoa(num: int|float|complex) -> str:
    """Convert a number to a string without calling repr()"""
    if isinstance(num, int):
        return str(num)

    if isinstance(num, float):
        s = f"{num:.17g}"
        # ensure a '.', adding if needed (unless in scientific notation)
        if '.' not in s and 'e' not in s:
            s = s + '.'
        return s

    if isinstance(num, complex):
        # these are always used as doubles, so it doesn't
        # matter if the '.' shows up
        return f"{num.real:.17g}+{num.imag:.17g}j"

    raise ValueError(f"Unknown numeric type: {repr(num)}")


XML_QUOTES = (
    ('&', '&amp;'),
    ('<', '&lt;'),
    ('>', '&gt;'),
    ('"', '&quot;'),
    ("'", '&apos;'),
)


def safe_string(s: str, isattr: bool = True) -> str:
    """Quote XML entries"""
    for repl in XML_QUOTES:
        s = s.replace(repl[0], repl[1])

    if isattr:
        # for others, use Python style escapes
        return s.encode('unicode_escape').decode('utf-8')

    return s


def unsafe_string(s: str, isattr: bool = True) -> str:
    """Recreate the original string from the string returned by safe_string()"""
    # Unqoute XML entries
    for repl in XML_QUOTES:
        s = s.replace(repl[1], repl[0])

    if isattr:
        s = s.replace("'", "\\x27")  # Need this to not interfere with ast

        tree = ast.parse("'" + s + "'", mode='eval')
        if not isinstance(tree.body, ast.Constant):
            raise ValueError(f"Invalid string '{s}' passed to unsafe_string()")
        return tree.body.s

    return s


# Maintain list of object identities for multiple and cyclical references
# (also to keep temporary objects alive)
VISITED: dict[int, Any] = {}


def _save_obj_with_id(node: minidom.Element, py_obj: Any) -> None:
    objid = node.getAttribute('id')
    if objid:  # might be None, or empty - shouldn't use as key
        VISITED[int(objid)] = py_obj


# Store the objects that can be pickled
CLASS_STORE: dict[str, type[Any]] = {}


def add_class_to_store(classname: str, klass: type[T]) -> None:
    """Put the class in the store (as 'classname')"""
    if classname and klass:
        CLASS_STORE[classname] = klass


def xmldump(filehandle: io.TextIOWrapper|None, py_obj: object,
            omit: Container[str]|None = None) -> str|None:
    """Create the XML representation as a string."""

    fh: io.TextIOWrapper
    if filehandle is None:
        fh = sio = io.StringIO()
    else:
        fh = filehandle

    omit = omit or ()

    # Store the ref id to the pickling object (if not deepcopying)
    global VISITED  # pylint: disable=global-statement
    objid = id(py_obj)
    VISITED = {
        objid: py_obj
    }

    # note -- setting family="obj" lets us know that a mutator was used on
    # the object. Otherwise, it's tricky to unpickle both <PyObject ...>
    # and <.. type="PyObject" ..> with the same code. Having family="obj" makes
    # it clear that we should slurp in a 'typeless' object and unmutate it.

    # note 2 -- need to add type= to <PyObject> when using mutators.
    # this is b/c a mutated object can still have a class= and
    # module= that we need to read before unmutating (i.e. the mutator
    # mutated into a PyObject)

    klass = py_obj.__class__
    klass_tag = klass.__name__

    # Generate the XML string
    # if klass not in CLASS_STORE.values():
    module = klass.__module__.replace('objdictgen.', '')  # Workaround to be backwards compatible

    id_tag = f' id="{objid}"' if objid is not None else ""

    fh.write(f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE PyObject SYSTEM "PyObjects.dtd">
<PyObject module="{module}" class="{klass_tag}"{id_tag}>
""")

    stuff = py_obj.__dict__

    # decide how to save the "stuff", depending on whether we need
    # to later grab it back as a single object
    if isinstance(stuff, dict):
        # don't need it as a single object - save keys/vals as
        # first-level attributes
        for key, val in stuff.items():
            if omit and key in omit:
                continue
            fh.write(_attr_tag(key, val, 0))
    else:
        raise ValueError(f"'{py_obj}.__dict__' is not a dict")

    fh.write('</PyObject>\n')

    if filehandle is None:
        sio.flush()
        return sio.getvalue()
    return None


def xmlload(filehandle: "SupportsRead[str|bytes]|bytes|str") -> Any:
    """Load pickled object from file fh."""

    fh: "SupportsRead[str|bytes]" = filehandle  # type: ignore[assignment]
    if isinstance(filehandle, str):
        fh = io.StringIO(filehandle)
    elif isinstance(filehandle, bytes):
        fh = io.BytesIO(filehandle)

    global VISITED  # pylint: disable=global-statement
    VISITED = {}  # Reset the visited collection

    return _thing_from_dom(minidom.parse(fh), None)


def _attr_tag(name: str, thing, level=0):
    start_tag = '  ' * level + f'<attr name="{name}" '
    close_tag = '  ' * level + '</attr>\n'
    return _tag_completer(start_tag, thing, close_tag, level)


def _item_tag(thing, level=0):
    start_tag = '  ' * level + '<item '
    close_tag = '  ' * level + '</item>\n'
    return _tag_completer(start_tag, thing, close_tag, level)


def _entry_tag(key, val, level=0):
    start_tag = '  ' * level + '<entry>\n'
    close_tag = '  ' * level + '</entry>\n'
    start_key = '  ' * level + '  <key '
    close_key = '  ' * level + '  </key>\n'
    key_block = _tag_completer(start_key, key, close_key, level + 1)
    start_val = '  ' * level + '  <val '
    close_val = '  ' * level + '  </val>\n'
    val_block = _tag_completer(start_val, val, close_val, level + 1)
    return start_tag + key_block + val_block + close_tag


def _tag_compound(start_tag: str, family_type: str, thing: Any) -> tuple[str, int]:
    """Make a start tag for a compound object, handling refs.
    Returns (start_tag,do_copy), with do_copy indicating whether a
    copy of the data is needed.
    """
    idt = id(thing)
    if VISITED.get(idt):
        start_tag = f'{start_tag}{family_type} refid="{idt}" />\n'
        return (start_tag, 0)

    start_tag = f'{start_tag}{family_type} id="{idt}">\n'
    return (start_tag, 1)


def _tag_completer(start_tag: str, orig_thing, close_tag: str, level: int) -> str:
    tag_body = []

    thing = orig_thing
    in_body = TYPE_IN_BODY.get(type(orig_thing), 0)

    if thing is None:
        start_tag = f'{start_tag}type="None" />\n'
        close_tag = ''

    # bool cannot be used as a base class (see sanity check above) so if thing
    # is a bool it will always be BooleanType, and either True or False
    elif isinstance(thing, bool):
        typestr = 'True' if thing is True else 'False'

        if in_body:
            start_tag = f'{start_tag}type="{typestr}">'
            close_tag = close_tag.lstrip()
        else:
            start_tag = f'{start_tag}type="{typestr}" value="" />\n'
            close_tag = ''

    elif isinstance(thing, (int, float, complex)):
        thing_str = ntoa(thing)

        if in_body:
            # we don't call safe_content() here since numerics won't
            # contain special XML chars.
            # the unpickler can either call unsafe_content() or not,
            # it won't matter
            start_tag = f'{start_tag}type="numeric">{thing_str}'
            close_tag = close_tag.lstrip()
        else:
            start_tag = f'{start_tag}type="numeric" value="{thing_str}" />\n'
            close_tag = ''

    elif isinstance(thing, str):
        if in_body:
            start_tag = f'{start_tag}type="string">{safe_string(thing, isattr=False)}'
            close_tag = close_tag.lstrip()
        else:
            start_tag = f'{start_tag}type="string" value="{safe_string(thing, isattr=True)}" />\n'
            close_tag = ''

    # General notes:
    #   1. When we make references, set type to referenced object
    #      type -- we don't need type when unpickling, but it may be useful
    #      to someone reading the XML file
    #   2. For containers, we have to stick the container into visited{}
    #      before pickling subitems, in case it contains self-references
    #      (we CANNOT just move the visited{} update to the top of this
    #      function, since that would screw up every _family_type() call)
    elif isinstance(thing, tuple):
        start_tag, do_copy = _tag_compound(start_tag, 'type="tuple"', orig_thing)
        if do_copy:
            for item in thing:
                tag_body.append(_item_tag(item, level + 1))
        else:
            close_tag = ''

    elif isinstance(thing, (list, UserList)):
        start_tag, do_copy = _tag_compound(start_tag, 'type="list"', orig_thing)
        # need to remember we've seen container before pickling subitems
        VISITED[id(orig_thing)] = orig_thing
        if do_copy:
            for item in thing:
                tag_body.append(_item_tag(item, level + 1))
        else:
            close_tag = ''

    elif isinstance(thing, (dict, UserDict)):
        start_tag, do_copy = _tag_compound(start_tag, 'type="dict"', orig_thing)
        # need to remember we've seen container before pickling subitems
        VISITED[id(orig_thing)] = orig_thing
        if do_copy:
            for key, val in thing.items():
                tag_body.append(_entry_tag(key, val, level + 1))
        else:
            close_tag = ''

    else:
        raise ValueError(f"Non-handled type {type(thing)}")

    # need to keep a ref to the object for two reasons -
    #  1. we can ref it later instead of copying it into the XML stream
    #  2. need to keep temporary objects around so their ids don't get reused
    VISITED[id(orig_thing)] = orig_thing

    return start_tag + ''.join(tag_body) + close_tag


def _thing_from_dom(dom_node: minidom.Element|minidom.Document, container: Any = None) -> Any:
    """Converts an [xml_pickle] DOM tree to a 'native' Python object"""
    node: minidom.Element
    for node in dom_node.childNodes:
        if not hasattr(node, '_attrs') or not node.nodeName != '#text':
            continue

        if node.nodeName == "PyObject":

            # Given a <PyObject> node, return an object of that type.
            # __init__ is NOT called on the new object, since the caller may want
            # to do some additional work first.
            classname = node.getAttribute('class')
            # allow <PyObject> nodes w/out module name
            # (possibly handwritten XML, XML containing "from-air" classes,
            # or classes placed in the CLASS_STORE)
            klass = CLASS_STORE.get(classname)
            if klass is None:
                raise ValueError(f"Cannot create class '{classname}'")
            container = klass.__new__(klass)  # type: ignore[call-overload]

            _save_obj_with_id(node, container)

            # slurp raw thing into a an empty object
            raw = _thing_from_dom(node, _EmptyClass())

            # Copy attributes into the new container object
            for k, v in raw.__dict__.items():
                setattr(container, k, v)

        elif node.nodeName in ['attr', 'item', 'key', 'val']:
            node_family = node.getAttribute('family')
            node_type: str = node.getAttribute('type')
            node_name = node.getAttribute('name')

            # check refid first (if present, type is type of referenced object)
            ref_id = node.getAttribute('refid')

            if ref_id:	 # might be empty or None
                if node.nodeName == 'attr':
                    setattr(container, node_name, VISITED[int(ref_id)])
                else:
                    container.append(VISITED[int(ref_id)])

                # done, skip rest of block
                continue

            # if we didn't find a family tag, guess (do after refid check --
            # old pickles will set type="ref" which this code can't handle)
            # If family is None or empty, guess family based on typename.
            if not node_family:
                if node_type not in TYPE_NAMES:
                    raise ValueError(f"Unknown type {node_type}")
                node_family = TYPE_NAMES[node_type]

            # Get text from node, whether in value=, or in element body.
            # we know where the text is, based on whether there is
            # a value= attribute. ie. pickler can place it in either
            # place (based on user preference) and unpickler doesn't care
            node_valuetext = ""
            if 'value' in node._attrs:  # type: ignore[attr-defined]  # pylint: disable=protected-access
                # text in tag
                ttext = node.getAttribute('value')
                node_valuetext = unsafe_string(ttext, isattr=True)
            else:
                # text in body
                node.normalize()
                if node.childNodes:
                    node_valuetext = unsafe_string(node.childNodes[0].nodeValue, isattr=False)

            # step 1 - set node_val to basic thing
            node_val: Any
            if node_family == 'none':
                node_val = None
            elif node_family == 'atom':
                node_val = node_valuetext
            elif node_family == 'seq':
                # seq must exist in VISITED{} before we unpickle subitems,
                # in order to handle self-references
                seq: list[Any] = []
                _save_obj_with_id(node, seq)
                node_val = _thing_from_dom(node, seq)
            elif node_family == 'map':
                # map must exist in VISITED{} before we unpickle subitems,
                # in order to handle self-references
                mapping: dict[Any, Any] = {}
                _save_obj_with_id(node, mapping)
                node_val = _thing_from_dom(node, mapping)
            elif node_family == 'uniq':
                # uniq is another special type that is handled here instead
                # of below.
                if node_type == 'True':
                    node_val = True
                elif node_type == 'False':
                    node_val = False
                else:
                    raise ValueError(f"Unknown uniq type {node_type}")
            else:
                raise ValueError(f"Unknown family {node_family},{node_type},{node_name}")

            # step 2 - take basic thing and make exact thing
            # Note there are several NOPs here since node_val has been decided
            # above for certain types. However, I left them in since I think it's
            # clearer to show all cases being handled (easier to see the pattern
            # when doing later maintenance).

            # pylint: disable=self-assigning-variable
            if node_type == 'None':
                node_val = None
            elif node_type == 'numeric':
                node_val = aton(node_val)
            elif node_type == 'string':
                node_val = node_val
            elif node_type == 'list':
                node_val = node_val
            elif node_type == 'tuple':
                # subtlety - if tuples could self-reference, this would be wrong
                # since the self ref points to a list, yet we're making it into
                # a tuple. it appears however that self-referencing tuples aren't
                # really all that legal (regular pickle can't handle them), so
                # this shouldn't be a practical problem.
                node_val = tuple(node_val)
            elif node_type == 'dict':
                node_val = node_val
            elif node_type == 'True':
                node_val = node_val
            elif node_type == 'False':
                node_val = node_val
            else:
                raise ValueError(f"Unknown type {node},{node_type}")

            if node.nodeName == 'attr':
                setattr(container, node_name, node_val)
            else:
                container.append(node_val)

            _save_obj_with_id(node, node_val)

        elif node.nodeName == 'entry':
            keyval = _thing_from_dom(node, [])
            key, val = keyval[0], keyval[1]
            container[key] = val
            # <entry> has no id for refchecking

        else:
            raise ValueError(f"Element {node.nodeName} is not in PyObjects.dtd")

    return container
