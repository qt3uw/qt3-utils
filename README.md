# Utility Classes and Functions for the QT3 Lab

This package provides a number of tools and fully-packaged programs for usage
in the Quantum Technologies Teaching and Test-Bed (QT3) lab at the University of Washington.

The QT3 lab confocal microscope utilizes the following hardware to perform
various spin-control experiments on quantum systems, such as NV centers in diamond:

 * TTL pulsers
   * Quantum Composer Sapphire
   * Spin Core PulseBlaster
 * Excelitas SPCM for photon detection
 * NI-DAQ card (PCIx 6363) for data acquisition and control
 * Jena System's Piezo Actuator Stage Control Amplifier
 * [Future] spectrometer

The code in this package facilitates usages of these devices to perform
experiments.

# Setup

An environment.yml file is included in the repository to easily
install a conda environment with the required dependencies.
Install with the following commands in an anaconda prompt.

```
git clone https://github.com/qt3uw/qt3-utils
cd qt3-utils
conda env create -f environment.yml
conda activate qt3-utils
python -m pip install .
```

# Usage

The simplest way to get started is to see one of the [example](examples) notebooks.

# Applications

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

## QT3 Confocal Scan

The console program `qt3scan` comes with this package.  This program launches
a GUI applications that will perform a confocal scan using the Jena system
piezo actuator.

The run-time options available are very similar to `qt3scope`.
Review the available command line options for the program. Pay special attention
to the `--signal-terminal` option, ensuring that terminal value matches the current
hardware setup.

```
> qt3scan --help
```

If default settings are correct, then should be able to run without options

```
> qt3scan
```

# Debugging

# LICENSE

[LICENCE](LICENSE)
