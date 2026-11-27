# CryoCon temperature controller — Python

Python automation for temperature-dependent four-wire resistance measurements with a **CryoCon Model 22C** and a VISA-connected digital multimeter.

The current `cryo-control.py` runs a configurable **sequence of temperature phases** (for example, cooldown then warmup). Each phase has its own feedback sensor, heater loop, setpoint, ramp rate, live plot, CSV file and final PNG image.

## Documentation

- [UofT APL specific tutorial](Docs/UofT-RES-specific.md)
- [Quick start](Docs/QuickStart.md) — experienced users, under 200 words.
- [Beginner setup and Spyder](Docs/Comprehensive-docs/Setup.md) — installation, environment and instrument addresses.
- [How the code works](Docs/Comprehensive-docs/Code-explanation.md) — annotated architecture, SCPI and source explanation.
- [Usage guide](Docs/Comprehensive-docs/Usage.md) — planning sweeps, monitoring, saving results and troubleshooting.

Start with [cryo-control.py](cryo-control.py); the supplied Conda specification is [cryocon-env.yml](cryocon-env.yml).

**Safety:** Example temperatures and wiring are laboratory-specific. Cooling requires external refrigeration. Verify heater/sensor mapping, PID tuning, power limits and independent hardware protection before enabling control. The script has not been validated as a safety interlock.
