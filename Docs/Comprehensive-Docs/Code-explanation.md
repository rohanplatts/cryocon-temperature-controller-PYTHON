# How the Code Was Developed, and How to Modify It

This document explains the development of the CryoCon temperature-control script, with the aim of helping future PHY424 students understand and extend it themselves.

The program began as a script for measuring resistance and temperature. Temperature control was subsequently introduced, followed by support for running several experiments automatically.

The important ideas are **communicating directly with instruments, constructing SCPI commands, controlling the order of operations, and organizing the code into reusable functions**.

Any modifications can be submitted as pull requests to this github page, or, you can fork it of course. 

## 1. The original measurement script

The starting point was a Python program that repeatedly measured:

- Temperature from CryoCon sensor A.
- Temperature from CryoCon sensor B.
- Four-wire resistance from a digital multimeter.
- Elapsed time.

The data were written to a CSV file and displayed in a live Matplotlib graph.

Four packages provide most of this functionality:

```python
import cryocon_22c_controller as cc
import pyvisa
import matplotlib.pyplot as plt
import csv
```

| Package | Purpose |
|---|---|
| `cryocon_22c_controller` | Communicates with the CryoCon Model 22C |
| `pyvisa` | Communicates with the digital multimeter |
| `matplotlib` | Produces the live resistance–temperature plot |
| `csv` | Writes experimental measurements to a file |

The CryoCon connection is established with:

```python
cryo = cc.CryoconController(port="COM3", backend="")
cryo.connect()
```

Once connected, temperature measurements are straightforward:

```python
temp_a = float(cryo.temperature("a"))
temp_b = float(cryo.temperature("b"))
```

Similarly, the multimeter is accessed through PyVISA:

```python
rm = pyvisa.ResourceManager()
dmm = rm.open_resource(DMM_ADDRESS)

dmm.write("CONF:FRES")
resistance = float(dmm.query("READ?").strip())
```

`CONF:FRES` configures four-wire resistance measurement, while `READ?` requests a reading.

Notice that the program communicates with the two instruments through different libraries. The measurement loop simply combines their readings into one dataset.

The next challenge was to make Python **change the CryoCon's temperature setpoint and heater configuration**, rather than merely observe them.

## 2. the Key: controlling the CryoCon using SCPI

The `cryocon_22c_controller` package provides convenient methods for common tasks, including reading temperatures and enabling control.

However, not every configurable parameter of the CryoCon is exposed through a dedicated Python method.

**The central insight was that we are not restricted to the methods explicitly provided by the Python library.**

The CryoCon understands a command language called **SCPI** (*Standard Commands for Programmable Instruments*).

The Python driver communicates through `easy-scpi` and provides a method:

```python
cryo.query("COMMAND")
```

This allows us to send supported CryoCon command strings directly.

The Python package handles the instrument connection; the CryoCon interprets the commands.

### Finding commands

The starting point for adding new functionality is the [CryoCon Model 22C User's Guide](https://file-storage.github.io/manuals/cryocon_22c_user_manual.pdf), particularly its remote-operation section.

For example, the following controller parameters are useful:

| Parameter | SCPI keyword |
|---|---|
| Control loop | `LOOP` |
| Feedback temperature sensor | `SOURCE` |
| Temperature setpoint | `SETP` |
| Setpoint ramp rate | `RATE` |
| Control mode | `TYPE` |
| Maximum setpoint | `MAXSET` |

A SCPI command follows a structure such as:

```SCPI
LOOP 1:SOURCE A
```

This assigns sensor A as the feedback source for control loop 1.

Likewise:

```SCPI
LOOP 1:RATE 0.5
```

sets the programmed ramp rate for loop 1 to 0.5 K/min.

To send these commands from Python:

```python
cryo.query("LOOP 1:SOURCE A")
cryo.query("LOOP 1:RATE 0.5")
```

The program usually uses **f-strings** instead of hard-coding the values:

```python
loop = 1
channel = "A"
rate = 0.5

cryo.query(f"LOOP {loop}:SOURCE {channel}")
cryo.query(f"LOOP {loop}:RATE {rate}")
```

This is important for generalisation.

### Reading parameters back

Appending `?` to a supported SCPI parameter generally requests its current value.

For example:

```python
source = cryo.query("LOOP 1:SOURCE?")
rate = cryo.query("LOOP 1:RATE?")
```

The distinction is:

- `LOOP 1:RATE 0.5` changes a setting.
- `LOOP 1:RATE?` reads a setting.

**Whenever adding a new control command, read the parameter back where possible.** Sending a command without receiving an error does not necessarily prove that the instrument accepted the intended value.

Instrument responses are often strings rather than Python numbers. For example, a temperature limit might be returned as `"300.000000K"`.

The script handles this by removing the known unit suffix before conversion:

```python
max_setpoint = float(
    cryo.query(f"LOOP {loop}:MAXSET?")
    .strip()
    .removesuffix("K")
)
```

When adding another command, check the manual for its response format, permitted values and units.

## 3. Adding temperature control

Having established how to send commands, the next task was to configure the heater correctly.

The CryoCon supports several control modes:

| Mode | Function |
|---|---|
| `OFF` | Disable the loop |
| `PID` | Standard PID temperature regulation |
| `RAMPP` | PID control with a ramping setpoint |
| `MAN` | Manually specified output |
| `TABLE` | PID using stored tuning parameters |
| `RAMPT` | Ramping using stored PID parameters |

The current script supports `PID` and `RAMPP`.

These mode names come from the instrument's command language, so their spelling matters.

### Why command order matters

In `RAMPP` mode, we want the controller to move its setpoint gradually from the current temperature toward a target.

If the final setpoint is applied without correctly initializing the ramp, the controller may not behave as intended.

The script therefore uses the following sequence:

1. Select the heater loop and feedback sensor.
2. Select `RAMPP` mode.
3. Configure the ramp rate.
4. Set the initial setpoint to the measured feedback temperature.
5. Enable temperature control.
6. Send the final target setpoint.

The essential code is:

```python
cryo.query(f"LOOP {loop}:SOURCE {channel.upper()}")
cryo.query(f"LOOP {loop}:TYPE {mode}")

if mode == "RAMPP":
    cryo.query(f"LOOP {loop}:RATE {RAMP_RATE}")

    initial_temp = float(cryo.temperature(channel))
    cryo.query(f"LOOP {loop}:SETP {initial_temp}")
else:
    cryo.query(f"LOOP {loop}:SETP {SETPOINT_K}")

cryo.enable()

if mode == "RAMPP":
    cryo.query(f"LOOP {loop}:SETP {SETPOINT_K}")
```

This is only the central command sequence. The actual program also performs validation, read-back checks and heater-loop management.

In `PID` mode, the final setpoint is applied directly; no programmed setpoint ramp is required.

### Feedback sensor selection

The `SOURCE` parameter specifies which sensor the CryoCon uses for feedback.

This matters because the sensor closest to the heater may respond significantly faster than one attached to the sample.

For our apparatus, sensor A generally responds more quickly to heater loop 1 than sensor B.

Using a poorly coupled feedback sensor can introduce overshoot or oscillations. The controller responds to the delayed sensor measurement, potentially applying too much or too little heat.

This is why **the feedback sensor and ramp rate should be chosen with the physical arrangement in mind**.

Also remember that the controller regulates heater power. Cooling requires a separate cryocooler; Python cannot make the apparatus cool faster than its cooling system permits.

## 4. From one experiment to multiple experiments

The original temperature-control version was designed around one set of parameters:

```python
CONTROL_CHANNEL = "A"
HEATER_LOOP = 1
CONTROL_MODE = "RAMPP"
SETPOINT_K = 270
RAMP_RATE = 0.5
```

Once that experiment finished, running another required changing the settings and executing the script again. This was made reusable through the following: 

### Step 1: Put the original program inside a function

Most of the original program was preserved, but placed inside:

```python
def run_experiment(experiment):
```

The argument `experiment` is a Python dictionary containing the settings for one phase.

At the beginning of the function, the dictionary values are assigned to the variables used throughout the existing program:

```python
name = experiment["name"]
CONTROL_CHANNEL = experiment["channel"]
HEATER_LOOP = experiment["heater_loop"]
CONTROL_MODE = experiment["mode"]
SETPOINT_K = experiment["setpoint_k"]
RAMP_RATE = experiment["ramp_rate"]
```

This approach minimizes changes to the original measurement code.

Rather than rewriting instrument commands to use dictionary lookups everywhere, the program keeps the original variable names inside the function.

### Step 2: Define a sequence

The settings for multiple phases are stored in a list:

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
        "ramp_rate": 1.0,
    },
]
```

Each dictionary represents one experiment.

### Step 3: Call the function repeatedly

At the end of the script:

```python
for experiment in EXPERIMENTS:
    run_experiment(experiment)
```

Python takes the first dictionary, passes it to `run_experiment()`, waits for that function to finish, and then proceeds to the next dictionary.

Each function call also creates its own timestamped filename and initializes fresh measurement arrays.

## 5. Implementing automatic experiment completion

Making experiments run sequentially introduced another problem:

**How does the program know when one experiment has finished?**

A fixed duration is unsuitable because the apparatus may reach different temperatures at different rates.

Instead, the script uses a temperature tolerance and a stabilization time.

The completion test is:

```python
controlled_temp = temp_a if channel == "a" else temp_b

if abs(controlled_temp - SETPOINT_K) <= TARGET_TOLERANCE_K:
    if stable_since is None:
        stable_since = time.monotonic()

    if time.monotonic() - stable_since >= HOLD_SECONDS:
        break
else:
    stable_since = None
```

The logic is:

1. Read the temperature from the selected feedback sensor.
2. Check whether it is sufficiently close to the target.
3. If so, start or continue the stabilization timer.
4. If the temperature leaves the permitted range, reset the timer.
5. Once the required time has elapsed continuously within the range, exit the measurement loop.

The `break` statement exits the `while True` measurement loop. The function then performs cleanup and returns to the outer `for` loop, which begins the next phase.

### Why use `time.monotonic()`?

`time.monotonic()` is intended for measuring elapsed time. it is not affected by the computer's clock being adjusted.

### How to modify the completion condition

Suppose a future experiment should finish only when **both temperature sensors** are within tolerance. (a very fair extension I might add).

The condition could be replaced with:

```python
within_tolerance = (
    abs(temp_a - SETPOINT_K) <= TARGET_TOLERANCE_K
    and
    abs(temp_b - SETPOINT_K) <= TARGET_TOLERANCE_K
)
```

The existing hold-timer logic could then use `if within_tolerance:`.

## 6. Recording and plotting measurements

The measurement loop retains most of the original data-acquisition code.

### Obtaining measurements

Each cycle reads:

```python
temp_a = float(cryo.temperature("a"))
temp_b = float(cryo.temperature("b"))
resistance = float(dmm.query("READ?").strip())
```

The script also calculates estimated uncertainties:

```python
u_a = 0.00005 * abs(temp_a) + 0.00008
u_b = 0.00005 * abs(temp_b) + 0.00008
u_r = 0.00012 * abs(resistance) + 4e-10
```

These formulas are inherited from the measurement code and should be verified against instrument specifications for quantitative uncertainty analysis.

### Writing CSV files

The `csv` module creates the file and writes its column headings.

Inside the measurement loop, the program adds a row:

```python
writer.writerow([
    elapsed, temp_a, temp_b, resistance,
    u_a, u_b, u_r
])

file.flush()
```

The `file.flush()` call asks Python to write buffered data promptly rather than waiting for the file to close.

This reduces the amount of data that may be lost if a run is interrupted.

### Updating the live plot

The program initially creates two empty plotted series:

```python
line_a, = ax.plot([], [], ".", label="Channel A")
line_b, = ax.plot([], [], ".", label="Channel B")
```

As measurements accumulate, it updates their existing data:

```python
r = np.abs(resistances)

line_a.set_data(temperature_a, r)
line_b.set_data(temperature_b, r)

ax.relim()
ax.autoscale_view()

fig.canvas.draw()
fig.canvas.flush_events()
```

This is more efficient than repeatedly creating an entirely new graph.

Notice that the graph plots the **absolute value** of resistance, whereas the CSV retains the signed measurement.

### Saving the plot

A PNG can be saved alongside the CSV using:

```python
if "fig" in locals() and csv_path.exists():
    fig.savefig(
        csv_path.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight"
    )
```

This belongs in the cleanup section if automatic plot export is desired.

`with_suffix(".png")` reuses the CSV filename but replaces its extension.

## 7. Cleanup and error handling

Laboratory programs must handle interruptions differently from ordinary data-processing scripts.

A failure while controlling a heater can leave equipment in an unsafe state.

For this reason, the script uses Python's `try`, `except` and `finally` structure.

The important property of `finally` is that its code is attempted whether the experiment finishes normally or raises an ordinary exception.

The cleanup logic attempts to:

1. Disengage CryoCon temperature control.
2. Verify that control is no longer enabled.
3. Restore previously modified control-loop modes when safe.
4. Close the DMM connection.
5. Disconnect the CryoCon.
6. Close the VISA resource manager.

The script tracks whether control was attempted and which other loop modes were changed. If heater shutdown cannot be confirmed, it raises an error rather than starting another experiment.

A `KeyboardInterrupt` is also re-raised so Ctrl+C cancels the entire sequence.

## 8. How to extend the script yourself

The most useful general procedure is:

### A. Adding a new CryoCon command

1. Consult the Model 22C manual's remote-operation command list.
2. Identify the command and its arguments.
3. Construct the SCPI string in Python.
4. Test a read-only query first, where available.
5. Add the command to the appropriate configuration section.
6. Verify the response or read the parameter back.
7. Consider whether the change needs to be reversed during cleanup.

For example, to investigate the configured ramp rate:

```python
response = cryo.query(f"LOOP {loop}:RATE?")
print(response)
```

To change the rate, after confirming the permitted range and hardware state:

```python
cryo.query(f"LOOP {loop}:RATE {RAMP_RATE}")
```

The same approach can be used to investigate other documented parameters.

### B. Adding another recorded quantity

Suppose we want the CSV to record the temperature difference between sensors A and B.

First calculate it inside the measurement loop:

```python
temp_difference = temp_b - temp_a
```

Then add a heading when the CSV is created:

```python
"Temperature difference B-A (K)"
```

Finally, append `temp_difference` to each `writer.writerow(...)` call.

A new instrument measurement follows the same pattern, except that it also requires a communication command and appropriate parsing.

### C. Changing how experiments are sequenced

The present program advances when the feedback temperature remains within tolerance for a specified duration.

That behaviour could be replaced or supplemented with other conditions, such as:

- Requiring both sensors to stabilize.
- Checking the temperature's rate of change.
- Waiting for an additional instrument measurement to satisfy a condition.
- Performing multiple readings at a fixed temperature before advancing.

These extensions belong in the **experiment completion section**, not in the instrument connection code.

Keep a distinction between the controller's internal temperature regulation and Python's logic for deciding when a phase is complete.

### D. Adding another control mode

The CryoCon supports modes beyond the `PID` and `RAMPP` modes currently permitted by the program.

However, adding a mode involves more than changing the accepted string in the validation code.

You must also determine:

- Which instrument parameters the new mode requires.
- The correct sequence for configuring those parameters.
- How the mode behaves when control is enabled.
- How to verify that configuration succeeded.
- How to stop and restore the instrument safely.

The manufacturer's manual, rather than assumptions based on the existing RAMPP implementation, should determine this behaviour.


## References

- [CryoCon Model 22C User's Guide](https://file-storage.github.io/manuals/cryocon_22c_user_manual.pdf) — instrument commands, arguments and control modes.
- [CryoCon Python driver](https://github.com/bicarlsen/cryocon-22c-controller) — Python interface used by the script.
- [easy-scpi](https://github.com/bicarlsen/easy-scpi) — underlying instrument communication library.
- [PyVISA documentation](https://pyvisa.readthedocs.io/en/latest/) — communication with VISA-compatible instruments.
- [Python documentation](https://docs.python.org/3/) — functions, exceptions, CSV files and timing.

For installation and ordinary operation, see the separate [Setup](setup.md) and [Usage](usage.md) guides.
