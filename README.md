# UW Quantum Defect Lab Utilities (base)
This repository contains the base software tools and applications for interfacing
with hardware used in the [Quantum Defect Laboratory](https://sites.google.com/uw.edu/optospintronics-lab/home) 
at the University of Washington.
This repository was initially forked from [`qt3-utils`](https://github.com/qt3uw/qt3-utils) 
(developed for the Quantum Technologies Teaching and Test-Bed (QT3) lab,
also at the University of Washington).

Currently, `qdl-utils` supports the following hardware for experiments with 
solid-state optical emitters and spin-qubits:

* TTL pulsers
  * Quantum Composer Sapphire
  * Spin Core PulseBlaster
* NI-DAQ card (PCIx 6363) for data acquisition and control
  * Edge counting from Excelitas SPCM for photon detection
  * Jena System's piezo actuator stage control
  * Mad City Labs piezo actuator stage control
* Newport Micrometers via serial connection

Additionally, several fully interfaced, Python applications are provided for 
standard and commonly used experiments:

* `qdlmove`: Customizable graphical interface for position control, reconfigurable 
  for mutltiple positioners.
* `qdlple`: Reconfigurable resonant excitation (photoluminescence excitation)
  spectroscopy. 
* `qdlscan`:  Reconfigurable 1-d and 2-d confocal scan imaging.
* `qdlscope`: Real-time oscilloscope readout from the SPCM via the digital input 
  terminal on the NI-DAQ board.

as well as some legacy applications from `qt3-utils`.

Applications are generally structured to be easily configured for different
setups (using supported hardware) via the use of YAML files.
Modifications to include additional hardware should also be relatively straightforward.
Finally, in the case where a custom one-off, experiment is required, many of the controllers 
and hardware interfaces can be utilized directly without the development of a GUI
or application.

### Intended usage
With the release of `v1.0.0` we are no longer actively developing features for the main 
`qdlutils` repository.
Bug fixes and modifications to existing applications may still be developed and pushed as 
needed, however large changes will not be actively developed (unless there is significant
need for such a feature).
Instead, users are expected to fork this repository and maintain/actively develop their
forks as needed for their own purposes.
In the event that specific features, changes, or bug fixes are of generic interest to multiple 
users, this repository may be merged/updated via a Pull Request.


## Setup

### Prerequisites

The utilities in this package depend on publicly available Python packages found
on PyPI and drivers built by National Instruments for DAQmx and
SpinCore for the PulseBlaster. These libraries must be installed separately.

* [National Instruments DAQmx](https://nidaqmx-python.readthedocs.io/en/latest/)
  * [driver downloads](http://www.ni.com/downloads/)
* [SpinCore's PulseBlaster](https://www.spincore.com/pulseblaster.html)
  * [spinAPI driver](http://www.spincore.com/support/spinapi/)

### Installation

Because this package is intended to be forked and customized for use in a
variety of experimental setups, we do not intend to release this package on PyPI.
Instead, users must clone `qdl-utils` (or their specific fork) onto their
own machine and install it locally.
Instructions for how to do this are provided below.

Note that Pull Requests (and commits to the `main` branch) on `qdl-utils` 
will generally be rejected.
Thus, it is strongly discouraged to install `qdl-utils` directly if you 
intend on tracking your changes with GitHub.
Instructions for creating a fork are provided below.


#### 0. Create your fork of the `qdl-utils` repository

Follow [these instructions to create a fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) 
via the GitHub web browser.
For QDL members, create the fork to be owned by the UW-Quantum-Defect-Lab GitHub organization
and name the fork appropriately as to be distinguishable for your project, e.g. `qdl-utils-diamond`
or `qdl-utils-magpi`.
For the purposes of this tutorial we will assume that the fork is named `my-qdl-utils-fork`.

Once the fork has been created on GitHub, move on to the next step.
Do not clone your fork yet; we will do this in the next steps.

If you wish to completely decouple from `qdl-utils` then you can follow [these
instructions to detach your fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/detaching-a-fork).
Note that this will prevent you from being able to Pull Request `qdl-utils` or
straightforwardly merge updates onto your repository.

#### 1. Create a development environment 

It is highly recommended that you utilize some form of virtual environment to
install your fork `my-qdl-utils-fork` (in this example).
It is assumed that you will use [Anaconda](https://docs.anaconda.com/anaconda/install/)
or its lightweight version [Miniconda](https://docs.anaconda.com/miniconda/).
If you are unfamiliar with `conda` please review [this tutorial](https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html).
For Windows users new to Anaconda, it is recommended to install Anaconda for only your user
and then utilize the provided Anaconda PowerShell Prompt terminal for the remainder
of this process.

Create a new virtual environment with Python 3.9. In this example we will name the
virtual environment `qdlutils`, but you can change it to something else if desired.
In a terminal configured to for `conda`, run

```
> conda create --name qdlutils python=3.9
```

to create the virtual environment and then activate it via

```
> conda activate qdlutils
```


#### 2. Clone your fork

Navigate (in the terminal) to the directory in which you would like to install
the full `qdl-utils` repository.
This includes not only the `qdlutils` package source code, but also examples, 
and any other files stored in the repository.
Note that you will often need to edit the source code so pick a directory which
you can easily access.

Once your present working directory is the desired location, clone your fork via

```
> git clone <URL of my-qdl-utils-fork>
```

You can get the URL for your fork from its GitHub page by clicking on the green 
"Code" button as shown in the following picture, then copying the URL:

![repo_url](https://github.com/user-attachments/assets/0396ff47-59e1-47fa-a7d9-053b81d58298)

For example, if we wanted to install the `qdl-utils` repo itself we could run
`git clone https://github.com/UW-Quantum-Defect-Lab/qdl-utils.git`.
Your URL will probably be something like `git clone https://github.com/UW-Quantum-Defect-Lab/my-qdl-utils-fork.git`.
Note that, for reasons explained above, cloning `qdl-utils` directly is not
recommended.


#### 3. Install the local repository in "editor" mode

Finally, move into the the newly created clone of your repository.
Assuming that the name of your fork is `my-qdl-utils-fork` we first move into 
the repository by

```
> cd my-qdl-utils-fork
```

and then install it locally in editor mode via

```
> pip install -e . 
```

Do not forget the `.`! 
This refers `pip` to the `pyproject.toml` file in the home directory
of the repository that does the installation.
The `-e` option ensures that any edits you make to the local repository 
are reflected in subsequent imports in Python scripts (without this you
would have to `pip` install after each edit).


Finally confirm that the installation worked correctly by launching the
Python interpreter and then importing the package:

```
> Python
Python 3.9 ...
>>> import qdlutils
>>>
```

#### 4. (Optional) Update Tk/Tcl

Upgrading Tcl/Tk via Anaconda overcomes some GUI bugs on Mac OS Sonoma

```
conda install 'tk>=8.6.13'
```

### Configuration
The base installation of `qdlutils` contains some basic configuration files in the form
of YAML files (`*.yaml`).
Within any of the `qdlapp` family applications (e.g. `qldscope`), the configuration file is
stored in the `qdlapp/config_files` directory (e.g. `qdlutils/qdlscope/config_files/*.yaml`).
Each application has a base configuration file `qdlapp_base.yaml` which contains the
default configuration for the hardware that is loaded by the application on startup.
For example, the `qdlscope_base.yaml` file reads

```
QDLSCOPE:
  ApplicationController:
    import_path : qdlutils.applications.qdlscope.application_controller
    class_name : ScopeController
    hardware :
      counter : Counter

  Counter:
    import_path : qdlutils.hardware.nidaq.counters.nidaqtimedratecounter
    class_name  : NidaqTimedRateCounter
    configure :
      daq_name : Dev1               # NI DAQ Device Name
      signal_terminal : PFI0        # DAQ Write channel
      clock_terminal :              # Digital input terminal for external clock
      clock_rate: 100000            # NI DAQ clock rate in Hz
      sample_time_in_seconds : 1    # Sampling time in seconds (updates via GUI)
      read_write_timeout : 10       # timeout in seconds for read/write operations
      signal_counter : ctr2         # NIDAQ counter to use for count
```

The header `QDLSCOPE` signifies that the YAML file corresponds to the `qdlscope` application.
When loading this file, the `qdlmove` application will read this file as a series of nested
dictionaries (demarcated but indentation).
The application then loads the hardware for the `Counter` using the class `class_name` defined 
in `import_path`, which is then configured using the `configure` dictionary.
Note that the structure of the YAML file for any given appliation will generally be different
as it depends on the design of the configuration file loader within each application.
Nevertheless, most configuration files are structured similarly.

Users should modify the YAML configuration files to to match the hardware configuration in 
their own systems.
Modifying the base configuration files is expected and will set the default behavior.
In some cases, the use of several different configurations (at different times) on the same
system might be desired (e.g. for switching between different counters).
All of the applications support the loading of YAML configuration files after startup,
however not all applications have this feature enabled by default.
In most cases this can be accomplished by some simple modificiation of the GUI and application
classes (simply copying functions from other applications should suffice).
Users may then create new YAML configuration files and save them in the `config_files` folder.

Additionally, users may find it convenient to modify the default settings for various GUI
elements within the applications (e.g. the scan range in `qdlscan`).
To do so, one should navigate to the `qdlapp/application_gui.py` script file and locate the
relevant GUI element, for example, to change the scan range in `qdlscan` one finds the lines

```
# in qdlscan/application_gui.py
tk.Label(scan_frame, text='Range (μm)').grid(row=row, column=0, padx=5, pady=2)
self.image_range_entry = tk.Entry(scan_frame, width=10)
self.image_range_entry.insert(0, 80)
self.image_range_entry.grid(row=row, column=1, padx=5, pady=2)
```

and then modify the line `self.image_range_entry.insert(0, 80)` changing the last argument from
`80` to whatever the desired value is.
A similar process can be achieved in all applications as desired.


## Using the software
If one intends to use multiple applications simultaneously it is recommended to run the applications
through the `qdlhome` application.
You can launch `qdlhome` via the `qdlutils` terminal command `qdlhome` or by navigating to 
`qdlutils/applications/qdlhome/main.py` and running it directly.
Note that `qdlhome` does not support the `qt3utils` legacy applications (although it would be possible
to set this up if desired).

Otherwise, single applications can be run directly from the terminal via commands installed with 
`qdlutils`.
The currently supported commands are:

```
qdlmove
qdlple
qdlscan
qdlscope
qt3scan
qt3scope
```

of which each open their respective applications.
Alternatively one can run the `main.py` file of the relevant application directly (or call 
its method `main()` in another script).

If a one-off experiment is desired then it is also possible to call the hardware classes
or even application controllers (e.g. in `qdlapp/application_controller.py`) on their own.
The `qdlutils` package already has some base experiments provided in `qdlutils.experiemnts`,
however these files are (in the current version), legacy code from `qt3utils`, and may
consequently require modification.
Experiments need not be created in the `qdlutils` package itself as all hardware classes
may be called from any location via standard imports.


## LICENSE

[BSD 3-Clause License](LICENSE)

Copyright (c) 2022, University of Washington

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

