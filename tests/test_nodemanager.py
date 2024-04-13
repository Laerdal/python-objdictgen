import pytest
from pprint import pprint

from objdictgen.nodemanager import NodeManager
from objdictgen.maps import OD
from objdictgen.jsonod import node_todict

def test_nodemanager_createnewnode():

    nm = NodeManager()

    nm.CreateNewNode(
        name="TestMaster", id=0x00, type="master", description="Longer description",
        profile="None", filepath="", nmt="Heartbeat",
        options=["DS302", "GenSYNC", "Emergency"]
    )
    nm.BufferCurrentNode()

    node = nm.current
    assert node.Name == "TestMaster"
    assert node.ID == 0x00
    assert node.Type == "master"
    assert node.Description == "Longer description"
    assert node.ProfileName == "None"

    nm.CloseCurrent()

    # FIXME: This doesn't work, it doesn't raise an error. The class doesn't
    # seem to unset the current node when closing it.
    # with pytest.raises(AttributeError):
    #     node = nm.current

    nm = NodeManager()
    nm.CreateNewNode(
        name="TestSlave", id=0x01, type="slave", description="Longer description",
        profile="None", filepath="", nmt="Heartbeat",
        options=["DS302", "GenSYNC", "Emergency"]
    )

    node = nm.current
    assert node.Name == "TestSlave"
    assert node.ID == 0x01
    assert node.Type == "slave"
    assert node.Description == "Longer description"
    assert node.ProfileName == "None"

    nm.CloseCurrent()


def test_nodemanager_load(odpath):

    nm = NodeManager()
    nm.OpenFileInCurrent(odpath / 'master.od')


def test_nodemanager_addmapvariabletocurrent(odpath):

    nm = NodeManager()
    nm.OpenFileInCurrent(odpath / 'master.od')

    nm.AddMapVariableToCurrent(0x2000, "A", OD.VAR, 0)

    node = nm.current
    assert node.IsEntry(0x2000)

    entry = node.GetIndexEntry(0x2000)
    object = entry['object']
    assert object['name'] == "A"
    assert object['struct'] == OD.VAR


def test_nodemanager_setcurrententry(odpath):

    nm = NodeManager()
    nm.OpenFileInCurrent(odpath / 'master.od')

    index = 0x2000
    subindex = 0
    nm.AddMapVariableToCurrent(index, "A", OD.VAR, 0)

    node = nm.current
    def getv(index):
        entry = node.GetIndexEntry(index)
        # from pprint import pprint
        # pprint(entry)
        object = entry['object']
        return entry['dictionary'], object['values'][0]

    # == DOMAIN tests ==
    nm.SetCurrentEntry(index, subindex, "DOMAIN", "type", "type")
    val, obj = getv(index)
    assert obj['type'] == node.GetTypeIndex("DOMAIN")

    for inv, outv in [
        ("00", "\x00"),
        ("11", "\x11"),
        ("AA", "\xAA"),
        ("CC", "\xCC"),
        ("FF", "\xFF"),
        ("E29C93", "\xE2\x9C\x93"),  # Is a unicode checkmark
    ]:
        nm.SetCurrentEntry(index, subindex, inv, "value", "domain")
        val, obj = getv(index)
        assert val == outv

        data, editors = nm.GetNodeEntryValues(node, index)
        for d in data:
            if d['type'] != 'DOMAIN':
                continue
            assert d['value'] == inv

        nd, _ = node_todict(node, rich=False)
        for jobj in nd['dictionary']:
            if jobj['index'] != index:
                continue
            pprint(jobj)
