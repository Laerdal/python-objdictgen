import os
import glob
import sys
import argparse
import shutil
import logging

from objdictgen import Node

parser = argparse.ArgumentParser()
parser.add_argument("od_dir", help="Directory to ODs")
parser.add_argument("out_dir", nargs="?", help="Output directory. Use od_dir if omitted.")
opts = parser.parse_args()

if opts.out_dir:
    out_dir = os.path.abspath(opts.out_dir)
else:
    out_dir = os.path.abspath(opts.od_dir)

# Initalize the python logger to simply output to stdout
log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))


def convert(fname):
    base = fname.replace('.od', '')

    print(f"Reading {fname}")
    node = Node.LoadFile(base + '.od')

    node.Validate(fix=True)

    print("    Writing json")
    node.DumpFile(base + '.json', filetype='json', sort=True)


for root, dirs, files in os.walk(opts.od_dir):
    for fname in files:
        if not fname.endswith('.od'):
            continue

        src = os.path.abspath(os.path.join(root, fname))
        dst = os.path.join(out_dir, fname)
        if src != dst:
            shutil.copyfile(src, dst)

        try:
            convert(dst)
        except Exception as err:
            print("FAILED: %s" %(err,))
