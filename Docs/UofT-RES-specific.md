PHY424 — CryoCon Python Setup

This guide is specific to the Resistivity in metals (RES) experiment station of  PHY424 / PHY426 / etc... laboratory computers. [01 Initial Setup](#-01-Initial-Setup) Explains how to set it up initially and how to use it, and some common problems. [02 Daily Use](#-02-Daily-Use) gives the concise commands to run every new lab session you wish to use the code. 

# 01 Initial Setup

## 1. Locate the files

The following files should already be available on the `T` drive:

- `T:\cryocon\cryocon-env.yml`
- `T:\cryocon\cryo-control.py`

If they are not, create the `T:\cryocon` folder and download [cryo-control.py](https://github.com/rohanplatts/cryocon-temperature-controller-PYTHON/blob/main/cryo-control.py) and [cryocon-env.yml](https://github.com/rohanplatts/cryocon-temperature-controller-PYTHON/blob/main/cryocon-env.yml) files to it, from this github repository. It is important that these files are saved to the `T` drive (or any external drive) as this drive is not wiped. 

## 2. Install the python environment

1. Press the Windows key, then search and open **Anaconda Navigator**.
2. Launch **Anaconda PowerShell Prompt**.
3. Enter the following commands, one at a time:

```powershell
cd T:\cryocon
conda env create -f cryocon-env.yml
```

Wait for the installation to finish.

## 3.  Open Spyder

1. In Anaconda Navigator, launch **Spyder**.
2. Select **New Console** → **New Console in Environment**.
3. Choose cryocon-env.
4. Close the original console so that only the cryocon-env console remains.

## 4. Open the Python script

In Spyder, select **File** → **Open**, then navigate to:

`T:\cryocon\cryo-control.py`

## 5. Program your temperature experiments

At the top of the script, find the `EXPERIMENTS` list. This determines which temperature sweeps the program performs, and in what order. All of the parameters are within the same section you found this list in, but the two remaining important global variables to learn are `HOLD_SECONDS` and `TARGET_TOLERANCE_K`. I will explain these below. 

Initially, it will look like this:

```python
EXPERIMENTS = [
    {
        "name": "cool-down",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 270.0,
        "ramp_rate": 0.5,
    },
    {
        "name": "warm-up",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 300.0,
        "ramp_rate": 1,
    },
]
```

What this means:

1. The controller attempts to ramp to the setpoint temperature (`setpoint_k`) 270 K at 0.5 K/min (`ramp-rate`), using temperature sensor A (`channel`) and heater loop 1 (`heater_loop`). 
2. Once the measured temperature satisfies:

`setpoint_k` - `TARGET_TOLERANCE_K` ≤ temperature measured at `channel` ≤ `setpoint_k` + `TARGET_TOLERANCE_K`

for `HOLD_SECONDS`, that experiment finishes.

4. The controller then attempts to ramp to 300 K at 1 K/min, again waiting for the latter stabilization.
5. The script then saves the plots, finishes editting the `.csv`'s and ends. 

Each experiment saves its own CSV data and PNG plot.

To change the experiment sequence, simply edit, add or remove dictionaries to the `EXPERIMENTS` list.

For example, suppose you want to run the following experiments, in the following order:

1. Ramp to 50 K at 2 K/min, using sensor A, then stabilize.
2. Ramp to 10 K at 0.5 K/min, using sensor B, then stabilize.
3. Ramp to 300 K at 1 K/min, using sensor A, then stabilize.

Then, the `EXPERIMENTS` list would be: 

```python
EXPERIMENTS = [
    {
        "name": "cool-down-1",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 50.0,
        "ramp_rate": 2.0,
    },
    {
        "name": "cool-down-2",
        "channel": "B",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 10.0,
        "ramp_rate": 0.5,
    },
    {
        "name": "warm-up",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 300.0,
        "ramp_rate": 1.0,
    },
]
```

All three experiments are recorded separately and run automatically in order, provided the apparatus can reach each target.

Suppose also you didnt know how cold the cooler could go, but didn't want the experiment to get stuck trying to get to 10 K, then you might adjust the `TARGET_TOLERANCE_K` and `HOLD_SECONDS` parameters to be: 

```python
TARGET_TOLERANCE_K = 5
HOLD_SECONDS = 660 #  = 60 (convert to seconds) * 1/ramp_rate (which is 2) * TARGET_TOLERANCE_K (5) + buffer (a minute) 
```
That way, if the cooler could actually only make it to 14 K, then the experiment wouldn't get stuck trying to reach 10 K ( since $ 14 < 10 + 5 =  `setpoint` + `TAREGT_TOLERANCE_K`), and if it actually could reach 10 K, it has `HOLD_SECONDS = 660` seconds to get there, which, if our ramp rate is less than our maximum cooling rate, is plenty of time to get there (should only need 1 / ramp_rate * TARET_TOLERANCE_K minutes to get there). Plus, you can read off the minimum temperature from the resulting figure, anyway. 

Understanding the parameters:

- `channel`: Temperature sensor (`A` or `B`) used as feedback for heater control.
- `heater_loop`: Physical heater output (`1` or `2`).
- `setpoint_k`: Target temperature in Kelvin.
- `ramp_rate`: Programmed setpoint ramp rate in K/min.
- `name`: Label used to identify the saved data.

## Important notes on cooling and temperature control

### 1. Cooling requires the cryocooler.

The CryoCon controls heaters only. For any experiment requiring cooling, the cryocooler must be running.

The heater can slow the cooling produced by the cryocooler, but it cannot accelerate cooling beyond the system’s natural cooling capability. To allow cooling at the system’s natural rate, you can select a sufficiently large ramp rate. Do not assume that increasing the setting makes the system cool faster.

### 2. Make sure your target temperature is achievable.

> **Note:** There is a third important parameter, `MAX_SAFE_TEMP_K`. If the temperature measurement ever exceeds this temperature, heating will stop and the script will halt. You may want to adjust this if needed. 

as mentioned before, if the cryocooler can only reach a temperature greater than your setpoint, the  experiment will never finish, and succeeding ones never start. A larger tolerance may allow an otherwise unreachable setpoint to satisfy the completion condition. However, it may also cause the experiment to finish before the lowest achievable temperature is reached. Therefore, if the cryocooler’s minimum temperature is unknown, you can either determine it, or use a large tolerance and large hold time to ensure it reaches the minima, and eventually passes onto the next experiment.

### 3. Choose the feedback sensor carefully.

Ideally, use a temperature sensor that responds promptly to the selected heater.

For our apparatus, this is generally heater loop 1 and sensor A.

You can also use sensor B. However, because of the thermal lag between heater loop 1 and sensor B, in effort to maintain a particular ramp rate, the controller may overshoot or oscillate periodically as it tries to keep dT/dt at the fixed ramp rate. 

A slower ramp rate in this case may reduce this effect by allowing more time for thermal equilibrium.

## Recommended initial test

Before running a long experiment, you can check that the system behaves as expected.

With the cryocooler operating and the temperature limits verified, try the following two-phase sequence:

EXPERIMENTS = [
    {
        "name": "cool-down-test",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 280.0,
        "ramp_rate": 1.0,
    },
    {
        "name": "warm-up-test",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 290.0,
        "ramp_rate": 2.0,
    },
]

Use example settings such as:

```python
TARGET_TOLERANCE_K = 0.2
HOLD_SECONDS = 60
```

These are example test settings; confirm they are appropriate for the apparatus before starting.

The program should:

1. Cool toward 280 K at a programmed rate of 1 K/min.
2. Remain within 279.8–280.2 K for 60 seconds.
3. Automatically begin warming toward 290 K at 2 K/min.
4. Stabilize at 290 K, then finish.

Check the live plots for sensible behaviour.

## 6. Run the experiment

1. Save the edited Python script.
2. Ensure the `cryocon-env` console is selected.
3. Press **F5** to run.
4. Monitor both temperatures and the CryoCon controller.

The sequence advances automatically after each stabilization period. Use **Ctrl+C** to interrupt the entire sequence, and confirm that temperature control is disengaged on the physical controller.

# 02 Daily use 

With the appropriate files saved on the `T` Drive in the `cryocon` folder, one will have to set up the conda environment each new time they log into the computer. Unless of course the T-drive has enough space for you to download the conda environment to it. Hence, your daily workflow will be: 

1. open anaconda navigator
2. open anaconda powershell prompt
3. `cd T:\cryocon`
4. `conda env create -f cryocon-env.yml -y`
5. open the python file in spyder
6. create a console in cryocon-env
7. done.

