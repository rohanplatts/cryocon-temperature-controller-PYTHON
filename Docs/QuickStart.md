# Quick start

1. Put the **current** `cryo-control.py` and `cryocon-env.yml` in the same working folder. Open Anaconda Prompt there:

   ```bat
   conda env create -f cryocon-env.yml
   conda activate cryocon-env
   ```

2. Open the code in your favourite IDE and run it in that conda environment. For Spyder, you will that the downloaded spyder version matches your spyder version. it defaults to 6.1.3. For Spyder, open **Consoles → New console in environment → cryocon-env**. The YAML targets Spyder **6.1.3**; other Spyder releases may require a different compatible `spyder-kernels` version.
3. Set `CRYO_PORT`, `DMM_ADDRESS`, `DATA_DIR` and `MATERIAL`. Edit `EXPERIMENTS` to specify each phase's name, sensor, heater loop, mode, target (K) and rate (K/min). Set `TARGET_TOLERANCE_K` and `HOLD_SECONDS`.
4. Verify wiring, sensor units, cooling, PID/heater limits and independent protection. Start with `ENABLE_CONTROL = False` to test acquisition; interrupt that test manually.
5. Run with **F5**. With control enabled, each phase records its own CSV until the feedback sensor stays within tolerance for the hold duration, saves its final plot as a PNG, and then starts the next phase. **No timeout exists.** Ctrl+C or errors cancel the remaining phases. Confirm physical control is OFF after stopping.

[Full setup](comprehensive-docs/setup.md) · [How it works](comprehensive-docs/code-explanation.md) · [Usage](comprehensive-docs/usage.md)
