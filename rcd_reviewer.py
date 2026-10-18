"""
RCD Reviewer — All-in-One (single-file build compatible)

This is the entry point for building ONE self-contained executable:

    pyinstaller --onefile --windowed --name RCDReviewer rcd_reviewer.py

It bundles every topic reviewer and formula drill directly into the exe
(no external .py files needed). The main menu has three buttons:

  1. Topics    -> submenu of all topic reviewers
  2. Formulas  -> submenu of all formula drills
  3. Website   -> opens the flowchart site in your default browser

Each sub-app opens in its own window, so you can always press
"Back to Main Menu" on the launcher to switch review modes without
closing anything.

Run it either as this file (python rcd_reviewer.py) or via the frozen exe.
"""

import os
import sys
import runpy
import subprocess
import webbrowser
import tkinter as tk
from tkinter import font as tkfont

# ------------------------------------------------------------------
# PyInstaller single-exe compatibility (must run before any app is loaded)
# ------------------------------------------------------------------
import sys, os

def _ensure_tkinter_submodules():
    """Make every tkinter submodule importable inside a PyInstaller --onefile
    build — THE fix for "reviewers won't open from the built exe".

    Root cause (verified against a real frozen build): PyInstaller extracts
    the stdlib `tkinter` *sources* next to the bundled app sources, e.g.
    _MEIPASS/tkinter/__init__.py alongside _MEIPASS/Topics/*.py. When an
    embedded script does `from tkinter import ttk`, Python resolves the
    `tkinter` package from that extracted folder, whose __path__ contains no
    compiled submodules — ttk/messagebox/etc. live only in the bundle's
    internal archive — so the import dies with
    "cannot import name 'ttk' from 'tkinter'".

    Fix: load each submodule directly from its source file with
    SourceFileLoader (bypassing the broken package-path lookup), register it
    in sys.modules under both `tkinter.X` and bare `X`, and attach it to the
    tkinter module object so `from tkinter import X` attribute lookups hit it
    without any finder being consulted at all.
    """
    import importlib
    import importlib.machinery
    import importlib.util
    import tkinter  # noqa: F401  (ensures the package itself is loaded)
    keep = []  # strong refs so nothing gets evicted from sys.modules
    for name in ("ttk", "messagebox", "filedialog", "simpledialog",
                 "colorchooser", "font", "scrolledtext", "commondialog",
                 "constants", "dialog", "dnd"):
        full = "tkinter." + name
        if full in sys.modules:
            mod = sys.modules[full]
        else:
            mod = None
            # 1) normal import first (works in dev / non-frozen runs)
            try:
                mod = importlib.import_module(full)
            except Exception:
                mod = None
            # 2) frozen fallback: exec the extracted .py file directly
            if mod is None:
                meipass = getattr(sys, "_MEIPASS", "")
                candidates = [os.path.join(meipass, "tkinter", name + ".py")] if meipass else []
                try:
                    candidates.append(os.path.join(os.path.dirname(importlib.util.find_spec("tkinter").origin), name + ".py"))
                except Exception:
                    pass
                for file in candidates:
                    if os.path.isfile(file):
                        try:
                            loader = importlib.machinery.SourceFileLoader(full, file)
                            spec = importlib.util.spec_from_loader(full, loader)
                            mod = importlib.util.module_from_spec(spec)
                            sys.modules[full] = mod
                            loader.exec_module(mod)
                        except Exception:
                            sys.modules.pop(full, None)
                            mod = None
                        if mod is not None:
                            break
            if mod is None:
                continue
        sys.modules[full] = mod
        sys.modules.setdefault(name, mod)      # bare-name safety net
        setattr(tkinter, name, mod)            # makes `from tkinter import X` work
        keep.append(mod)
    return keep

# Imported eagerly at startup AND again right before each embedded app runs
# (run_app_inline), because in a frozen single-file build the reviewer apps'
# `from tkinter import ttk, messagebox ...` lines otherwise fail with
# "cannot import name 'ttk' from 'tkinter'".
_TK_SUBMODULES = _ensure_tkinter_submodules()

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
WEBSITE_URL = "https://j2dadeee.github.io/RCD-Flowcharts/"

TOPIC_APPS = [
    ("Topics/1_gravity_load_analysis.py",            "1. Gravity Load Analysis (Tributary Loads)"),
    ("Topics/2_SRB_DRB_Anslysis.py",                 "2. SRB / DRB Beam Analysis"),
    ("Topics/3_singly_reinforced_concrete_design.py","3. Singly Reinforced Beam Design"),
    ("Topics/4_doubly_reinforced_concrete_design.py","4. Doubly Reinforced Beam Design"),
    ("Topics/5_t-beams_analysis.py",                 "5. T-Beam Analysis (Case 1)"),
    ("Topics/6_t-beams_case2.py",                    "6. T-Beam Analysis (Case 2)"),
    ("Topics/7_t-beams_design.py",                   "7. T-Beam Design"),
    ("Topics/8_shear_reinforcement.py",              "8. Shear Reinforcement Design"),
    ("Topics/9_one_way_slab.py",                     "9. One-Way Slab Design"),
    ("Topics/10_column.py",                          "10. Column (Spiral) Reviewer"),
]

FORMULA_APPS = [
    ("Formulas/1_strength_reduction_factor.py", "1. Strength Reduction Factor (φ)"),
    ("Formulas/2_beta.py",                      "2. Beta 1 (β₁) Determination"),
    ("Formulas/3_minimum_depth.py",             "3. Beam Minimum Depth (ACI 318)"),
    ("Formulas/4_flexural_resistance.py",       "4. Flexural Resistance & Rho"),
    ("Formulas/5_rho.py",                       "5. Reinforcement Ratios (ρ)"),
    ("Formulas/6_rebar_spacing.py",             "6. Rebar / Stirrup Spacing"),
    ("Formulas/7_effective_beam_width.py",      "7. Effective Beam Width (bf)"),
    ("Formulas/8_psmin_spiral_column.py",       "8. ρs,min — Minimum Spiral Ratio"),
    ("Formulas/9_spiral_spacing.py",            "9. Spiral Spacing (S)"),
]

ALL_APPS = TOPIC_APPS + FORMULA_APPS

# ------------------------------------------------------------------
# COLORS / STYLE
# ------------------------------------------------------------------
BG        = "#1e2430"   # main background
CARD      = "#2a3242"   # button background
CARD_HOV  = "#39465c"   # hover background
FG        = "#eef2f7"
ACCENT    = "#4f8cff"
SUB       = "#9fb0c3"


def _script_dir():
    """Folder containing this script (dev) or the .exe (frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _script_dir()


def resolve_app_path(rel_path):
    """Locate a bundled app's source file.

    Order of search:
      1. PyInstaller bundle (_MEIPASS) — present when built with
         `--add-data "Topics;." --add-data "Formulas;."` style options,
         i.e. the fully self-contained single-exe build.
      2. Next to the script/exe — plain source-tree run, or a folder
         distribution where the .py files sit beside the launcher.
    """
    candidates = [
        os.path.join(getattr(sys, "_MEIPASS", ""), rel_path),
        os.path.join(BASE_DIR, rel_path),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


# ------------------------------------------------------------------
# APP LAUNCHING
# ------------------------------------------------------------------
def launch_app_in_process(rel_path):
    """Open the app in a NEW process that runs this same executable.

    Works identically whether we are running from source or frozen into
    a single .exe — the child re-enters this module with --run-app and
    calls mainloop itself, so each reviewer gets its own window while
    the menu stays available.
    """
    if getattr(sys, "frozen", False):
        # Re-invoke THIS executable in child mode (fully self-contained).
        cmd = [sys.executable, "--run-app", rel_path]
    else:
        cmd = [sys.executable, os.path.abspath(__file__), "--run-app", rel_path]
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
        return True
    except OSError:
        return False


def run_app_child():
    """Child mode (--run-app <path>): execute ONE reviewer app in THIS fresh
    interpreter and exit when its window closes.

    A brand-new process is used deliberately: inside the long-lived menu
    process, PyInstaller's frozen-importer state makes late runtime imports
    of tkinter submodules unreliable. A freshly booted child that pre-loads
    every tkinter submodule at startup (see _ensure_tkinter_submodules) runs
    the app script with plain runpy — verified working in frozen builds.
    """
    try:
        _idx = sys.argv.index("--run-app")
        rel_path = sys.argv[_idx + 1]
    except (ValueError, IndexError):
        sys.exit("Usage: RCDReviewer --run-app <relative/app/path.py>")
    path = resolve_app_path(rel_path)
    if path is None:
        sys.exit(f"App not found in bundle: {rel_path}")
    # Strip our own flag so the embedded app sees clean argv.
    sys.argv = sys.argv[:_idx] + sys.argv[_idx + 2:]
    # Belt & suspenders: ensure submodules are loaded right before exec.
    _ensure_tkinter_submodules()
    runpy.run_path(path, run_name="__main__")
    sys.exit(0)


# ------------------------------------------------------------------
# MAIN MENU
# ------------------------------------------------------------------
class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD Reviewer — Main Menu")
        self.configure(bg=BG)
        self.geometry("560x520")
        self.minsize(480, 440)

        self.big_font = tkfont.Font(family="Segoe UI", size=20, weight="bold")
        self.title_font = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.body_font = tkfont.Font(family="Segoe UI", size=11)
        self.small_font = tkfont.Font(family="Segoe UI", size=9)

        self.current_screen = None
        self.show_main()

    # --------------------------------------------------------------
    # Shared widgets
    # --------------------------------------------------------------
    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _header(self, title, subtitle=""):
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=24, pady=(22, 8))
        tk.Label(head, text=title, font=self.big_font, bg=BG, fg=FG).pack(anchor="w")
        if subtitle:
            tk.Label(head, text=subtitle, font=self.small_font,
                     bg=BG, fg=SUB).pack(anchor="w", pady=(2, 0))

    def _menu_button(self, parent, text, sub, command, color=ACCENT):
        btn = tk.Button(parent, text=text + "\n" + sub, font=self.body_font,
                        bg=CARD, fg=FG, activebackground=CARD_HOV,
                        activeforeground=FG, relief="flat", bd=0,
                        highlightthickness=0, cursor="hand2",
                        justify="left", anchor="w", padx=18, pady=12,
                        command=command)
        btn.pack(fill="x", padx=24, pady=7, ipady=4)

        def on_enter(e, b=btn, c=color):
            b.configure(bg=CARD_HOV, fg=c)

        def on_leave(e, b=btn):
            b.configure(bg=CARD, fg=FG)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _back_button(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", side="bottom", padx=24, pady=(6, 20))
        btn = tk.Button(bar, text="←  Back", font=self.title_font,
                        bg="#3b2f4a", fg=FG, activebackground="#4d3d61",
                        activeforeground=FG, relief="flat", bd=0,
                        highlightthickness=0, cursor="hand2",
                        padx=22, pady=8, command=self.show_main)
        btn.pack(side="left")
        btn.bind("<Enter>", lambda e: btn.configure(bg="#4d3d61"))
        btn.bind("<Leave>", lambda e: btn.configure(bg="#3b2f4a"))

    # --------------------------------------------------------------
    # Screens
    # --------------------------------------------------------------
    def show_main(self):
        self._clear()
        self.current_screen = "main"
        self._header("RCD Reviewer", "Pick a review mode to practice.")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, pady=(14, 0))

        self._menu_button(body, "📘  Topics",
                          "Step-by-step reviewers: loads, beams, slabs, columns…",
                          self.show_topics)
        self._menu_button(body, "🧮  Formulas",
                          "Quick drill apps for individual formulas (φ, β₁, ρ, bf…)",
                          self.show_formulas, color="#7bd88f")
        self._menu_button(body, "🌐  Website — Flowcharts",
                          f"Open {WEBSITE_URL} in your browser",
                          self.open_website, color="#ffb86c")

        tk.Label(self, text="Tip: every app opens in its own window — press Back any time.",
                 font=self.small_font, bg=BG, fg=SUB).pack(pady=(4, 0))

    def _list_screen(self, header, subtitle, apps, icon_color):
        self._clear()
        self.current_screen = header
        self._header(header, subtitle)

        # scrollable list in case there are many entries
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        for rel_path, label in apps:
            def cmd(p=rel_path):
                ok = launch_app_in_process(p)
                if not ok:
                    self.bell()

            self._menu_button(inner, label, "", cmd, color=icon_color)

        self._back_button()

    def show_topics(self):
        self._list_screen("Topics", "Choose a topic reviewer:",
                          TOPIC_APPS, ACCENT)

    def show_formulas(self):
        self._list_screen("Formulas", "Choose a formula drill:",
                          FORMULA_APPS, "#7bd88f")

    def open_website(self):
        try:
            webbrowser.open(WEBSITE_URL, new=2)
        except Exception:
            pass  # no browser available; nothing else to do


# ------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------
if "--run-app" in sys.argv:
    run_app_child()
else:
    app = MainMenu()
    app.mainloop()
