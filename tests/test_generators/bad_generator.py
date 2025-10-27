"""Example of an invalid .py file you could pass with the --generate-with arg.
In this case the function name does not match the expected name"""

from objdictgen.typing import NodeProtocol, TPath

def Generate_File(filepath: TPath, node: NodeProtocol):
    return ""