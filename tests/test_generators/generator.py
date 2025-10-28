"""Example of a valid .py file you could pass with the --generate-with arg"""

from objdictgen.typing import NodeProtocol, TPath

def GenerateFile(filepath: TPath, node: NodeProtocol):
    print("success")