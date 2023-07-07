# Objdictgen (`odg`)

This is python tools for working with Object Dictionary (OD) files for
the CanFestival communication library. CanFestival is an open source
implementation of the [CANopen](https://www.can-cia.org/canopen/)
communication protocol.

This repo is located:

> https://github.com/laerdal-svg/python-objdictgen

objdictgen includes tools to generate c code that works in tandem with a
canfestival library. This tool has been built to work together with the
Laerdal Medical fork for the canfestival library:

> https://github.com/laerdal-svg/canfestival-laerdal

objdictgen is a tool to parse, view and manipulate files containing object
dictionary (OD). An object dictionary is entries with data and configuration
in CANopen devices. The `odg` executable is installed. It supports
reading and writing OD files in `.json` format, in legacy XML `.od` and `.eds`
files. It can generate c code for use with the canfestival library.


## Motivation

The biggest improvement with the new tool over the original implementation is
the introduction of a new `.json` based format to store the object dictionary.
The JSON format is well-known and easy to read. The tool supports jsonc,
allowing comments in the json file. `odg` will process the file in a repeatable
manner, making it possible support diffing of the `.json` file output. `odg`
remains 100% compatible with the legacy `.od` format on both input and output.

The original objdictedit and objdictgen tool were written in legacy python2 and
and this is a port to python3. The package still remains compatible with
python2, as python2 is required for running the UI tools.

This tool is a fork from upstream canfestival-3-asc repo:

> https://github.com/laerdal-svg/canfestival-3-asc


## Install

To install into a virtual environment `venv`. Check out this repo and go to
the top in a command-prompt (here assuming Windows and git bash):

    $ py -3 -mvenv venv
    $ venv/Scripts/python -mpip install --upgrade pip wheel setuptools
    $ venv/Scripts/pip install .

After this `venv/Scripts/odg.exe` will exist and can be called
from anywhere to run it.


### Python 2

To run the `objdictedit` GUI, wxPython is required and it is only available
for Python 2.7. Download and install both.

   * https://www.python.org/downloads/release/python-2716/
   * https://sourceforge.net/projects/wxpython/files/wxPython/2.8.12.1/

To setup the virtual environment run (assuming git bash):

    $ py.exe -2 -mvirtualenv --system-site-packages venv-27
    $ venv-27/Scripts/python -mpip install --upgrade pip wheel setuptools
    $ venv-27/Scripts/pip install .

NOTE: The `py.exe` tool is only shipped with recent Python 3.


## `odg` command-line tool

`odg` is a command-line tool which is installed when the python package
`objdictgen` is installed.

Invocation:

    $ odg <options>
    $ python -mobjdictgen <options>   # <-- If odg is unavailable

`odg --help` and `odg <command> --help` exists and shows the command options.
The most useful commands are:

    $ odg list <od-files...>              # List contents of the OD
    $ odg convert <od-file1> <od-file2>   # Convert OD file
    $ odg convert <od-file> <c-file>      # Convert OD to c code
    $ odg diff <od-file1> <od-file2>      # Show differences between OD


### Legacy commands

The legacy commands `objdictgen` and `objdictedit` are still available. The
same commands are available under `odg gen` and `odg edit` respectively. Note
that Python 2 is required to run `objdictedit` due to the dependency on the
old wxpython library.


## JSON schema

[src/objdictgen/schema/od.schema.json](src/objdictgen/schema/od.schema.json)
provides a JSON schema for the JSON OD format. This can be used for validation
in editors.

To use the schema in **VS Code**, the following configuration must be added to
your `settings.json`. After this is is installed, IntelliSense will show field
descriptions, help with values and validate the file.

```json
    "json.schemas": [
      {
        "fileMatch": [
          "**.json"
        ],
        "url": "./src/objdictgen/schema/od.schema.json"
      }
    ],
    "files.associations": {
        "*.json": "jsonc"
    }
```


## Conversion

The recommended way to convert existing/legacy `.od` files to the new JSON
format is:

    $ odg generate <file.od> <file.json> --fix --drop-unused [--nosort]

The `--fix` option might be necessary if the OD-file contains internal
inconsistencies. It is safe to run this option as it will not delete any active
parameters. The `--drop-unused` will remove any unused *profile* and *DS-302*
parameter that might be used in the file.


## License

Objdictgen has been based on the python tool included in CanFestival. This
original work from CanFestival is:

    Copyright (C): Edouard TISSERANT, Francis DUPIN and Laurent BESSARD

The Python 3 port and tool improvements have been implemented under

    Copyright (C) 2022 Svein Seldal, Laerdal Medical AS
