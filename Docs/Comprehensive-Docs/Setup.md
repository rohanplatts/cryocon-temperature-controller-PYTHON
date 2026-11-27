# Installation and Spyder setup

This tutorial assumes you are using a Windows laboratory computer. You do not need previous experience with Python environments. Do not start the heater while installing or testing the software.

## 1. What you need

- A CryoCon Model 22C connected through its serial interface (the supplied script uses a Windows COM port).
- A supported digital multimeter (DMM) connected through VISA; the original configuration uses USB and four-wire resistance.
- Anaconda or another Conda distribution, and Spyder. If they are not installed, ask the laboratory administrator or follow the [Spyder installation guide](https://docs.spyder-ide.org/current/installation.html).
- A working VISA runtime and necessary USB/serial drivers. The laboratory may already have NI-VISA or Keysight IO Libraries Suite installed. Ask the lab administrator before installing drivers or changing driver settings.
- Permission to operate the apparatus and write to the intended data folder.

The CryoCon and DMM are separate instruments. Python communicates with each through its own connection.

## 2. Download the code

On the [repository page](https://github.com/rohanplatts/cryocon-temperature-controller-PYTHON), click **Code → Download ZIP**, then extract the ZIP into a folder you can access. You do not need Git for this. Alternatively, if Git is installed:

```bat
git clone https://github.com/rohanplatts/cryocon-temperature-controller-PYTHON.git
cd cryocon-temperature-controller-PYTHON
```

The folder should contain the **current** [cryo-control.py](../../cryo-control.py) and [cryocon-env.yml](../../cryocon-env.yml). The Python file is the experiment program; the YAML lists its dependencies. Keep both files together. If your repository download still contains the older `cryo-control.py.py`, place the newer `cryo-control.py` beside the YAML, and open **that** file in Spyder. Do not accidentally run the earlier single-setpoint version.

## 3. Check your Spyder version

Open Spyder (for example, from Anaconda Navigator) and click **Help → About Spyder**. Write down its version. Close any running experiment normally and confirm the controller is stopped before restarting a console or changing software.

Spyder is the editor; its IPython console is a separate Python process. A Conda environment contains a particular Python installation and packages. The package called `spyder-kernels` links that environment to Spyder. Its version must be compatible with the version of the editor.

The supplied YAML uses Python 3.10 and pins `spyder-kernels=3.1.3`, intended for Spyder 6.1.3. Spyder 6.1.3 accepts kernel versions from 3.1.3 up to, but not including, 3.2.0. Other versions may require different kernels.

You do **not** need to install the full Spyder application inside the experiment environment.

## 4. Create the environment

Open **Anaconda Prompt** from the Windows Start menu. This is not the console inside Spyder. Navigate to the extracted folder. For example, if it is stored at `T:\cryocon`:

```bat
cd /d "T:\cryocon"
dir
conda env create -f cryocon-env.yml
conda activate cryocon-env
```

Replace the example path with your actual folder location. In PowerShell use `cd "T:\cryocon"` instead of `cd /d`. The `dir` command should show the YAML before you run Conda.

If the environment already exists, use `conda activate cryocon-env` rather than creating it again. To intentionally apply updated dependencies, `conda env update -n cryocon-env -f cryocon-env.yml` updates it; note that this reapplies the YAML's kernel pin.

Test the installation:

```bat
python -c "import sys, numpy, matplotlib, pyvisa, cryocon_22c_controller, spyder_kernels; print(sys.executable); print(spyder_kernels.__version__)"
```

If an import fails, read the named missing package or traceback. Do not reinstall Anaconda or change its base environment as your first response.

### If your Spyder version is different

First try the environment in Spyder (step 5). If Spyder displays a kernel compatibility error, it normally provides the version range and installation command it needs. Copy the **Conda** command into Anaconda Prompt after activating `cryocon-env`. For example, the range for Spyder 6.1.3 is:

```bat
conda activate cryocon-env
conda install -c conda-forge "spyder-kernels>=3.1.3,<3.2.0"
```

This is an example for 6.1.3 only. For a different release use its actual requested range, not this example. A substantially different Spyder version may require an updated Python environment. If Conda cannot resolve it, consult the lab administrator or use a separate compatible environment; do not force an incompatible installation. If maintaining a local copy of the YAML for that version, change its kernel pin too.

## 5. Open the correct Spyder console

1. Launch your usual Spyder.
2. Open **Consoles → New console in environment** and choose **cryocon-env**. You may alternatively find this option by right-clicking a console tab.
3. Wait for the new IPython prompt (such as `In [1]:`). In that console type:

   ```python
   import sys
   print(sys.executable)
   ```

The path should point into your experiment environment, normally ending in `envs\cryocon-env\python.exe`.

If your environment is not listed, open **Tools → Preferences → Python interpreter**, select a custom interpreter and browse to its `python.exe`. Find its exact path in Anaconda Prompt:

```bat
conda activate cryocon-env
python -c "import sys; print(sys.executable)"
```

Apply the preference and open a new console (or restart an idle kernel). Repeat the check. Older Spyder releases may have slightly different menu labels; use the Python interpreter preference if the environment submenu is unavailable.

Do not type `conda activate` in the Spyder IPython console: it cannot replace that console's running Python interpreter.

### If the console never starts

A new console should eventually display an input prompt, not remain stuck for several minutes. While no experiment is running, close/restart Spyder and test the imports in Anaconda Prompt (step 4). Compare a base console with the experiment console. Confirm the kernel version matches and inspect any startup traceback. If both consoles fail, consult Spyder's troubleshooting guide. Never force-terminate a kernel while it is controlling a heater without first stopping the controller physically.

## 6. Enable live plots

In Spyder, go to **Tools → Preferences → IPython Console → Graphics**. Select **Qt** as the graphics backend, apply and restart the idle kernel. In the new console:

```python
import matplotlib.pyplot as plt
print(plt.get_backend())
```

An interactive backend such as `QtAgg` is desired, not Inline. The script attempts to switch from Inline itself. If Qt imports fail, the environment may also need a Qt binding (not explicitly listed in the YAML). With the experiment environment active, ask Conda to install one, for example:

```bat
conda install -c conda-forge pyqt
```

Restart the console and check again. Do not confuse the static Plots pane with the interactive plot window.

## 7. Identify the actual instrument addresses

The addresses in the script are examples from one particular laboratory; they are not universal.

**CryoCon:** In Windows, open Device Manager and expand **Ports (COM & LPT)**. Identify the serial port belonging to the CryoCon or its USB-to-serial adapter (check the cable and lab records). If it is COM5 instead of COM3, set `CRYO_PORT = "COM5"`. Do not guess or unplug active equipment.

**DMM:** In the correct Spyder console, while the instruments are not in use by another program, run:

```python
import pyvisa
rm = pyvisa.ResourceManager()
try:
    print(rm.list_resources())
finally:
    rm.close()
```

A USB resource may begin `USB0::` and end `::INSTR`. Copy the complete resource belonging to your DMM into `DMM_ADDRESS`, including its serial number. A different interface may have a different format. Confirm its identity against the device label or VISA utility. Do not copy the CryoCon's COM port into the DMM address.

If no VISA library is found, or the expected device is missing, check cables, drivers, the installed VISA vendor utility and whether another process holds the connection. `pyvisa` is the Python interface; installing it alone does not necessarily install the hardware runtime. Use the lab's supported driver rather than changing backends blindly.

## 8. Configure the script and test without heating

Open `cryo-control.py` in Spyder with **File → Open**. Edit the settings at its top, save it, and ensure the selected console is the experiment environment. Do not alter the instrument-communication blocks as part of basic setup.

```python
# Replace these settings in the script (example values only).
MATERIAL = "copper"
DATA_DIR = Path(r"C:\LabData")
CRYO_PORT = "COM5"
DMM_ADDRESS = "YOUR_ACTUAL_VISA_RESOURCE"
ENABLE_CONTROL = False
```

Use an existing or writable data location. The `r` before a Windows path prevents backslashes being interpreted as escape sequences. The program creates the output folder if it can.

The program now has an `EXPERIMENTS` list, not a single global `SETPOINT_K` or `RAMP_RATE`. Use the current `cryo-control.py`, not the older `cryo-control.py.py`. Each dictionary specifies one phase:

```python
EXPERIMENTS = [
    {
        "name": "cool-down",     # Becomes part of the CSV filename
        "channel": "A",         # Temperature sensor used for feedback
        "heater_loop": 1,       # Powered heater output 1 or 2
        "mode": "RAMPP",        # "RAMPP" or "PID"
        "setpoint_k": 270.0,    # Temperature target in K
        "ramp_rate": 0.5,       # Programmed K/min; used for RAMPP
    },
    {
        "name": "warm-up",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 300.0,
        "ramp_rate": 0.5,
    },
]

TARGET_TOLERANCE_K = 0.1  # +/- K, illustrative
HOLD_SECONDS = 60         # Seconds within range
```

These are the current file's example settings, **not validated conditions for your instrument**. Add or remove dictionary entries to add or remove phases. With a single dictionary, only one phase runs. The script automatically changes phases *only after* the measured feedback temperature stays within the target band for the hold duration; if the temperature leaves the band, its timer resets. There is no maximum number of minutes: a phase can continue indefinitely if it cannot reach/stabilize at the target. Cooling needs a real heat-removal mechanism, not just a lower heater setpoint. See the [usage guide](usage.md) before attempting automatic control.

Before running, verify with the operator that both temperature inputs report kelvin, their calibration and placement are known, and the DMM's four-wire leads and measurement current are appropriate. The instrument must initially have control disengaged, even in measurement-only mode. The script still validates all phase settings and configures the DMM when control is disabled.

Press **F5** (Run file); if Spyder asks where to run it, choose the current console in the correct environment. Check that temperatures and resistance appear in the console, that the graph updates, and that the CSV gains rows. After a phase completes or you interrupt a run, check for a PNG with the same name as the CSV. With `ENABLE_CONTROL = False`, the phase completion test still runs; if room temperature is nowhere near the example target, **the test will continue indefinitely**. There is no phase time limit; an unattainable target requires the operator to intervene. For a quick acquisition check, interrupt the test yourself. Interrupt normally using Ctrl+C in the console or Spyder's interrupt action. This cancels all remaining phases. Confirm the controller remains disengaged. Closing the plot alone is not a reliable stop.

Only enable heating after completing the pre-run checks in the [usage guide](usage.md).

## References and further help

- [Spyder: using the IPython console](https://docs.spyder-ide.org/current/panes/ipythonconsole.html)
- [Spyder: kernel troubleshooting](https://docs.spyder-ide.org/current/troubleshooting/common-illnesses.html)
- [Spyder 6.1.3 package requirements](https://github.com/spyder-ide/spyder/issues/25670)
- [PyVISA: communicating with instruments](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html)
- [CryoCon Python driver](https://github.com/bicarlsen/cryocon-22c-controller)

[Quick start](../quick-start.md) · [Code explanation](code-explanation.md) · [Usage guide](usage.md)
