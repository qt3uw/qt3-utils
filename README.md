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

### Normal Installation

```
pip install qt3utils
```

The `qt3utils` package depends on a handful of other [qt3 packages](https://github.com/qt3uw) and will be installed for you by default.
Additional information may also be [found here](https://github.com/qt3uw/qt3softwaredocs).

#### Update Tk/Tcl

Upgrading Tcl/Tk via Anaconda overcomes some GUI bugs on Mac OS Sonoma

```
conda install 'tk>=8.6.13'
```


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
digital input terminal on the NI DAQ. Further development may allow it to 
display count rates from other hardware.

It can be from the command line / terminal

```
> qt3scope
```

After `pip install`, there will be an executible file in your python environment. You
should be able to create a softlink to that executable to a desktop or task bar icon, allowing
to launch the program from a mouse click.

Starting in version 1.0.3, graphical dropdown menus and configuration windows
will allow users to configure various hardware options. 


#### YAML Configuration

Data Acquisition hardware supported by QT3Scope can also be configured by selecting a YAML file.
The YAML file must contain a specific structure and names as shown below. 


###### Default NIDAQ Edge Counter YAML configuration:

```yaml
QT3Scope:
  DAQController:
    import_path : qt3utils.applications.controllers.nidaqedgecounter
    class_name  : QT3ScopeNIDAQEdgeCounterController
    configure : 
      daq_name : Dev1  # NI DAQ Device Name
      signal_terminal : PFI0  # NI DAQ terminal connected to input digital TTL signal
      clock_terminal :    # Specifies the digital input terminal to the NI DAQ to use for a clock. If left blank, interprets as None or NULL
      clock_rate: 100000  # NI DAQ clock rate in Hz
      num_data_samples_per_batch : 1000
      read_write_timeout : 10  # timeout in seconds for read/write operations
      signal_counter : ctr2  # NI DAQ counter to use for counting the input signal, e.g. ctr0, ctr1, ctr2, or ctr3
```

###### Default Random Data Generator configuration:

```yaml
QT3Scope:
  DAQController:
    import_path : qt3utils.applications.controllers.random_data_generator
    class_name  : QT3ScopeRandomDataController
    configure : 
      simulate_single_light_source : False
      num_data_samples_per_batch : 10
      default_offset: 100
      signal_noise_amp: 0.5
```

All hardware controllers built for QT3Scope have a default
configuration YAML file, which are found in 
[src/qt3utils/applications/controllers](src/qt3utils/applications/controllers).

### QT3 Confocal Scan

The console program `qt3scan` performs a 2D (x,y) scan using a data acquisition
controller object and a position controller object. The default controllers use
an NIDAQ device that counts TTL edges (typically from an SPCM) and sets
analog voltage values on a Jena system piezo actuator.

```
> qt3scan
```

Similar to `qt3scope`, the supported hardware can be configured via GUI or YAML file. 

All hardware controllers that are built for QT3Scope have a default
configuration YAML file, which will be found in 
[src/qt3utils/applications/controllers](src/qt3utils/applications/controllers).

###### Default NIDAQ Edge Counter YAML configuration:

```yaml
QT3Scan:
  DAQController:
    import_path : qt3utils.applications.controllers.nidaqedgecounter
    class_name  : QT3ScanNIDAQEdgeCounterController
    configure : 
      daq_name : Dev1  # NI DAQ Device Name
      signal_terminal : PFI0  # NI DAQ terminal connected to input digital TTL signal
      clock_terminal :    # Specifies the digital input terminal to the NI DAQ to use for a clock. If left blank, interprets as None or NULL
      clock_rate: 100000  # NI DAQ clock rate in Hz
      num_data_samples_per_batch : 250
      read_write_timeout : 10  # timeout in seconds for read/write operations
      signal_counter : ctr2  # NI DAQ counter to use for counting the input signal, e.g. ctr0, ctr1, ctr2, or ctr3

  PositionController:
    import_path : qt3utils.applications.controllers.nidaqpiezocontroller    
    class_name  : QT3ScanNIDAQPositionController
    configure : 
      daq_name : Dev1  # NI DAQ Device Name
      write_channels : ao0,ao1,ao2  # NI DAQ analog output channels to use for writing position
      read_channels : ai0,ai1,ai2  # NI DAQ analog input channels to use for reading position
      scale_microns_per_volt : 8  # conversion factor from volts to microns, can also supply a list [8,8,8] or [6,4.2,5] 
      zero_microns_volt_offset: 0  # the voltage value that defines the position 0,0,0, can also supply a list [0,0,0] or [5,5,5] 
      minimum_allowed_position : 0  # microns
      maximum_allowed_position : 80  # microns
      settling_time_in_seconds : 0.001

```

###### Default Princeton Spectrometer YAML configuration:

```yaml
QT3Scan:
  DAQController:
    import_path : qt3utils.applications.controllers.princeton_spectrometer
    class_name  : QT3ScanPrincetonSpectrometerController
    configure :
      exposure_time : 2000 # This is in ms
      center_wavelength : 700 # This is in nm
      sensor_temperature_set_point : -70 # This is in Celsius
      grating_selected : "[500nm,300][2][0]" # Varies based on spectrometer type
      wave_start : 600
      wave_end : 850
      experiment_name: "LF_Control"

  PositionController:
    import_path : qt3utils.applications.controllers.nidaqpiezocontroller
    class_name  : QT3ScanNIDAQPositionController
    configure :
      daq_name : Dev1  # NI DAQ Device Name
      write_channels : ao0,ao1,ao2  # NI DAQ analog output channels to use for writing position
      read_channels : ai0,ai1,ai2  # NI DAQ analog input channels to use for reading position
      scale_microns_per_volt : 8  # conversion factor from volts to microns, can also supply a list [8,8,8] or [6,4.2,5]
      zero_microns_volt_offset: 0  # the voltage value that defines the position 0,0,0, can also supply a list [0,0,0] or [5,5,5]
      minimum_allowed_position : 0  # microns
      maximum_allowed_position : 80  # microns
      settling_time_in_seconds : 0.001

```

###### Default Random Data Generator configuration:

```yaml
QT3Scan:
  PositionController:
    import_path : qt3utils.applications.controllers.random_data_generator    
    class_name  : QT3ScanDummyPositionController
    configure : 
      maximum_allowed_position : 80
      minimum_allowed_position : 0

  DAQController:
    import_path : qt3utils.applications.controllers.random_data_generator
    class_name  : QT3ScanRandomDataController
    configure : 
      simulate_single_light_source : True
      num_data_samples_per_batch : 10
      default_offset: 100
      signal_noise_amp: 0.1

```

###### Default Spectrometer Random Data Generator configuration:

```yaml
QT3Scope:
  DAQController:
    import_path : qt3utils.applications.controllers.random_data_generator
    class_name  : QT3ScopeRandomDataController
    configure : 
      simulate_single_light_source : False
      num_data_samples_per_batch : 10
      default_offset: 100
      signal_noise_amp: 0.5

QT3Scan:
  PositionController:
    import_path : qt3utils.applications.controllers.random_data_generator    
    class_name  : QT3ScanDummyPositionController
    configure : 
      maximum_allowed_position : 80
      minimum_allowed_position : 0

  DAQController:
    import_path : qt3utils.applications.controllers.random_data_generator
    class_name  : QT3ScanRandomDataController
    configure : 
      simulate_single_light_source : True
      num_data_samples_per_batch : 10
      default_offset: 100
      signal_noise_amp: 0.1

```

### QT3 Piezo Controller

The console program `qt3piezo` comes installed via the 'nipiezojenapy' package, and may be launched from the command line.

```
> qt3piezo
```

This application can only be configured via command line options at this time.
The `nipiezojenapy` python package should probably be moved into `qt3utils`. 


# QT3Scope / QT3Scan Hardware Development

Follow these instructions in order to add new hardware support to `qt3scope` or `qt3scan`.

For each application, you'll need to build a Python classes that adheres to each application's interfaces.

## QT3Scope


1. Build a class that adheres to `QT3ScopeDAQControllerInterface` as defined in
[src/qt3utils/applications/qt3scope/interface.py](src/qt3utils/applications/qt3scope/interface.py). There are a number of methods
that you must construct. Two examples are [QT3ScopeRandomDataController](src/qt3utils/applications/controllers/random_data_generator.py)
and [QT3ScopeNIDAQEdgeCounterController](src/qt3utils/applications/controllers/nidaqedgecounter.py#L13). 
In addition to controlling hardware and returning data, they must also supply a way to configure the object via 
Python dictionary (`configure` method) and graphically (`configure_view` method).
2. Create a YAML file with a default configuration, similar to that found in 
[random_data_generator.yaml](src/qt3utils/applications/controllers/random_data_generator.yaml) or [](src/qt3utils/applications/controllers/nidaq_edge_counter.yaml)
3. Add your new controller to `SUPPORTED_CONTROLLERS` found in [qt3scope](src/qt3utils/applications/qt3scope/main.py#L51)

## QT3Scan

Similar to `qt3scope` but with a little more work.

There are three controllers that are needed by `qt3scan`:
* Application Controller -- [QT3ScanApplicationControllerInterface](src/qt3utils/applications/qt3scan/interface.py#L106) 
* DAQ Controller -- [QT3ScanDAQControllerInterface](src/qt3utils/applications/qt3scan/interface.py#L59) 
* Position Controller -- [QT3ScanPositionControllerInterface](src/qt3utils/applications/qt3scan/interface.py#L7)

### 1. Application Controller 

Currently there are two implementations of the Application Controller. [The first application controller](src/qt3utils/applications/qt3scan/controller.py#L14) is made to support standard 2D (x,y) scans. It is used for scans using the NIDAQ Edge Counter
Controller, NIDAQ Position Controller, Random Data Generator and Dummy 
Position Controller. 

If you do not need any changes to the save function 
or special functionality to right-click on the scan image, then you can probably 
re-use this Application Controller. 

[The second application controller](https://github.com/qt3uw/qt3-utils/blob/134sub-changes-to-interface/src/qt3utils/applications/qt3scan/controller.py#L180) is an implements the hyperspectral image where each pixel each pixel in the 2D scan is based on a spectrum
of counts over a range of wavelengths.
`QT3ScanHyperSpectralApplicationController` class implements this 
data view when a user right-clicks on the scan and along with a function
to save the full 3-dimensional data set. 

### 2. DAQ Controller

To support new hardware that acquires data, build an implementation of `QT3ScanDAQControllerInterface`.
The DAQ controller interface is now split into two distinct interfaces:

- Counter DAQ Controller (`QT3ScanCounterDAQControllerInterface`): This interface is specifically designed for hardware that functions primarily as counters, such as devices measuring photon counts or other discrete events. It extends the base DAQ controller interface by adding methods tailored to sampling counts and computing count rates.

- Spectrometer DAQ Controller (`QT3ScanSpectrometerDAQControllerInterface`): This is tailored for spectrometers that acquire spectral data. This interface adds a method to sample the spectrum, making it easier for developers to integrate spectrometers into the QT3Scan framework.

Examples are [QT3ScanRandomDataController](src/qt3utils/applications/controllers/random_data_generator.py#L124),
[QT3ScanNIDAQEdgeCounterController](src/qt3utils/applications/controllers/nidaqedgecounter.py#L139), and `QT3ScanPrincetonSpectrometerController`

Create a new python module in in `src/qt3utils/applications/controllers` for your hardware controller.

### 3. Position Controller

To support a new Position Controller build an implementation of `QT3ScanPositionControllerInterface`.
Examples are [QT3ScanDummyPositionController](src/qt3utils/applications/controllers/random_data_generator.py#L160),
and [QT3ScanNIDAQPositionController](src/qt3utils/applications/controllers/nidaqpiezocontroller.py#L9)

Create a new python module in in `src/qt3utils/applications/controllers` for your position controller.

### 4. Default YAML file

Create a default YAML file that configures your DAQ and Position Controllers. Place the YAML file in
`src/qt3utils/applications/controllers`

### 5. Update QT3Scan.main

Add your new controllers to [qt3scan.main.py](src/qt3utils/applications/qt3scan/main.py#L46)


# General Python Development

If you wish you make changes to qt3-utils (and hopefully merge those improvements into this repository) here are some brief instructions to get started. These instructions assume you are a 
member of the QT3 development team and have permission to push branches to this repo. If you are not, you can 
instead fork this repo into your own GitHub account, perform development and then issue a pull-request from 
your forked repo to this repo through GitHub. Alternatively, reach out to a maintainer of this repo to be added as a developer. 

These are mostly general guidelines for software development and 
could be followed for other projects.

### 1. Create a development environment 

Use Conda, venv or virtualenv with Python = 3.9. 

```
> conda create --name qt3utilsdev python=3.9
```

As of this writing, we have primarily tested and used Python 3.9. 
Reach out to a Maintainer to discuss moving to newer versions of
Python if this is needed. 

### 2. Activate that environment

```
> conda activate qt3utilsdev
```

### 3. Clone this repository

```
> git clone https://github.com/qt3uw/qt3-utils.git
```

### 4. Install qt3-utils in "editor" mode

```
> cd qt3-utils
> pip install -e . 
```

The `pip install -e .` command installs the package in editor mode. 
This allows you to make changes to the source code and immediately
see the effects of those changes in a Python interpreter. It saves
you from having to call "pip install" each time you make a change and 
want to test it. 


### 5. Create a new Issue

It's generally good practice to first create an Issue in this GitHub
repository which describes the problem that needs to be addressed. 
It's also a good idea to be familiar with the current Issues that 
already exist. The change you want to make may already be 
reported by another user. In that case, you could collaborate 
with that person. 

### 6. Create a new branch for your work

```
> git checkout -b X-add-my-fancy-new-feature
```
where it's good practice to use X to refer to a specific Issue to fix 
in this repository. 

You should create a new branch only for a specific piece of new work
that will be added to this repository. It is highly discouraged to create
a separate branch for your microscope only and to use that branch
to perform version control for Python scripts or Jupyter notebooks 
that run experiments. 
If you need version control for your exerpiment scripts and notebooks, you
should create a separate git repository and install qt3utils 
in the normal way (`pip install -U qt3utils`) in a Python environment 
for your experimental work. If you need to have recent changes to qt3utils
published to PyPI for your work, reach out to a Maintainer of this 
repo to ask them to release a new version. 

### 7. Add your code and test with your hardware!

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

Historically, documentation for this project has been "just okay". Please 
help this by adding any documentation for your changes where appropriate.
There is now a `docs` folder that you can use to include any major
additions or changes. 

### 8. Push your branch

Once development and testing are complete you will want to push your
branch to Github in order to merge it into the rest of the code-base.

When you first push a branch to Github, you will need to issue this 
command.

```
> git push -u origin X-add-my-fancy-new-feature
```

As you add more commits to your branch, you'll still want to 
push those changes every once in a while with a simple

```
> git push
```

(assuming that X-add-my-fancy-new-feature is your current 
local working branch)

Finally, before you issue a pull request, you will want to
synchrononize your branch with any other changes made in 'main'
to ensure there are no conflicting changes.

This is the following "flow" that has been used successfully in
various development projects. However, there are other ways
to do this. 

```
> git checkout main
> git pull
> git checkout X-add-my-fancy-new-feature
> git rebase main
> git push -f
```

The series of commands above will pull down new changes from 
Github's main branch to your local working copy. The `rebase` 
command will then "replay" your changes on top of the 
most recent HEAD of the main branch. If there are conflicts,
git will notify you and you will be forced to fix those
conflicts before continuing with the rebase. If it seems too
complicated, you can `git rebase --abort` to recover and
then figure out what to do next. Reach out to a more experienced
colleague, perhaps, for help. 

The final `git push -f` is necessary (if there were indeed new
commits on the main branch) and will "force" push your branch
to Github. This is necessary due to the way git works. 

You should then test your local branch with your hardware again!

This particular flow has the benefit of making a very clear git
history that shows all the commits for each branch being
merged in logical order. 

Instead of following the instructions above, you may consider
trying GitHub's "rebase" option when issuing a pull request. 
It will attempt the same set of operations. However, you may 
not have the opportunity to test the changes locally. 

### 9. Issue a pull request

At the top of this qt3-utils GitHub repository is a 'pull-request' tab,
from where you can create a request to merge your branch to another
branch (usually you merge to main)

When you issue a pull request, be very clear and verbose about the 
changes you are making. New code must be reviewed by another colleague
before it gets merged to master. Your pull request should include things like

* a statement describing what is changed or new
* a reference to the Issue being fixed here (Github will automatically generate a handy link)
* a statement describing why you chose your specific implementation
* results of tests on your hardware setup, which could be data, screenshots, etc. There should be a clear record demonstrating functionality.
* a Jupyter notebook in the "examples" folder that demonstrate usage and changes
* documentation

### 10. Perform Self Review

Before asking a colleague to review your changes, it's generally
a good idea to review the changes yourself in Github. 
When you see your updates from this perspective you may find
typos and changes that you wish to address first.

### 11. Obtain a Code Review from a colleague

Due to our lack of a test rig, merging should be done with care and
code reviews should be taken seriously. If you are asked by a colleague
to review their code, make sure to ask a lot of questions as you read
through it. You may even want to test the branch on your own setup 
to ensure it doesn't break anything. 

### 12. Address Changes

If you and your reviewer decide changes are needed, go back 
to your branch, make changes and push new commits. Repeat
steps 7, 8, 10, 11 and 12 until you are satisfied. 

### 13. Merge!

If you are satisfied and confident that your changes are 
ready, and your reviewer has approved the changes, press the
green Merge button. 
## Notes



# Debugging

# LICENSE

[LICENCE](LICENSE)
