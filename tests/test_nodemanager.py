
from objdictgen.nodemanager import NodeManager


def test_create_master():

    m1 = NodeManager()
    m1.CreateNewNode(
        name="TestMaster", id=0x00, type="master", description="Longer description",
        profile="None", filepath=None, nmt="Heartbeat",
        options=["DS302", "GenSYNC", "Emergency"]
    )
    m1.CloseCurrent()


def test_create_slave():

    m1 = NodeManager()
    m1.CreateNewNode(
        name="TestSlave", id=0x01, type="slave", description="Longer description",
        profile="None", filepath=None, nmt="Heartbeat",
        options=["DS302", "GenSYNC", "Emergency"]
    )
    m1.CloseCurrent()


def test_load(odpath):

    m1 = NodeManager()
    m1.OpenFileInCurrent(odpath / 'master.od')
