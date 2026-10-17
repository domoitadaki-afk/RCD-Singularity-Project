"""
RCD DRB Design Reviewer — NSCP 2015 Ultimate Strength Design
Single-file Tkinter app. No external dependencies.

Flow:
  Setup (given b, d, D, cc, db, Mu, materials) -> Step 1..7 -> Summary
Doubly-reinforced design. Assumes phi = 0.90 throughout.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import random

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
PHI = 0.90
TOL = 0.005
DAGG_DEFAULT = 19.0
BAR_CHOICES = [16, 20, 22, 25, 26, 28, 32, 36]   # for auto-retry expansion

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

def beta1(fc):
    if fc <= 28:
        return 0.85
    elif fc <= 55:
        return 0.85 - 0.05 * (fc - 28) / 7.0
    else:
        return 0.65

# ------------------------------------------------------------------
# SOLVER
# ------------------------------------------------------------------
def solve_all(p):
    """p keys: b, d, D, cc, db, fc, fy, dagg, Mu (kN·m). phi=0.90 fixed."""
    b = p["b"]; d = p["d"]; D = p["D"]; cc = p["cc"]
    db = p["db"]; fc = p["fc"]; fy = p["fy"]; dagg = p["dagg"]
    Mu = p["Mu"]

    out = {
        "b": b, "d": d, "D": D, "cc": cc, "db": db,
        "fc": fc, "fy": fy, "dagg": dagg, "Mu": Mu, "phi": PHI,
    }

    # ---------- Step 2: rho_max and As_max ----------
    b1 = beta1(fc)
    rho_max = (3.0 / 8.0) * (0.85 * b1 * fc / fy)
    As_max = rho_max * b * d
    out["beta1"] = b1
    out["rho_max"] = rho_max
    out["As_max"] = As_max

    # ---------- Step 3: a, c, fs ----------
    a = As_max * fy / (0.85 * fc * b)
    c = a / b1
    fs = 600.0 * (d - c) / c
    out["a"] = a
    out["c"] = c
    out["fs"] = fs
    out["steel_yields"] = fs > fy

    # transition-phi report (not used in design)
    if fs <= fy:
        phi_check = 0.65
    elif fs < 1000.0:
        phi_check = 0.65 + 0.25 * (fs - fy) / (1000.0 - fy)
    else:
        phi_check = 0.90
    out["phi_check"] = phi_check

    # ---------- Step 4: phi Mn1 ----------
    phiMn1 = PHI * As_max * fy * (d - a / 2.0) / 1e6   # kN·m
    out["phiMn1"] = phiMn1
    out["is_drb"] = Mu > phiMn1

    if not out["is_drb"]:
        return out

    # ---------- Step 5: phi Mn2, As2, AsT ----------
    phiMn2 = Mu - phiMn1
    As2 = phiMn2 * 1e6 / (PHI * fy * (d - cc))
    AsT = As_max + As2
    out["phiMn2"] = phiMn2
    out["As2"] = As2
    out["AsT"] = AsT
    out["d_prime"] = cc

    # ---------- Step 6: bar counts (initial, using db) ----------
    Ab = math.pi * db * db / 4.0
    nb_total_exact = AsT / Ab
    nb_comp_exact  = As2 / Ab
    nb_total = math.ceil(nb_total_exact)
    nb_comp  = math.ceil(nb_comp_exact)
    nb_tension = nb_total - nb_comp
    out["Ab"] = Ab
    out["nb_total_exact"] = nb_total_exact
    out["nb_comp_exact"] = nb_comp_exact
    out["nb_total"] = nb_total
    out["nb_comp"] = nb_comp
    out["nb_tension"] = nb_tension

    # ---------- Step 7: verify with actual bars; auto-retry with bigger db ----------
    def verify(db_try, nb_tot, nb_c):
        Ab_try = math.pi * db_try * db_try / 4.0
        As1_actual = (nb_tot - nb_c) * Ab_try
        As2_actual = nb_c * Ab_try
        phiMn1_act = PHI * As1_actual * fy * (d - a / 2.0) / 1e6
        phiMn2_act = PHI * As2_actual * fy * (d - cc) / 1e6
        return As1_actual, As2_actual, phiMn1_act, phiMn2_act, phiMn1_act + phiMn2_act

    attempts = []
    final_db = db
    final_nb_tot = nb_total
    final_nb_c = nb_comp
    final_As1 = final_As2 = final_phiMn1 = final_phiMn2 = final_phiMn = None
    ok = False

    # first attempt with given db
    A1, A2, PM1, PM2, PMtot = verify(final_db, final_nb_tot, final_nb_c)
    attempts.append((final_db, final_nb_tot, final_nb_c, A1, A2, PM1, PM2, PMtot))
    if PMtot >= Mu:
        ok = True
        final_As1, final_As2, final_phiMn1, final_phiMn2, final_phiMn = A1, A2, PM1, PM2, PMtot
    else:
        # auto-retry: try larger db sizes, recompute nb from AsT/Ab
        for db_try in BAR_CHOICES:
            if db_try <= final_db:
                continue
            Ab_try = math.pi * db_try * db_try / 4.0
            nb_tot_try = math.ceil(AsT / Ab_try)
            nb_c_try   = math.ceil(As2 / Ab_try)
            if nb_tot_try < 2 or nb_tot_try > 20:
                continue
            A1t, A2t, PM1t, PM2t, PMtott = verify(db_try, nb_tot_try, nb_c_try)
            attempts.append((db_try, nb_tot_try, nb_c_try, A1t, A2t, PM1t, PM2t, PMtott))
            if PMtott >= Mu:
                ok = True
                final_db = db_try
                final_nb_tot = nb_tot_try
                final_nb_c = nb_c_try
                final_As1, final_As2, final_phiMn1, final_phiMn2, final_phiMn = A1t, A2t, PM1t, PM2t, PMtott
                break

    out["attempts"] = attempts
    out["verify_ok"] = ok
    out["final_db"] = final_db
    out["final_nb_total"] = final_nb_tot
    out["final_nb_comp"] = final_nb_c
    out["final_nb_tension"] = final_nb_tot - final_nb_c
    out["final_As1"] = final_As1
    out["final_As2"] = final_As2
    out["final_phiMn1"] = final_phiMn1
    out["final_phiMn2"] = final_phiMn2
    out["final_phiMn"] = final_phiMn

    return out

# ------------------------------------------------------------------
# RANDOMIZER (targets DRB)
# ------------------------------------------------------------------
def random_problem():
    for _ in range(300):
        b  = float(random.choice([300, 320, 350, 380, 400]))
        d  = float(random.choice([500, 550, 600, 650, 700, 710]))
        cc = float(random.choice([60, 65, 70, 75]))
        D  = d + cc
        db = float(random.choice([20, 25, 28, 32]))
        fc = random.choice([21.0, 24.0, 27.6, 28.0])
        fy = random.choice([275.0, 345.0, 415.0, 420.0])
        dagg = random.choice([19.0, 25.0])

        # Need a Mu high enough to trigger DRB. Compute phiMn1 first and set Mu
        # to something ~1.15-1.6x phiMn1.
        b1 = beta1(fc)
        rho_max = (3.0 / 8.0) * (0.85 * b1 * fc / fy)
        As_max = rho_max * b * d
        a = As_max * fy / (0.85 * fc * b)
        phiMn1 = PHI * As_max * fy * (d - a / 2.0) / 1e6
        if phiMn1 <= 0:
            continue
        # cap the ratio so the resulting As2 is realistic
        ratio = random.uniform(1.15, 1.55)
        Mu = phiMn1 * ratio
        # sanity: As2 shouldn't exceed ~3x As_max
        As2_est = (Mu - phiMn1) * 1e6 / (PHI * fy * (d - cc))
        if As2_est > 3.0 * As_max or As2_est <= 0:
            continue
        return {"b": b, "d": d, "D": D, "cc": cc, "db": db,
                "fc": fc, "fy": fy, "dagg": dagg, "Mu": round(Mu, 2)}
    # fallback
    return {"b": 300.0, "d": 390.0, "D": 450.0, "cc": 60.0, "db": 28.0,
            "fc": 20.7, "fy": 275.0, "dagg": 19.0, "Mu": 400.0}

# ------------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------------
class DRBDesigner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD DRB Design Reviewer")

        # ---- fit the window to the actual screen (fix for 11" MacBook) ----
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = max(760, min(1260, sw - 40))
        win_h = max(520, min(860, sh - 120))   # leave room for menu bar + dock
        x = max(0, (sw - win_w) // 2)
        y = max(0, (sh - win_h) // 3)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(min(760, win_w), min(520, win_h))

        self.problem = {
            "b": 300.0, "d": 390.0, "D": 450.0, "cc": 60.0, "db": 28.0,
            "fc": 20.7, "fy": 275.0, "dagg": 19.0, "Mu": 400.0,
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
            ("b", f"{p['b']:.0f} mm"), ("d", f"{p['d']:.0f} mm"),
            ("D", f"{p['D']:.0f} mm"), ("cc = d'", f"{p['cc']:.0f} mm"),
            ("db", f"{p['db']:.0f} mm"),
            ("f'c", f"{p['fc']:.2f} MPa"), ("fy", f"{p['fy']:.0f} MPa"),
            ("Mu", f"{p['Mu']:.2f} kN·m"),
        ]
        base_count = len(items)

        if self.solution:
            s = self.solution
            unlocked = self.passed | self.revealed
            extras = []
            if 2 in unlocked:
                extras.append(("ρmax", f"{s['rho_max']:.5f}"))
                extras.append(("As_max", f"{s['As_max']:.1f}"))
            if 3 in unlocked:
                extras.append(("a", f"{s['a']:.3f}"))
                extras.append(("c", f"{s['c']:.3f}"))
            if 4 in unlocked:
                extras.append(("φMn1", f"{s['phiMn1']:.3f}"))
            if 5 in unlocked and s.get("is_drb"):
                extras.append(("AsT", f"{s['AsT']:.1f}"))
            if 6 in unlocked and s.get("is_drb"):
                extras.append(("nb_total", f"{s['nb_total']}"))
            if 7 in unlocked and s.get("is_drb"):
                extras.append(("final", f"{s['final_nb_tension']}+{s['final_nb_comp']}–{s['final_db']:.0f}mm"))
            items = items + extras

        # Wrap into however many columns actually fit on this screen.
        width = self.winfo_width()
        if width < 100:
            width = self.winfo_screenwidth()
        usable = width - (270 if self._hist_visible else 40)
        usable = max(400, usable)
        cols = max(4, min(len(items), usable // 110))

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
        for tag, col in [("green", "#0a7a0a"), ("yellow", "#a67c00"),
                         ("gray", "#666"), ("red", "#a00")]:
            self.hist_text.tag_config(tag, foreground=col)
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
            1: "Step 1 — Mu (given)",
            2: "Step 2 — ρmax and As_max",
            3: "Step 3 — a, c, fs",
            4: "Step 4 — φMn1 and DRB verdict",
            5: "Step 5 — φMn2, As2, AsT",
            6: "Step 6 — Bar counts (nb_total, nb_comp)",
            7: "Step 7 — Verification with actual bars",
            8: "Summary",
        }
        tk.Label(self.step_area, text=titles[n],
                 font=("Segoe UI", 14, "bold"), bg="#f4f4f4").pack(anchor="w", pady=(0, 8))
        builder = {
            0: self._build_page_0, 1: self._build_page_1, 2: self._build_page_2,
            3: self._build_page_3, 4: self._build_page_4, 5: self._build_page_5,
            6: self._build_page_6, 7: self._build_page_7, 8: self._build_page_8,
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
        if self.page == 0 and self.solution is None:
            messagebox.showinfo("Start Review first",
                                "Click 'Start Review' to lock in the given values.")
            return
        if self.page in (1, 2, 3, 4, 5, 6, 7):
            if self.page not in self.passed and self.page not in self.revealed:
                if not messagebox.askyesno("Skip check?",
                        "You haven't checked this step. Continue anyway?"):
                    return
        # SRB early exit — if not DRB, jump to summary
        if self.page == 4 and self.solution and not self.solution.get("is_drb"):
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
        tk.Button(top, text="🎲 Randomize (DRB)", bg="#ffe9b3", width=18,
                  command=self._randomize).pack(side="left", padx=2)
        tk.Button(top, text="▶ Start Review", bg="#cde8cd", width=14,
                  command=self._start_review).pack(side="left", padx=6)

        tk.Label(f, text="Given / Properties (editable)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(6, 4))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w", pady=(0, 8))

        fields = [
            ("b (mm)",   "b",  "{:.0f}"),
            ("d (mm)",   "d",  "{:.0f}"),
            ("D (mm)",   "D",  "{:.0f}"),
            ("cc = d' (mm)", "cc", "{:.0f}"),
            ("db (mm)",  "db", "{:.0f}"),
            ("f'c (MPa)","fc", "{:.2f}"),
            ("fy (MPa)", "fy", "{:.1f}"),
            ("dagg (mm)","dagg", "{:.1f}"),
            ("Mu (kN·m)","Mu", "{:.2f}"),
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

        tk.Label(f, text="Note: φ = 0.90 is assumed throughout (design assumption). "
                         "d' = cc.",
                 bg="#f4f4f4", fg="#666", font=("Segoe UI", 9, "italic"),
                 wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))

    def _read_props(self):
        try:
            for key in ["b", "d", "D", "cc", "db", "fc", "fy", "dagg", "Mu"]:
                self.problem[key] = float(self.prop_vars[key].get())
        except ValueError:
            messagebox.showerror("Invalid", "All properties must be numeric.")
            return False
        if self.problem["d"] >= self.problem["D"]:
            messagebox.showerror("Invalid", "d must be less than D.")
            return False
        if self.problem["cc"] >= self.problem["d"] / 2.0:
            messagebox.showerror("Invalid", "cc looks too large for this d.")
            return False
        return True

    def _randomize(self):
        try:
            p = random_problem()
        except Exception as e:
            messagebox.showerror("Randomizer error", str(e))
            return
        self.problem = p
        for key in ["b", "d", "D", "cc", "db", "fc", "fy", "dagg", "Mu"]:
            self.prop_vars[key].set(f"{p[key]:.4g}")
        self._refresh_top_given()
        self.log(f"Randomized (DRB).", "gray")
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
        self.log("— Review started —", "head")
        if self.solution.get("is_drb"):
            self.log("✓ Confirmed DRB (Mu > φMn1).", "gray")
        else:
            self.log("⚠ NOT DRB — Mu ≤ φMn1. This is SRB territory.", "yellow")
        self._show_page(1)

    # ==============================================================
    # PAGE 1 — Mu
    # ==============================================================
    def _build_page_1(self):
        f = self.step_area
        p = self.problem
        tk.Label(f, text=f"Mu is given directly: {p['Mu']:.3f} kN·m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="If Mu is given as MDL and MLL separately, compute Mu = 1.2 MDL + 1.6 MLL.",
                 bg="#f4f4f4", fg="#666", wraplength=720,
                 justify="left").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="Mu =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v = self._mk_var("s1.Mu", "")
        e = tk.Entry(grid, textvariable=v, width=14, justify="center")
        e.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN·m", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        self.s1_mu = (v, e)

    # ==============================================================
    # PAGE 2 — rho_max, As_max
    # ==============================================================
    def _build_page_2(self):
        f = self.step_area
        p = self.problem
        fc = p["fc"]; fy = p["fy"]
        b1 = beta1(fc)
        tk.Label(f, text=f"β₁ = {b1:.4f}  (f'c = {fc:.2f} MPa)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="ρmax = (3/8) · (0.85 β₁ f'c / fy)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="As_max = ρmax · b · d",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [("ρmax", "s2.rhomax", ""), ("As_max", "s2.Asmax", "mm²")]
        self.s2_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s2_entries[key] = (v, e)

    # ==============================================================
    # PAGE 3 — a, c, fs
    # ==============================================================
    def _build_page_3(self):
        f = self.step_area
        tk.Label(f, text="C = T  →  0.85 f'c · a · b = As_max · fy   →  a = As_max·fy / (0.85 f'c b)",
                 bg="#f4f4f4", fg="#333", wraplength=720,
                 justify="left").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="c = a / β₁",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="fs = 600·(d − c) / c    [check steel yields]",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [("a", "s3.a", "mm"), ("c", "s3.c", "mm"), ("fs", "s3.fs", "MPa")]
        self.s3_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s3_entries[key] = (v, e)
        tk.Label(f, text="Note: φ = 0.90 is used regardless (design assumption).",
                 bg="#f4f4f4", fg="#666", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(8, 0))

    # ==============================================================
    # PAGE 4 — phiMn1 + DRB check
    # ==============================================================
    def _build_page_4(self):
        f = self.step_area
        tk.Label(f, text="φMn1 = φ · As_max · fy · (d − a/2)     [φ = 0.90]",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="Compare: if Mu > φMn1, this is DRB. Else SRB.",
                 bg="#f4f4f4", fg="#666").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        tk.Label(grid, text="φMn1 =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v = self._mk_var("s4.phiMn1", "")
        e = tk.Entry(grid, textvariable=v, width=14, justify="center")
        e.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN·m", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        self.s4_phimn1 = (v, e)

        tk.Label(f, text="Verdict — pick one:", bg="#f4f4f4",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.verdict_pick = self._mk_var("s4.verdict", "")
        for lbl in ["Mu > φMn1  →  DRB (proceed with doubly)",
                    "Mu ≤ φMn1  →  SRB (not this app)"]:
            tk.Radiobutton(f, text=lbl, variable=self.verdict_pick, value=lbl,
                           bg="#f4f4f4", anchor="w", justify="left").pack(anchor="w")

    # ==============================================================
    # PAGE 5 — phiMn2, As2, AsT
    # ==============================================================
    def _build_page_5(self):
        f = self.step_area
        s = self.solution
        if s and not s.get("is_drb"):
            tk.Label(f, text="Not DRB — this step does not apply.",
                     bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            return
        tk.Label(f, text="φMn2 = Mu − φMn1", bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="As2 = φMn2 / (φ · fy · (d − d'))     [d' = cc]",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="AsT = As_max + As2",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [("φMn2", "s5.phiMn2", "kN·m"),
                ("As2 = A'_s", "s5.As2", "mm²"),
                ("AsT (total tension steel)", "s5.AsT", "mm²")]
        self.s5_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s5_entries[key] = (v, e)

    # ==============================================================
    # PAGE 6 — bar counts
    # ==============================================================
    def _build_page_6(self):
        f = self.step_area
        s = self.solution
        if s and not s.get("is_drb"):
            tk.Label(f, text="Not DRB — this step does not apply.",
                     bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            return
        tk.Label(f, text="Ab = π/4 · db²", bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="nb_total = ceil(AsT / Ab)     nb_comp = ceil(As2 / Ab)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="nb_tension = nb_total − nb_comp",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [("Ab", "s6.Ab", "mm²"),
                ("nb_total", "s6.nbtotal", "pcs"),
                ("nb_comp", "s6.nbcomp", "pcs"),
                ("nb_tension = nb_total − nb_comp", "s6.nbtens", "pcs")]
        self.s6_entries = {}
        for i, (label, key, unit) in enumerate(rows):
            tk.Label(grid, text=label + " =", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(key, "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, pady=2)
            tk.Label(grid, text=unit, bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.s6_entries[key] = (v, e)

    # ==============================================================
    # PAGE 7 — verification
    # ==============================================================
    def _build_page_7(self):
        f = self.step_area
        s = self.solution
        if s and not s.get("is_drb"):
            tk.Label(f, text="Not DRB — this step does not apply.",
                     bg="#f4f4f4", fg="#a67c00",
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 6))
            return
        tk.Label(f, text="Verify with actual bars (after rounding up). "
                         "As1 = (nb_total − nb_comp)·Ab,   As2 = nb_comp·Ab.",
                 bg="#f4f4f4", fg="#333", wraplength=720,
                 justify="left").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="φMn1_actual = φ · As1 · fy · (d − a/2)     [same a as before]",
                 bg="#f4f4f4", fg="#333", wraplength=720,
                 justify="left").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="φMn2_actual = φ · As2 · fy · (d − d')",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 2))
        tk.Label(f, text="φMn = φMn1_actual + φMn2_actual  ≥ Mu?  →  OK if yes.",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [("As1_actual", "s7.As1", "mm²"),
                ("As2_actual", "s7.As2", "mm²"),
                ("φMn1_actual", "s7.phiMn1", "kN·m"),
                ("φMn2_actual", "s7.phiMn2", "kN·m"),
                ("φMn_total", "s7.phiMn", "kN·m")]
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

        if not s.get("is_drb"):
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#a67c00")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="NOT A DRB PROBLEM", font=("Segoe UI", 13, "bold"),
                     fg="#a67c00", bg="#ffffff").pack(padx=16, pady=12)
            tk.Label(f, text=f"Mu ({s['Mu']:.3f} kN·m) ≤ φMn1 ({s['phiMn1']:.3f} kN·m).",
                     bg="#f4f4f4", fg="#333").pack(anchor="w")
            tk.Label(f, text="Use the SRB app instead.",
                     bg="#f4f4f4", fg="#666").pack(anchor="w")
        else:
            box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#0a7a0a")
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="FINAL DRB DESIGN", font=("Segoe UI", 12, "bold"),
                     bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(10, 6))
            tk.Label(box,
                     text=f"Tension: {s['final_nb_tension']} pcs of {s['final_db']:.0f} mmØ",
                     font=("Consolas", 12, "bold"), fg="#0a7a0a", bg="#ffffff").grid(row=1, column=0, columnspan=2)
            tk.Label(box,
                     text=f"Compression: {s['final_nb_comp']} pcs of {s['final_db']:.0f} mmØ",
                     font=("Consolas", 12, "bold"), fg="#0a7a0a", bg="#ffffff").grid(row=2, column=0, columnspan=2)
            tk.Label(box,
                     text=f"φMn = {s['final_phiMn']:.3f} kN·m  vs  Mu = {s['Mu']:.3f} kN·m  "
                          f"({'OK' if s['verify_ok'] else 'STILL SHORT'})",
                     font=("Consolas", 11), bg="#ffffff").grid(row=3, column=0, columnspan=2, padx=16, pady=(6, 12))

            if s["final_db"] != s["db"]:
                tk.Label(f, text=f"Note: db was auto-upgraded from {s['db']:.0f} mm to "
                                 f"{s['final_db']:.0f} mm to satisfy φMn ≥ Mu.",
                         bg="#f4f4f4", fg="#a67c00", font=("Segoe UI", 9, "italic"),
                         wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))
            if not s["verify_ok"]:
                tk.Label(f, text="⚠ Warning: even the largest bar size on the list couldn't verify. "
                                 "Consider increasing section size.",
                         bg="#f4f4f4", fg="#a00", wraplength=720,
                         justify="left").pack(anchor="w", pady=(4, 0))

        tk.Label(f, text="Recap:", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(14, 4))
        recap = tk.Text(f, width=74, height=16, font=("Consolas", 9), bg="#ffffff")
        recap.pack(anchor="w", fill="x")
        lines = [
            f"b = {s['b']:.0f} mm   d = {s['d']:.0f} mm   D = {s['D']:.0f} mm   cc = d' = {s['cc']:.0f} mm",
            f"db (given) = {s['db']:.0f} mm   f'c = {s['fc']:.2f} MPa   fy = {s['fy']:.0f} MPa   dagg = {s['dagg']:.1f} mm",
            f"Mu = {s['Mu']:.3f} kN·m   φ = {s['phi']}",
            "",
            f"β₁ = {s['beta1']:.4f}   ρmax = {s['rho_max']:.5f}   As_max = {s['As_max']:.3f} mm²",
            f"a = {s['a']:.3f} mm   c = {s['c']:.3f} mm   fs = {s['fs']:.3f} MPa (yields: {s['steel_yields']})",
            f"φ_check (report) = {s['phi_check']:.4f}   (design uses φ = {s['phi']})",
            f"φMn1 = {s['phiMn1']:.3f} kN·m",
        ]
        if s.get("is_drb"):
            lines += [
                f"φMn2 = {s['phiMn2']:.3f} kN·m",
                f"As2 (= A'_s) = {s['As2']:.3f} mm²   AsT = {s['AsT']:.3f} mm²",
                f"Ab = {s['Ab']:.3f} mm²   nb_total = {s['nb_total']}   nb_comp = {s['nb_comp']}   nb_tension = {s['nb_tension']}",
                "",
                f"Verification with actual bars (db = {s['final_db']:.0f} mm):",
                f"  As1_actual = {s['final_As1']:.3f} mm²   As2_actual = {s['final_As2']:.3f} mm²",
                f"  φMn1 = {s['final_phiMn1']:.3f} kN·m   φMn2 = {s['final_phiMn2']:.3f} kN·m",
                f"  φMn = {s['final_phiMn']:.3f} kN·m   ≥ Mu = {s['Mu']:.3f} kN·m  →  "
                f"{'OK' if s['verify_ok'] else 'SHORT'}",
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
        u = parse(self.s1_mu[0].get())
        ok = u is not None and close(u, s["Mu"])
        self._mark(self.s1_mu[1], ok)
        if ok:
            self._set_status("✓ Step 1 correct!", "#0a7a0a")
            self.log(f"Step 1: Mu={fmt(s['Mu'])} correct.", "green")
            self.passed.add(1); self.revealed.discard(1)
        else:
            self._set_status("✗ Step 1 has errors.", "#a00")
            self.log(f"Step 1: Mu expected {fmt(s['Mu'])} (got {u}).", "yellow")
            messagebox.showwarning("Step 1", f"Mu: expected {fmt(s['Mu'])} kN·m (got {u})")

    def _check_step2(self):
        s = self.solution
        expected = {"s2.rhomax": s["rho_max"], "s2.Asmax": s["As_max"]}
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s2_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s2_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp, 5)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 2 correct!", "#0a7a0a")
            self.log("Step 2: ρmax, As_max correct.", "green")
            self.passed.add(2); self.revealed.discard(2)
        else:
            self._set_status("✗ Step 2 has errors.", "#a00")
            self.log("Step 2 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 2", "\n".join(msgs))

    def _check_step3(self):
        s = self.solution
        expected = {"s3.a": s["a"], "s3.c": s["c"], "s3.fs": s["fs"]}
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s3_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s3_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 3 correct!", "#0a7a0a")
            self.log("Step 3: a, c, fs correct.", "green")
            self.passed.add(3); self.revealed.discard(3)
        else:
            self._set_status("✗ Step 3 has errors.", "#a00")
            self.log("Step 3 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 3", "\n".join(msgs))

    def _check_step4(self):
        s = self.solution
        u = parse(self.s4_phimn1[0].get())
        ok = u is not None and close(u, s["phiMn1"])
        self._mark(self.s4_phimn1[1], ok)

        if s.get("is_drb"):
            expected_verdict = "Mu > φMn1  →  DRB (proceed with doubly)"
        else:
            expected_verdict = "Mu ≤ φMn1  →  SRB (not this app)"
        verdict_ok = (self.verdict_pick.get() == expected_verdict)

        if ok and verdict_ok:
            self._set_status("✓ Step 4 correct!", "#0a7a0a")
            self.log(f"Step 4: φMn1={fmt(s['phiMn1'])}, verdict correct.", "green")
            self.passed.add(4); self.revealed.discard(4)
        else:
            msgs = []
            if not ok: msgs.append(f"φMn1: expected {fmt(s['phiMn1'])} (got {u})")
            if not verdict_ok: msgs.append(f"Verdict: expected '{expected_verdict}' (got '{self.verdict_pick.get()}')")
            self._set_status("✗ Step 4 has errors.", "#a00")
            self.log("Step 4 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 4", "\n".join(msgs))

    def _check_step5(self):
        s = self.solution
        if not s.get("is_drb"):
            self._set_status("— Step 5 skipped (SRB).", "#a67c00")
            self.passed.add(5)
            return
        expected = {"s5.phiMn2": s["phiMn2"], "s5.As2": s["As2"], "s5.AsT": s["AsT"]}
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s5_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s5_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 5 correct!", "#0a7a0a")
            self.log(f"Step 5: As2={fmt(s['As2'])}, AsT={fmt(s['AsT'])} correct.", "green")
            self.passed.add(5); self.revealed.discard(5)
        else:
            self._set_status("✗ Step 5 has errors.", "#a00")
            self.log("Step 5 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 5", "\n".join(msgs))

    def _check_step6(self):
        s = self.solution
        if not s.get("is_drb"):
            self._set_status("— Step 6 skipped (SRB).", "#a67c00")
            self.passed.add(6)
            return
        expected = {
            "s6.Ab": s["Ab"], "s6.nbtotal": float(s["nb_total"]),
            "s6.nbcomp": float(s["nb_comp"]), "s6.nbtens": float(s["nb_tension"]),
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s6_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s6_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 6 correct!", "#0a7a0a")
            self.log(f"Step 6: nb_total={s['nb_total']}, nb_comp={s['nb_comp']} correct.", "green")
            self.passed.add(6); self.revealed.discard(6)
        else:
            self._set_status("✗ Step 6 has errors.", "#a00")
            self.log("Step 6 errors:", "yellow")
            for m in msgs: self.log("  " + m, "yellow")
            messagebox.showwarning("Step 6", "\n".join(msgs))

    def _check_step7(self):
        s = self.solution
        if not s.get("is_drb"):
            self._set_status("— Step 7 skipped (SRB).", "#a67c00")
            self.passed.add(7)
            return
        expected = {
            "s7.As1": s["final_As1"], "s7.As2": s["final_As2"],
            "s7.phiMn1": s["final_phiMn1"], "s7.phiMn2": s["final_phiMn2"],
            "s7.phiMn": s["final_phiMn"],
        }
        all_ok = True; msgs = []
        for k, exp in expected.items():
            u = parse(self.s7_entries[k][0].get())
            ok = u is not None and close(u, exp)
            self._mark(self.s7_entries[k][1], ok)
            if not ok:
                all_ok = False; msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        if all_ok:
            self._set_status("✓ Step 7 correct!", "#0a7a0a")
            self.log(f"Step 7: φMn_total={fmt(s['final_phiMn'])} correct.", "green")
            self.passed.add(7); self.revealed.discard(7)
        else:
            self._set_status("✗ Step 7 has errors.", "#a00")
            self.log("Step 7 errors:", "yellow")
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
            self._set_entry(self.s1_mu, fmt(s["Mu"]))
        elif p == 2:
            self._set_entry(self.s2_entries["s2.rhomax"], fmt(s["rho_max"], 5))
            self._set_entry(self.s2_entries["s2.Asmax"],  fmt(s["As_max"]))
        elif p == 3:
            self._set_entry(self.s3_entries["s3.a"],  fmt(s["a"]))
            self._set_entry(self.s3_entries["s3.c"],  fmt(s["c"]))
            self._set_entry(self.s3_entries["s3.fs"], fmt(s["fs"]))
        elif p == 4:
            self._set_entry(self.s4_phimn1, fmt(s["phiMn1"]))
            if s.get("is_drb"):
                self.verdict_pick.set("Mu > φMn1  →  DRB (proceed with doubly)")
            else:
                self.verdict_pick.set("Mu ≤ φMn1  →  SRB (not this app)")
        elif p == 5:
            if not s.get("is_drb"):
                self.revealed.add(5); return
            self._set_entry(self.s5_entries["s5.phiMn2"], fmt(s["phiMn2"]))
            self._set_entry(self.s5_entries["s5.As2"],    fmt(s["As2"]))
            self._set_entry(self.s5_entries["s5.AsT"],    fmt(s["AsT"]))
        elif p == 6:
            if not s.get("is_drb"):
                self.revealed.add(6); return
            self._set_entry(self.s6_entries["s6.Ab"],      fmt(s["Ab"]))
            self._set_entry(self.s6_entries["s6.nbtotal"], fmt(s["nb_total"]))
            self._set_entry(self.s6_entries["s6.nbcomp"],  fmt(s["nb_comp"]))
            self._set_entry(self.s6_entries["s6.nbtens"],  fmt(s["nb_tension"]))
        elif p == 7:
            if not s.get("is_drb"):
                self.revealed.add(7); return
            self._set_entry(self.s7_entries["s7.As1"],    fmt(s["final_As1"]))
            self._set_entry(self.s7_entries["s7.As2"],    fmt(s["final_As2"]))
            self._set_entry(self.s7_entries["s7.phiMn1"], fmt(s["final_phiMn1"]))
            self._set_entry(self.s7_entries["s7.phiMn2"], fmt(s["final_phiMn2"]))
            self._set_entry(self.s7_entries["s7.phiMn"],  fmt(s["final_phiMn"]))
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
        lines = ["RCD DRB Design — Summary", "=" * 40]
        lines += [
            f"b = {s['b']:.0f} mm   d = {s['d']:.0f} mm   D = {s['D']:.0f} mm   cc = d' = {s['cc']:.0f} mm",
            f"db (given) = {s['db']:.0f} mm   f'c = {s['fc']:.2f} MPa   fy = {s['fy']:.0f} MPa",
            f"Mu = {s['Mu']:.3f} kN·m   φ = {s['phi']}",
            "",
            f"ρmax = {s['rho_max']:.5f}   As_max = {s['As_max']:.3f} mm²",
            f"a = {s['a']:.3f} mm   c = {s['c']:.3f} mm   fs = {s['fs']:.3f} MPa",
            f"φMn1 = {s['phiMn1']:.3f} kN·m",
        ]
        if not s.get("is_drb"):
            lines.append("Result: NOT DRB (use SRB app)")
        else:
            lines += [
                f"φMn2 = {s['phiMn2']:.3f} kN·m   As2 = {s['As2']:.3f} mm²   AsT = {s['AsT']:.3f} mm²",
                f"nb_total = {s['nb_total']}   nb_comp = {s['nb_comp']}   nb_tension = {s['nb_tension']}",
                f"Verification: φMn = {s['final_phiMn']:.3f} kN·m vs Mu = {s['Mu']:.3f} kN·m "
                f"({'OK' if s['verify_ok'] else 'SHORT'})",
                f"Final: {s['final_nb_tension']} pcs of {s['final_db']:.0f} mmØ (tension), "
                f"{s['final_nb_comp']} pcs of {s['final_db']:.0f} mmØ (compression)",
            ]
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Summary copied to clipboard.", "#0a7a0a")
        self.log("Summary copied to clipboard.", "gray")


if __name__ == "__main__":
    app = DRBDesigner()
    app.mainloop()