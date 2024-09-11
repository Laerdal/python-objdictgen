
import os
import re
import warnings
import objdictgen
from setuptools import SetuptoolsDeprecationWarning
from setuptools.config import read_configuration

warnings.filterwarnings("ignore", category=SetuptoolsDeprecationWarning)


def convert(infile, outfile):
    ''' Tool to replace @@{VAR_NAME} in files.'''

    pat = re.compile(r'^(.*?)@@{(.[^}]+)}(.*)$', re.S)

    config = read_configuration('setup.cfg')["metadata"]

    # Some hacks
    config['version_tuple'] = objdictgen.__version_tuple__
    config['copyright'] = objdictgen.__copyright__

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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='Input file')
    parser.add_argument('output', help='Output file')
    args = parser.parse_args()

    convert(args.input, args.output)
