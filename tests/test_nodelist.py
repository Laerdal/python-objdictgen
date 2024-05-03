import pytest

from objdictgen.nodemanager import NodeManager
from objdictgen.nodelist import NodeList, main
from objdictgen.node import Node


def test_nodelist_main(wd):

    main(wd)


def test_nodelist_load_and_save(wd):
    """ Create a new nodelist project """

    manager = NodeManager()
    nodelist = NodeList(manager)

    nodelist.LoadProject('.')
    nodelist.SaveProject()


def test_nodelist_setup(wd, odpath):
    """ Open an existing nodelist """

    od = Node.LoadFile(odpath / 'slave.json')
    od.DumpFile('slave.eds', 'eds')

    manager = NodeManager()
    nodelist = NodeList(manager)

    nodelist.LoadProject('.')
    nodelist.LoadEDS('slave.eds')
    nodelist.AddSlaveNode('slave', 2, 'slave.eds')
    nodelist.SaveProject()
    nodelist.SaveNodeList()

    main('.')
