import csv
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import pyvisa
import cryocon_22c_controller as cc


# ============================================================
# SETTINGS
# ============================================================

MATERIAL = "copper" 
DATA_DIR = Path(r"T:\HMData\november-2026\test") # Results save directory

CRYO_PORT = "COM3"
DMM_ADDRESS = "USB0::0x2A8D::0x1301::MY60057353::INSTR"

# ============================================================
# EXPERIMENT SEQUENCE
# ============================================================

# Define consecutive experiments below. Each dictionary is one phase.
# Change the temperatures/rates only after checking the actual apparatus.
# Add or remove dictionaries to change the number of phases.
# Each phase has a separate CSV file and live plot.
# A cooldown needs a physical cooling mechanism; the heater cannot refrigerate.

# Temperature control: the channel is the FEEDBACK temperature sensor.
"""
Note that if the sensor is well 
insulated from the corresponding heater loop, you will notice looping in the 
Resistance vs Temperature plot. It is thus best to use the sensor that is 
most responsive to the active heater loop, and reduce the ramp_rate 
to encourage thermal equilibrium between the sensor of desire and the most 
responsive sensor. 

For example, if i am using heater loop 1, and sensor A is close to it, whilst 
sensor B is in thermal contact with the sample holder and represents the actual
temperature of the sample, then during cooling, i will use 
CONTROL_CHANNEL = "A", with a small ramp rate. 

"""

EXPERIMENTS = [
    {
        "name": "test-warm",       # Appears in the CSV filename
        "channel": "A",           # Feedback sensor: "A" or "B"
        "heater_loop": 1,         # Powered output: 1 or 2
        "mode": "RAMPP",          # "PID" or "RAMPP"
        "setpoint_k": 280,      # Final temperature, kelvin
        "ramp_rate": 3,         # Kelvin per minute; used for RAMPP
    },
    {
        "name": "warm-up",
        "channel": "A",
        "heater_loop": 1,
        "mode": "RAMPP",
        "setpoint_k": 275,
        "ramp_rate": 2,
    },
]

ENABLE_CONTROL = True

# A phase finishes when its feedback sensor stays within this range
# of its target for HOLD_SECONDS. If it leaves the range, the timer resets.
# There is deliberately NO time limit. A phase can run indefinitely until
# it stabilizes, you interrupt it, an instrument errors, or a safety check trips.
TARGET_TOLERANCE_K = 0.2  # +/- kelvin
HOLD_SECONDS = 60         # seconds

# Safety and measurements
MAX_SAFE_TEMP_K = 305.0 # kelvin
SCAN_INTERVAL = 0.5 # seconds
PLOT_EVERY = 1 # number of measurements


# ============================================================
# RUN ONE EXPERIMENT
# ============================================================

"""
A note on the modifications made to the original 'data-reading' code
to morph it into a 'data-reading' AND 'temperature-controlling' script. This 
docstring contains details on the central insights that guided the code. If
one wishes to make changes to the code, one should read this doc-string. 

The Below initial connection to the instruments follows the original code. 
The new code follows from the `if ENABLE_CONTROL' qualifier. The Key insight 
to modifying the original code to allow the control of the instruments was that 
we were not restricted to the arguments that appear directly in 
`cryocon-22c-controller' (a python library adapted to python control of these 
cryocon instruments). Since it employs easy-scipi, the native language of the 
temperature controllers, we can use its cryo.query("str") method to parse 
through a SCIPI-command (here `str' is the SCIPI command that the controller 
can natively read parsed through to cryo.query() as a string, that 
cryocon-22c-controller simply syncs to the controller). 

The main component needed for controller connection is simply (in this case
change port as needed):

    ```PY
    import cryocon_22c_controller as cc
    cryo = cc.CryoconController(port="COM3", backend="")
    cryo.connect()
    ```

for example, if one wants to change the source of the heating input channel and 
the source of heat, reading the cryocon:model 22c User guide, one learns that 
the relevant SCIPI parameter is `SOURCE' and `LOOP' respectively. So if you 
want to change this to channel A, using heater loop 1, one would use the 
following: 
    
    ```PY 
    CONTROL_CHANNEL = "A"
    HEATER_LOOP = 1 
    cryo.query(f"LOOP {HEATER_LOOP}:SOURCE {CONTROL_CHANNEL}")
    ```

A list of the SCIPI parameters that you might care about, pulled from the 
manufacturers documentation:

    ___________________________________________________________________________
    |                                 |                                       |
    |<brief description of parameter> | <SCIPI parameter>                     |
    |_________________________________|_______________________________________|
    | Heater input source             | SOURCE                                |
    |_________________________________|_______________________________________|
    | Heater Loop                     | LOOP                                  |
    |_________________________________|_______________________________________|
    | SetPoint                        | SETP                                  |
    |_________________________________|_______________________________________|
    | Ramp Rate                       | RATE                                  |
    |_________________________________|_______________________________________|
    | Temperature Control type        | TYPE                                  |
    |_________________________________|_______________________________________|


Note that, for temperature control type, this code only supports PID and RAMP. 
    But the SCIPI command options are available for all remaining as: 
    
    ___________________________________________________________________________
    |                                |                                        |
    | <CONTROL TYPE>                 | <MEANING>                              |
    |________________________________|________________________________________|
    | oFF                            | Disable loop                           |
    |________________________________|________________________________________|
    | PID                            | Standard temperature regulation        |
    |________________________________|________________________________________|
    | RAMPP                          | PID with temperature Ramping           |
    |________________________________|________________________________________|
    | MAN                            | Manually specified                     |
    |________________________________|________________________________________|
    | TABLE                          | PID using stored tuning parameteers    |
    |________________________________|________________________________________|
    | RAMPT                          | ramping with stored PID parameters     |
    |________________________________|________________________________________|


One final important thing. All parameters must be specified chronologically 
in the python script BEFORE the set point is specified.

"""
    
def run_experiment(experiment):
    """Run one phase using the original CryoCon and DMM measurement script.

    The outer for-loop below calls this function once for each dictionary.
    After the feedback sensor stays near the target for HOLD_SECONDS, this
    function finishes its CSV, stops the heater, closes connections, and
    returns. Ctrl+C or an error stops the entire sequence.
    """

    name = experiment["name"]
    CONTROL_CHANNEL = experiment["channel"]
    HEATER_LOOP = experiment["heater_loop"]
    CONTROL_MODE = experiment["mode"]
    SETPOINT_K = experiment["setpoint_k"]
    RAMP_RATE = experiment["ramp_rate"]

    # Every phase gets a distinct file (e.g. ..._copper_cool-down.csv).
    timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    csv_path = DATA_DIR / f"RvsT_{timestamp}_{MATERIAL}_{name}.csv"
    print(f"\n===== STARTING {name} =====")

    if HOLD_SECONDS < 0 or TARGET_TOLERANCE_K <= 0:
        raise ValueError("HOLD_SECONDS must be nonnegative and TARGET_TOLERANCE_K positive")
    if not isinstance(PLOT_EVERY, int) or PLOT_EVERY < 1:
        raise ValueError("PLOT_EVERY must be a positive integer")

    # ============================================================
    # VALIDATE SETTINGS AND GRAPHICS BACKEND
    # ============================================================

    channel = CONTROL_CHANNEL.lower()
    mode = CONTROL_MODE.upper()
    loop = HEATER_LOOP

    if channel not in ("a", "b"):
        raise ValueError("Channel must be A or B")

    # there are 4 control loops, but only two have built in heater power supplies. 
    if loop not in (1, 2):
        raise ValueError("Heater loop must be 1 or 2")

    if mode not in ("PID", "RAMPP"):
        raise ValueError("Mode must be PID or RAMPP")

    if mode == "RAMPP" and not (0 < RAMP_RATE <= 100):
        raise ValueError("Invalid ramp rate")

    if not (0 < SETPOINT_K < MAX_SAFE_TEMP_K):
        raise ValueError("Setpoint exceeds safety limit")

    # Ensure interactive graphics before activating the heater.
    if "inline" in plt.get_backend().lower():
        try:
            plt.switch_backend("QtAgg")
        except Exception as exc:
            raise RuntimeError(
                "Live plotting requires the Qt backend. "
                "In Spyder: Preferences > IPython Console > "
                "Graphics > Backend > Qt, then restart the kernel."
            ) from exc

    print("Matplotlib backend:", plt.get_backend())


    # ============================================================
    # CONNECT INSTRUMENTS
    # ============================================================

    rm = pyvisa.ResourceManager()
    cryo = cc.CryoconController(port=CRYO_PORT, backend="")


    dmm = None
    connected = False
    control_attempted = False
    changed_modes = {}

    times = []
    temperature_a = []
    temperature_b = []
    resistances = []

    try:
        cryo.connect()
        connected = True

        dmm = rm.open_resource(DMM_ADDRESS)
        dmm.timeout = 10000
        dmm.write("SYSTE:REMOTE")
        dmm.write("*CLS")
        dmm.write("CONF:FRES")

        if cryo.enabled:
            raise RuntimeError("Temperature control is already active")

        if str(cryo.units[channel]).strip().upper() != "K":
            raise RuntimeError("Selected sensor must use kelvin")

        max_setpoint = float(
            cryo.query(f"LOOP {loop}:MAXSET?")
            .strip()
            .removesuffix("K")
        )

        if SETPOINT_K > max_setpoint:
            raise ValueError("Setpoint exceeds controller maximum")

        print(f"Sensor: {channel.upper()}")
        print(f"Heater loop: {loop}")
        print(f"Mode: {mode}")
        print(f"Target: {SETPOINT_K} K")
        print(f"Heater range: {cryo.get_range(loop)}")

        # ========================================================
        # CONFIGURE TEMPERATURE CONTROL
        # ========================================================

        if ENABLE_CONTROL:

            # Only use the selected heater loop.
            # Other loop modes are restored after control stops.
            for i in range(1, 5):
                if i == loop:
                    continue

                previous = cryo.query(f"LOOP {i}:TYPE?").strip()

                if previous.upper() != "OFF":
                    changed_modes[i] = previous
                    cryo.query(f"LOOP {i}:TYPE OFF")

                    if cryo.query(f"LOOP {i}:TYPE?").strip().upper() != "OFF":
                        raise RuntimeError(f"Could not disable loop {i}")

            # Select feedback sensor
            cryo.query(f"LOOP {loop}:SOURCE {channel.upper()}")

            source = cryo.query(f"LOOP {loop}:SOURCE?").strip().upper()

            if source not in (channel.upper(), f"CH{channel.upper()}"):
                raise RuntimeError(f"Unexpected loop source: {source}")

            # Configure mode and ramp
            cryo.query(f"LOOP {loop}:TYPE {mode}")

            if mode == "RAMPP":
                cryo.query(f"LOOP {loop}:RATE {RAMP_RATE}")

                initial_temp = float(cryo.temperature(channel))
                cryo.query(f"LOOP {loop}:SETP {initial_temp}")

            else:
                cryo.query(f"LOOP {loop}:SETP {SETPOINT_K}")

            actual_mode = cryo.query(f"LOOP {loop}:TYPE?").strip().upper()

            if actual_mode != mode:
                raise RuntimeError(f"Mode mismatch: {actual_mode}")

            print("Configured mode:", actual_mode)

            if mode == "RAMPP":
                print("Ramp rate:", cryo.query(f"LOOP {loop}:RATE?"))

            # Enable heater control
            control_attempted = True
            cryo.enable()

            if not cryo.enabled:
                raise RuntimeError("Temperature control did not engage")

            if mode == "RAMPP":
                cryo.query(f"LOOP {loop}:SETP {SETPOINT_K}")

            print("Control active:", cryo.enabled)
            print("Setpoint:", cryo.query(f"LOOP {loop}:SETP?"))

        # ========================================================
        # INITIALIZE LIVE PLOT
        # ========================================================

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        plt.ion()
        fig, ax = plt.subplots(figsize=(9, 6))

        line_a, = ax.plot(
            [], [], ".", markersize=4, label="Channel A"
        )

        line_b, = ax.plot(
            [], [], ".", markersize=4, label="Channel B"
        )

        ax.set_xlabel("Temperature (K)")
        ax.set_ylabel("Resistance (Ohm)")
        ax.set_title(f"Resistance vs Temperature - {MATERIAL}")
        ax.grid(True)
        ax.legend()

        plt.show(block=False)
        fig.canvas.draw()
        fig.canvas.flush_events()

        # ========================================================
        # MEASUREMENT LOOP
        # ========================================================

        start_time = time.monotonic()
        stable_since = None  # Start timing when the sensor enters the target band.

        with open(csv_path, "w", newline="") as file:
            writer = csv.writer(file)

            writer.writerow([
                "Time (s)",
                "Temperature A (K)",
                "Temperature B (K)",
                "Resistance (Ohm)",
                "Uncertainty A (K)",
                "Uncertainty B (K)",
                "Uncertainty R (Ohm)"
            ])

            while True:
                scan_start = time.monotonic()

                # Read temperatures and resistance
                temp_a = float(cryo.temperature("a"))
                temp_b = float(cryo.temperature("b"))

                if max(temp_a, temp_b) >= MAX_SAFE_TEMP_K:
                    raise RuntimeError("Temperature safety limit exceeded")

                resistance = float(dmm.query("READ?").strip())

                elapsed = time.monotonic() - start_time

                # Measurement uncertainties
                u_a = 0.00005 * abs(temp_a) + 0.00008
                u_b = 0.00005 * abs(temp_b) + 0.00008
                u_r = 0.00012 * abs(resistance) + 4e-10

                # Store measurements
                times.append(elapsed)
                temperature_a.append(temp_a)
                temperature_b.append(temp_b)
                resistances.append(resistance)

                # Save immediately
                writer.writerow([
                    elapsed, temp_a, temp_b, resistance,
                    u_a, u_b, u_r
                ])
                file.flush()

                print(
                    f"t: {elapsed:.1f}s | "
                    f"A: {temp_a:.4f} K | "
                    f"B: {temp_b:.4f} K | "
                    f"R: {resistance:.6g} Ohm"
                )

                # =================================================
                # LIVE PLOT UPDATE
                # =================================================

                if len(times) % PLOT_EVERY == 0:

                    r = np.abs(resistances)

                    # Update existing points without clearing axes
                    line_a.set_data(temperature_a, r)
                    line_b.set_data(temperature_b, r)

                    # Automatically rescale axes
                    ax.relim()
                    ax.autoscale_view()

                    # Force live redraw
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                    plt.pause(0.05)

                # =================================================
                # EXPERIMENT COMPLETION (new)
                # =================================================

                # Use the same feedback sensor as the heater controller.
                # Do not advance to the next experiment until the measured
                # temperature remains in the target band for HOLD_SECONDS.
                controlled_temp = temp_a if channel == "a" else temp_b

                if abs(controlled_temp - SETPOINT_K) <= TARGET_TOLERANCE_K:
                    if stable_since is None:
                        stable_since = time.monotonic()
                    if time.monotonic() - stable_since >= HOLD_SECONDS:
                        print(f"Phase '{name}' complete: held for {HOLD_SECONDS}s")
                        break
                else:
                    stable_since = None  # Restart if the sensor leaves the band.

                # Maintain measurement interval
                time.sleep(max(
                    0,
                    SCAN_INTERVAL - (time.monotonic() - scan_start)
                ))


    except KeyboardInterrupt:
        print("\nMeasurement stopped by user.")
        raise  # Do not proceed to the next phase after Ctrl+C.

    except Exception as error:
        print(f"\nERROR: {error}")
        raise


    finally:
        # ========================================================
        # CLEANUP
        # ========================================================

        safe_to_restore = not control_attempted
        shutdown_failed = False

        if connected and control_attempted:
            try:
                cryo.disable()
                if cryo.enabled:
                    raise RuntimeError("CryoCon still reports control active")
                print("Temperature control stopped.")
                safe_to_restore = True
            except Exception as error:
                print("WARNING: Could not stop controller:", error)
                print("Use the physical STOP button.")
                shutdown_failed = True

        if connected and safe_to_restore:
            for i, previous in changed_modes.items():
                try:
                    cryo.query(f"LOOP {i}:TYPE {previous}")
                except Exception as error:
                    print(f"Could not restore loop {i}: {error}")

        if dmm is not None:
            dmm.close()

        if connected:
            cryo.disconnect()

        rm.close()
        # Save the final figure
        if "fig" in locals() and csv_path.exists():
            fig.savefig(csv_path.with_suffix(".png"), dpi=300, bbox_inches="tight")
        
        
        plt.ioff()
        plt.show(block=False)  # Leave the plot available; do not block the next phase.

        print(f"Data saved to: {csv_path}")

        # Do not run the next phase if we could not confirm control stopped.
        if shutdown_failed:
            raise RuntimeError(
                "Could not confirm that heater control stopped. "
                "The remaining experiments have been cancelled."
            )

# ============================================================
# RUN ALL EXPERIMENTS IN ORDER
# ============================================================

# After each function call returns normally, the next phase starts.
# A phase does NOT time out: it must meet the target and hold requirement.
# Errors stop the sequence; do not automatically retry a heater failure.
try:
    for experiment in EXPERIMENTS:
        run_experiment(experiment)
except KeyboardInterrupt:
    print("Experiment sequence cancelled; no further phases started.")
