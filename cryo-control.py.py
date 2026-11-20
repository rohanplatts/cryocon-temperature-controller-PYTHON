
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

MATERIAL = "Lead"
DATA_DIR = Path(r"T:\HMData")

CRYO_PORT = "COM3"
DMM_ADDRESS = "USB0::0x2A8D::0x1301::MY60057353::INSTR"

# Temperature control
CONTROL_CHANNEL = "A"
HEATER_LOOP = 1
CONTROL_MODE = "RAMPP"

SETPOINT_K = 300.0
RAMP_RATE = 1.0
ENABLE_CONTROL = True

# Safety and measurements
MAX_SAFE_TEMP_K = 305.0
SCAN_INTERVAL = 0.5
PLOT_EVERY = 1

timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
csv_path = DATA_DIR / f"RvsT_{timestamp}_{MATERIAL}.csv"


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

"""
Below initial connection to the instruments follows the original code. 
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

            # Maintain measurement interval
            time.sleep(max(
                0,
                SCAN_INTERVAL - (time.monotonic() - scan_start)
            ))


except KeyboardInterrupt:
    print("\nMeasurement stopped by user.")

except Exception as error:
    print(f"\nERROR: {error}")
    raise


finally:
    # ========================================================
    # CLEANUP
    # ========================================================

    safe_to_restore = not control_attempted

    if connected and control_attempted:
        try:
            cryo.disable()
            print("Temperature control stopped.")
            safe_to_restore = True
        except Exception as error:
            print("WARNING: Could not stop controller:", error)
            print("Use the physical STOP button.")

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

    plt.ioff()
    plt.show()

    print(f"Data saved to: {csv_path}")
