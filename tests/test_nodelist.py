
from objdictgen.nodemanager import NodeManager
from objdictgen.nodelist import NodeList


def test_nodelist_create(wd):
    """ Create a new nodelist project """

    manager = NodeManager()
    nodelist = NodeList(manager)

    nodelist.LoadProject('.')
    nodelist.SaveProject()


def test_nodelist_load(wd):
    """ Open an existing nodelist """

    manager = NodeManager()
    nodelist = NodeList(manager)

    nodelist.LoadProject('.')
