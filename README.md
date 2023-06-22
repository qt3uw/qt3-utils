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

Details of how the experiment classes work and how you can modify
them are found in [ExperimentsDoc.md](docs/ExeperimentsDoc.md)

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

# Development

If you wish you make changes to qt3-utils (and hopefully merge those improvements into this repository), here are some brief instructions to get started. These instructions assume you are a member of the QT3 development team and have permission to push branches to this repo. If you are not, you can instead fork this repo into your own GitHub account, perform development and then issue a pull-request from your forked repo to this repo through GitHub. Alternatively, reach out to a maintainer of this repo to be added as a developer. 

1. Create a new development python environment (using Conda, venv or virtualenv) with Python = 3.9 or greater

```
> conda create --name qt3utilsdev python=3.9
```

2. Activate that environment

```
> conda activate qt3utilsdev
```

3. Clone this repository

```
> git clone https://github.com/qt3uw/qt3-utils.git
```

4. Install qt3-utils in "editor" mode

```
> cd qt3-utils
> pip install -e . 
```

5. Create a new branch for your work

```
> git checkout -b add-my-fancy-new-feature
```

6. Add your code and test, test, test!

7. Push your branch

```
> git push -u origin add-my-fancy-new-feature
```

8. Issue a pull request from this website


A few notes about development for this repository.

The `pip install -e .` command installs the package in editor mode. 
This allows you to make changes to the source code and immediately
see the effects of those changes in a Python interpreter. It saves
you from having to call "pip install" each time you make a change and 
want to test it. 

We do not have an official style convention, unfortunately. However
please try to follow best-practices as outlined either in 
[PEP 8 styleguide](https://peps.python.org/pep-0008/)
or [Google's styleguide](https://google.github.io/styleguide/pyguide.html).
There are other resources online, of course, that provide "best-practices"
advice. Having said that, you will certainly find places where I've 
broken those guides. (Ideally, somebody would go through with a linter
and fix all of these.). Please heavily document your source code. 

We do not have an automatic test rig. This *could* be added by somebody
if desired. But that could be complicated given that this code requires
specific local hardware and the setup for each experiment 
is likely to be different. So, be sure to test your code rigorously and 
make sure there are no unintended side-effects. 

When you issue a pull request, be very clear and verbose about the 
changes you are making. New code must be reviewed by another colleague
before it gets merged to master. Your pull request should

* clearly state what is changed or new
* state why you chose your specific implementation
* include results of tests on your hardware setup, which could be data, screenshots, etc. There should be a clear record demonstrating functionality.
* potentially include a Jupyter notebook in the "examples" folder that demonstrate usage and changes
* include documentation

Due to our lack of a test rig, merging should be done with care and
code reviews should be taken seriously. If you are asked by a colleague
to review their code, make sure to ask a lot of questions as you read
through it. You may even want to test the branch on your own setup 
to ensure it doesn't break anything. 

Historically, documentation for this project has been "just okay". Please 
help this by adding any documentation for your changes where appropriate.
There is now a `docs` folder that you can use to include any major
additions or changes. 

# Debugging

# LICENSE

[LICENCE](LICENSE)
