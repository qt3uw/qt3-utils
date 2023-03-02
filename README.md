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

### Prerequisites

The utilities in this package depend on publicly available Python packages found
on PyPI and drivers built by National Instruments for DAQmx and
SpinCore for the PulseBlaster. These libraries must be installed separately.

* [National Instruments DAQmx](https://nidaqmx-python.readthedocs.io/en/latest/)
  * [driver downloads](http://www.ni.com/downloads/)
* [SpinCore's PulseBlaster](https://www.spincore.com/pulseblaster.html)
  * [spinAPI driver](http://www.spincore.com/support/spinapi/)

## Installation

Once the prerequisite packages have been installed, qt3utils can be installed from pip.

```
pip install qt3utils
```

The `qt3utils` package depends on a handful of other [qt3 packages](https://github.com/qt3uw) and will be installed for you by default.
Additional information may also be [found here](https://github.com/qt3uw/qt3softwaredocs).


# Usage

This package provides GUI applications and a Python API for controlling the hardware and running experiments.

For instructions on using the python API,
the simplest way to get started is to see one of the [example](examples) Jupyter notebooks.

The following notebooks demonstrate usage of their respective experiment classes and
the necessary hardware control objects for those experiments

  * [CWODMR](examples/default_cwodmr.ipynb)
  * [Pulsed ODMR](examples/default_podmr.ipynb)
  * [Rabi Oscillations](examples/default_rabi.ipynb)
  * [Ramsey](examples/default_ramsey.ipynb) (similar usage for spin/Hahn echo and dynamical decoupling)

Additionally, there are two notebooks that demonstrate some basic hardware tests

  * [Pulse Blaster Tests](examples/pulse_blaster_testing.ipynb)
  * [MW Switch Tests](examples/testing_MW_switch.ipynb)
  
Most classes and methods contain docstrings that describe functionality, which you can
discover through the python help() function.

Help to [automatically generate documentation](https://github.com/qt3uw/qt3-utils/issues/66) would be appreciated.


## Applications

### QT3 Oscilloscope

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

### QT3 Confocal Scan

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

### QT3 Piezo Controller

The console program `qt3piezo` comes installed via the 'nipiezojenapy' package, and may be launched from the command line.

```
> qt3piezo
```

Similarly, this applications can be configured via command line options to match the haredware setup.


# Debugging

# LICENSE

[LICENCE](LICENSE)
