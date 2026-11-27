# Usage guide: temperature sweeps and data collection

This guide describes the **multi-phase** version of [cryo-control.py](../../cryo-control.py). It retains the original CryoCon/DMM measurement code inside `run_experiment()` and executes it once for each dictionary in `EXPERIMENTS`. It assumes the two-line plot-saving snippet has already been added to the `finally` block.

The script measures four-wire resistance as a function of temperature during cooldowns, warmups and other setpoint changes. **Temperature control is not refrigeration:** the CryoCon adjusts a heater, but the apparatus must already be capable of removing heat for a cooldown.

## 1. Safety and preparation

Before enabling control, verify the following with the responsible experimentalist:

1. **Actual wiring:** Which physical heater is connected to loop 1 or 2? Where are sensors A and B? Which sensor responds promptly to that heater, and which represents the sample temperature?
2. **Thermal capability:** Can the system reach both target temperatures? Is a physical cooling mechanism present and working?
3. **Control tuning:** Are heater range, power limits, PID parameters and controller maximum setpoints approved for this apparatus? The script **does not** set or tune these.
4. **Protection:** Is independent hardware overtemperature protection active? Can the operator reach the physical STOP button? The Python check is not a substitute for a real interlock.
5. **Measurement:** Are the DMM's four-wire leads, excitation current, range and expected resistance appropriate? Are both sensor calibrations and units correct?
6. **Files and connections:** Are the serial and VISA addresses correct, is the data folder writable, and is temperature control initially disengaged?

The example temperatures, limits and rates below are copied from the current program, **not validated operating recommendations**.

## 2. Global settings

Open [cryo-control.py](../../cryo-control.py) in Spyder. Global settings affect every phase:

| Setting | Purpose | Current example |
| --- | --- | --- |
| `MATERIAL` | Label for plots and filenames | `"copper"` |
| `DATA_DIR` | Where CSV and PNG files are written | `T:\HMData\november-2026` |
| `CRYO_PORT` | Serial connection to CryoCon | `"COM3"` |
| `DMM_ADDRESS` | VISA address of multimeter | Lab-specific USB resource |
| `ENABLE_CONTROL` | Whether the script initiates heating control | `True` |
| `TARGET_TOLERANCE_K` | Permitted distance from target, ±K | `0.1` |
| `HOLD_SECONDS` | Continuous time inside permitted range | `60` s |
| `MAX_SAFE_TEMP_K` | Software cutoff for either sensor | `305.0` K |
| `SCAN_INTERVAL` | Requested delay between scan starts | `0.5` s |
| `PLOT_EVERY` | Refresh plot every N readings | `1` |

**Units:** `SCAN_INTERVAL` is in **seconds**, `PLOT_EVERY` is a **number of measurements**, and each `ramp_rate` is in **K/min**. For example, `SCAN_INTERVAL = 0.5` requests about 2 readings/s; `PLOT_EVERY = 5` would redraw about every 2.5 s if instrument communication and plotting are sufficiently fast.

## 3. Program the experiment list

Edit **`EXPERIMENTS`**, not the instrument-control loop, for ordinary temperature sweeps. Each dictionary describes a phase; phases run **from top to bottom**:

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

These illustrate the **current script's values**, not universal safe setpoints. For a single experiment, leave one dictionary. For a third stage, copy a dictionary and change its fields. Choose short, filesystem-safe `name` values so the data files have useful labels.

| Dictionary field | Meaning |
| --- | --- |
| `name` | Text included in progress messages and CSV/PNG filenames |
| `channel` | Feedback sensor, `"A"` or `"B"` |
| `heater_loop` | Powered heater output: `1` or `2` |
| `mode` | `"RAMPP"` for programmed setpoint ramp, `"PID"` for direct regulation |
| `setpoint_k` | Final target in kelvin |
| `ramp_rate` | Programmed setpoint speed in K/min; used only in RAMPP mode |

**Feedback sensor vs sample sensor:** `channel` controls the heater *and* determines whether the software considers that phase complete. Both sensors are recorded. If B is on the sample but A is nearer the heater, the phase could finish when **A** stabilizes even if B still lags. Inspect both readings and choose the ramp, sensor and hold time for the actual experiment.

## 4. When does a phase finish?

For every reading, the program compares the measured feedback temperature to the target:

```python
abs(controlled_temp - SETPOINT_K) <= TARGET_TOLERANCE_K
```

If that is true, it starts or continues the hold timer. If the reading leaves the permitted band, the timer resets. After `HOLD_SECONDS` continuously within tolerance, the phase ends: its CSV closes, the controller is asked to disengage, the instruments disconnect, and the next phase starts.

For example, with a **270 K** target, tolerance **±0.1 K** and hold **60 s**, the feedback sensor must stay in **269.9–270.1 K for 60 seconds**. This tests the *measured feedback temperature*, not the other sensor or a controller ramp-status flag. It does not by itself prove full sample thermal equilibrium.

**There is no `max_minutes` or automatic phase timeout.** A phase can run indefinitely if the target cannot be reached or maintained. Stop it manually if necessary; do not rely on a timed abort.

### PID compared with RAMPP

In `RAMPP`, the program chooses the rate, sets an initial setpoint at the current feedback temperature, engages control, then sends the final target. A lower target asks the **programmed setpoint** to decrease; the apparatus needs actual cooling to follow it. `ramp_rate = 0.5` means **0.5 K/min** of programmed setpoint movement, not a guaranteed sample cooling/heating rate.

In `PID`, the script sets the final target directly and the `ramp_rate` value is unused. The same feedback-temperature hold test determines when to advance.

## 5. Measurement-only test before heating

First set:

```python
ENABLE_CONTROL = False
```

Run in a correctly configured Spyder console (see [setup](setup.md)). The script still opens both instruments, configures the DMM, checks that control is initially disengaged and measures both temperatures and resistance. It does **not** initiate temperature regulation itself.

**Important:** The target-and-hold condition still applies with `ENABLE_CONTROL = False`. A test far from the example target may run forever, so **interrupt it yourself** after verifying that sensor readings, resistance, live plotting and CSV writing work. An interruption stops the whole sequence; it does not advance to the next phase.

## 6. Running a controlled sequence

After the safety checks, set `ENABLE_CONTROL = True`, save the script and press **F5** in Spyder. Review the startup messages for the sensor, heater loop, mode, target, current heater range, actual ramp-rate read-back and the active-control state. Also check the *physical CryoCon display*: successful Python communication alone does not establish that the intended heater is operating safely.

The live plot shows **absolute resistance versus temperature**, using a separate x-axis temperature series for each sensor. The CSV records signed resistance and sequential measurements. The figure refreshes every `PLOT_EVERY` data points.

Illustrative console output:

```text
t: 12.0s | A: 295.1000 K | B: 294.3600 K | R: 8.5745 Ohm
Phase 'cool-down' complete: held for 60s
===== STARTING warm-up =====
```

These readings are examples, not observed data. When one phase finishes, the function disconnects from both instruments; the next phase reconnects them. Short gaps between phases are therefore expected.

## 7. Files produced: CSV and PNG

Each phase writes a distinct **CSV** and, with your two-line `fig.savefig(...)` addition, a **PNG** in `DATA_DIR`:

```text
RvsT_24_11_2026_13_00_00_copper_cool-down.csv
RvsT_24_11_2026_13_00_00_copper_cool-down.png
RvsT_24_11_2026_16_00_00_copper_warm-up.csv
RvsT_24_11_2026_16_00_00_copper_warm-up.png
```

The PNG has the **same filename stem** as its CSV and is saved at **300 DPI** by the lines you added to the function's `finally` block:

```python
if "fig" in locals() and csv_path.exists():
    fig.savefig(csv_path.with_suffix(".png"), dpi=300, bbox_inches="tight")
```

The save is attempted at the end of each phase, including ordinary Ctrl+C interruption **if** the figure and CSV have been created and execution reaches that statement. If `PLOT_EVERY > 1`, the last few acquired points may be missing from the picture, though they remain in the CSV. A forced kernel kill or power loss may prevent PNG creation. The CSV is the primary experimental record.

| CSV column | Meaning |
| --- | --- |
| `Time (s)` | Seconds since acquisition for *this phase* began; restarts from zero next phase |
| `Temperature A (K)` | Reading from sensor A |
| `Temperature B (K)` | Reading from sensor B |
| `Resistance (Ohm)` | Signed four-wire DMM reading |
| `Uncertainty A (K)` and `Uncertainty B (K)` | Approximate temperature uncertainty formulas used in the code |
| `Uncertainty R (Ohm)` | Approximate resistance uncertainty formula used in the code |

Each CSV row is flushed immediately. The uncertainty formulas are inherited from the measurement program; they are **not a verified calibration/uncertainty budget**. Record sensor placement, heater settings, DMM range/current, sample details and other experimental conditions separately because not all are stored in the output files.

## 8. Stopping safely

To stop **every remaining phase**, interrupt the Spyder console with **Ctrl+C** or Spyder's **Interrupt** action. The script re-raises Ctrl+C so the outer loop does **not** proceed to the next experiment. Cleanup attempts `cryo.disable()`, checks the controller's reported enabled state, restores temporarily disabled loop modes, closes instrument connections, and leaves the final graph available. Verify on the **physical controller** that regulation really is off; use **physical STOP** if required.

Exceeding `MAX_SAFE_TEMP_K` during measurement raises an error and attempts cleanup. Serial failure, blocked I/O, forced termination and computer crashes may prevent Python from stopping the heater. Software controls cannot replace a hardware cutoff or direct supervision of an unvalidated setup.

## 9. Common problems

| Symptom | What to check |
| --- | --- |
| A required Python import fails | Conda environment and Spyder kernel; [setup](setup.md) |
| COM/VISA connection unavailable | Correct address, driver, cable and whether another program holds the device |
| `Temperature control is already active` | Consult operator; the script expects control initially disengaged |
| Setpoint exceeds controller maximum | Confirm the approved controller limits and selected loop; don't raise limits just to bypass the check |
| Another loop cannot be disabled | Check whether the loop serves other equipment; do not bypass without operator approval |
| Cooling too slow or no cooldown | Physical refrigeration/thermal sink, sensor placement and thermal coupling |
| Sensor A and B disagree / R–T curve loops | Thermal lag, sample contact, feedback sensor choice and ramp rate |
| Phase never finishes | Feedback must remain inside the target band for `HOLD_SECONDS`; there is no timeout |
| Live plot frozen | Qt backend, active plot window and `PLOT_EVERY` |
| PNG missing | The save snippet, CSV/figure existence, completed cleanup and file permissions |
| A filename prints but no data appears | Failure before file creation, output permissions or empty CSV; inspect traceback |

See [how the code works](code-explanation.md) for the SCPI commands and Python implementation, and [setup](setup.md) for installing the packages, handling different Spyder versions and identifying ports.
