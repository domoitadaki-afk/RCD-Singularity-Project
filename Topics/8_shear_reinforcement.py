"""
RCD Shear Design Reviewer — NSCP-style
Single-file Tkinter app. No external dependencies.

Flow:
  Setup (branch target + randomize) -> Step 1..7 -> Summary
Computed values at each step are type-and-checked with feedback.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import random

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
PHI = 0.75
TOL = 0.005
LAMBDA = 1.0

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

def round_down_to(x, step):
    return math.floor(x / step) * step

# ------------------------------------------------------------------
# BRANCH LABELS
# ------------------------------------------------------------------
BRANCH_ANY = "Random (any branch)"
BRANCH_NONE = "No stirrups required"
BRANCH_MIN  = "Minimum stirrups only"
BRANCH_NORM = "Design stirrups — normal"
BRANCH_HIGH = "Design stirrups — high Vs"
BRANCH_REDES = "Redesign section warning"

BRANCHES = [BRANCH_ANY, BRANCH_NONE, BRANCH_MIN, BRANCH_NORM, BRANCH_HIGH, BRANCH_REDES]

# ------------------------------------------------------------------
# SOLVER
# ------------------------------------------------------------------
def solve_all(p):
    ln = p["ln"]; b = p["b"]; d = p["d"]; dv = p["dv"]
    fc = p["fc"]; fy = p["fy"]; Ws = p["Ws"]
    DL = p["DL"]; LL = p["LL"]

    Wu = 1.2 * DL + 1.6 * LL
    Vu = Wu * (ln / 1000.0) / 2.0
    Vud = Vu * (ln / 2.0 - Ws / 2.0 - d) / (ln / 2.0)

    Vc = 0.17 * LAMBDA * math.sqrt(fc) * b * d / 1000.0
    phiVc = PHI * Vc
    half_phiVc = 0.5 * phiVc

    if Vud <= half_phiVc:
        branch = "none"
    elif Vud <= phiVc:
        branch = "min"
    else:
        branch = "design"

    out = {
        "Wu": Wu, "Vu": Vu, "Vud": Vud,
        "Vc": Vc, "phiVc": phiVc, "half_phiVc": half_phiVc,
        "branch": branch,
        "ln": ln, "b": b, "d": d, "D": p["D"], "dv": dv,
        "fc": fc, "fy": fy, "Ws": Ws, "DL": DL, "LL": LL,
    }

    if branch != "design":
        Av = 2.0 * math.pi / 4.0 * dv * dv
        out["Av"] = Av
        s_av_1 = Av * fy / (0.062 * math.sqrt(fc) * b)
        s_av_2 = Av * fy / (0.35 * b)
        S_Avmin = min(s_av_1, s_av_2)
        out["S_Avmin"] = S_Avmin
        out["s_av_1"] = s_av_1
        out["s_av_2"] = s_av_2
        S_branch = min(0.5 * d, 600.0)
        out["S_branch"] = S_branch
        out["Smax"] = min(S_branch, S_Avmin, 200.0)
        return out

    phiVs = Vud - phiVc
    Vs = phiVs / PHI
    Vs_max = 0.66 * math.sqrt(fc) * b * d / 1000.0
    out["phiVs"] = phiVs
    out["Vs"] = Vs
    out["Vs_max"] = Vs_max
    out["redesign"] = Vs > Vs_max

    Av = 2.0 * math.pi / 4.0 * dv * dv
    S_req_raw = PHI * Av * fy * d / (phiVs * 1000.0)
    S_req = round_down_to(S_req_raw, 50.0)
    out["Av"] = Av
    out["S_req_raw"] = S_req_raw
    out["S_req"] = S_req

    Vs_low_limit = 0.33 * math.sqrt(fc) * b * d / 1000.0
    out["Vs_low_limit"] = Vs_low_limit
    if Vs <= Vs_low_limit:
        S_branch = min(0.5 * d, 600.0)
        branch_smax = "low"
    else:
        S_branch = min(0.25 * d, 300.0)
        branch_smax = "high"
    out["S_branch"] = S_branch
    out["branch_smax"] = branch_smax

    s_av_1 = Av * fy / (0.062 * math.sqrt(fc) * b)
    s_av_2 = Av * fy / (0.35 * b)
    S_Avmin = min(s_av_1, s_av_2)
    out["S_Avmin"] = S_Avmin
    out["s_av_1"] = s_av_1
    out["s_av_2"] = s_av_2

    Smax = min(S_branch, S_Avmin, 200.0)
    out["Smax"] = Smax
    out["spacing_ok"] = S_req <= Smax

    ln_max = phiVc * (ln / 2.0) / Vu
    out["ln_max"] = ln_max
    L_req = ln / 2.0 - Ws / 2.0 - 50.0 - ln_max
    out["L_req"] = L_req
    N_req = math.ceil(L_req / S_req) if S_req > 0 else 0
    N_max = math.ceil(ln_max / Smax) if Smax > 0 else 0
    out["N_req"] = N_req
    out["N_max"] = N_max

    return out

# ------------------------------------------------------------------
# RANDOMIZER
# ------------------------------------------------------------------
def random_problem(target_branch):
    """Generate a realistic problem whose Vud lands in target_branch."""

    def make_base():
        ln = float(random.choice(range(3000, 8000, 100)))
        b  = float(random.choice(range(250, 400, 10)))
        d  = float(random.choice(range(350, 600, 10)))
        D  = d + float(random.choice([60, 70, 80, 90, 100]))
        dv = float(random.choice([10, 12]))
        fc = random.choice([21.0, 25.0, 28.0, 32.0])
        fy = random.choice([275.0, 300.0, 415.0])
        Ws = float(random.choice([250.0, 300.0, 350.0, 400.0]))
        return ln, b, d, D, dv, fc, fy, Ws

    def derive_DL_LL(ln, b, d, Ws, target_Vud):
        """Back-solve DL & LL so Vud hits target_Vud, with realistic DL:LL ratio."""
        half = ln / 2.0
        offset = Ws / 2.0 + d
        denom = half - offset
        if denom <= 100:
            return None
        Vu_target = target_Vud * half / denom
        Wu_target = 2.0 * Vu_target / (ln / 1000.0)
        # realistic ratio DL/LL between 0.9 and 1.8
        ratio = random.uniform(0.9, 1.8)
        LL = Wu_target / (1.2 * ratio + 1.6)
        DL = ratio * LL
        # realistic bounds: 8 to 60 kN/m
        if not (8.0 <= DL <= 60.0 and 8.0 <= LL <= 60.0):
            return None
        return DL, LL

    # ANY: pick a section, then sample Vud as a multiple of ØVc so it's consistent
    if target_branch == BRANCH_ANY:
        for _ in range(200):
            ln, b, d, D, dv, fc, fy, Ws = make_base()
            Vc = 0.17 * math.sqrt(fc) * b * d / 1000.0
            phiVc = PHI * Vc
            # random multiplier from 0.3x to 2.2x of phiVc
            target_Vud = phiVc * random.uniform(0.3, 2.2)
            pair = derive_DL_LL(ln, b, d, Ws, target_Vud)
            if pair is None:
                continue
            DL, LL = pair
            return {"ln": ln, "b": b, "d": d, "D": D, "dv": dv,
                    "fc": fc, "fy": fy, "Ws": Ws, "DL": DL, "LL": LL}
        # very loose fallback
        return {"ln": 4000.0, "b": 280.0, "d": 480.0, "D": 540.0, "dv": 10.0,
                "fc": 25.0, "fy": 300.0, "Ws": 300.0, "DL": 20.0, "LL": 15.0}

    best_near = None
    best_score = None

    for _ in range(400):
        try:
            ln, b, d, D, dv, fc, fy, Ws = make_base()
            Vc = 0.17 * math.sqrt(fc) * b * d / 1000.0
            phiVc = PHI * Vc
            Vs_low = 0.33 * math.sqrt(fc) * b * d / 1000.0
            Vs_maxcap = 0.66 * math.sqrt(fc) * b * d / 1000.0

            if target_branch == BRANCH_NONE:
                target_Vud = random.uniform(0.20, 0.45) * phiVc
            elif target_branch == BRANCH_MIN:
                target_Vud = random.uniform(0.55, 0.95) * phiVc
            elif target_branch == BRANCH_NORM:
                lo = 1.08 * phiVc
                hi = phiVc + PHI * Vs_low * 0.85
                if hi <= lo:
                    continue
                target_Vud = random.uniform(lo, hi)
            elif target_branch == BRANCH_HIGH:
                lo = phiVc + PHI * Vs_low * 1.10
                hi = phiVc + PHI * Vs_maxcap * 0.90
                if hi <= lo:
                    continue
                target_Vud = random.uniform(lo, hi)
            elif target_branch == BRANCH_REDES:
                # just barely past the cap — realistic and triggers redesign
                lo = phiVc + PHI * Vs_maxcap * 1.08
                hi = phiVc + PHI * Vs_maxcap * 1.35
                if hi <= lo:
                    continue
                target_Vud = random.uniform(lo, hi)
            else:
                continue

            pair = derive_DL_LL(ln, b, d, Ws, target_Vud)
            if pair is None:
                continue
            DL, LL = pair

            p = {"ln": ln, "b": b, "d": d, "D": D, "dv": dv,
                 "fc": fc, "fy": fy, "Ws": Ws, "DL": DL, "LL": LL}

            sol = solve_all(p)

            if target_branch == BRANCH_NONE and sol["branch"] == "none":
                return p
            if target_branch == BRANCH_MIN and sol["branch"] == "min":
                return p
            if target_branch == BRANCH_NORM:
                if sol["branch"] == "design" and not sol["redesign"] and sol["branch_smax"] == "low":
                    return p
            if target_branch == BRANCH_HIGH:
                if sol["branch"] == "design" and not sol["redesign"] and sol["branch_smax"] == "high":
                    return p
            if target_branch == BRANCH_REDES:
                if sol["branch"] == "design" and sol["redesign"]:
                    return p

            score = abs(sol["Vud"] - target_Vud) / max(phiVc, 1.0)
            if best_score is None or score < best_score:
                best_score = score
                best_near = p

        except Exception:
            continue

    if best_near is not None:
        return best_near

    # hand-tuned fallbacks, all realistic
    fallbacks = {
        BRANCH_NONE:  {"ln": 5000.0, "b": 350.0, "d": 500.0, "D": 570.0, "dv": 10.0,
                       "fc": 28.0, "fy": 415.0, "Ws": 300.0, "DL": 18.0, "LL": 12.0},
        BRANCH_MIN:   {"ln": 5000.0, "b": 300.0, "d": 450.0, "D": 510.0, "dv": 10.0,
                       "fc": 25.0, "fy": 300.0, "Ws": 300.0, "DL": 28.0, "LL": 20.0},
        BRANCH_NORM:  {"ln": 4000.0, "b": 280.0, "d": 480.0, "D": 540.0, "dv": 10.0,
                       "fc": 25.0, "fy": 300.0, "Ws": 300.0, "DL": 53.0, "LL": 50.0},
        BRANCH_HIGH:  {"ln": 6000.0, "b": 300.0, "d": 400.0, "D": 460.0, "dv": 10.0,
                       "fc": 25.0, "fy": 300.0, "Ws": 300.0, "DL": 45.0, "LL": 35.0},
        BRANCH_REDES: {"ln": 7000.0, "b": 250.0, "d": 300.0, "D": 360.0, "dv": 10.0,
                       "fc": 21.0, "fy": 300.0, "Ws": 300.0, "DL": 55.0, "LL": 45.0},
    }
    return dict(fallbacks.get(target_branch, fallbacks[BRANCH_NORM]))

# ------------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------------
class ShearDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD Shear Design Reviewer")

        # ---- fit the window to the actual screen (fix for 11" MacBook) ----
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = max(760, min(1220, sw - 40))
        win_h = max(520, min(820, sh - 120))   # leave room for menu bar + dock
        x = max(0, (sw - win_w) // 2)
        y = max(0, (sh - win_h) // 3)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(min(760, win_w), min(520, win_h))

        self.problem = {
            "ln": 4000.0, "b": 280.0, "d": 480.0, "D": 540.0, "dv": 10.0,
            "fc": 25.0, "fy": 300.0, "Ws": 300.0, "DL": 53.0, "LL": 50.0,
        }
        self.solution = None
        self.page = 0
        self.max_page = 8
        self.user_inputs = {}
        self.passed = set()
        self.revealed = set()
        self.history_lines = []

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
        """Re-wrap the 'given' panel when the window is resized."""
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
        # Only scroll if the pointer is currently over the step area.
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
            if abs(d) >= 120:            # Windows
                delta = int(-d / 120)
            else:                         # macOS / trackpad
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

        # ---- scrollable step area ----
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

        # Bind wheel app-wide; the handler checks the pointer location.
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

    # ==============================================================
    # TOP GIVEN PANEL  (wraps into multiple rows on narrow windows)
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
            ("ln", f"{p['ln']:.0f} mm"),
            ("b",  f"{p['b']:.0f} mm"),
            ("d",  f"{p['d']:.0f} mm"),
            ("D",  f"{p['D']:.0f} mm"),
            ("dv", f"{p['dv']:.0f} mm"),
            ("f'c", f"{p['fc']:.0f} MPa"),
            ("fy",  f"{p['fy']:.0f} MPa"),
            ("Ws",  f"{p['Ws']:.0f} mm"),
            ("DL",  f"{p['DL']:.3f} kN/m"),
            ("LL",  f"{p['LL']:.3f} kN/m"),
        ]

        if self.solution:
            s = self.solution
            unlocked = self.passed | self.revealed
            extras = []
            if 1 in unlocked:
                extras.append(("Wu",  f"{s['Wu']:.3f} kN/m"))
                extras.append(("Vu",  f"{s['Vu']:.3f} kN"))
            if 2 in unlocked:
                extras.append(("Vud", f"{s['Vud']:.3f} kN"))
            if 3 in unlocked:
                extras.append(("ØVc", f"{s['phiVc']:.3f} kN"))
            if 6 in unlocked:
                extras.append(("Smax", f"{s['Smax']:.0f} mm"))
            items = items + extras

        # Wrap into however many columns actually fit on this screen.
        width = self.winfo_width()
        if width < 100:
            width = self.winfo_screenwidth()
        usable = width - (270 if self._hist_visible else 40)
        usable = max(400, usable)
        cols = max(4, min(len(items), usable // 105))

        for i, (label, val) in enumerate(items):
            r, c = divmod(i, cols)
            is_extra = i >= 10
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

        # right-side buttons first, so the expanding status label doesn't eat them
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
            1: "Step 1 — Wu and Vu",
            2: "Step 2 — Vud (critical section)",
            3: "Step 3 — Vc and ØVc  +  branch decision",
            4: "Step 4 — ØVs and Vs  +  max-Vs check",
            5: "Step 5 — Av and S_req",
            6: "Step 6 — Vs, thresholds, and S_max",
            7: "Step 7 — Layout zoning",
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

        # reset scroll to top on every page change
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
        if self.page in (1, 2, 3, 4, 5, 6, 7):
            if self.page not in self.passed and self.page not in self.revealed:
                if not messagebox.askyesno("Skip check?",
                        "You haven't checked this step. Continue anyway?"):
                    return
        if self.page == 3 and self.solution:
            if self.solution["branch"] in ("none", "min"):
                self._show_page(8)
                return
        if self.page == 4 and self.solution and self.solution.get("redesign"):
            self._show_page(8)
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
        top.pack(anchor="w", pady=(0, 10))

        tk.Label(top, text="Branch to test:", bg="#f4f4f4",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.branch_var = self._mk_var("setup.branch", BRANCH_NORM)
        cb = ttk.Combobox(top, textvariable=self.branch_var, values=BRANCHES,
                          width=28, state="readonly")
        cb.pack(side="left", padx=8)

        tk.Button(top, text="🎲 Randomize", bg="#ffe9b3", width=13,
                  command=self._randomize).pack(side="left", padx=6)
        tk.Button(top, text="▶ Start Review", bg="#cde8cd", width=13,
                  command=self._start_review).pack(side="left", padx=6)

        tk.Label(f, text="Given / Properties (editable)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(6, 4))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w", pady=(0, 8))

        fields = [
            ("ln (mm)",  "ln",  "{:.0f}"),
            ("b (mm)",   "b",   "{:.0f}"),
            ("d (mm)",   "d",   "{:.0f}"),
            ("D (mm)",   "D",   "{:.0f}"),
            ("dv (mm)",  "dv",  "{:.0f}"),
            ("f'c (MPa)","fc",  "{:.0f}"),
            ("fy (MPa)", "fy",  "{:.0f}"),
            ("Ws (mm)",  "Ws",  "{:.0f}"),
            ("DL (kN/m)","DL",  "{:.3f}"),
            ("LL (kN/m)","LL",  "{:.3f}"),
        ]
        self.prop_vars = {}
        for i, (label, key, _) in enumerate(fields):
            row, col = divmod(i, 2)
            tk.Label(grid, text=label, bg="#f4f4f4").grid(row=row, column=col * 2,
                                                          sticky="e", padx=(0, 6), pady=3)
            v = self._mk_var(f"prop.{key}", f"{self.problem[key]:.4g}")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=row, column=col * 2 + 1, sticky="w", padx=(0, 20), pady=3)
            self.prop_vars[key] = v

        tk.Label(f, text="Edit any field, then click Start Review. Or Randomize to generate a new problem.",
                 bg="#f4f4f4", fg="#666", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(4, 0))

    def _read_props(self):
        try:
            for key in ["ln", "b", "d", "D", "dv", "fc", "fy", "Ws", "DL", "LL"]:
                self.problem[key] = float(self.prop_vars[key].get())
        except ValueError:
            messagebox.showerror("Invalid", "All properties must be numeric.")
            return False
        if self.problem["d"] >= self.problem["D"]:
            messagebox.showerror("Invalid", "d must be less than D.")
            return False
        if self.problem["ln"] / 2.0 <= self.problem["Ws"] / 2.0 + self.problem["d"]:
            messagebox.showerror("Invalid", "ln is too short for the given Ws and d.")
            return False
        return True

    def _randomize(self):
        target = self.branch_var.get()
        try:
            p = random_problem(target)
        except Exception as e:
            messagebox.showerror("Randomizer error", f"Could not generate: {e}")
            return
        self.problem = p
        for key in ["ln", "b", "d", "D", "dv", "fc", "fy", "Ws", "DL", "LL"]:
            self.prop_vars[key].set(f"{p[key]:.4g}")
        self._refresh_top_given()
        self.log(f"Randomized ({target}).", "gray")
        self._set_status("New problem generated. Click Start Review.", "#0a5")

    def _start_review(self):
        if not self._read_props():
            return
        self.solution = solve_all(self.problem)
        self._refresh_top_given()
        self.passed.clear()
        self.revealed.clear()
        # wipe user answers for the steps so we don't carry over old typed values
        for k in list(self.user_inputs.keys()):
            if k.startswith("s1.") or k.startswith("s2.") or k.startswith("s3.") \
               or k.startswith("s4.") or k.startswith("s5.") or k.startswith("s6.") \
               or k.startswith("s7."):
                del self.user_inputs[k]
        self.log("— Review started —", "head")
        br = self.solution["branch"]
        self.log(f"Target branch: {self.branch_var.get()}", "gray")
        self.log(f"Actual branch: {br}", "gray")
        self._show_page(1)

    # ==============================================================
    # PAGE 1
    # ==============================================================
    def _build_page_1(self):
        f = self.step_area
        p = self.problem
        tk.Label(f, text=f"Wu = 1.2 DL + 1.6 LL    with DL = {p['DL']:.3f} kN/m, LL = {p['LL']:.3f} kN/m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="Vu = Wu · ln / 2", bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="Wu =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v1 = self._mk_var("s1.Wu", "")
        e1 = tk.Entry(grid, textvariable=v1, width=14, justify="center")
        e1.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN/m", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        tk.Label(grid, text="Vu =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v2 = self._mk_var("s1.Vu", "")
        e2 = tk.Entry(grid, textvariable=v2, width=14, justify="center")
        e2.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        self.s1_wu = (v1, e1); self.s1_vu = (v2, e2)

    # ==============================================================
    # PAGE 2
    # ==============================================================
    def _build_page_2(self):
        f = self.step_area
        p = self.problem
        half = p["ln"] / 2.0
        offset = p["Ws"] / 2.0 + p["d"]
        tk.Label(f, text=f"By ratio and proportion at d = {p['d']:.0f} mm from face of support:",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text=f"Vu / (ln/2) = Vud / (ln/2 − Ws/2 − d)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text=f"ln/2 = {half:.3f} mm,   Ws/2 = {p['Ws']/2:.0f} mm,   d = {p['d']:.0f} mm   →   denominator = {half - offset:.3f} mm",
                 bg="#f4f4f4", fg="#666", wraplength=760, justify="left").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="Vud =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v = self._mk_var("s2.Vud", "")
        e = tk.Entry(grid, textvariable=v, width=14, justify="center")
        e.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        self.s2_vud = (v, e)

    # ==============================================================
    # PAGE 3
    # ==============================================================
    def _build_page_3(self):
        f = self.step_area
        p = self.problem
        tk.Label(f, text=f"Vc = 0.17 λ √f'c · b · d   with λ = 1.0, f'c = {p['fc']:.0f} MPa",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text=f"ØVc = 0.75 · Vc", bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="Vc =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v1 = self._mk_var("s3.Vc", "")
        e1 = tk.Entry(grid, textvariable=v1, width=14, justify="center")
        e1.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        tk.Label(grid, text="ØVc =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v2 = self._mk_var("s3.phiVc", "")
        e2 = tk.Entry(grid, textvariable=v2, width=14, justify="center")
        e2.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        self.s3_vc = (v1, e1); self.s3_phivc = (v2, e2)

        tk.Label(f, text="Branch decision — pick the correct path:",
                 bg="#f4f4f4", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.branch_pick = self._mk_var("s3.branch_pick", "")
        for lbl in [
            "Vud ≤ 0.5 ØVc  →  no stirrups required",
            "0.5 ØVc < Vud ≤ ØVc  →  minimum stirrups only",
            "Vud > ØVc  →  design stirrups",
        ]:
            tk.Radiobutton(f, text=lbl, variable=self.branch_pick, value=lbl,
                           bg="#f4f4f4", anchor="w", justify="left").pack(anchor="w")

    # ==============================================================
    # PAGE 4
    # ==============================================================
    def _build_page_4(self):
        f = self.step_area
        tk.Label(f, text="ØVs = Vud − ØVc       Vs = ØVs / 0.75",
                bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="ØVs =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v1 = self._mk_var("s4.phiVs", "")
        e1 = tk.Entry(grid, textvariable=v1, width=14, justify="center")
        e1.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        tk.Label(grid, text="Vs =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v2 = self._mk_var("s4.Vs", "")
        e2 = tk.Entry(grid, textvariable=v2, width=14, justify="center")
        e2.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        self.s4_phivs = (v1, e1); self.s4_vs = (v2, e2)

        tk.Label(f, text="Max check: Vs_max = 0.66 √f'c · b · d  (kN)",
                bg="#f4f4f4", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        tk.Label(f, text="If Vs > Vs_max, section must be redesigned (larger b or d).",
                bg="#f4f4f4", fg="#666").pack(anchor="w")

        # Show the cap so you know if you're in redesign territory
        if self.solution and self.solution["branch"] == "design":
            vs_max = self.solution["Vs_max"]
            tk.Label(f, text=f"Section cap: Vs_max = {vs_max:.3f} kN",
                    bg="#f4f4f4", fg="#a67c00", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(6, 0))

    # ==============================================================
    # PAGE 5
    # ==============================================================
    def _build_page_5(self):
        f = self.step_area
        tk.Label(f, text="Av = 2 · π/4 · dv²     (2 legs assumed)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="S_req = Ø · Av · fy · d / ØVs     (round DOWN to nearest 50 mm)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="Av =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v1 = self._mk_var("s5.Av", "")
        e1 = tk.Entry(grid, textvariable=v1, width=14, justify="center")
        e1.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="mm²", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        tk.Label(grid, text="S_req (raw) =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v2 = self._mk_var("s5.Sreq_raw", "")
        e2 = tk.Entry(grid, textvariable=v2, width=14, justify="center")
        e2.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="mm", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        tk.Label(grid, text="S_req (rounded) =", bg="#f4f4f4").grid(row=2, column=0, sticky="e", pady=3)
        v3 = self._mk_var("s5.Sreq", "")
        e3 = tk.Entry(grid, textvariable=v3, width=14, justify="center")
        e3.grid(row=2, column=1, pady=3)
        tk.Label(grid, text="mm", bg="#f4f4f4").grid(row=2, column=2, sticky="w", padx=6)
        self.s5_av = (v1, e1); self.s5_sraw = (v2, e2); self.s5_sreq = (v3, e3)

    # ==============================================================
    # PAGE 6  (Vs_max and S_Avmin fields removed per request)
    # ==============================================================
    def _build_page_6(self):
        f = self.step_area
        tk.Label(f, text="Compute each candidate, then governing S_max.",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("Vs", "s6.Vs", "kN"),
            ("0.33 √f'c · b · d", "s6.thresh_low", "kN"),
            ("Branch S_max (0.5d & 600  or  0.25d & 300)", "s6.Sbranch", "mm"),
            ("S_max (governing, cap 200)", "s6.Smax", "mm"),
        ]
        self.s6_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s6_entries[key] = (v, e)

    # ==============================================================
    # PAGE 7
    # ==============================================================
    def _build_page_7(self):
        f = self.step_area
        tk.Label(f, text="Layout zoning — where each spacing applies.",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="ln_max = ØVc · (ln/2) / Vu     L_req = ln/2 − Ws/2 − 50 − ln_max",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="N_req = ceil(L_req / S_req)     N_max = ceil(ln_max / S_max)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("ln_max", "s7.lnmax", "mm"),
            ("L_req",  "s7.Lreq",  "mm"),
            ("N_req",  "s7.Nreq",  "pcs"),
            ("N_max",  "s7.Nmax",  "pcs"),
        ]
        self.s7_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s7_entries[key] = (v, e)

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
        br = s["branch"]

        if br == "none":
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#0a7a0a")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="NO STIRRUPS REQUIRED", font=("Segoe UI", 13, "bold"),
                     fg="#0a7a0a", bg="#ffffff").pack(padx=16, pady=12)
            tk.Label(f, text=f"Reason: Vud ({s['Vud']:.3f} kN) ≤ 0.5 ØVc ({s['half_phiVc']:.3f} kN).",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
            tk.Label(f, text="Concrete alone can carry the shear. Provide nominal ties per code.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
        elif br == "min":
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#a67c00")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="MINIMUM STIRRUPS ONLY", font=("Segoe UI", 13, "bold"),
                     fg="#a67c00", bg="#ffffff").pack(padx=16, pady=12)
            tk.Label(f, text=f"Reason: 0.5 ØVc ({s['half_phiVc']:.3f}) < Vud ({s['Vud']:.3f}) ≤ ØVc ({s['phiVc']:.3f}).",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
            tk.Label(f, text=f"Provide Avmin. Governing S_max = {s['Smax']:.0f} mm.",
                     bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(4, 0))
            tk.Label(f, text=f"Layout: 1 @ 50 mm, then REST @ {s['Smax']:.0f} mm.",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
        elif s.get("redesign"):
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#a00")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="REDESIGN SECTION", font=("Segoe UI", 13, "bold"),
                     fg="#a00", bg="#ffffff").pack(padx=16, pady=12)
            tk.Label(f, text=f"Vs ({s['Vs']:.3f} kN) > Vs_max ({s['Vs_max']:.3f} kN).",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
            tk.Label(f, text="Section too small for required shear reinforcement. Increase b or d.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
        else:
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#0a7a0a")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="FINAL STIRRUP LAYOUT", font=("Segoe UI", 11, "bold"),
                     bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(10, 6))
            tk.Label(box, text=f"{s['dv']:.0f} mmØ stirrups spaced at:",
                     font=("Segoe UI", 11), bg="#ffffff").grid(row=1, column=0, columnspan=2)
            tk.Label(box,
                     text=f"1 @ 50 mm,  {s['N_req']} @ {s['S_req']:.0f} mm,  REST @ {s['Smax']:.0f} mm",
                     font=("Consolas", 13, "bold"), fg="#0a7a0a", bg="#ffffff").grid(
                         row=2, column=0, columnspan=2, padx=16, pady=(6, 12))

            if not s["spacing_ok"]:
                tk.Label(f, text=f"⚠ Warning: S_req ({s['S_req']:.0f}) > S_max ({s['Smax']:.0f}). "
                                 f"Use S_max or increase bar size / legs.",
                         bg="#f4f4f4", fg="#a00", wraplength=760, justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(f, text="Recap:", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(14, 4))
        recap = tk.Text(f, width=72, height=12, font=("Consolas", 9), bg="#ffffff")
        recap.pack(anchor="w", fill="x")
        lines = [
            f"ln = {s['ln']:.0f} mm   b = {s['b']:.0f} mm   d = {s['d']:.0f} mm   D = {s['D']:.0f} mm",
            f"dv = {s['dv']:.0f} mm   f'c = {s['fc']:.0f} MPa   fy = {s['fy']:.0f} MPa   Ws = {s['Ws']:.0f} mm",
            f"DL = {s['DL']:.3f} kN/m   LL = {s['LL']:.3f} kN/m",
            "",
            f"Wu   = {s['Wu']:.3f} kN/m",
            f"Vu   = {s['Vu']:.3f} kN",
            f"Vud  = {s['Vud']:.3f} kN",
            f"Vc   = {s['Vc']:.3f} kN   ØVc = {s['phiVc']:.3f} kN",
        ]
        if br == "design":
            lines += [
                f"ØVs  = {s['phiVs']:.3f} kN   Vs = {s['Vs']:.3f} kN",
                f"Vs_max = {s['Vs_max']:.3f} kN   redesign = {s['redesign']}",
                f"Av   = {s['Av']:.3f} mm²   S_req = {s['S_req']:.0f} mm",
                f"Vs_low_limit = {s['Vs_low_limit']:.3f} kN   branch_smax = {s['branch_smax']}",
                f"S_branch = {s['S_branch']:.0f} mm   S_Avmin = {s['S_Avmin']:.3f} mm   S_max = {s['Smax']:.0f} mm",
                f"ln_max = {s['ln_max']:.3f} mm   L_req = {s['L_req']:.3f} mm",
                f"N_req = {s['N_req']}   N_max = {s['N_max']}",
            ]
        for ln in lines:
            recap.insert("end", ln + "\n")
        recap.configure(state="disabled")

        tk.Button(f, text="Copy Summary to Clipboard", bg="#c9daf8",
                  command=self.copy_summary).pack(anchor="w", pady=(10, 0))

    # ==============================================================
    # CHECK LOGIC
    # ==============================================================
    def _set_status(self, msg, color="#333"):
        self.status.configure(text=msg, fg=color)

    def _mark(self, widget, ok):
        try:
            widget.configure(bg=("#e0ffe0" if ok else "#ffe0e0"))
        except tk.TclError:
            pass

    def _set_entry(self, pair, value_str):
        """Force an entry to show a value (defensive: sets both var and widget)."""
        var, entry = pair
        var.set(value_str)
        try:
            entry.delete(0, "end")
            entry.insert(0, value_str)
            entry.configure(bg="#e0ffe0")
        except tk.TclError:
            pass

    def check_current(self):
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
        u = parse(self.s1_wu[0].get()); ok1 = u is not None and close(u, s["Wu"]); self._mark(self.s1_wu[1], ok1)
        v = parse(self.s1_vu[0].get()); ok2 = v is not None and close(v, s["Vu"]); self._mark(self.s1_vu[1], ok2)
        if ok1 and ok2:
            self._set_status("✓ Step 1 correct!", "#0a7a0a")
            self.log(f"Step 1: Wu={fmt(s['Wu'])}, Vu={fmt(s['Vu'])} correct.", "green")
            self.passed.add(1); self.revealed.discard(1)
        else:
            msgs = []
            if not ok1: msgs.append(f"Wu: expected {fmt(s['Wu'])} kN/m (got {u})")
            if not ok2: msgs.append(f"Vu: expected {fmt(s['Vu'])} kN (got {v})")
            self._set_status("✗ Step 1 has errors.", "#a00")
            self.log("Step 1 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 1", "\n".join(msgs))

    def _check_step2(self):
        s = self.solution
        v = parse(self.s2_vud[0].get())
        ok = v is not None and close(v, s["Vud"])
        self._mark(self.s2_vud[1], ok)
        if ok:
            self._set_status("✓ Step 2 correct!", "#0a7a0a")
            self.log(f"Step 2: Vud={fmt(s['Vud'])} correct.", "green")
            self.passed.add(2); self.revealed.discard(2)
        else:
            self._set_status("✗ Step 2 has errors.", "#a00")
            self.log(f"Step 2 attempted — Vud expected {fmt(s['Vud'])} (got {v}).", "yellow")
            messagebox.showwarning("Step 2", f"Vud: expected {fmt(s['Vud'])} kN (got {v})")

    def _check_step3(self):
        s = self.solution
        u = parse(self.s3_vc[0].get()); vc_ok = u is not None and close(u, s["Vc"]); self._mark(self.s3_vc[1], vc_ok)
        v = parse(self.s3_phivc[0].get()); phivc_ok = v is not None and close(v, s["phiVc"]); self._mark(self.s3_phivc[1], phivc_ok)

        if s["branch"] == "none":
            expected_branch = "Vud ≤ 0.5 ØVc  →  no stirrups required"
        elif s["branch"] == "min":
            expected_branch = "0.5 ØVc < Vud ≤ ØVc  →  minimum stirrups only"
        else:
            expected_branch = "Vud > ØVc  →  design stirrups"
        br_ok = (self.branch_pick.get() == expected_branch)

        if vc_ok and phivc_ok and br_ok:
            self._set_status("✓ Step 3 correct!", "#0a7a0a")
            self.log(f"Step 3: Vc={fmt(s['Vc'])}, ØVc={fmt(s['phiVc'])}, branch={s['branch']} correct.", "green")
            self.passed.add(3); self.revealed.discard(3)
        else:
            msgs = []
            if not vc_ok: msgs.append(f"Vc: expected {fmt(s['Vc'])} kN (got {u})")
            if not phivc_ok: msgs.append(f"ØVc: expected {fmt(s['phiVc'])} kN (got {v})")
            if not br_ok: msgs.append(f"Branch: expected '{expected_branch}' (got '{self.branch_pick.get()}')")
            self._set_status("✗ Step 3 has errors.", "#a00")
            self.log("Step 3 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 3", "\n".join(msgs))

    def _check_step4(self):
        s = self.solution
        u = parse(self.s4_phivs[0].get()); phivs_ok = u is not None and close(u, s["phiVs"]); self._mark(self.s4_phivs[1], phivs_ok)
        v = parse(self.s4_vs[0].get()); vs_ok = v is not None and close(v, s["Vs"]); self._mark(self.s4_vs[1], vs_ok)
        if phivs_ok and vs_ok:
            self._set_status("✓ Step 4 correct!", "#0a7a0a")
            self.log(f"Step 4: ØVs={fmt(s['phiVs'])}, Vs={fmt(s['Vs'])} correct.", "green")
            self.passed.add(4); self.revealed.discard(4)
        else:
            msgs = []
            if not phivs_ok: msgs.append(f"ØVs: expected {fmt(s['phiVs'])} kN (got {u})")
            if not vs_ok: msgs.append(f"Vs: expected {fmt(s['Vs'])} kN (got {v})")
            self._set_status("✗ Step 4 has errors.", "#a00")
            self.log("Step 4 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 4", "\n".join(msgs))

    def _check_step5(self):
        s = self.solution
        a = parse(self.s5_av[0].get()); av_ok = a is not None and close(a, s["Av"]); self._mark(self.s5_av[1], av_ok)
        b = parse(self.s5_sraw[0].get()); sraw_ok = b is not None and close(b, s["S_req_raw"]); self._mark(self.s5_sraw[1], sraw_ok)
        c = parse(self.s5_sreq[0].get()); sreq_ok = c is not None and close(c, s["S_req"]); self._mark(self.s5_sreq[1], sreq_ok)
        if av_ok and sraw_ok and sreq_ok:
            self._set_status("✓ Step 5 correct!", "#0a7a0a")
            self.log(f"Step 5: Av={fmt(s['Av'])}, S_req={fmt(s['S_req'])} correct.", "green")
            self.passed.add(5); self.revealed.discard(5)
        else:
            msgs = []
            if not av_ok: msgs.append(f"Av: expected {fmt(s['Av'])} mm² (got {a})")
            if not sraw_ok: msgs.append(f"S_req raw: expected {fmt(s['S_req_raw'])} mm (got {b})")
            if not sreq_ok: msgs.append(f"S_req rounded: expected {fmt(s['S_req'])} mm (got {c})")
            self._set_status("✗ Step 5 has errors.", "#a00")
            self.log("Step 5 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 5", "\n".join(msgs))

    def _check_step6(self):
        s = self.solution
        expected = {
            "s6.Vs": s["Vs"],
            "s6.thresh_low": s["Vs_low_limit"],
            "s6.Sbranch": s["S_branch"],
            "s6.Smax": s["Smax"],
        }
        all_ok = True
        msgs = []
        for k, exp in expected.items():
            u = parse(self.s6_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s6_entries[k][1], ok)
            if not ok:
                all_ok = False
                msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 6 correct!", "#0a7a0a")
            self.log(f"Step 6: S_max={fmt(s['Smax'])} correct.", "green")
            self.passed.add(6); self.revealed.discard(6)
        else:
            self._set_status("✗ Step 6 has errors.", "#a00")
            self.log("Step 6 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 6", "\n".join(msgs[:8]))

    def _check_step7(self):
        s = self.solution
        expected = {
            "s7.lnmax": s["ln_max"],
            "s7.Lreq": s["L_req"],
            "s7.Nreq": float(s["N_req"]),
            "s7.Nmax": float(s["N_max"]),
        }
        all_ok = True
        msgs = []
        for k, exp in expected.items():
            u = parse(self.s7_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s7_entries[k][1], ok)
            if not ok:
                all_ok = False
                msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 7 correct! You're ready for the summary.", "#0a7a0a")
            self.log(f"Step 7: N_req={s['N_req']}, N_max={s['N_max']} correct.", "green")
            self.passed.add(7); self.revealed.discard(7)
        else:
            self._set_status("✗ Step 7 has errors.", "#a00")
            self.log("Step 7 attempted — errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 7", "\n".join(msgs))

    # ==============================================================
    # REVEAL — defensive: use _set_entry to force widget update
    # ==============================================================
    def reveal_current(self):
        if not self.solution:
            return
        s = self.solution
        p = self.page
        if p == 1:
            self._set_entry(self.s1_wu, fmt(s["Wu"]))
            self._set_entry(self.s1_vu, fmt(s["Vu"]))
        elif p == 2:
            self._set_entry(self.s2_vud, fmt(s["Vud"]))
        elif p == 3:
            self._set_entry(self.s3_vc, fmt(s["Vc"]))
            self._set_entry(self.s3_phivc, fmt(s["phiVc"]))
            if s["branch"] == "none":
                self.branch_pick.set("Vud ≤ 0.5 ØVc  →  no stirrups required")
            elif s["branch"] == "min":
                self.branch_pick.set("0.5 ØVc < Vud ≤ ØVc  →  minimum stirrups only")
            else:
                self.branch_pick.set("Vud > ØVc  →  design stirrups")
        elif p == 4:
            self._set_entry(self.s4_phivs, fmt(s["phiVs"]))
            self._set_entry(self.s4_vs, fmt(s["Vs"]))
        elif p == 5:
            self._set_entry(self.s5_av, fmt(s["Av"]))
            self._set_entry(self.s5_sraw, fmt(s["S_req_raw"]))
            self._set_entry(self.s5_sreq, fmt(s["S_req"]))
        elif p == 6:
            vals = {
                "s6.Vs": s["Vs"], "s6.thresh_low": s["Vs_low_limit"],
                "s6.Sbranch": s["S_branch"], "s6.Smax": s["Smax"],
            }
            for k, v in vals.items():
                self._set_entry(self.s6_entries[k], fmt(v))
        elif p == 7:
            vals = {
                "s7.lnmax": s["ln_max"], "s7.Lreq": s["L_req"],
                "s7.Nreq": float(s["N_req"]), "s7.Nmax": float(s["N_max"]),
            }
            for k, v in vals.items():
                self._set_entry(self.s7_entries[k], fmt(v))
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
        lines = ["RCD Shear Design — Summary", "=" * 40]
        lines += [
            f"ln = {s['ln']:.0f} mm   b = {s['b']:.0f} mm   d = {s['d']:.0f} mm   D = {s['D']:.0f} mm",
            f"dv = {s['dv']:.0f} mm   f'c = {s['fc']:.0f} MPa   fy = {s['fy']:.0f} MPa   Ws = {s['Ws']:.0f} mm",
            f"DL = {s['DL']:.3f} kN/m   LL = {s['LL']:.3f} kN/m",
            "",
            f"Wu = {s['Wu']:.3f} kN/m",
            f"Vu = {s['Vu']:.3f} kN",
            f"Vud = {s['Vud']:.3f} kN",
            f"Vc = {s['Vc']:.3f} kN   ØVc = {s['phiVc']:.3f} kN",
        ]
        br = s["branch"]
        if br == "none":
            lines.append("Result: NO STIRRUPS REQUIRED")
        elif br == "min":
            lines.append(f"Result: MINIMUM STIRRUPS ONLY — Smax = {s['Smax']:.0f} mm")
        else:
            lines += [
                f"ØVs = {s['phiVs']:.3f} kN   Vs = {s['Vs']:.3f} kN",
                f"Vs_max = {s['Vs_max']:.3f} kN",
                f"Av = {s['Av']:.3f} mm²   S_req = {s['S_req']:.0f} mm",
                f"S_max = {s['Smax']:.0f} mm",
                f"ln_max = {s['ln_max']:.3f} mm   L_req = {s['L_req']:.3f} mm",
                f"N_req = {s['N_req']}   N_max = {s['N_max']}",
            ]
            if s.get("redesign"):
                lines.append("Result: REDESIGN SECTION")
            else:
                lines.append(f"Result: 1 @ 50mm, {s['N_req']} @ {s['S_req']:.0f} mm, REST @ {s['Smax']:.0f} mm")
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Summary copied to clipboard.", "#0a7a0a")
        self.log("Summary copied to clipboard.", "gray")


if __name__ == "__main__":
    app = ShearDesigner()
    app.mainloop()