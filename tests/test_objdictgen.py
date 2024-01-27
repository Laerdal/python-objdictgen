import os
import objdictgen.__main__


def run_objdictgen(arg_list, mocker, odfile, fn):
    od = odfile.name
    if "-l" in arg_list:
        od = f"{od}_legacy"
        odfile = f"{odfile}_legacy"
    mocker.patch("sys.argv", arg_list)
    objdictgen.__main__.main_objdictgen()

    if os.path.exists(f"{odfile}.c"):
        assert fn.diff(f"{odfile}.c", f"{od}.c", n=0)
        assert fn.diff(f"{odfile}.h", f"{od}.h", n=0)
        assert fn.diff(f"{odfile}_objectdefines.h", f"{od}_objectdefines.h", n=0)


def test_objdictgen(wd, mocker, odfile, fn):
    """ Test that objdictgen generates equal output as reference """
    od = odfile.name
    arg_list = ["objdictgen", f"-i{odfile}.od", f"-o{od}.c"]
    run_objdictgen(arg_list, mocker, odfile, fn)


def test_objdictgen_legacy(wd, mocker, odfile, fn):
    """ Test that objdictgen generates equal legacy output as reference """
    od = odfile.name
    arg_list = ["objdictgen", "-l", f"-i{odfile}.od", f"-o{od}_legacy.c"]
    run_objdictgen(arg_list, mocker, odfile, fn)
