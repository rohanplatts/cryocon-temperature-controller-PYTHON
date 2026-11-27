PHY424 — CryoCon Python Setup

This guide is specific to the PHY424 laboratory computers.

1. Locate the files

The following files should already be available on the T: drive:

* T:\cryocon\cryocon-env.yml
* T:\cryocon\cryo-controller.py

2. Install the Python environment

1. Press the Windows key and open Anaconda Navigator.
2. Launch Anaconda PowerShell Prompt.
3. Enter the following commands, one at a time:

cd T:\cryocon
conda env create -f cryocon-env.yml

Wait for the installation to finish.

Note: If the environment already exists, skip this step.

3. Open Spyder

1. In Anaconda Navigator, launch Spyder.
2. Select New Console → New Console in Environment.
3. Choose cryocon-env.
4. Close the original console so that only the cryocon-env console remains.

4. Open the Python script

In Spyder, select File → Open, then navigate to:

T:\cryocon\cryo-controller.py

5. Program your temperature experiments

At the top of the script, find the EXPERIMENTS list. This determines which temperature sweeps the program performs, and in what order.

Initially, it will look like this:

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
        "ramp_rate": 0.5,
    },
]

What this means:

1. The controller attempts to ramp to 270 K at 0.5 K/min, using temperature sensor A and heater loop 1.
2. Once the measured temperature remains within the specified tolerance for HOLD_SECONDS, that experiment finishes.
3. The controller then attempts to ramp to 300 K at 0.5 K/min, again waiting for stabilization.

Each experiment saves its own CSV data and PNG plot.

To change the experiment sequence, simply edit, add or remove dictionaries.

For example, suppose you want three experiments:

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

This programs the following sequence:

1. Ramp to 50 K at 2 K/min, using sensor A, then stabilize.
2. Ramp to 10 K at 0.5 K/min, using sensor B, then stabilize.
3. Ramp to 300 K at 1 K/min, using sensor A, then stabilize.

All three experiments are recorded separately and run automatically in order, provided the apparatus can reach each target.

Understanding the parameters:

* channel: Temperature sensor (A or B) used as feedback for heater control.
* heater_loop: Physical heater output (1 or 2).
* setpoint_k: Target temperature in Kelvin.
* ramp_rate: Programmed setpoint ramp rate in K/min.
* name: Label used to identify the saved data.

Important notes on cooling and temperature control

1. Cooling requires the cryocooler.

The CryoCon controls heaters only. For any experiment requiring cooling, the cryocooler must be running.

The heater can slow the cooling produced by the cryocooler, but it cannot accelerate cooling beyond the system’s natural cooling capability. To allow cooling at the system’s natural rate, you can select a sufficiently large ramp rate. Do not assume that increasing the setting makes the system cool faster.

2. Make sure your target temperature is achievable.

Suppose you program a cooldown to 7 K, followed by a warmup.

If the cryocooler can only reach 9 K, the program will never complete the first experiment under a narrow temperature tolerance. Consequently, the warmup will never begin.

Two parameters control when an experiment finishes:

* TARGET_TOLERANCE_K: The permitted temperature deviation from the target, in Kelvin.
* HOLD_SECONDS: The number of consecutive seconds the measured feedback temperature must remain within that range.

For example:

TARGET_TOLERANCE_K = 0.2
HOLD_SECONDS = 60

For a target of 10 K, this means the measured feedback temperature must remain between 9.8 K and 10.2 K for 60 seconds before the next experiment begins.

A larger tolerance may allow an otherwise unreachable setpoint to satisfy the completion condition. However, it may also cause the experiment to finish before the lowest achievable temperature is reached. Therefore, if the cryocooler’s minimum temperature is unknown, you can either determine it, or use a large tolerance and large hold time to ensure it reaches the minima, and eventually passes onto the next experiment.

3. Choose the feedback sensor carefully.

Ideally, use a temperature sensor that responds promptly to the selected heater.

For our apparatus, this is generally heater loop 1 and sensor A.

You can also use sensor B. However, because of the thermal lag between heater loop 1 and sensor B, in effort to maintain a particular rank rate, the controller may overshoot or oscillate periodically as it tries to control dT/dt.

A slower ramp rate in this case may reduce this effect by allowing more time for thermal equilibrium.

Recommended initial test

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

For example, use:

TARGET_TOLERANCE_K = 0.2
HOLD_SECONDS = 60

These are example test settings; confirm they are appropriate for the apparatus before starting.

The program should:

1. Cool toward 280 K at a programmed rate of 1 K/min.
2. Remain within 279.8–280.2 K for 60 seconds.
3. Automatically begin warming toward 290 K at 2 K/min.
4. Stabilize at 290 K, then finish.

Check the live plots for sensible behaviour, particularly whether the measured temperature follows the intended ramp without excessive oscillation.

6. Run the experiment

1. Save the edited Python script.
2. Ensure the cryocon-env console is selected.
3. Press F5 to run.
4. Monitor both temperatures and the CryoCon controller.

The sequence advances automatically after each stabilization period. Use Ctrl+C to interrupt the entire sequence, and confirm that temperature control is disengaged on the physical controller.