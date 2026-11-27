# How the code works

This guide explains [cryo-control.py](../../cryo-control.py) so that a student can understand and modify it.

The aim is not to implement a temperature controller in Python: the CryoCon already contains that controller. Python tells it what to do, reads the instruments and saves the experiment.

The current version also runs multiple temperature phases in sequence and saves the final plot as a PNG.

## 1. The physical system

A temperature sensor measures temperature. A heater supplies heat. A control loop uses a chosen sensor reading and a target temperature to regulate an output.

```text
Target temperature → CryoCon PID loop → heater → apparatus
                           ↑                         |
                           └──── temperature sensor ┘

Python configures the loop and reads both sensors and the DMM.
```

Inputs A and B are independent temperature sensors. They are not heater numbers. Either may be assigned as feedback for a loop, but the physical wiring and thermal coupling determine whether the choice is sensible.

| Loop | Physical output |
| --- | --- |
| 1 | Primary powered heater |
| 2 | Secondary powered heater |
| 3, 4 | Analogue voltage outputs for external equipment, not built-in heater power supplies |

The program restricts selection to loops 1 and 2. The hardware supports four loops.

A sensor that responds slowly or not at all to a chosen heater can cause excessive heating elsewhere. Confirm the actual wiring rather than relying on channel names.

In PID mode the controller regulates using the difference between measured and target temperature. In RAMPP mode its internal target changes at a programmed rate; PID attempts to follow it.

The actual sample temperature is not guaranteed to follow the ramp exactly. Cooling requires an appropriate thermal sink or refrigeration.

## 2. Original explanations in the program

The script's original feedback-sensor note is reproduced below, with only line wrapping adjusted:

> Note that if the sensor is well insulated from the corresponding heater loop, you will notice looping in the Resistance vs Temperature plot. It is thus best to use the sensor that is most responsive to the active heater loop, and reduce the ramp_rate to encourage thermal equilibrium between the sensor of desire and the most responsive sensor.
>
> For example, if i am using heater loop 1, and sensor A is close to it, whilst sensor B is in thermal contact with the sample holder and represents the actual temperature of the sample, then during cooling, i will use CONTROL_CHANNEL = "A", with a small ramp rate.

This is experimental advice specific to sensor/heater coupling.

Importantly, the feedback sensor controls heater action, while the other sensor may track sample temperature. The target-completion test uses the **feedback sensor**, not necessarily the sample sensor.

### Original explanation of the instrument commands

The following is adapted closely from the large explanatory string in the script. Tables have been converted to Markdown. Spelling of SCPI and small technical wording errors have been corrected so that the text distinguishes the communication library from the command language.

> Below, initial connection to the instruments follows the original code. The new code follows from the `if ENABLE_CONTROL` qualifier. The key insight to modifying the original code to allow control of the instruments was that we were not restricted to the arguments that appear directly in `cryocon-22c-controller` (a Python library adapted to Python control of these CryoCon instruments). Since it employs `easy-scpi`, we can use its `cryo.query("str")` method to pass through a SCPI command (here `str` is the SCPI command that the controller can natively read, passed through to `cryo.query()` as a string). The library handles communication with the controller.
>
> The main component needed for controller connection is simply (in this case change port as needed):

```python
import cryocon_22c_controller as cc

cryo = cc.CryoconController(port="COM3", backend="")
cryo.connect()
```

> For example, if one wants to change the source of the heating input channel and the source of heat, reading the CryoCon Model 22C User's Guide, one learns that the relevant SCPI parameters are `SOURCE` and `LOOP`, respectively. So if you want to change this to channel A, using heater loop 1, one would use the following:

```python
CONTROL_CHANNEL = "A"
HEATER_LOOP = 1

cryo.query(f"LOOP {HEATER_LOOP}:SOURCE {CONTROL_CHANNEL}")
```

> A list of the SCPI parameters that you might care about, pulled from the manufacturer's documentation:

| Brief description of parameter | SCPI parameter |
| --- | --- |
| Heater input source | SOURCE |
| Heater loop | LOOP |
| Setpoint | SETP |
| Ramp rate | RATE |
| Temperature control type | TYPE |

> Note that, for temperature control type, this code only supports PID and RAMPP. But the SCPI command options are available for the remaining modes:

| CONTROL TYPE | MEANING |
| --- | --- |
| OFF | Disable loop |
| PID | Standard temperature regulation |
| RAMPP | PID with temperature ramping |
| MAN | Manually specified output |
| TABLE | PID using stored tuning parameters |
| RAMPT | Ramping with stored PID parameters |

> One final important thing. All parameters must be specified chronologically in the Python script BEFORE the final setpoint is specified.

That final sentence describes the intended ramp sequence for this program; it is not a universal rule for every instrument command.

See section 6. The snippets above illustrate syntax, not a complete or safe heating procedure.

## 3. How to construct SCPI commands and arguments

SCPI stands for **Standard Commands for Programmable Instruments**.

The instrument understands command strings; a Python driver transmits them. `easy-scpi` is a Python library, not the language itself.

The Model 22C manual describes loop commands using patterns such as:

```text
LOOP {1 | 2 | 3 | 4}:RATe <rate>
```

The braces, vertical bars and angle brackets here are documentation notation, not literal characters to send.

Pick one loop number and replace the placeholder with a real numeric value.

The uppercase portion of a mixed-case keyword is its short form; the documented full form can also be used.

A colon separates parts of the command; spaces separate the command from its arguments. A question mark requests a value.

| Intent | Example sent to CryoCon |
| --- | --- |
| Read source | `LOOP 1:SOURCE?` |
| Read control type | `LOOP 1:TYPE?` |
| Read setpoint | `LOOP 1:SETP?` |
| Read ramp rate | `LOOP 1:RATE?` |
| Read power limit | `LOOP 1:MAXPWR?` |
| Set source to A | `LOOP 1:SOURCE A` |
| Set ramp rate to 0.5 | `LOOP 1:RATE 0.5` |

The last two examples modify the instrument; do not send them merely to test communication. Verify all relevant safety conditions before writing parameters.

### Python f-strings

Python f-strings substitute the values between braces:

```python
loop = 1
rate = 0.5

command = f"LOOP {loop}:RATE {rate}"

print(command)
# LOOP 1:RATE 0.5
```

Printing the string does not send anything to the controller.

To read a parameter from an established connection, use:

```python
response = cryo.query(f"LOOP {loop}:MAXSET?")
print(response)
```

The response is text, often with whitespace or units.

For example, this instrument returned `300.000000K`, which `float()` cannot parse directly. The program strips whitespace and removes the known K suffix before conversion.

Do not blindly strip arbitrary units: confirm the units and range.

### Why use cryo.query()?

The [CryoCon driver](https://github.com/bicarlsen/cryocon-22c-controller) explains why `query()` is used even when setting parameters: “All commands generate a response from the controller”.

This keeps its command/response handling synchronized.

For the DMM, use its own protocol: typically `write()` for a setting and `query()` for a response.

The manufacturer's [22C manual](https://file-storage.github.io/manuals/cryocon_22c_user_manual.pdf), Remote Operation, describes accepted commands and arguments.

Do not assume another model accepts them.

When adding a feature:

1. Find the documented command.
2. Check its arguments and units.
3. Prefer a read-only query when first investigating it.
4. Make an approved change only after checking the relevant hardware.
5. Read back the result to verify it was accepted.

## 4. What changed for multiple experiments

The program was deliberately **wrapped rather than rewritten**.

The original instrument configuration, acquisition loop, CSV writer, plotting and cleanup are inside:

```python
def run_experiment(experiment):
```

The final `for` loop calls it once per dictionary:

```python
for experiment in EXPERIMENTS:
    run_experiment(experiment)
```

The dictionaries at the top contain the per-phase settings:

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
        "ramp_rate": 0.5,
    },
]
```

These are source-code examples, not independently validated thermal conditions.

The fields mean:

| Field | Meaning |
| --- | --- |
| `name` | Short label included in the filename |
| `channel` | Feedback sensor A or B |
| `heater_loop` | Powered output 1 or 2 |
| `mode` | PID or RAMPP |
| `setpoint_k` | Target temperature in kelvin |
| `ramp_rate` | Programmed K/min rate, used for RAMPP |

The number and order of dictionaries determine the sequence.

One dictionary gives one experiment.

Shared settings remain outside the dictionaries:

- `ENABLE_CONTROL`
- `MATERIAL`
- `DATA_DIR`
- Connection addresses
- `MAX_SAFE_TEMP_K`
- `SCAN_INTERVAL`
- `PLOT_EVERY`
- `TARGET_TOLERANCE_K`
- `HOLD_SECONDS`

### The new completion test

After each acquired data point the script compares the **measured feedback temperature** to `SETPOINT_K`:

```python
controlled_temp = temp_a if channel == "a" else temp_b

if abs(controlled_temp - SETPOINT_K) <= TARGET_TOLERANCE_K:

    if stable_since is None:
        stable_since = time.monotonic()

    if time.monotonic() - stable_since >= HOLD_SECONDS:
        print(f"Phase '{name}' complete.")
        break

else:
    stable_since = None
```

If the sensor leaves the permitted band, the stability timer starts over.

For example:

```python
TARGET_TOLERANCE_K = 0.1
HOLD_SECONDS = 60
```

These require the measured feedback temperature to remain within ±0.1 K of the target for approximately one minute.

This checks the measured sensor temperature, not whether the CryoCon's programmed ramp status says complete.

The parameters are experimental choices, not a proof of thermal equilibrium throughout the sample.

**There is deliberately no `max_minutes` or overall phase timeout.**

If a setpoint is unreachable, the current phase can continue indefinitely unless interrupted, communication fails or a safety mechanism acts.

A failed phase does not automatically advance.

### What happens between phases?

When the inner measurement loop breaks:

1. The current CSV file is closed.
2. The original `finally` block attempts to disengage temperature control.
3. The instrument connections are closed.
4. The final plot is saved as a PNG.
5. The function returns.
6. The outer loop starts the next experiment.

This reconnection between stages is intentional: it preserves the existing experiment code and cleanup approach instead of introducing persistent instrument state.

The `except KeyboardInterrupt` branch re-raises Ctrl+C, so it cannot silently trigger the next phase.

**Important:** Instrument shutdown must be confirmed at the physical controller. A software stop request alone does not guarantee that the heater has disengaged.

## 5. Settings, validation and instrument initialization

The imports supply:

- CSV writing
- Timestamps
- Filesystem paths
- Array operations
- Plotting
- VISA communication
- The CryoCon driver

The settings block separates values an operator changes from the measurement logic below.

The script normalizes channel and mode strings and rejects unsupported values.

It checks the setpoint against a software ceiling and requires a positive ramp rate no greater than 100 in RAMPP mode. This is a code validation limit, not a safe rate recommendation.

It tries to switch an Inline Matplotlib backend to QtAgg for interactive graphics.

It then creates a VISA resource manager and a CryoCon object.

Inside the `try` block it connects to the controller and opens the DMM.

```python
dmm.write("SYSTE:REMOTE")
dmm.write("*CLS")
dmm.write("CONF:FRES")
```

These request remote operation, clear instrument status and configure four-wire resistance.

`READ?` later triggers/returns a reading.

Configuration and repeated measurement are separate.

Four-wire resistance uses separate excitation and voltage-sense leads. It reduces lead-resistance effects, but excitation current, self-heating, range and integration time still matter.

Consult the actual DMM manual before changing them.

The program requires control to be initially disengaged, checks the selected sensor's units and reads the maximum allowed setpoint.

The maximum setpoint is a controller setting, not proof of apparatus safety.

## 6. Temperature control: the central change

The original measurement script read sensor temperatures and existing setpoints. It did not initiate regulation.

The newer code enters the configuration block if `ENABLE_CONTROL` is true.

The procedure is:

1. Query loops 1–4 and temporarily turn every non-selected loop OFF, remembering its former mode.
2. Assign the chosen sensor to the selected heater with `SOURCE` and verify the reported source.
3. Set the chosen `TYPE`.
4. In RAMPP, set `RATE` and set the initial target to the measured feedback temperature. In PID, set the final target directly.
5. Check the reported mode.
6. Call `cryo.enable()` and check that the instrument reports control engaged.
7. In RAMPP, send the final target after engaging control.
8. Print the reported setpoint and continue measuring.

The core command sequence in the program is:

```python
# Excerpt only:
# The actual script includes configuration and safety checks.

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

The [22C manual](https://file-storage.github.io/manuals/cryocon_22c_user_manual.pdf), printed pp. 57–59, describes the ramp sequence: configure the rate and starting setpoint, engage regulation, then change the setpoint to initiate the ramp.

It continues regulating after completion.

The program chooses the present measured temperature as the starting setpoint. That is a design decision, not a guaranteed smooth transition.

Stable PID parameters and appropriate power limits must already be configured.

### Example: calculating ramp duration

Suppose:

- Starting temperature: 294 K
- Final target: 300 K
- Ramp rate: 0.5 K/min

The ideal programmed ramp duration is:

```text
(300 - 294) / 0.5 = 12 minutes
```

This describes the programmed setpoint. It does not guarantee that the actual sample takes 12 minutes to reach 300 K.

The global `CONTROL` command, wrapped by `enable()`, can engage every configured control loop.

Temporarily disabling the other loops is a deliberate policy for a single-heater experiment, not a hardware requirement that all experiments use a single loop.

It must be permitted by the operator.

The program does not change PID gains or heater range.

## 7. Acquisition and timing

The `while True` loop reads both temperatures, checks the software limit and queries resistance.

It appends readings to in-memory lists, writes a row to the CSV, prints a summary and refreshes the plot.

```python
temp_a = float(cryo.temperature("a"))
temp_b = float(cryo.temperature("b"))

resistance = float(dmm.query("READ?").strip())
```

The readings are sequential, not simultaneous.

`time.monotonic()` measures elapsed time and scan duration without depending on changes to the wall clock.

Sleeping only for the remaining requested interval aims for the requested cadence.

Slow instrument responses or plotting may make sampling slower than requested.

The acquisition loop now has one additional exit: the feedback sensor meets the target-band and hold-time condition.

It then closes the current CSV and returns so the outer loop can run the next phase.

The software ceiling, an error or an interrupt can also end a run.

## 8. CSV, uncertainties and saved PNGs

The date/time, material and experiment name form a filename.

For example:

```text
RvsT_24_11_2026_13_00_00_copper_cool-down.csv
```

The same base name is used for the saved PNG.

The CSV contains:

| Column | Meaning |
| --- | --- |
| Time (s) | Elapsed time since acquisition started |
| Temperature A (K) | Sensor A |
| Temperature B (K) | Sensor B |
| Resistance (Ohm) | Signed DMM reading |
| Uncertainty A (K) | Estimated temperature A uncertainty |
| Uncertainty B (K) | Estimated temperature B uncertainty |
| Uncertainty R (Ohm) | Estimated resistance uncertainty |

Writing and flushing each row reduces data loss if Python is interrupted.

It is not a guarantee of durable writes during power or network failures.

Time begins at zero for **each phase**. The files are separate rather than one continuous record.

### Uncertainty calculations

The uncertainty expressions are inherited from the original code, with the channel-B calculation corrected:

```python
u_a = 0.00005 * abs(temp_a) + 0.00008
u_b = 0.00005 * abs(temp_b) + 0.00008
u_r = 0.00012 * abs(resistance) + 4e-10
```

These are not independently validated calibration models.

Review the sensor and DMM specifications, selected range, calibration and uncertainty budget before using them for published results.

### Saved plot: one PNG per phase

With the figure-saving change already added in the `finally` block, the plot is saved in the same directory as the CSV:

```python
if "fig" in locals() and csv_path.exists():
    fig.savefig(
        csv_path.with_suffix(".png"),
        dpi=300,
        bbox_inches="tight"
    )
```

For example:

```text
RvsT_24_11_2026_13_00_00_copper_cool-down.csv
RvsT_24_11_2026_13_00_00_copper_cool-down.png
```

`with_suffix(".png")` replaces only the extension.

The guard avoids attempting a save before the graph or CSV exists.

The figure represents the last plotted dataset for that phase.

If `PLOT_EVERY` is greater than one, the most recent measurements might not be reflected in the plot when stopping. All acquired readings remain in the CSV.

A forced Python termination or power failure may prevent the PNG from being saved.

The PNG is not a substitute for the raw CSV.

## 9. Live plotting

Instead of clearing and reconstructing axes for every sample, the script creates two point series once.

`set_data()` changes the existing series.

`relim()` and `autoscale_view()` adjust the axes.

Drawing, flushing GUI events and pausing briefly keep the window responsive.

`PLOT_EVERY` controls refresh frequency independently of CSV logging.

The plot uses absolute resistance for each temperature input.

The CSV preserves the resistance sign. A negative resistance reading may be diagnostically important.

The live plot does not include uncertainty bars, although the uncertainty values remain in the CSV.

## 10. Shutdown and known limitations

The `try/except/finally` structure handles normal interruption and ordinary errors.

If the script attempted to engage control, its cleanup attempts to stop the CryoCon before restoring other loop modes.

It closes both instrument connections and keeps the final figure available without blocking the next stage.

Restored loop modes can become active again on a later global CONTROL command. Selected loop settings remain changed.

A software stop request must not be treated as confirmation of physical heater shutdown.

### Current limitations

The following are limitations of the implementation, not features:

- Only the selected sensor's units are checked, even though both are logged as K and used in the software cutoff.
- The maximum setpoint is checked before changing feedback source. Checking afterward would be more robust.
- Temperature safety checks begin during acquisition, after control can be engaged.
- Invalid/nonfinite readings and hardware fault states are not explicitly validated.
- The program prints ramp/setpoint read-backs but does not compare all their numeric values.
- Forced termination, broken communication or blocked reads can prevent timely shutdown.
- Software is not a replacement for independent hardware overtemperature protection.
- The cleanup message can print a filename even if acquisition never started. Verify the CSV exists and contains rows.
- The PNG-save guard checks that a CSV exists, not that the CSV contains valid data.
- Data lists grow throughout each phase, and every plot refresh redraws all accumulated points.
- There is no upper phase-duration limit.
- A stable feedback sensor does not prove that the entire sample has equilibrated.
- No direct sample temperature-gradient or temperature-rate-of-change stabilization test is included.

## 11. How to modify the program

Begin with an offline change or measurement-only test.

**For another temperature stage, add one dictionary to `EXPERIMENTS`. No additional function or instrument logic is needed.**

Change settings rather than the acquisition logic unless a genuinely new feature is needed.

### Changing stabilization criteria

For example, to finish each phase after 120 seconds within ±0.2 K:

```python
TARGET_TOLERANCE_K = 0.2
HOLD_SECONDS = 120
```

These parameters are shared between all phases.

### Adding or removing experiments

To remove a phase, delete its dictionary.

To repeat one, copy its dictionary and change its `name` and target.

Do not duplicate the entire program or add additional `for` loops inside the measurement loop.

### Changing the temperature ramp

Modify:

```python
"setpoint_k": 270.0,
"ramp_rate": 0.5,
```

The ability to run multiple phases does **not** mean the apparatus can cool at a chosen rate just by changing `ramp_rate`.

It must have a physical mechanism to remove heat.

### Adding new measurements

To add another measured quantity:

1. Find the relevant instrument command in its manual.
2. Query the instrument using its existing connection.
3. Parse and validate the response.
4. Add a matching CSV column header.
5. Write the new measurement into each row.
6. Decide whether it should also appear on the plot.

To implement a new control mode, review its hardware behavior and command ordering, then update validation and read-back checks.

Never remove shutdown checks or raise limits merely to bypass an error.

## 12. Primary references

- [CryoCon Model 22C User's Guide](https://file-storage.github.io/manuals/cryocon_22c_user_manual.pdf) — hardware, overtemperature protection, ramping and remote-control commands.
- [cryocon-22c-controller](https://github.com/bicarlsen/cryocon-22c-controller) — Python driver and methods.
- [easy-scpi](https://github.com/bicarlsen/easy-scpi) — communication layer.
- [PyVISA](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html) — instrument communication.
- [Matplotlib interactive figures](https://matplotlib.org/stable/users/explain/figure/interactive_guide.html) — interactive plotting.
- [Python time](https://docs.python.org/3/library/time.html) — timing and monotonic clocks.
- [Keysight Truevolt documentation](https://www.keysight.com/us/en/support/34461A/digital-multimeter-6-5-digit-truevolt-dmm.html) — consult the manual for the actual DMM model and firmware.

[Setup](setup.md) · [Usage guide](usage.md) · [Quick start](../quick-start.md)
