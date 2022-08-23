# Utility Classes and Functions for the QT3 Lab


# Setup

### Requirements

The utilities in this package depend on publicly available Python packages found
on PyPI and on packages developed in-house. This public packages will be installed
automatically when you run the setup script (below). However, you will
need to manually install the in-house packages

* gadamc/qcsapphire
* gadamc/qt3RFSynthControl

## Installation

```
git clone https://github.com/gadamc/qt3nidaq-config
cd qt3nidaq-config
python -m pip install .
```

# Usage

In general, it's encouraged to supply usage instructions within
the docstrings for the modules, classes and functions found in this package.

# Examples

# Programs

## QT3 Oscilloscope

The console program `qt3scope` comes with this package. It allows you to run
a simple program from the command-line that reads the count rate on a particular
digital input terminal on the NI DAQ.

Review the available command line options for the program. Pay special attention
to the `--signal-terminal` option, ensuring that terminal value matches the current
hardware setup.

```
> qt3scope --help
```

If default settings are correct, then should be able to run without options

```
> qt3scope
```

# Debugging

# LICENSE

[LICENCE](LICENSE)
