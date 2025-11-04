
import importlib.metadata
import os
import re
from pprint import pprint
from typing import Any

import objdictgen


def convert(infile, outfile):
    ''' Tool to replace @@{VAR_NAME} in files.'''

    pat = re.compile(r'^(.*?)@@{(.[^}]+)}(.*)$', re.S)

    config: dict[str, Any] = dict(importlib.metadata.metadata("objdictgen"))

    # Generate a 4-tuple version number
    version = objdictgen.__version__
    version_tuple = tuple(int(x) for x in version.split('.') if x.isdigit())
    version_tuple = version_tuple + (0,) * (4 - len(version_tuple))

    config['_version_tuple'] = version_tuple
    config['_copyright'] = objdictgen.__copyright__

    # Shorten description for file description field and print it
    pr_config = config.copy()
    pr_config["Description"] = pr_config["Description"][0:60] + "..."
    pprint(pr_config)

    with open(infile, "r", encoding="utf-8") as fin:
        out = ''
        for line in fin:

            while True:
                m = pat.fullmatch(line)
                if not m:
                    out += line
                    break

                out += m[1]
                name = m[2]
                line = m[3]  # Remainder for the next iteration
                if name in config:
                    out += str(config[m[2]])

                elif name in os.environ:
                    out += os.environ[name]

                else:
                    raise KeyError(f"The variable {name} is not defined")

    with open(outfile, 'w', encoding="utf-8") as fout:
        fout.write(out)

    print(f"Converted {infile} -> {outfile}\n{out}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Input file')
    parser.add_argument('output', help='Output file')
    args = parser.parse_args()

    convert(args.input, args.output)
