# Build RCD Reviewer as a fully self-contained folder

Everything here is pure Tkinter + Python standard library, so PyInstaller
compiles each app cleanly with `--onefile --windowed` — no hidden imports,
no data files to bundle.

## On Windows (what your friends will run)

1. Install PyInstaller once:
   ```
   pip install pyinstaller
   ```
2. Double-click **build_all.bat** (or run it from a terminal in this folder).
3. Wait for it to finish. It compiles the menu plus all 10 Topics apps and
   9 Formula apps into one folder:

   ```
   RCD Reviewer/
   ├── RCDReviewer.exe        ← friends double-click this
   ├── Topics/
   │   ├── 1_gravity_load_analysis.exe
   │   └── ... (10 exes)
   └── Formulas/
       ├── 1_strength_reduction_factor.exe
       └── ... (9 exes)
   ```

4. Zip the whole **RCD Reviewer** folder and share it. No Python needed on
   their PCs — keep the folder structure intact (the menu launches the exes
   by path).

## How the launcher knows what to do

- Running `python main_menu.py` normally → launches the `.py` scripts.
- Running the frozen exe (`sys.frozen` is set) → automatically launches the
  matching `.exe` in `Topics\` / `Formulas\` instead.
- The 🌐 Website button calls `webbrowser.open()` — works identically in dev
  and compiled builds.

## Notes / gotchas

- **Build on Windows if the target is Windows.** PyInstaller cannot
  cross-compile; the exe matches the OS you build on.
- Expect ~10–15 MB per exe (each bundles its own Python + Tkinter), so the
  zipped folder will be roughly 150–250 MB before compression. If size
  matters, build the sub-apps with `--onedir` instead and share via a zip —
  same idea, just more small files.
- First launch of an onefile exe is a few seconds slower (it unpacks itself
  to a temp folder); after that it's instant.
- Windows SmartScreen may warn about unsigned exes since they're freshly
  built — click "More info → Run anyway". This is normal for personal builds.
- Adding a new reviewer app later? Just drop the `.py` into `Topics/` or
  `Formulas/`, add one line to `TOPIC_APPS`/`FORMULA_APPS` in main_menu.py,
  and re-run build_all.bat — it picks up every `.py` in those folders
  automatically.
