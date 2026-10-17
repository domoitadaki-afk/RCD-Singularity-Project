"""
RCD Reviewer — Main Menu
Single-file Tkinter launcher. No external dependencies.

Three buttons:
  1. Topics    -> opens a submenu listing every topic reviewer app
  2. Formulas  -> opens a submenu listing every formula practice app
  3. Website   -> opens the flowchart website in your default browser

Every sub-app is launched as a separate process, so a "Back to Main Menu"
button is always available without disturbing the app you opened.
"""

import os
import sys
import subprocess
import webbrowser
import tkinter as tk
from tkinter import font as tkfont

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOPICS_DIR = os.path.join(BASE_DIR, "Topics")
FORMULAS_DIR = os.path.join(BASE_DIR, "Formulas")

# Flowchart website (opens in default browser)
WEBSITE_URL = "https://j2dadeee.github.io/RCD-Flowcharts/"

# (filename, display label) for each review mode
TOPIC_APPS = [
    ("1_gravity_load_analysis.py",            "1. Gravity Load Analysis (Tributary Loads)"),
    ("2_SRB_DRB_Anslysis.py",                 "2. SRB / DRB Beam Analysis"),
    ("3_singly_reinforced_concrete_design.py","3. Singly Reinforced Beam Design"),
    ("4_doubly_reinforced_concrete_design.py","4. Doubly Reinforced Beam Design"),
    ("5_t-beams_analysis.py",                 "5. T-Beam Analysis (Case 1)"),
    ("6_t-beams_case2.py",                    "6. T-Beam Analysis (Case 2)"),
    ("7_t-beams_design.py",                   "7. T-Beam Design"),
    ("8_shear_reinforcement.py",              "8. Shear Reinforcement Design"),
    ("9_one_way_slab.py",                     "9. One-Way Slab Design"),
    ("10_column.py",                          "10. Column (Spiral) Reviewer"),
]

FORMULA_APPS = [
    ("1_strength_reduction_factor.py", "1. Strength Reduction Factor (φ)"),
    ("2_beta.py",                      "2. Beta 1 (β₁) Determination"),
    ("3_minimum_depth.py",             "3. Beam Minimum Depth (ACI 318)"),
    ("4_flexural_resistance.py",       "4. Flexural Resistance & Rho"),
    ("5_rho.py",                       "5. Reinforcement Ratios (ρ)"),
    ("6_rebar_spacing.py",             "6. Rebar / Stirrup Spacing"),
    ("7_effective_beam_width.py",      "7. Effective Beam Width (bf)"),
    ("8_psmin_spiral_column.py",       "8. ρs,min — Minimum Spiral Ratio"),
    ("9_spiral_spacing.py",            "9. Spiral Spacing (S)"),
]

# ------------------------------------------------------------------
# COLORS / STYLE
# ------------------------------------------------------------------
BG        = "#1e2430"   # main background
CARD      = "#2a3242"   # button background
CARD_HOV  = "#39465c"   # hover background
FG        = "#eef2f7"
ACCENT    = "#4f8cff"
SUB       = "#9fb0c3"


def launch_app(folder, filename):
    """Run a reviewer app in its own process so the menu stays usable."""
    path = os.path.join(folder, filename)
    if not os.path.isfile(path):
        return False
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([sys.executable, path], cwd=folder, **kwargs)
        return True
    except OSError:
        return False


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

    def _list_screen(self, header, subtitle, folder, apps, icon_color):
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

        for fname, label in apps:
            def cmd(f=fname):
                ok = launch_app(folder, f)
                if not ok:
                    self.bell()

            self._menu_button(inner, label, "", cmd, color=icon_color)

        self._back_button()

    def show_topics(self):
        self._list_screen("Topics", "Choose a topic reviewer:",
                          TOPICS_DIR, TOPIC_APPS, ACCENT)

    def show_formulas(self):
        self._list_screen("Formulas", "Choose a formula drill:",
                          FORMULAS_DIR, FORMULA_APPS, "#7bd88f")

    def open_website(self):
        try:
            webbrowser.open(WEBSITE_URL, new=2)
        except Exception:
            pass  # no browser available; nothing else to do


if __name__ == "__main__":
    app = MainMenu()
    app.mainloop()
