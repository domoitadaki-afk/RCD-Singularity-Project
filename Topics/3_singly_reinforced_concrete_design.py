"""
RCD SRB Design Reviewer — NSCP 2015 Ultimate Strength Design
Single-file Tkinter app. No external dependencies.

Flow:
  Setup (given toggle + randomize) -> Step 1..7 -> Summary
Doubly-reinforced detection stops the review at Step 5.

Step 7 now uses a dropdown to pick the bar diameter; nb, s, s_min
are then computed for whichever bar you chose.
"""

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import math
import random

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
PHI_FLEX = 0.90
GAMMA_C = 23.6           # kN/m^3
TOL = 0.005              # 0.5% relative tolerance
BAR_SIZES = [16, 20, 25, 28, 32]   # standard diameters in mm
DAGG_DEFAULT = 19.0      # mm

# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------
def close(a, b, tol=TOL):
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= tol

def fmt(x, n=3):
    return f"{x:.{n}f}"

def parse(text):
    if text is None:
        return None
    s = str(text).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None

def round_up_to(x, step):
    return math.ceil(x / step) * step

def beta1(fc):
    if fc <= 28:
        return 0.85
    elif fc <= 55:
        return 0.85 - 0.05 * (fc - 28) / 7.0
    else:
        return 0.65

def compute_bar_fit(As, b, cc, dagg, db):
    """For a chosen bar diameter db, return (nb, s, s_min).
    nb  = number of bars (>=2)
    s   = clear spacing between bars (mm), using dv = 10 mm stirrups
    s_min = max(50, db, 4/3 * dagg)
    """
    dv = 10.0
    area_one = math.pi * db * db / 4.0
    nb = math.ceil(As / area_one)
    if nb < 2:
        nb = 2
    if nb > 1:
        s = (b - 2 * cc - 2 * dv - nb * db) / (nb - 1)
    else:
        s = 999.0
    s_min = max(50.0, db, 4.0 * dagg / 3.0)
    return nb, s, s_min

# ------------------------------------------------------------------
# SOLVER
# ------------------------------------------------------------------
def solve_all(p):
    """Given dict p with L, DL, LL, fc, fy, cc, dagg, and optionally b_given, d_given.
    Returns dict of all step values, or a dict with 'drb' flag if doubly-reinforced."""

    L  = p["L"]; DL = p["DL"]; LL = p["LL"]
    fc = p["fc"]; fy = p["fy"]; cc = p["cc"]; dagg = p["dagg"]
    b_given = p.get("b_given")
    d_given = p.get("d_given")

    # ---------- Step 1: factored moment ----------
    wu = 1.2 * DL + 1.6 * LL
    Mu_init = wu * (L ** 2) / 8.0       # simply supported

    out = {
        "L": L, "DL": DL, "LL": LL, "fc": fc, "fy": fy, "cc": cc, "dagg": dagg,
        "wu": wu, "Mu_init": Mu_init,
    }

    # ---------- Step 2: rho limits ----------
    rho_min_1 = 1.4 / fy
    rho_min_2 = 0.25 * math.sqrt(fc) / fy
    rho_min = max(rho_min_1, rho_min_2)
    b1 = beta1(fc)
    rho_max = (3.0 / 8.0) * (0.85 * b1 * fc / fy)
    rho_act_init = 0.75 * rho_max

    out["rho_min_1"] = rho_min_1
    out["rho_min_2"] = rho_min_2
    out["rho_min"] = rho_min
    out["beta1"] = b1
    out["rho_max"] = rho_max
    out["rho_act_init"] = rho_act_init

    # ---------- Step 3: sizing (only if b, d are NOT given) ----------
    if b_given is None or d_given is None:
        R_init = PHI_FLEX * rho_act_init * fy * (1 - rho_act_init * fy / (1.7 * fc))
        out["R_init"] = R_init
        Mu_Nmm = Mu_init * 1e6
        b_raw = (Mu_Nmm / (2.25 * R_init)) ** (1.0 / 3.0)
        b_round = round_up_to(b_raw, 10.0)
        d_from_b = 1.5 * b_round
        D_round = round_up_to(d_from_b + cc, 10.0)
        out["b_raw"] = b_raw
        out["b"] = b_round
        out["d"] = d_from_b
        out["D"] = D_round
        out["sizing_done"] = True
    else:
        out["b"] = b_given
        out["d"] = d_given
        out["D"] = d_given + cc
        out["sizing_done"] = False

    b = out["b"]; d = out["d"]; D = out["D"]

    # ---------- Step 4: self-weight adjustment ----------
    if out["sizing_done"]:
        w_beam = GAMMA_C * (b / 1000.0) * (D / 1000.0)   # kN/m
        M_beam = w_beam * (L ** 2) / 8.0
        Mu_updated = Mu_init + 1.2 * M_beam
        out["w_beam"] = w_beam
        out["M_beam"] = M_beam
        out["Mu_updated"] = Mu_updated
        out["Mu_used"] = Mu_updated
    else:
        out["w_beam"] = None
        out["M_beam"] = None
        out["Mu_updated"] = None
        out["Mu_used"] = Mu_init

    # ---------- Step 5: R_actual and rho_actual ----------
    Mu_used = out["Mu_used"]
    R_actual = (Mu_used * 1e6) / (b * d * d)
    out["R_actual"] = R_actual

    A = 1.0
    B = -(1.7 * fc) / fy
    C = (1.7 * fc * R_actual) / (PHI_FLEX * fy * fy)
    disc = B * B - 4 * A * C
    if disc < 0:
        out["drb"] = True
        return out
    rho_actual = (-B - math.sqrt(disc)) / (2 * A)
    out["rho_actual_computed"] = rho_actual

    if rho_actual < rho_min:
        rho_govern = rho_min
        out["governing"] = "rho_min"
    elif rho_actual > rho_max:
        out["drb"] = True
        return out
    else:
        rho_govern = rho_actual
        out["governing"] = "rho_actual"

    out["rho_govern"] = rho_govern

    # ---------- Step 6: As ----------
    As = rho_govern * b * d
    out["As"] = As

    # ---------- Step 7: bar selection (auto-pick, used as "app suggestion") ----------
    chosen_db = None
    chosen_nb = None
    chosen_s = None
    for db in BAR_SIZES:
        nb, s, req_s = compute_bar_fit(As, b, cc, dagg, db)
        if nb > 7:
            continue
        if s >= req_s:
            chosen_db = db; chosen_nb = nb; chosen_s = s
            break

    if chosen_db is None:
        chosen_db = BAR_SIZES[-1]
        chosen_nb, chosen_s, _ = compute_bar_fit(As, b, cc, dagg, chosen_db)

    out["bar_db"] = chosen_db
    out["bar_nb"] = chosen_nb
    out["bar_s"] = chosen_s
    out["s_min"] = max(50.0, chosen_db, 4.0 * dagg / 3.0)
    out["spacing_ok"] = chosen_s >= out["s_min"]

    return out

# ------------------------------------------------------------------
# RANDOMIZER
# ------------------------------------------------------------------
def random_problem(given_mode):
    """given_mode: 'sizing' (b,d unknown) or 'given' (b,d known)"""
    L  = round(random.uniform(4.0, 9.0), 1)
    DL = round(random.uniform(8.0, 22.0), 1)
    LL = round(random.uniform(8.0, 20.0), 1)
    fc = random.choice([21.0, 24.0, 27.6, 28.0, 32.0])
    fy = random.choice([276.0, 345.0, 414.0])
    cc = random.choice([40.0, 50.0])
    dagg = random.choice([19.0, 25.0])

    p = {"L": L, "DL": DL, "LL": LL, "fc": fc, "fy": fy, "cc": cc, "dagg": dagg}

    if given_mode == "sizing":
        p["b_given"] = None
        p["d_given"] = None
    else:
        b = random.choice([250.0, 300.0, 350.0, 400.0])
        d = random.choice([400.0, 450.0, 500.0, 540.0, 600.0])
        p["b_given"] = b
        p["d_given"] = d
    return p

# ------------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------------
class SRBDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD SRB Design Reviewer")

        # ---- fit the window to the actual screen ----
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = max(760, min(1240, sw - 40))
        win_h = max(520, min(840, sh - 120))
        x = max(0, (sw - win_w) // 2)
        y = max(0, (sh - win_h) // 3)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(min(760, win_w), min(520, win_h))

        self.problem = {
            "L": 4.0, "DL": 10.0, "LL": 10.0,
            "fc": 27.6, "fy": 276.0, "cc": 50.0, "dagg": 19.0,
            "b_given": None, "d_given": None,
        }
        self.solution = None
        self.page = 0
        self.max_page = 8
        self.user_inputs = {}
        self.passed = set()
        self.revealed = set()
        self.history_lines = []
        self.mode = "sizing"

        # layout helpers / state
        self._given_cols = 0
        self._resize_job = None
        self._last_given_width = 0
        self._hist_visible = win_w >= 1080

        self._build_layout()
        self._build_history()
        self._build_top_given()
        self._build_nav()
        self._show_page(0)

        if not self._hist_visible:
            self.right.pack_forget()

        self.bind("<Configure>", self._on_root_configure)

    # ==============================================================
    # WINDOW / SCROLL HELPERS
    # ==============================================================
    def _on_root_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(200, self._relayout_given)

    def _relayout_given(self):
        self._resize_job = None
        w = self.winfo_width()
        if abs(w - self._last_given_width) < 30:
            return
        self._last_given_width = w
        self._refresh_top_given()

    def _on_wheel(self, event):
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            w = None
        inside = False
        node = w
        while node is not None:
            if node is self.step_canvas:
                inside = True
                break
            try:
                node = node.master
            except Exception:
                node = None
        if not inside:
            return

        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            d = event.delta
            if abs(d) >= 120:
                delta = int(-d / 120)
            else:
                delta = -1 if d > 0 else 1
        self.step_canvas.yview_scroll(delta, "units")

    def toggle_history(self):
        if self._hist_visible:
            self.right.pack_forget()
            self._hist_visible = False
        else:
            self.right.pack(side="right", fill="y")
            self._hist_visible = True
        self._last_given_width = 0
        self._refresh_top_given()

    # ==============================================================
    # PERSISTENT STRINGVAR
    # ==============================================================
    def _mk_var(self, key, default=""):
        if key in self.user_inputs:
            init = self.user_inputs[key]
        else:
            init = default
            self.user_inputs[key] = init
        v = tk.StringVar(value=init)
        def _cb(*a):
            self.user_inputs[key] = v.get()
        v.trace_add("write", _cb)
        return v

    # ==============================================================
    # LAYOUT
    # ==============================================================
    def _build_layout(self):
        self.topbar = tk.Frame(self, bg="#eef3fa",
                               highlightthickness=1, highlightbackground="#b8c4d6")
        self.topbar.pack(side="top", fill="x")

        self.bottom = tk.Frame(self, bg="#e8e8e8",
                               highlightthickness=1, highlightbackground="#bbb")
        self.bottom.pack(side="bottom", fill="x")

        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)

        self.left = tk.Frame(outer, bg="#f4f4f4")
        self.left.pack(side="left", fill="both", expand=True)

        self.right = tk.Frame(outer, width=250, bg="#fafafa",
                              highlightthickness=1, highlightbackground="#ccc")
        self.right.pack(side="right", fill="y")
        self.right.pack_propagate(False)

        # scrollable step area
        self.step_canvas = tk.Canvas(self.left, bg="#f4f4f4",
                                     highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self.left, orient="vertical",
                            command=self.step_canvas.yview)
        self.step_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.step_canvas.pack(side="left", fill="both", expand=True)

        self.step_area = tk.Frame(self.step_canvas, bg="#f4f4f4")
        self._step_win = self.step_canvas.create_window(
            (12, 12), window=self.step_area, anchor="nw")

        self.step_area.bind(
            "<Configure>",
            lambda e: self.step_canvas.configure(
                scrollregion=self.step_canvas.bbox("all")))
        self.step_canvas.bind(
            "<Configure>",
            lambda e: self.step_canvas.itemconfigure(
                self._step_win, width=max(200, e.width - 24)))

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

    # ==============================================================
    # TOP GIVEN PANEL
    # ==============================================================
    def _build_top_given(self):
        tk.Label(self.topbar, text="GIVEN  /  PROPERTIES", font=("Segoe UI", 9, "bold"),
                 bg="#eef3fa", anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        self.given_row = tk.Frame(self.topbar, bg="#eef3fa")
        self.given_row.pack(fill="x", padx=10, pady=(0, 6))
        self._refresh_top_given()

    def _refresh_top_given(self):
        for w in self.given_row.winfo_children():
            w.destroy()
        p = self.problem
        items = [
            ("L",  f"{p['L']:.2f} m"),
            ("DL", f"{p['DL']:.2f} kN/m"),
            ("LL", f"{p['LL']:.2f} kN/m"),
            ("f'c", f"{p['fc']:.1f} MPa"),
            ("fy",  f"{p['fy']:.0f} MPa"),
            ("cc",  f"{p['cc']:.0f} mm"),
            ("dagg", f"{p['dagg']:.0f} mm"),
        ]
        if p.get("b_given") is not None and p.get("d_given") is not None:
            items.append(("b", f"{p['b_given']:.0f} mm"))
            items.append(("d", f"{p['d_given']:.0f} mm"))
        else:
            items.append(("b,d", "solve"))

        base_count = len(items)

        if self.solution:
            s = self.solution
            unlocked = self.passed | self.revealed
            extras = []
            if 1 in unlocked:
                extras.append(("Mu", f"{s['Mu_init']:.3f} kN·m"))
            if 2 in unlocked:
                extras.append(("ρmin", f"{s['rho_min']:.5f}"))
                extras.append(("ρmax", f"{s['rho_max']:.5f}"))
            if s.get("sizing_done") and 3 in unlocked:
                extras.append(("b×D", f"{s['b']:.0f}×{s['D']:.0f}"))
            if 5 in unlocked and "rho_govern" in s:
                extras.append(("ρgov", f"{s['rho_govern']:.5f}"))
            if 6 in unlocked and "As" in s:
                extras.append(("As", f"{s['As']:.1f} mm²"))
            if 7 in unlocked and "bar_db" in s:
                extras.append(("bars(auto)", f"{s['bar_nb']}–{s['bar_db']:.0f}mm"))
            items = items + extras

        width = self.winfo_width()
        if width < 100:
            width = self.winfo_screenwidth()
        usable = width - (270 if self._hist_visible else 40)
        usable = max(400, usable)
        cols = max(4, min(len(items), usable // 105))

        for i, (label, val) in enumerate(items):
            r, c = divmod(i, cols)
            is_extra = i >= base_count
            fg_lbl = "#0a5" if is_extra else "#345"
            fg_val = "#0a5" if is_extra else "#123"
            box = tk.Frame(self.given_row, bg="#eef3fa")
            box.grid(row=r, column=c, padx=4, pady=1, sticky="w")
            tk.Label(box, text=label, font=("Segoe UI", 8, "bold"),
                     bg="#eef3fa", fg=fg_lbl).pack(anchor="w")
            tk.Label(box, text=val,
                     font=("Consolas", 10, "bold" if is_extra else "normal"),
                     bg="#eef3fa", fg=fg_val).pack(anchor="w")

        self._given_cols = cols

    # ==============================================================
    # NAV BAR
    # ==============================================================
    def _build_nav(self):
        bar = tk.Frame(self.bottom, bg="#e8e8e8")
        bar.pack(fill="x", padx=8, pady=6)

        self.btn_hist = tk.Button(bar, text="History", width=9,
                                  command=self.toggle_history)
        self.btn_hist.pack(side="right", padx=2)
        self.btn_copy = tk.Button(bar, text="Copy Summary", width=13,
                                  command=self.copy_summary)
        self.btn_copy.pack(side="right", padx=2)

        self.btn_back = tk.Button(bar, text="◀ Back", width=8, command=self.go_back)
        self.btn_back.pack(side="left", padx=2)
        self.btn_check = tk.Button(bar, text="✓ Check", width=8, bg="#cde8cd",
                                   command=self.check_current)
        self.btn_check.pack(side="left", padx=2)
        self.btn_reveal = tk.Button(bar, text="Reveal", width=8, bg="#ffe9b3",
                                    command=self.reveal_current)
        self.btn_reveal.pack(side="left", padx=2)
        self.btn_next = tk.Button(bar, text="Next ▶", width=8, bg="#c9daf8",
                                  command=self.go_next)
        self.btn_next.pack(side="left", padx=2)
        self.btn_reset = tk.Button(bar, text="Reset", width=8, command=self.reset_all)
        self.btn_reset.pack(side="left", padx=(10, 2))

        self.status = tk.Label(bar, text="", bg="#e8e8e8", anchor="w",
                               font=("Segoe UI", 9, "italic"))
        self.status.pack(side="left", padx=8, fill="x", expand=True)

    # ==============================================================
    # HISTORY
    # ==============================================================
    def _build_history(self):
        tk.Label(self.right, text="HISTORY", font=("Segoe UI", 10, "bold"),
                 bg="#fafafa").pack(anchor="w", padx=8, pady=(8, 4))
        wrap = tk.Frame(self.right, bg="#fafafa")
        wrap.pack(fill="both", expand=True, padx=4, pady=4)
        self.hist_text = tk.Text(wrap, width=30, wrap="word", bg="#ffffff",
                                 relief="flat", font=("Consolas", 9))
        sb = ttk.Scrollbar(wrap, command=self.hist_text.yview)
        self.hist_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.hist_text.pack(side="left", fill="both", expand=True)
        self.hist_text.tag_config("green", foreground="#0a7a0a")
        self.hist_text.tag_config("yellow", foreground="#a67c00")
        self.hist_text.tag_config("gray", foreground="#666666")
        self.hist_text.tag_config("red", foreground="#a00")
        self.hist_text.tag_config("head", foreground="#1a1a1a",
                                  font=("Consolas", 9, "bold"))
        self.hist_text.configure(state="disabled")

    def log(self, text, tag="gray"):
        self.history_lines.append((text, tag))
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", text + "\n", tag)
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")

    def clear_history(self):
        self.history_lines.clear()
        self.hist_text.configure(state="normal")
        self.hist_text.delete("1.0", "end")
        self.hist_text.configure(state="disabled")

    # ==============================================================
    # PAGE SWITCHER
    # ==============================================================
    def _clear_step_area(self):
        for w in self.step_area.winfo_children():
            w.destroy()

    def _show_page(self, n):
        self.page = n
        self._clear_step_area()

        titles = {
            0: "Setup — Given / Properties",
            1: "Step 1 — Factored Moment Mu",
            2: "Step 2 — Reinforcement Ratios",
            3: "Step 3 — Beam Sizing (b, d, D)",
            4: "Step 4 — Self-Weight Adjustment",
            5: "Step 5 — Actual R and ρ",
            6: "Step 6 — Required Steel Area As",
            7: "Step 7 — Bar Selection and Spacing",
            8: "Summary",
        }
        tk.Label(self.step_area, text=titles[n],
                 font=("Segoe UI", 14, "bold"), bg="#f4f4f4").pack(anchor="w", pady=(0, 8))

        builder = {
            0: self._build_page_0,
            1: self._build_page_1,
            2: self._build_page_2,
            3: self._build_page_3,
            4: self._build_page_4,
            5: self._build_page_5,
            6: self._build_page_6,
            7: self._build_page_7,
            8: self._build_page_8,
        }[n]
        builder()

        try:
            self.step_canvas.yview_moveto(0)
        except Exception:
            pass

        self.btn_back.configure(state=("normal" if n > 0 else "disabled"))
        self.btn_next.configure(state=("normal" if n < self.max_page else "disabled"))
        checkable = n in (1, 2, 3, 4, 5, 6, 7)
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))

    def go_back(self):
        if self.page > 0:
            self._show_page(self.page - 1)

    def go_next(self):
        if self.page == 0 and self.solution is None:
            messagebox.showinfo("Start Review first",
                                "Click 'Start Review' to lock in the given values.")
            return
        if self.page in (1, 2, 3, 4, 5, 6, 7):
            if self.page not in self.passed and self.page not in self.revealed:
                if not messagebox.askyesno("Skip check?",
                        "You haven't checked this step. Continue anyway?"):
                    return
        if self.page == 5 and self.solution and self.solution.get("drb"):
            self._show_page(8)
            return
        if self.page == 2 and self.solution and not self.solution.get("sizing_done"):
            self._show_page(5)
            return
        if self.page < self.max_page:
            self._show_page(self.page + 1)

    def reset_all(self):
        if messagebox.askyesno("Reset", "Clear all progress and start fresh?"):
            self.user_inputs.clear()
            self.passed.clear()
            self.revealed.clear()
            self.clear_history()
            self.solution = None
            self._refresh_top_given()
            self._show_page(0)

    # ==============================================================
    # PAGE 0 — SETUP
    # ==============================================================
    def _build_page_0(self):
        f = self.step_area

        top = tk.Frame(f, bg="#f4f4f4")
        top.pack(anchor="w", pady=(0, 6))

        tk.Label(top, text="Mode:", bg="#f4f4f4",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.mode_var = self._mk_var("setup.mode", "sizing")
        ttk.Combobox(top, textvariable=self.mode_var,
                     values=["sizing", "given"], width=12,
                     state="readonly").pack(side="left", padx=8)
        tk.Label(top, text="(sizing = solve b,d,D  |  given = b,d entered)",
                 bg="#f4f4f4", fg="#666", font=("Segoe UI", 9)).pack(side="left")

        top2 = tk.Frame(f, bg="#f4f4f4")
        top2.pack(anchor="w", pady=(4, 10))
        tk.Button(top2, text="🎲 Randomize", bg="#ffe9b3", width=14,
                  command=self._randomize).pack(side="left", padx=2)
        tk.Button(top2, text="▶ Start Review", bg="#cde8cd", width=14,
                  command=self._start_review).pack(side="left", padx=6)

        tk.Label(f, text="Given / Properties (editable)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(6, 4))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w", pady=(0, 8))

        fields = [
            ("L (m)",       "L",  "{:.3f}"),
            ("DL (kN/m)",   "DL", "{:.3f}"),
            ("LL (kN/m)",   "LL", "{:.3f}"),
            ("f'c (MPa)",   "fc", "{:.2f}"),
            ("fy (MPa)",    "fy", "{:.1f}"),
            ("cc (mm)",     "cc", "{:.1f}"),
            ("dagg (mm)",   "dagg", "{:.1f}"),
            ("b (mm)",      "b_given", "{}"),
            ("d (mm)",      "d_given", "{}"),
        ]
        self.prop_vars = {}
        for i, (label, key, _) in enumerate(fields):
            row, col = divmod(i, 2)
            tk.Label(grid, text=label, bg="#f4f4f4").grid(row=row, column=col * 2,
                                                          sticky="e", padx=(0, 6), pady=3)
            default = self.problem[key] if self.problem[key] is not None else ""
            v = self._mk_var(f"prop.{key}",
                             f"{default}" if default != "" else "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=row, column=col * 2 + 1, sticky="w", padx=(0, 20), pady=3)
            self.prop_vars[key] = v

        tk.Label(f, text="b and d are blank when mode = 'sizing'. Fill them when mode = 'given'.",
                 bg="#f4f4f4", fg="#666", font=("Segoe UI", 9, "italic"),
                 wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))

    def _read_props(self):
        try:
            for key in ["L", "DL", "LL", "fc", "fy", "cc", "dagg"]:
                self.problem[key] = float(self.prop_vars[key].get())
        except ValueError:
            messagebox.showerror("Invalid", "All numeric properties must be filled.")
            return False

        mode = self.mode_var.get()
        if mode == "given":
            try:
                b = float(self.prop_vars["b_given"].get())
                d = float(self.prop_vars["d_given"].get())
            except ValueError:
                messagebox.showerror("Invalid", "Mode is 'given' — enter numeric b and d.")
                return False
            self.problem["b_given"] = b
            self.problem["d_given"] = d
        else:
            self.problem["b_given"] = None
            self.problem["d_given"] = None
        return True

    def _randomize(self):
        try:
            p = random_problem(self.mode_var.get())
        except Exception as e:
            messagebox.showerror("Randomizer error", str(e))
            return
        self.problem = p
        for key in ["L", "DL", "LL", "fc", "fy", "cc", "dagg"]:
            self.prop_vars[key].set(f"{p[key]:.4g}")
        for key in ["b_given", "d_given"]:
            val = p.get(key)
            self.prop_vars[key].set("" if val is None else f"{val:.4g}")
        self._refresh_top_given()
        self.log(f"Randomized ({self.mode_var.get()}).", "gray")
        self._set_status("New problem generated. Click Start Review.", "#0a5")

    def _start_review(self):
        if not self._read_props():
            return
        self.solution = solve_all(self.problem)
        self._refresh_top_given()
        self.passed.clear()
        self.revealed.clear()
        for k in list(self.user_inputs.keys()):
            if k.startswith("s1.") or k.startswith("s2.") or k.startswith("s3.") \
               or k.startswith("s4.") or k.startswith("s5.") or k.startswith("s6.") \
               or k.startswith("s7."):
                del self.user_inputs[k]
        # seed the Step-7 bar dropdown with the app's auto-pick
        if not self.solution.get("drb") and "bar_db" in self.solution:
            self.user_inputs["s7.db_choice"] = str(int(self.solution["bar_db"]))
        self.log("— Review started —", "head")
        self.log(f"Mode: {self.mode_var.get()}", "gray")
        if self.solution.get("drb"):
            self.log("⚠ This problem is DOUBLY REINFORCED.", "yellow")
        self._show_page(1)

    # ==============================================================
    # PAGE 1 — Mu
    # ==============================================================
    def _build_page_1(self):
        f = self.step_area
        p = self.problem
        tk.Label(f, text=f"wu = 1.2 DL + 1.6 LL = 1.2({p['DL']:.3f}) + 1.6({p['LL']:.3f})",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text=f"Mu = wu · L² / 8    with L = {p['L']:.3f} m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="wu =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v1 = self._mk_var("s1.wu", "")
        e1 = tk.Entry(grid, textvariable=v1, width=14, justify="center")
        e1.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN/m", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        tk.Label(grid, text="Mu =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v2 = self._mk_var("s1.Mu", "")
        e2 = tk.Entry(grid, textvariable=v2, width=14, justify="center")
        e2.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="kN·m", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        self.s1_wu = (v1, e1); self.s1_mu = (v2, e2)

    # ==============================================================
    # PAGE 2 — rho limits
    # ==============================================================
    def _build_page_2(self):
        f = self.step_area
        p = self.problem
        fc = p["fc"]; fy = p["fy"]
        b1 = beta1(fc)
        tk.Label(f, text=f"ρmin = max( 1.4/fy ,  0.25√f'c / fy )",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text=f"β₁ = {b1:.4f}   (for f'c = {fc:.2f} MPa)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="ρmax = (3/8) · (0.85 β₁ f'c / fy)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="ρact_init = 0.75 · ρmax",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("ρmin_1 (1.4/fy)", "s2.rhomin1", ""),
            ("ρmin_2 (0.25√f'c/fy)", "s2.rhomin2", ""),
            ("ρmin (governing)", "s2.rhomin", ""),
            ("ρmax", "s2.rhomax", ""),
            ("ρact_init = 0.75 ρmax", "s2.rhoact", ""),
        ]
        self.s2_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            self.s2_entries[key] = (v, e)

    # ==============================================================
    # PAGE 3 — Sizing
    # ==============================================================
    def _build_page_3(self):
        f = self.step_area
        s = self.solution
        if s and not s.get("sizing_done"):
            tk.Label(f, text="b and d are GIVEN — sizing step is skipped.",
                     bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            tk.Label(f, text="Click Next to continue to the Reinforcement step.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
            return

        tk.Label(f, text="R_init = φ ρact_init fy (1 − ρact_init fy / (1.7 f'c))",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="b = ∛( Mu / (2.25 · R_init) )    [Mu in N·mm]",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="Round b up to nearest 10 mm, then d = 1.5b, D = d + cc (round up to 10).",
                 bg="#f4f4f4", fg="#666", wraplength=720, justify="left").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("R_init", "s3.Rinit", ""),
            ("b (raw)", "s3.braw", "mm"),
            ("b (rounded)", "s3.b", "mm"),
            ("d = 1.5b", "s3.d", "mm"),
            ("D = d + cc (rounded)", "s3.D", "mm"),
        ]
        self.s3_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s3_entries[key] = (v, e)

    # ==============================================================
    # PAGE 4 — Self-weight
    # ==============================================================
    def _build_page_4(self):
        f = self.step_area
        s = self.solution
        if s and not s.get("sizing_done"):
            tk.Label(f, text="b and d are GIVEN — self-weight adjustment is skipped.",
                     bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            tk.Label(f, text="Click Next to continue to the Reinforcement step.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
            return

        tk.Label(f, text=f"w_beam = γc · b · D   (γc = {GAMMA_C} kN/m³)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="M_beam = w_beam · L² / 8",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="Mu_updated = Mu + 1.2 · M_beam",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("w_beam", "s4.wbeam", "kN/m"),
            ("M_beam", "s4.Mbeam", "kN·m"),
            ("Mu_updated", "s4.Mu", "kN·m"),
        ]
        self.s4_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s4_entries[key] = (v, e)

    # ==============================================================
    # PAGE 5 — Actual R and rho
    # ==============================================================
    def _build_page_5(self):
        f = self.step_area
        tk.Label(f, text="R_actual = Mu / (b · d²)    [Mu in N·mm]",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="Solve ρact from: R_actual = φ ρact fy (1 − ρact fy / (1.7 f'c))",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="Governing: if ρact < ρmin → use ρmin;   if ρact > ρmax → DRB.",
                 bg="#f4f4f4", fg="#666", wraplength=720, justify="left").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("R_actual", "s5.Ract", ""),
            ("ρact (computed)", "s5.rhoact", ""),
            ("ρ_governing", "s5.rhogov", ""),
        ]
        self.s5_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            self.s5_entries[key] = (v, e)

        tk.Label(f, text="Governing branch — pick one:",
                 bg="#f4f4f4", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.gov_pick = self._mk_var("s5.gov_pick", "")
        for lbl in [
            "ρact < ρmin  →  use ρmin",
            "ρmin ≤ ρact ≤ ρmax  →  use ρact (SRB)",
            "ρact > ρmax  →  DOUBLY REINFORCED (stop)",
        ]:
            tk.Radiobutton(f, text=lbl, variable=self.gov_pick, value=lbl,
                           bg="#f4f4f4", anchor="w", justify="left").pack(anchor="w")

    # ==============================================================
    # PAGE 6 — As
    # ==============================================================
    def _build_page_6(self):
        f = self.step_area
        s = self.solution
        if s and s.get("drb"):
            tk.Label(f, text="⚠ DOUBLY REINFORCED — As step is not applicable for SRB.",
                     bg="#f4f4f4", fg="#a00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            tk.Label(f, text="Proceed to Summary for details.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
            return

        tk.Label(f, text="As = ρ_governing · b · d",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="As =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v = self._mk_var("s6.As", "")
        e = tk.Entry(grid, textvariable=v, width=14, justify="center")
        e.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="mm²", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        self.s6_as = (v, e)

    # ==============================================================
    # PAGE 7 — Bar selection (with dropdown)
    # ==============================================================
    def _build_page_7(self):
        f = self.step_area
        s = self.solution
        if s and s.get("drb"):
            tk.Label(f, text="⚠ DOUBLY REINFORCED — bar selection step is not applicable for SRB.",
                     bg="#f4f4f4", fg="#a00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            return

        tk.Label(f, text="Choose a bar diameter from the dropdown, then compute nb, s, s_min.",
                 bg="#f4f4f4", fg="#333", font=("Segoe UI", 10, "bold"),
                 wraplength=720, justify="left").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="nb = ceil(As / (π/4 · db²))",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="s = (b − 2cc − 2dv − nb·db) / (nb − 1)    (dv = 10 mm stirrups)",
                 bg="#f4f4f4", fg="#333", wraplength=720, justify="left").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="s_min = max(50, db, 4/3 · dagg)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        # --- bar size dropdown ---
        bar_row = tk.Frame(f, bg="#f4f4f4")
        bar_row.pack(anchor="w", pady=(0, 4))
        tk.Label(bar_row, text="Bar size (db):", bg="#f4f4f4",
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        default_db = str(int(s["bar_db"])) if s and "bar_db" in s else "20"
        self.bar_choice_var = self._mk_var("s7.db_choice", default_db)
        self.bar_combo = ttk.Combobox(
            bar_row, textvariable=self.bar_choice_var,
            values=[str(int(b)) for b in BAR_SIZES],
            width=6, state="readonly")
        self.bar_combo.pack(side="left", padx=8)
        self.bar_combo.bind("<<ComboboxSelected>>", self._on_bar_choice_changed)

        tk.Label(bar_row, text="mm", bg="#f4f4f4").pack(side="left")

        # --- hint about the auto-pick ---
        if s and "bar_db" in s:
            auto_txt = (f"App's auto-pick: {s['bar_nb']} pcs of "
                        f"{s['bar_db']:.0f} mmØ  "
                        f"(s = {s['bar_s']:.2f} mm, s_min = {s['s_min']:.2f} mm, "
                        f"{'OK' if s['spacing_ok'] else 'NOT OK'})")
            tk.Label(f, text=auto_txt, bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 9, "italic"),
                     wraplength=720, justify="left").pack(anchor="w", pady=(0, 8))

        # --- entries for nb, s, s_min ---
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("nb",         "s7.nb",   "pcs"),
            ("s (clear)",  "s7.s",    "mm"),
            ("s_min",      "s7.smin", "mm"),
        ]
        self.s7_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(
                row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(
                row=i, column=2, sticky="w", padx=6)
            self.s7_entries[key] = (v, e)

        # --- live spacing verdict for the chosen db ---
        self.s7_verdict = tk.Label(f, text="", bg="#f4f4f4",
                                   font=("Segoe UI", 9, "italic"))
        self.s7_verdict.pack(anchor="w", pady=(8, 0))
        self._update_bar_verdict()

    def _on_bar_choice_changed(self, event=None):
        """When the user picks a new bar, clear nb / s / s_min so they retype
        the values for the new diameter, and refresh the verdict label."""
        for k in ("s7.nb", "s7.s", "s7.smin"):
            pair = self.s7_entries.get(k)
            if pair:
                pair[0].set("")
                try:
                    pair[1].configure(bg="white")
                except tk.TclError:
                    pass
        self._update_bar_verdict()

    def _update_bar_verdict(self):
        s = self.solution
        if not s or s.get("drb") or "As" not in s:
            self.s7_verdict.configure(text="")
            return
        try:
            db = float(self.bar_choice_var.get())
        except (TypeError, ValueError):
            self.s7_verdict.configure(text="")
            return
        nb, sp, smin = compute_bar_fit(s["As"], s["b"], s["cc"], s["dagg"], db)
        ok = (sp >= smin) and (nb <= 7)
        if nb > 7:
            note = f"{nb} bars — exceeds practical limit (7)."
        elif sp < smin:
            note = f"clear spacing {sp:.2f} mm < s_min {smin:.2f} mm  →  too tight."
        else:
            note = f"clear spacing {sp:.2f} mm ≥ s_min {smin:.2f} mm  →  OK."
        color = "#0a7a0a" if ok else "#a00"
        self.s7_verdict.configure(text=note, fg=color)

    # ==============================================================
    # PAGE 8 — SUMMARY
    # ==============================================================
    def _build_page_8(self):
        f = self.step_area
        if not self.solution:
            tk.Label(f, text="No solution yet. Go to Setup and click Start Review.",
                     bg="#f4f4f4", fg="#a00").pack(anchor="w")
            return

        s = self.solution

        if s.get("drb"):
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#a00")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="DOUBLY REINFORCED (DRB)", font=("Segoe UI", 13, "bold"),
                     fg="#a00", bg="#ffffff").pack(padx=16, pady=12)
            tk.Label(f, text=f"Computed ρact = {s.get('rho_actual_computed', 0):.5f} exceeds "
                             f"ρmax = {s['rho_max']:.5f}.",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
            tk.Label(f, text="This problem is outside the SRB scope. Design as DRB.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
        else:
            # show both the auto-pick and the user's chosen bar (if any)
            try:
                user_db = float(self.bar_choice_var.get()) if hasattr(self, "bar_choice_var") else None
            except (TypeError, ValueError):
                user_db = None

            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#0a7a0a")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="FINAL SRB DESIGN", font=("Segoe UI", 12, "bold"),
                     bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(10, 6))
            tk.Label(box, text=f"Section: {s['b']:.0f} mm × {s['D']:.0f} mm  (d = {s['d']:.0f} mm)",
                     font=("Consolas", 12), bg="#ffffff").grid(row=1, column=0, columnspan=2)
            tk.Label(box, text=f"As = {s['As']:.1f} mm²",
                     font=("Consolas", 12), bg="#ffffff").grid(row=2, column=0, columnspan=2)
            tk.Label(box, text=f"App auto-pick: {s['bar_nb']} pcs of {s['bar_db']:.0f} mmØ",
                     font=("Consolas", 12, "bold"), fg="#0a7a0a", bg="#ffffff").grid(
                         row=3, column=0, columnspan=2, padx=16, pady=(6, 2))

            if user_db is not None and user_db != s["bar_db"]:
                nb_u, sp_u, smin_u = compute_bar_fit(s["As"], s["b"], s["cc"], s["dagg"], user_db)
                tk.Label(box,
                         text=f"Your pick: {nb_u} pcs of {user_db:.0f} mmØ  "
                              f"(s = {sp_u:.2f} mm, s_min = {smin_u:.2f} mm, "
                              f"{'OK' if sp_u >= smin_u else 'NOT OK'})",
                         font=("Consolas", 11), fg="#345", bg="#ffffff").grid(
                             row=4, column=0, columnspan=2, padx=16, pady=(2, 12))
            else:
                tk.Label(box, text="(matches your Step 7 selection)",
                         font=("Consolas", 10, "italic"), fg="#666", bg="#ffffff").grid(
                             row=4, column=0, columnspan=2, padx=16, pady=(0, 12))

            if not s["spacing_ok"]:
                tk.Label(f, text=f"⚠ Auto-pick warning: s = {s['bar_s']:.1f} mm < s_min = {s['s_min']:.1f} mm. "
                                 f"May need multiple layers or larger section.",
                         bg="#f4f4f4", fg="#a00", wraplength=720,
                         justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(f, text="Recap:", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(14, 4))
        recap = tk.Text(f, width=72, height=14, font=("Consolas", 9), bg="#ffffff")
        recap.pack(anchor="w", fill="x")
        lines = [
            f"L = {s['L']:.3f} m   DL = {s['DL']:.3f} kN/m   LL = {s['LL']:.3f} kN/m",
            f"f'c = {s['fc']:.2f} MPa   fy = {s['fy']:.1f} MPa   cc = {s['cc']:.1f} mm   dagg = {s['dagg']:.1f} mm",
            "",
            f"wu = {s['wu']:.3f} kN/m   Mu_init = {s['Mu_init']:.3f} kN·m",
            f"ρmin_1 = {s['rho_min_1']:.5f}   ρmin_2 = {s['rho_min_2']:.5f}   ρmin = {s['rho_min']:.5f}",
            f"β₁ = {s['beta1']:.4f}   ρmax = {s['rho_max']:.5f}   ρact_init = {s['rho_act_init']:.5f}",
        ]
        if s.get("sizing_done"):
            lines += [
                f"R_init = {s['R_init']:.4f}",
                f"b_raw = {s['b_raw']:.3f} mm → b = {s['b']:.0f} mm",
                f"d = 1.5b = {s['d']:.0f} mm   D = {s['D']:.0f} mm",
                f"w_beam = {s['w_beam']:.3f} kN/m   M_beam = {s['M_beam']:.3f} kN·m",
                f"Mu_updated = {s['Mu_updated']:.3f} kN·m",
            ]
        lines += [
            f"R_actual = {s['R_actual']:.4f}",
            f"ρact (computed) = {s.get('rho_actual_computed', 0):.5f}",
        ]
        if "rho_govern" in s:
            lines += [
                f"Governing: {s['governing']}  →  ρ = {s['rho_govern']:.5f}",
                f"As = {s['As']:.1f} mm²",
                f"Auto-pick: {s['bar_nb']} pcs of {s['bar_db']:.0f} mmØ",
                f"Clear spacing s = {s['bar_s']:.2f} mm   s_min = {s['s_min']:.2f} mm   "
                f"{'OK' if s['spacing_ok'] else 'NOT OK'}",
            ]
        for ln in lines:
            recap.insert("end", ln + "\n")
        recap.configure(state="disabled")

        tk.Button(f, text="Copy Summary to Clipboard", bg="#c9daf8",
                  command=self.copy_summary).pack(anchor="w", pady=(10, 0))

    # ==============================================================
    # CHECK
    # ==============================================================
    def _set_status(self, msg, color="#333"):
        self.status.configure(text=msg, fg=color)

    def _mark(self, widget, ok):
        try:
            widget.configure(bg=("#e0ffe0" if ok else "#ffe0e0"))
        except tk.TclError:
            pass

    def _set_entry(self, pair, value_str):
        var, entry = pair
        var.set(value_str)
        try:
            entry.delete(0, "end")
            entry.insert(0, value_str)
            entry.configure(bg="#e0ffe0")
        except tk.TclError:
            pass

    def check_current(self):
        if self.solution is None:
            messagebox.showinfo("No active problem",
                                "Click 'Start Review' on the Setup page first.")
            return
        p = self.page
        if p == 1: self._check_step1()
        elif p == 2: self._check_step2()
        elif p == 3: self._check_step3()
        elif p == 4: self._check_step4()
        elif p == 5: self._check_step5()
        elif p == 6: self._check_step6()
        elif p == 7: self._check_step7()
        self._refresh_top_given()

    def _check_step1(self):
        s = self.solution
        u1 = parse(self.s1_wu[0].get()); ok1 = u1 is not None and close(u1, s["wu"])
        u2 = parse(self.s1_mu[0].get()); ok2 = u2 is not None and close(u2, s["Mu_init"])
        self._mark(self.s1_wu[1], ok1); self._mark(self.s1_mu[1], ok2)
        if ok1 and ok2:
            self._set_status("✓ Step 1 correct!", "#0a7a0a")
            self.log(f"Step 1: wu={fmt(s['wu'])}, Mu={fmt(s['Mu_init'])} correct.", "green")
            self.passed.add(1); self.revealed.discard(1)
        else:
            msgs = []
            if not ok1: msgs.append(f"wu: expected {fmt(s['wu'])} kN/m (got {u1})")
            if not ok2: msgs.append(f"Mu: expected {fmt(s['Mu_init'])} kN·m (got {u2})")
            self._set_status("✗ Step 1 has errors.", "#a00")
            self.log("Step 1 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 1", "\n".join(msgs))

    def _check_step2(self):
        s = self.solution
        expected = {
            "s2.rhomin1": s["rho_min_1"],
            "s2.rhomin2": s["rho_min_2"],
            "s2.rhomin":  s["rho_min"],
            "s2.rhomax":  s["rho_max"],
            "s2.rhoact":  s["rho_act_init"],
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s2_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s2_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp, 5)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 2 correct!", "#0a7a0a")
            self.log(f"Step 2: ρ values correct.", "green")
            self.passed.add(2); self.revealed.discard(2)
        else:
            self._set_status("✗ Step 2 has errors.", "#a00")
            self.log("Step 2 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 2", "\n".join(msgs))

    def _check_step3(self):
        s = self.solution
        if not s.get("sizing_done"):
            self._set_status("— Step 3 skipped (b, d given).", "#a67c00")
            self.passed.add(3)
            return
        expected = {
            "s3.Rinit": s["R_init"],
            "s3.braw":  s["b_raw"],
            "s3.b":     s["b"],
            "s3.d":     s["d"],
            "s3.D":     s["D"],
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s3_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s3_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 3 correct!", "#0a7a0a")
            self.log(f"Step 3: b={s['b']:.0f}, d={s['d']:.0f}, D={s['D']:.0f} correct.", "green")
            self.passed.add(3); self.revealed.discard(3)
        else:
            self._set_status("✗ Step 3 has errors.", "#a00")
            self.log("Step 3 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 3", "\n".join(msgs))

    def _check_step4(self):
        s = self.solution
        if not s.get("sizing_done"):
            self._set_status("— Step 4 skipped (b, d given).", "#a67c00")
            self.passed.add(4)
            return
        expected = {
            "s4.wbeam": s["w_beam"],
            "s4.Mbeam": s["M_beam"],
            "s4.Mu":    s["Mu_updated"],
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s4_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s4_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 4 correct!", "#0a7a0a")
            self.log(f"Step 4: Mu_updated={fmt(s['Mu_updated'])} correct.", "green")
            self.passed.add(4); self.revealed.discard(4)
        else:
            self._set_status("✗ Step 4 has errors.", "#a00")
            self.log("Step 4 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 4", "\n".join(msgs))

    def _check_step5(self):
        s = self.solution
        u_ract = parse(self.s5_entries["s5.Ract"][0].get())
        ract_ok = u_ract is not None and close(u_ract, s["R_actual"])
        self._mark(self.s5_entries["s5.Ract"][1], ract_ok)

        if s.get("drb"):
            gov_ok = (self.gov_pick.get() == "ρact > ρmax  →  DOUBLY REINFORCED (stop)")
            if ract_ok and gov_ok:
                self._set_status("✓ Step 5 correct — DRB detected.", "#0a7a0a")
                self.log("Step 5: correctly identified as DRB.", "green")
                self.passed.add(5); self.revealed.discard(5)
            else:
                msgs = []
                if not ract_ok: msgs.append(f"R_actual: expected {fmt(s['R_actual'])} (got {u_ract})")
                if not gov_ok: msgs.append(f"Branch: expected 'DOUBLY REINFORCED (stop)' (got '{self.gov_pick.get()}')")
                self._set_status("✗ Step 5 has errors.", "#a00")
                for m in msgs: self.log("  " + m, "yellow")
                messagebox.showwarning("Step 5", "\n".join(msgs))
            return

        u_act = parse(self.s5_entries["s5.rhoact"][0].get())
        act_ok = u_act is not None and close(u_act, s["rho_actual_computed"])
        self._mark(self.s5_entries["s5.rhoact"][1], act_ok)

        u_gov = parse(self.s5_entries["s5.rhogov"][0].get())
        gov_ok = u_gov is not None and close(u_gov, s["rho_govern"])
        self._mark(self.s5_entries["s5.rhogov"][1], gov_ok)

        if s["governing"] == "rho_min":
            expected_branch = "ρact < ρmin  →  use ρmin"
        else:
            expected_branch = "ρmin ≤ ρact ≤ ρmax  →  use ρact (SRB)"
        br_ok = (self.gov_pick.get() == expected_branch)

        if ract_ok and act_ok and gov_ok and br_ok:
            self._set_status("✓ Step 5 correct!", "#0a7a0a")
            self.log(f"Step 5: ρ_governing={fmt(s['rho_govern'], 5)} correct.", "green")
            self.passed.add(5); self.revealed.discard(5)
        else:
            msgs = []
            if not ract_ok: msgs.append(f"R_actual: expected {fmt(s['R_actual'])} (got {u_ract})")
            if not act_ok: msgs.append(f"ρact: expected {fmt(s['rho_actual_computed'],5)} (got {u_act})")
            if not gov_ok: msgs.append(f"ρ_gov: expected {fmt(s['rho_govern'],5)} (got {u_gov})")
            if not br_ok: msgs.append(f"Branch: expected '{expected_branch}' (got '{self.gov_pick.get()}')")
            self._set_status("✗ Step 5 has errors.", "#a00")
            self.log("Step 5 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 5", "\n".join(msgs))

    def _check_step6(self):
        s = self.solution
        if s.get("drb"):
            self._set_status("— Step 6 skipped (DRB).", "#a67c00")
            self.passed.add(6)
            return
        u = parse(self.s6_as[0].get())
        ok = u is not None and close(u, s["As"])
        self._mark(self.s6_as[1], ok)
        if ok:
            self._set_status("✓ Step 6 correct!", "#0a7a0a")
            self.log(f"Step 6: As={fmt(s['As'],1)} mm² correct.", "green")
            self.passed.add(6); self.revealed.discard(6)
        else:
            self._set_status("✗ Step 6 has errors.", "#a00")
            self.log(f"Step 6: As expected {fmt(s['As'],1)} (got {u}).", "yellow")
            messagebox.showwarning("Step 6", f"As: expected {fmt(s['As'],1)} mm² (got {u})")

    def _check_step7(self):
        s = self.solution
        if s.get("drb"):
            self._set_status("— Step 7 skipped (DRB).", "#a67c00")
            self.passed.add(7)
            return

        # ---- read chosen bar from dropdown ----
        try:
            db_chosen = float(self.bar_choice_var.get())
        except (TypeError, ValueError):
            messagebox.showwarning("Step 7", "Please pick a bar size from the dropdown.")
            return

        nb_exp, s_exp, smin_exp = compute_bar_fit(
            s["As"], s["b"], s["cc"], s["dagg"], db_chosen)

        expected = {
            "s7.nb":   float(nb_exp),
            "s7.s":    s_exp,
            "s7.smin": smin_exp,
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s7_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s7_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")

        # extra info: is this bar physically OK?
        fits = (s_exp >= smin_exp) and (nb_exp <= 7)
        if all_ok:
            tail = "" if fits else "  (note: spacing/bar count outside practical limits — but math is correct for the chosen bar)"
            self._set_status(f"✓ Step 7 correct for {db_chosen:.0f} mmØ.", "#0a7a0a")
            self.log(f"Step 7: {nb_exp}–{db_chosen:.0f}mm, s={fmt(s_exp,2)} correct.{tail}",
                     "green")
            self.passed.add(7); self.revealed.discard(7)
            if not fits:
                self.log("  ⚠ chosen bar has s < s_min or nb > 7.", "yellow")
        else:
            self._set_status("✗ Step 7 has errors.", "#a00")
            self.log(f"Step 7 errors for {db_chosen:.0f} mmØ:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 7", "\n".join(msgs))

    # ==============================================================
    # REVEAL
    # ==============================================================
    def reveal_current(self):
        if not self.solution:
            messagebox.showinfo("No active problem",
                                "Click 'Start Review' on the Setup page first.")
            return
        s = self.solution
        p = self.page
        if p == 1:
            self._set_entry(self.s1_wu, fmt(s["wu"]))
            self._set_entry(self.s1_mu, fmt(s["Mu_init"]))
        elif p == 2:
            self._set_entry(self.s2_entries["s2.rhomin1"], fmt(s["rho_min_1"], 5))
            self._set_entry(self.s2_entries["s2.rhomin2"], fmt(s["rho_min_2"], 5))
            self._set_entry(self.s2_entries["s2.rhomin"],  fmt(s["rho_min"], 5))
            self._set_entry(self.s2_entries["s2.rhomax"],  fmt(s["rho_max"], 5))
            self._set_entry(self.s2_entries["s2.rhoact"],  fmt(s["rho_act_init"], 5))
        elif p == 3:
            if not s.get("sizing_done"):
                self.revealed.add(3)
                self.log("Step 3 revealed (skipped).", "yellow")
                self._set_status("Step 3 N/A.", "#a67c00")
                return
            self._set_entry(self.s3_entries["s3.Rinit"], fmt(s["R_init"]))
            self._set_entry(self.s3_entries["s3.braw"],  fmt(s["b_raw"]))
            self._set_entry(self.s3_entries["s3.b"],     fmt(s["b"]))
            self._set_entry(self.s3_entries["s3.d"],     fmt(s["d"]))
            self._set_entry(self.s3_entries["s3.D"],     fmt(s["D"]))
        elif p == 4:
            if not s.get("sizing_done"):
                self.revealed.add(4)
                self.log("Step 4 revealed (skipped).", "yellow")
                self._set_status("Step 4 N/A.", "#a67c00")
                return
            self._set_entry(self.s4_entries["s4.wbeam"], fmt(s["w_beam"]))
            self._set_entry(self.s4_entries["s4.Mbeam"], fmt(s["M_beam"]))
            self._set_entry(self.s4_entries["s4.Mu"],    fmt(s["Mu_updated"]))
        elif p == 5:
            self._set_entry(self.s5_entries["s5.Ract"], fmt(s["R_actual"]))
            if s.get("drb"):
                self.gov_pick.set("ρact > ρmax  →  DOUBLY REINFORCED (stop)")
            else:
                self._set_entry(self.s5_entries["s5.rhoact"], fmt(s["rho_actual_computed"], 5))
                self._set_entry(self.s5_entries["s5.rhogov"], fmt(s["rho_govern"], 5))
                if s["governing"] == "rho_min":
                    self.gov_pick.set("ρact < ρmin  →  use ρmin")
                else:
                    self.gov_pick.set("ρmin ≤ ρact ≤ ρmax  →  use ρact (SRB)")
        elif p == 6:
            if s.get("drb"):
                self.revealed.add(6)
                return
            self._set_entry(self.s6_as, fmt(s["As"], 1))
        elif p == 7:
            if s.get("drb"):
                self.revealed.add(7)
                return
            # reveal values for the CURRENTLY selected bar in the dropdown
            try:
                db_chosen = float(self.bar_choice_var.get())
            except (TypeError, ValueError):
                db_chosen = s["bar_db"]
                self.bar_choice_var.set(str(int(db_chosen)))
            nb, sp, smin = compute_bar_fit(s["As"], s["b"], s["cc"], s["dagg"], db_chosen)
            self._set_entry(self.s7_entries["s7.nb"],   fmt(nb))
            self._set_entry(self.s7_entries["s7.s"],    fmt(sp, 2))
            self._set_entry(self.s7_entries["s7.smin"], fmt(smin, 2))
            self._update_bar_verdict()
        self.revealed.add(p)
        self.log(f"Step {p} revealed.", "yellow")
        self._refresh_top_given()
        self._set_status("Answers revealed.", "#a67c00")

    # ==============================================================
    # COPY SUMMARY
    # ==============================================================
    def copy_summary(self):
        if not self.solution:
            messagebox.showinfo("Nothing to copy", "Start a review first.")
            return
        s = self.solution
        lines = ["RCD SRB Design — Summary", "=" * 40]
        lines += [
            f"L = {s['L']:.3f} m   DL = {s['DL']:.3f} kN/m   LL = {s['LL']:.3f} kN/m",
            f"f'c = {s['fc']:.2f} MPa   fy = {s['fy']:.1f} MPa   cc = {s['cc']:.1f} mm   dagg = {s['dagg']:.1f} mm",
            "",
            f"wu = {s['wu']:.3f} kN/m   Mu_init = {s['Mu_init']:.3f} kN·m",
            f"ρmin = {s['rho_min']:.5f}   ρmax = {s['rho_max']:.5f}   ρact_init = {s['rho_act_init']:.5f}",
        ]
        if s.get("sizing_done"):
            lines += [
                f"b = {s['b']:.0f} mm   d = {s['d']:.0f} mm   D = {s['D']:.0f} mm",
                f"Mu_updated = {s['Mu_updated']:.3f} kN·m",
            ]
        lines.append(f"R_actual = {s['R_actual']:.4f}")

        if s.get("drb"):
            lines.append("Result: DOUBLY REINFORCED (outside SRB scope)")
        else:
            lines += [
                f"ρact = {s['rho_actual_computed']:.5f}   governing: {s['governing']}  →  ρ = {s['rho_govern']:.5f}",
                f"As = {s['As']:.1f} mm²",
                f"Auto-pick: {s['bar_nb']} pcs of {s['bar_db']:.0f} mmØ  "
                f"(s = {s['bar_s']:.2f} mm, s_min = {s['s_min']:.2f} mm)",
                f"Result: {s['b']:.0f} mm × {s['D']:.0f} mm section, As = {s['As']:.1f} mm², "
                f"{s['bar_nb']}–{s['bar_db']:.0f} mmØ bars",
            ]
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Summary copied to clipboard.", "#0a7a0a")
        self.log("Summary copied to clipboard.", "gray")


if __name__ == "__main__":
    app = SRBDesigner()
    app.mainloop()