"""
RCD Reviewer — Tributary Load / Slab-to-Beam Load Transfer
Single-file Tkinter app. No external dependencies.
Based on NSCP-style solution flow.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random

# ------------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------------
GAMMA_C = 23.6          # kN/m^3, reinforced stone incl. gravel (locked)
TOL = 0.005             # 0.5% relative tolerance

# Given loads per panel: (id, label, FF, C, LL) in kPa.
# This list is MUTABLE — the Randomize button swaps the FF/C/LL in place.
PANEL_LOAD_TABLE = [
    ("P12", "A-C, 1-2",   0.19, 0.05, 6.0),
    ("P34", "A-C, 3-4",   0.19, 0.05, 2.4),
    ("P45", "A-C, 4-5",   1.10, 0.12, 3.8),
    ("P23", "A-D, 2-3",   1.10, 0.12, 3.8),
]

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

# ------------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------------
class RCDReviewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD Reviewer — Tributary Load to Beam B")

        # ---- fit window to actual screen ----
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = max(760, min(1180, sw - 40))
        win_h = max(520, min(800, sh - 120))
        x = max(0, (sw - win_w) // 2)
        y = max(0, (sh - win_h) // 3)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(min(760, win_w), min(520, win_h))

        # ---------- session state ----------
        self.state = {
            "x_spans": {"1-2": 6.0, "2-3": 2.0, "3-4": 6.0, "4-5": 2.0},
            "y_spans": {"A-B": 6.0, "B-C": 5.0, "C-D": 2.0},
            "t_slab_mm": 125.0,
            "beam_b_mm": 300.0,
            "beam_h_mm": 400.0,
            "col_mm": 400.0,
            "target_grid": "B",
            "lf_dl": 1.2,
            "lf_ll": 1.6,
            "user_inputs": {},
            "passed": set(),
            "revealed": set(),
        }

        self.page = 0
        self.max_page = 7
        self.history_lines = []
        self._resize_job = None
        self._last_given_width = 0
        self._hist_visible = win_w >= 1000

        # ---------- build UI ----------
        self._build_layout()
        self._build_top_given()
        self._build_history()
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
        if key in self.state["user_inputs"]:
            init = self.state["user_inputs"][key]
        else:
            init = default
            self.state["user_inputs"][key] = init
        v = tk.StringVar(value=init)
        def _cb(*a):
            self.state["user_inputs"][key] = v.get()
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
        tk.Label(self.topbar, text="GIVEN LOADS", font=("Segoe UI", 9, "bold"),
                 bg="#eef3fa", anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        self.given_row = tk.Frame(self.topbar, bg="#eef3fa")
        self.given_row.pack(fill="x", padx=10, pady=(0, 6))
        self._refresh_top_given()

    def _refresh_top_given(self):
        for w in self.given_row.winfo_children():
            w.destroy()

        cards = []
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            cards.append((label, f"FF={fmt(ff,2)}  C={fmt(c,2)}  LL={fmt(ll,2)}"))
        cards.append(("γ_c (locked)", f"{fmt(GAMMA_C,1)} kN/m³"))

        width = self.winfo_width()
        if width < 100:
            width = self.winfo_screenwidth()
        usable = width - (270 if self._hist_visible else 40)
        usable = max(400, usable)
        cols = max(2, min(len(cards), usable // 190))

        for i, (label, val) in enumerate(cards):
            r, c = divmod(i, cols)
            is_gamma = (i == len(cards) - 1)
            fg_lbl = "#a67c00" if is_gamma else "#345"
            fg_val = "#a67c00" if is_gamma else "#123"
            box = tk.Frame(self.given_row, bg="#eef3fa")
            box.grid(row=r, column=c, padx=8, pady=1, sticky="w")
            tk.Label(box, text=label, font=("Segoe UI", 8, "bold"),
                     bg="#eef3fa", fg=fg_lbl).pack(anchor="w")
            tk.Label(box, text=val, font=("Consolas", 9),
                     bg="#eef3fa", fg=fg_val).pack(anchor="w")

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
    # HISTORY SIDEBAR
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
    # PAGE SWITCHING
    # ==============================================================
    def _clear_step_area(self):
        for w in self.step_area.winfo_children():
            w.destroy()

    def _show_page(self, n):
        self.page = n
        self._clear_step_area()

        titles = {
            0: "Inputs",
            1: "Step 1 — Given Loads",
            2: "Step 2 — Slab Analysis",
            3: "Step 3 — Slab Loads",
            4: "Step 4 — Tributary Areas",
            5: "Step 5 — UDL per Span",
            6: "Step 6 — V and M",
            7: "Summary",
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
        }[n]
        builder()

        try:
            self.step_canvas.yview_moveto(0)
        except Exception:
            pass

        self.btn_back.configure(state=("normal" if n > 0 else "disabled"))
        self.btn_next.configure(state=("normal" if n < self.max_page else "disabled"))
        checkable = n in (2, 3, 4, 5, 6)
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))

    def go_back(self):
        if self.page > 0:
            self._show_page(self.page - 1)

    def go_next(self):
        if self.page == 0:
            if not self._save_inputs(silent=True):
                return
        if self.page in (2, 3, 4, 5, 6):
            if self.page not in self.state["passed"] and self.page not in self.state["revealed"]:
                if not messagebox.askyesno(
                        "Skip check?",
                        "You haven't checked this step yet. Continue anyway?"):
                    return
        if self.page < self.max_page:
            self._show_page(self.page + 1)

    def reset_all(self):
        if messagebox.askyesno("Reset", "Clear all inputs and answers?"):
            self.state["user_inputs"].clear()
            self.state["passed"].clear()
            self.state["revealed"].clear()
            self.clear_history()
            self._show_page(0)

    # ==============================================================
    # RANDOMIZER
    # ==============================================================
    def randomize_given(self):
        """Generate a brand-new random problem and reset the session."""
        if not messagebox.askyesno(
                "Randomize",
                "Generate a new random problem?\n\n"
                "This will replace the current geometry AND the given panel loads, "
                "and clear all your progress."):
            return

        # ---- Geometry: pick ranges that keep the trapezoid top width positive ----
        # x_span 1-2 and 3-4 must be > y_span B-C so (L - S_bot) > 0.
        x12 = round(random.uniform(5.0, 8.0), 1)
        x23 = round(random.uniform(1.5, 3.0), 1)
        x34 = round(random.uniform(5.0, 8.0), 1)
        x45 = round(random.uniform(1.5, 3.0), 1)

        yAB = round(random.uniform(5.0, 8.0), 1)
        yBC = round(random.uniform(3.0, 4.5), 1)   # always < x12, x34
        yCD = round(random.uniform(1.5, 3.0), 1)

        t_slab = float(random.choice([100, 120, 125, 150, 175, 200]))
        beam_b = float(random.choice([250, 300, 350, 400]))
        beam_h = float(random.choice([400, 450, 500, 550, 600]))
        col    = float(random.choice([300, 350, 400, 450, 500]))

        # ---- Panel loads: upper panels lighter, lower panels heavier (realistic) ----
        new_ff_c_ll = {
            "P12": (round(random.uniform(0.10, 0.30), 2),
                    round(random.uniform(0.03, 0.08), 2),
                    round(random.uniform(1.9, 3.5), 1)),
            "P34": (round(random.uniform(0.10, 0.30), 2),
                    round(random.uniform(0.03, 0.08), 2),
                    round(random.uniform(1.9, 3.5), 1)),
            "P45": (round(random.uniform(0.80, 1.50), 2),
                    round(random.uniform(0.08, 0.15), 2),
                    round(random.uniform(3.0, 4.8), 1)),
            "P23": (round(random.uniform(0.80, 1.50), 2),
                    round(random.uniform(0.08, 0.15), 2),
                    round(random.uniform(3.0, 4.8), 1)),
        }

        # ---- Apply to state ----
        self.state["x_spans"] = {"1-2": x12, "2-3": x23, "3-4": x34, "4-5": x45}
        self.state["y_spans"] = {"A-B": yAB, "B-C": yBC, "C-D": yCD}
        self.state["t_slab_mm"] = t_slab
        self.state["beam_b_mm"] = beam_b
        self.state["beam_h_mm"] = beam_h
        self.state["col_mm"] = col
        self.state["lf_dl"] = 1.2
        self.state["lf_ll"] = 1.6
        self.state["target_grid"] = "B"

        # ---- Replace the given-load table IN PLACE (so all readers see new values) ----
        for i, (pid, label, _ff, _c, _ll) in enumerate(PANEL_LOAD_TABLE):
            nf, nc, nl = new_ff_c_ll[pid]
            PANEL_LOAD_TABLE[i] = (pid, label, nf, nc, nl)

        # ---- Clear session ----
        self.state["user_inputs"].clear()
        self.state["passed"].clear()
        self.state["revealed"].clear()
        self.clear_history()

        # ---- Refresh UI ----
        self._refresh_top_given()
        self._show_page(0)

        # ---- Log the new problem ----
        self.log("— Randomized new problem —", "head")
        self.log(f"X-spans (m): 1-2={x12}, 2-3={x23}, 3-4={x34}, 4-5={x45}", "gray")
        self.log(f"Y-spans (m): A-B={yAB}, B-C={yBC}, C-D={yCD}", "gray")
        self.log(f"Slab t = {t_slab:.0f} mm  |  Beam = {beam_b:.0f}×{beam_h:.0f} mm  |  "
                 f"Col = {col:.0f} mm", "gray")
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            self.log(f"  {label}: FF={ff}, C={c}, LL={ll}", "gray")
        self._set_status("New random problem generated. Click Next to begin.", "#0a5")

    # ==============================================================
    # PAGE 0 — INPUTS
    # ==============================================================
    def _build_page_0(self):
        f = self.step_area
        tk.Label(f, text="Edit geometry. Given loads (FF/C/LL) and γ_c are fixed.",
                 bg="#f4f4f4", fg="#444").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text="Or click 🎲 Randomize for a new random scenario (clears progress).",
                 bg="#f4f4f4", fg="#888", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")

        # X spans
        tk.Label(grid, text="X-spans (m)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").grid(row=0, column=0, sticky="w", pady=(0, 4))
        for i, key in enumerate(["1-2", "2-3", "3-4", "4-5"], start=1):
            tk.Label(grid, text=f"{key}:", bg="#f4f4f4").grid(row=i, column=0, sticky="e")
            v = self._mk_var(f"in.x.{key}", str(self.state["x_spans"][key]))
            tk.Entry(grid, textvariable=v, width=10).grid(row=i, column=1, padx=4, pady=2, sticky="w")

        # Y spans
        tk.Label(grid, text="Y-spans (m)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=(30, 0), pady=(0, 4))
        for i, key in enumerate(["A-B", "B-C", "C-D"], start=1):
            tk.Label(grid, text=f"{key}:", bg="#f4f4f4").grid(row=i, column=2, sticky="e", padx=(30, 0))
            v = self._mk_var(f"in.y.{key}", str(self.state["y_spans"][key]))
            tk.Entry(grid, textvariable=v, width=10).grid(row=i, column=3, padx=4, pady=2, sticky="w")

        row0 = 5
        tk.Label(grid, text="Slab t (mm):", bg="#f4f4f4").grid(row=row0, column=0, sticky="e", pady=(10, 0))
        v = self._mk_var("in.t_slab", str(self.state["t_slab_mm"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0, column=1, sticky="w", pady=(10, 0))

        tk.Label(grid, text="Beam b (mm):", bg="#f4f4f4").grid(row=row0 + 1, column=0, sticky="e")
        v = self._mk_var("in.beam_b", str(self.state["beam_b_mm"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0 + 1, column=1, sticky="w")

        tk.Label(grid, text="Beam h (mm):", bg="#f4f4f4").grid(row=row0 + 2, column=0, sticky="e")
        v = self._mk_var("in.beam_h", str(self.state["beam_h_mm"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0 + 2, column=1, sticky="w")

        tk.Label(grid, text="Column (mm):", bg="#f4f4f4").grid(row=row0 + 3, column=0, sticky="e")
        v = self._mk_var("in.col", str(self.state["col_mm"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0 + 3, column=1, sticky="w")

        tk.Label(grid, text="Load factor DL:", bg="#f4f4f4").grid(row=row0, column=2, sticky="e", padx=(30, 0), pady=(10, 0))
        v = self._mk_var("in.lf_dl", str(self.state["lf_dl"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0, column=3, sticky="w", pady=(10, 0))

        tk.Label(grid, text="Load factor LL:", bg="#f4f4f4").grid(row=row0 + 1, column=2, sticky="e", padx=(30, 0))
        v = self._mk_var("in.lf_ll", str(self.state["lf_ll"]))
        tk.Entry(grid, textvariable=v, width=10).grid(row=row0 + 1, column=3, sticky="w")

        tk.Label(grid, text="γ_c (kN/m³):", bg="#f4f4f4").grid(row=row0 + 2, column=2, sticky="e", padx=(30, 0))
        tk.Label(grid, text=f"{GAMMA_C:.1f}  (locked)", bg="#f4f4f4", fg="#666").grid(row=row0 + 2, column=3, sticky="w")

        tk.Label(grid, text="Target gridline:", bg="#f4f4f4").grid(row=row0 + 3, column=2, sticky="e", padx=(30, 0))
        v = self._mk_var("in.target_grid", self.state["target_grid"])
        ttk.Combobox(grid, textvariable=v, values=["A", "B", "C", "D"], width=8,
                     state="readonly").grid(row=row0 + 3, column=3, sticky="w")

        # ---- Buttons row ----
        btn_row = tk.Frame(f, bg="#f4f4f4")
        btn_row.pack(anchor="w", pady=(16, 0))
        tk.Button(btn_row, text="Save Inputs", bg="#c9daf8", width=13,
                  command=self._save_inputs).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="🎲 Randomize", bg="#ffe9b3", width=13,
                  command=self.randomize_given).pack(side="left")

        tk.Label(f, text="(Inputs are auto-saved when you click Next.)",
                 bg="#f4f4f4", fg="#888", font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(6, 0))

        if not self.history_lines:
            self.log("— Session started —", "head")
            self.log("Inputs page loaded.", "gray")

    def _save_inputs(self, silent=False):
        try:
            for key in ["1-2", "2-3", "3-4", "4-5"]:
                self.state["x_spans"][key] = float(self.state["user_inputs"][f"in.x.{key}"])
            for key in ["A-B", "B-C", "C-D"]:
                self.state["y_spans"][key] = float(self.state["user_inputs"][f"in.y.{key}"])
            self.state["t_slab_mm"] = float(self.state["user_inputs"]["in.t_slab"])
            self.state["beam_b_mm"] = float(self.state["user_inputs"]["in.beam_b"])
            self.state["beam_h_mm"] = float(self.state["user_inputs"]["in.beam_h"])
            self.state["col_mm"] = float(self.state["user_inputs"]["in.col"])
            self.state["lf_dl"] = float(self.state["user_inputs"]["in.lf_dl"])
            self.state["lf_ll"] = float(self.state["user_inputs"]["in.lf_ll"])
            self.state["target_grid"] = self.state["user_inputs"].get("in.target_grid", "B")
        except ValueError:
            if not silent:
                messagebox.showerror("Invalid input", "All inputs must be numeric. "
                                                    "Check for blank fields or stray letters.")
            return False
        except KeyError as e:
            if not silent:
                messagebox.showerror("Missing field", f"Internal error: field {e} not found. "
                                                    "Try clicking Reset.")
            return False

        # Sanity: ensure trapezoid top width stays positive
        if self.state["y_spans"]["B-C"] >= self.state["x_spans"]["1-2"] or \
           self.state["y_spans"]["B-C"] >= self.state["x_spans"]["3-4"]:
            if not silent:
                messagebox.showerror("Invalid geometry",
                                     "Y-span B-C must be less than X-span 1-2 and 3-4 "
                                     "so the trapezoid has a positive top width.")
            return False

        if not silent:
            self.log(f"Inputs saved: X={list(self.state['x_spans'].values())}  "
                    f"Y={list(self.state['y_spans'].values())}", "gray")
            self.log(f"  t_slab={self.state['t_slab_mm']}mm  "
                    f"beam={self.state['beam_b_mm']}x{self.state['beam_h_mm']}mm  "
                    f"γ_c={GAMMA_C}", "gray")
            messagebox.showinfo("Saved", "Inputs saved. Proceed to Step 1.")
        return True

    # ==============================================================
    # PAGE 1 — GIVEN LOADS
    # ==============================================================
    def _build_page_1(self):
        f = self.step_area
        tk.Label(f, text="Given loads (read-only). These are the values from the problem.",
                 bg="#f4f4f4", fg="#444").pack(anchor="w", pady=(0, 8))

        cols = ("Panel", "FF (kPa)", "C (kPa)", "LL (kPa)")
        tv = ttk.Treeview(f, columns=cols, show="headings", height=6)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=140, anchor="center")
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            tv.insert("", "end", values=(label, fmt(ff, 2), fmt(c, 2), fmt(ll, 2)))
        tv.pack(anchor="w", pady=6)

        tk.Label(f, text=f"γ_concrete = {GAMMA_C} kN/m³ (reinforced stone incl. gravel, locked)",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(8, 0))
        tk.Label(f, text="Note: FF and C are superimposed dead loads; LL is the minimum "
                         "uniform live load per NSCP.",
                 bg="#f4f4f4", fg="#666", wraplength=700, justify="left").pack(anchor="w", pady=(8, 0))

    # ==============================================================
    # PAGE 2 — SLAB ANALYSIS
    # ==============================================================
    def _panel_geoms(self):
        """Per-panel governing bay: (label, S, L)."""
        xs = self.state["x_spans"]
        ys = self.state["y_spans"]
        return {
            "P12": ("A-B, 1-2", xs["1-2"], ys["A-B"]),
            "P34": ("A-B, 3-4", xs["3-4"], ys["A-B"]),
            "P45": ("A-C, 4-5", xs["4-5"], ys["A-B"]),
            "P23": ("A-C, 2-3", xs["2-3"], ys["A-B"]),
        }

    def _expected_step2(self):
        geoms = self._panel_geoms()
        out = {}
        for pid, (label, S, L) in geoms.items():
            m = S / L
            cls = "Two-Way" if m >= 0.5 else "One-Way"
            out[pid] = (m, cls)
        return out

    def _build_page_2(self):
        f = self.step_area
        tk.Label(f, text="For each panel, compute m = S/L and classify. S = short side, L = long side.",
                 bg="#f4f4f4", fg="#444", wraplength=760,
                 justify="left").pack(anchor="w", pady=(0, 8))

        geoms = self._panel_geoms()
        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w", pady=4)

        headers = ["Panel", "S (m)", "L (m)", "Your m", "Classification"]
        for j, h in enumerate(headers):
            tk.Label(grid, text=h, font=("Segoe UI", 9, "bold"), bg="#f4f4f4",
                     borderwidth=1, relief="solid", width=16).grid(row=0, column=j, sticky="nsew")

        self.entry_m = {}
        self.combo_class = {}
        for i, pid in enumerate(["P12", "P34", "P45", "P23"], start=1):
            label, S, L = geoms[pid]
            tk.Label(grid, text=label, bg="#f4f4f4", borderwidth=1, relief="solid",
                     width=16).grid(row=i, column=0, sticky="nsew")
            tk.Label(grid, text=fmt(S, 2), bg="#f4f4f4", borderwidth=1, relief="solid",
                     width=16).grid(row=i, column=1, sticky="nsew")
            tk.Label(grid, text=fmt(L, 2), bg="#f4f4f4", borderwidth=1, relief="solid",
                     width=16).grid(row=i, column=2, sticky="nsew")

            v_m = self._mk_var(f"s2.{pid}.m", "")
            e_m = tk.Entry(grid, textvariable=v_m, width=18, justify="center")
            e_m.grid(row=i, column=3, sticky="nsew", padx=1, pady=1)
            self.entry_m[pid] = (v_m, e_m)

            v_c = self._mk_var(f"s2.{pid}.cls", "")
            cb = ttk.Combobox(grid, textvariable=v_c, width=14, justify="center",
                              values=["", "One-Way", "Two-Way"], state="readonly")
            cb.grid(row=i, column=4, sticky="nsew", padx=1, pady=1)
            self.combo_class[pid] = v_c

        tk.Label(f, text="Reminder: m < 0.5 → One-Way;  m ≥ 0.5 → Two-Way.",
                 bg="#f4f4f4", fg="#666").pack(anchor="w", pady=(8, 0))

    # ==============================================================
    # PAGE 3 — SLAB LOADS
    # ==============================================================
    def _slab_self_weight(self):
        t_m = self.state["t_slab_mm"] / 1000.0
        return GAMMA_C * t_m

    def _expected_step3(self):
        out = {}
        w_slab = self._slab_self_weight()
        lf_dl = self.state["lf_dl"]
        lf_ll = self.state["lf_ll"]
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            DL = ff + c + w_slab
            U = lf_dl * DL + lf_ll * ll
            out[pid] = (DL, ll, U)
        return out

    def _build_page_3(self):
        f = self.step_area
        w_slab = self._slab_self_weight()
        tk.Label(f, text=f"Slab self-weight = γ_c · t = {GAMMA_C} × {self.state['t_slab_mm']/1000:.3f} "
                         f"= {fmt(w_slab)} kPa",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 6))
        tk.Label(f, text="For each panel enter DL (kPa), LL (kPa), and factored U = 1.2DL + 1.6LL (kPa).",
                 bg="#f4f4f4", fg="#444", wraplength=760,
                 justify="left").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")

        headers = ["Panel", "DL (kPa)", "LL (kPa)", "U (kPa)"]
        for j, h in enumerate(headers):
            tk.Label(grid, text=h, font=("Segoe UI", 9, "bold"), bg="#f4f4f4",
                     borderwidth=1, relief="solid", width=18).grid(row=0, column=j, sticky="nsew")

        self.entry_dl = {}
        self.entry_ll3 = {}
        self.entry_u = {}
        for i, (pid, label, ff, c, ll) in enumerate(PANEL_LOAD_TABLE, start=1):
            tk.Label(grid, text=label, bg="#f4f4f4", borderwidth=1, relief="solid",
                     width=18).grid(row=i, column=0, sticky="nsew")
            v1 = self._mk_var(f"s3.{pid}.DL", "")
            e1 = tk.Entry(grid, textvariable=v1, width=20, justify="center")
            e1.grid(row=i, column=1, sticky="nsew", padx=1, pady=1)

            v2 = self._mk_var(f"s3.{pid}.LL", "")
            e2 = tk.Entry(grid, textvariable=v2, width=20, justify="center")
            e2.grid(row=i, column=2, sticky="nsew", padx=1, pady=1)

            v3 = self._mk_var(f"s3.{pid}.U", "")
            e3 = tk.Entry(grid, textvariable=v3, width=20, justify="center")
            e3.grid(row=i, column=3, sticky="nsew", padx=1, pady=1)

            self.entry_dl[pid] = (v1, e1)
            self.entry_ll3[pid] = (v2, e2)
            self.entry_u[pid] = (v3, e3)

    # ==============================================================
    # PAGE 4 — TRIBUTARY AREAS
    # ==============================================================
    def _expected_step4(self):
        xs = self.state["x_spans"]
        ys = self.state["y_spans"]
        def areas_for_span(x_key):
            L_bay = xs[x_key]
            S_top = ys["A-B"]
            S_bot = ys["B-C"]
            A_tri = 0.5 * L_bay * (S_top / 2)
            b1 = L_bay
            b2 = L_bay - S_bot
            h = S_bot / 2
            A_trap = 0.5 * (b1 + b2) * h
            return A_tri, A_trap
        A1, A2 = areas_for_span("1-2")
        A3, A4 = areas_for_span("3-4")
        return {"A1": A1, "A2": A2, "A3": A3, "A4": A4}

    def _build_page_4(self):
        f = self.step_area
        tk.Label(f, text="Enter the tributary areas to Beam B for spans 1-2 and 3-4.",
                 bg="#f4f4f4", fg="#444").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")

        labels = [
            ("A1", "Triangle — upper panel (bay A-B, span 1-2)"),
            ("A2", "Trapezoid — lower panel (bay B-C, span 1-2)"),
            ("A3", "Triangle — upper panel (bay A-B, span 3-4)"),
            ("A4", "Trapezoid — lower panel (bay B-C, span 3-4)"),
        ]
        self.entry_areas = {}
        for i, (key, desc) in enumerate(labels):
            tk.Label(grid, text=f"{key}:", font=("Segoe UI", 9, "bold"),
                     bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=3)
            tk.Label(grid, text=desc, bg="#f4f4f4").grid(row=i, column=1, sticky="w", pady=3)
            v = self._mk_var(f"s4.{key}", "")
            e = tk.Entry(grid, textvariable=v, width=12, justify="center")
            e.grid(row=i, column=2, sticky="w", padx=6, pady=3)
            tk.Label(grid, text="m²", bg="#f4f4f4").grid(row=i, column=3, sticky="w")
            self.entry_areas[key] = (v, e)

        tk.Label(f, text="Tributary shapes (sketch)", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(14, 4))

        cf = tk.Frame(f, bg="#f4f4f4")
        cf.pack(anchor="w", fill="x", expand=True)
        self.trib_canvas = tk.Canvas(cf, height=330, bg="white",
                                     highlightthickness=1, highlightbackground="#bbb")
        self.trib_canvas.pack(fill="x", expand=True)
        self.trib_canvas.bind("<Configure>", lambda e: self._draw_tributary(e.width))
        self.trib_canvas.after(60, self._safe_initial_trib_draw)

    def _safe_initial_trib_draw(self):
        try:
            if self.trib_canvas.winfo_exists():
                self._draw_tributary(self.trib_canvas.winfo_width())
        except Exception:
            pass

    def _draw_tributary(self, W):
        cv = self.trib_canvas
        cv.delete("all")
        if W < 100:
            return

        xs = self.state["x_spans"]
        ys = self.state["y_spans"]
        L1 = xs["1-2"]; L3 = xs["3-4"]
        S_top = ys["A-B"]; S_bot = ys["B-C"]

        y_beam = 160
        m_l = 40
        m_r = 40
        gap = 60
        avail = W - m_l - m_r - gap
        if avail < 240:
            avail = 240
        beam_len = avail / 2.0

        max_h_top = 75
        max_h_bot = 75

        def draw_span(x0, L, span_label, tri_key, trap_key):
            x1 = x0 + beam_len
            scale = beam_len / L

            h_top = (S_top / 2.0) * scale
            if h_top > max_h_top:
                h_top = max_h_top
            h_bot = (S_bot / 2.0) * scale
            if h_bot > max_h_bot:
                h_bot = max_h_bot

            inset = (S_bot / 2.0) * scale
            if inset > beam_len * 0.42:
                inset = beam_len * 0.42

            cv.create_line(x0, y_beam, x1, y_beam, width=6, fill="#222")

            tip = ((x0 + x1) / 2.0, y_beam - h_top)
            cv.create_polygon(x0, y_beam, x1, y_beam, tip[0], tip[1],
                              outline="#1a6", fill="#d6f5e3", width=2)
            cv.create_text(tip[0], y_beam - h_top * 0.55,
                           text=f"{tri_key}\nh = {fmt(S_top/2, 2)} m",
                           font=("Segoe UI", 8), fill="#0a5", justify="center")

            cv.create_polygon(x0, y_beam, x1, y_beam,
                              x1 - inset, y_beam + h_bot,
                              x0 + inset, y_beam + h_bot,
                              outline="#16a", fill="#d6e8f5", width=2)
            cv.create_text((x0 + x1) / 2.0, y_beam + h_bot * 0.55,
                           text=f"{trap_key}\nh = {fmt(S_bot/2, 2)} m",
                           font=("Segoe UI", 8), fill="#036", justify="center")

            cv.create_text((x0 + x1) / 2.0, y_beam + 12, text=span_label,
                           font=("Segoe UI", 9, "bold"), fill="#222", anchor="n")

            y_dim = y_beam + max_h_bot + 40
            cv.create_line(x0, y_dim, x1, y_dim, fill="#666", dash=(3, 2))
            for xx in (x0, x1):
                cv.create_line(xx, y_dim - 5, xx, y_dim + 5, fill="#666")
            cv.create_text((x0 + x1) / 2.0, y_dim - 10,
                           text=f"L = {fmt(L, 2)} m",
                           font=("Segoe UI", 9), fill="#333")

        draw_span(m_l, L1, "Span 1-2", "A1", "A2")
        draw_span(m_l + beam_len + gap, L3, "Span 3-4", "A3", "A4")

        cv.create_text(m_l, 20, anchor="w",
                       text="Green triangle = panel above the beam (bay A-B).   "
                            "Blue trapezoid = panel below the beam (bay B-C).",
                       font=("Segoe UI", 8), fill="#666")

    # ==============================================================
    # PAGE 5 — UDL PER SPAN
    # ==============================================================
    def _expected_step5(self):
        exp3 = self._expected_step3()
        exp4 = self._expected_step4()
        xs = self.state["x_spans"]
        lf_dl = self.state["lf_dl"]
        b_m = self.state["beam_b_mm"] / 1000.0
        h_m = self.state["beam_h_mm"] / 1000.0
        w_beam_nom = GAMMA_C * b_m * h_m
        w_beam_factored = lf_dl * w_beam_nom

        U12 = exp3["P12"][2]
        L12 = xs["1-2"]
        udl1 = exp4["A1"] * U12 / L12
        udl2 = exp4["A2"] * U12 / L12
        udl_12_slab = udl1 + udl2
        udl_12_total = udl_12_slab + w_beam_factored

        U34 = exp3["P34"][2]
        L34 = xs["3-4"]
        udl3 = exp4["A3"] * U34 / L34
        udl4 = exp4["A4"] * U34 / L34
        udl_34_slab = udl3 + udl4
        udl_34_total = udl_34_slab + w_beam_factored

        return {
            "w_beam_nom": w_beam_nom, "w_beam_factored": w_beam_factored,
            "udl1": udl1, "udl2": udl2, "udl_12_slab": udl_12_slab, "udl_12_total": udl_12_total,
            "udl3": udl3, "udl4": udl4, "udl_34_slab": udl_34_slab, "udl_34_total": udl_34_total,
        }

    def _build_page_5(self):
        f = self.step_area
        exp = self._expected_step5()
        tk.Label(f, text=f"Beam self-weight (nominal) = γ_c · b · h = {GAMMA_C} × "
                         f"{self.state['beam_b_mm']/1000:.3f} × {self.state['beam_h_mm']/1000:.3f} "
                         f"= {fmt(exp['w_beam_nom'])} kN/m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 4))
        tk.Label(f, text=f"Factored beam self-weight = {self.state['lf_dl']} × {fmt(exp['w_beam_nom'])} "
                         f"= {fmt(exp['w_beam_factored'])} kN/m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))
        tk.Label(f, text="Enter the UDL per span. UDL = A·U / L, then add factored beam self-weight.",
                 bg="#f4f4f4", fg="#444", wraplength=760,
                 justify="left").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")
        rows = [
            ("UDL1 (A1·U₁₂ / L₁₂)", "udl1"),
            ("UDL2 (A2·U₁₂ / L₁₂)", "udl2"),
            ("UDL 1-2 (slab only)", "udl_12_slab"),
            ("UDL 1-2 (incl. beam SW)", "udl_12_total"),
            ("UDL3 (A3·U₃₄ / L₃₄)", "udl3"),
            ("UDL4 (A4·U₃₄ / L₃₄)", "udl4"),
            ("UDL 3-4 (slab only)", "udl_34_slab"),
            ("UDL 3-4 (incl. beam SW)", "udl_34_total"),
        ]
        self.entry_udl = {}
        for i, (desc, key) in enumerate(rows):
            tk.Label(grid, text=desc + ":", bg="#f4f4f4").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=2)
            v = self._mk_var(f"s5.{key}", "")
            e = tk.Entry(grid, textvariable=v, width=14, justify="center")
            e.grid(row=i, column=1, sticky="w", pady=2)
            tk.Label(grid, text="kN/m", bg="#f4f4f4").grid(row=i, column=2, sticky="w", padx=6)
            self.entry_udl[key] = (v, e)

    # ==============================================================
    # PAGE 6 — V AND M
    # ==============================================================
    def _expected_step6(self):
        exp5 = self._expected_step5()
        w = exp5["udl_12_total"]
        L = self.state["x_spans"]["1-2"]
        V = w * L / 2
        M = w * L * L / 8
        return {"w": w, "L": L, "V": V, "M": M}

    def _build_page_6(self):
        f = self.step_area
        exp = self._expected_step6()
        tk.Label(f, text="Simply supported span 1-2. Use w = UDL 1-2 (incl. beam SW).",
                 bg="#f4f4f4", fg="#444").pack(anchor="w", pady=(0, 8))
        tk.Label(f, text=f"w = {fmt(exp['w'])} kN/m,  L = {fmt(exp['L'])} m",
                 bg="#f4f4f4", fg="#333").pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(f, bg="#f4f4f4")
        grid.pack(anchor="w")

        tk.Label(grid, text="V_max = w·L / 2  =", bg="#f4f4f4").grid(row=0, column=0, sticky="e", pady=3)
        v_v = self._mk_var("s6.V", "")
        e_v = tk.Entry(grid, textvariable=v_v, width=14, justify="center")
        e_v.grid(row=0, column=1, pady=3)
        tk.Label(grid, text="kN", bg="#f4f4f4").grid(row=0, column=2, sticky="w", padx=6)
        self.entry_v = (v_v, e_v)

        tk.Label(grid, text="M_u = w·L² / 8  =", bg="#f4f4f4").grid(row=1, column=0, sticky="e", pady=3)
        v_m = self._mk_var("s6.M", "")
        e_m = tk.Entry(grid, textvariable=v_m, width=14, justify="center")
        e_m.grid(row=1, column=1, pady=3)
        tk.Label(grid, text="kN·m", bg="#f4f4f4").grid(row=1, column=2, sticky="w", padx=6)
        self.entry_mu = (v_m, e_m)

    # ==============================================================
    # PAGE 7 — SUMMARY
    # ==============================================================
    def _build_page_7(self):
        f = self.step_area
        exp6 = self._expected_step6()
        exp5 = self._expected_step5()

        box = tk.Frame(f, bg="#ffffff", highlightthickness=2, highlightbackground="#0a7a0a")
        box.pack(anchor="w", pady=8)
        tk.Label(box, text="V_max", font=("Segoe UI", 12, "bold"), bg="#ffffff").grid(
            row=0, column=0, padx=16, pady=(12, 2), sticky="e")
        tk.Label(box, text=f"{fmt(exp6['V'])} kN", font=("Consolas", 14, "bold"),
                 fg="#0a7a0a", bg="#ffffff").grid(row=0, column=1, padx=16, pady=(12, 2), sticky="w")
        tk.Label(box, text="M_u", font=("Segoe UI", 12, "bold"), bg="#ffffff").grid(
            row=1, column=0, padx=16, pady=(2, 12), sticky="e")
        tk.Label(box, text=f"{fmt(exp6['M'])} kN·m", font=("Consolas", 14, "bold"),
                 fg="#0a7a0a", bg="#ffffff").grid(row=1, column=1, padx=16, pady=(2, 12), sticky="w")

        tk.Label(f, text="Recap of key values:", font=("Segoe UI", 10, "bold"),
                 bg="#f4f4f4").pack(anchor="w", pady=(16, 4))
        recap = tk.Text(f, width=70, height=12, font=("Consolas", 9), bg="#ffffff")
        recap.pack(anchor="w", fill="x")
        lines = [
            f"γ_c                 = {GAMMA_C} kN/m³",
            f"Slab self-weight    = {fmt(self._slab_self_weight())} kPa",
            f"Beam self-weight    = {fmt(exp5['w_beam_nom'])} kN/m (nominal)",
            f"Factored beam SW    = {fmt(exp5['w_beam_factored'])} kN/m",
            f"UDL 1-2 (slab)      = {fmt(exp5['udl_12_slab'])} kN/m",
            f"UDL 1-2 (total)     = {fmt(exp5['udl_12_total'])} kN/m",
            f"UDL 3-4 (slab)      = {fmt(exp5['udl_34_slab'])} kN/m",
            f"UDL 3-4 (total)     = {fmt(exp5['udl_34_total'])} kN/m",
            f"V_max               = {fmt(exp6['V'])} kN",
            f"M_u                 = {fmt(exp6['M'])} kN·m",
        ]
        for ln in lines:
            recap.insert("end", ln + "\n")
        recap.configure(state="disabled")

        tk.Button(f, text="Copy Summary to Clipboard", bg="#c9daf8",
                  command=self.copy_summary).pack(anchor="w", pady=(10, 0))

    # ==============================================================
    # CHECK / REVEAL
    # ==============================================================
    def _set_status(self, msg, color="#333"):
        self.status.configure(text=msg, fg=color)

    def _mark(self, widget, ok):
        try:
            widget.configure(bg=("#e0ffe0" if ok else "#ffe0e0"))
        except tk.TclError:
            pass

    def check_current(self):
        p = self.page
        if p == 2:
            self._check_step2()
        elif p == 3:
            self._check_step3()
        elif p == 4:
            self._check_step4()
        elif p == 5:
            self._check_step5()
        elif p == 6:
            self._check_step6()

    def _check_step2(self):
        exp = self._expected_step2()
        all_ok = True
        msgs = []
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            m_exp, cls_exp = exp[pid]
            m_user = parse(self.entry_m[pid][0].get())
            cls_user = self.combo_class[pid].get()
            ok = (m_user is not None and close(m_user, m_exp) and cls_user == cls_exp)
            self._mark(self.entry_m[pid][1], ok)
            if not ok:
                all_ok = False
                msgs.append(f"{label}: expected m={fmt(m_exp,4)}, {cls_exp}  "
                            f"(got m={m_user}, {cls_user or '—'})")
        if all_ok:
            self._set_status("✓ Step 2 correct!", "#0a7a0a")
            self.log("Step 2: all m and classifications correct.", "green")
            self.state["passed"].add(2)
            self.state["revealed"].discard(2)
        else:
            self._set_status("✗ Step 2 has errors.", "#a00")
            self.log("Step 2 attempted — errors:", "yellow")
            for m in msgs:
                self.log("  " + m, "yellow")
            messagebox.showwarning("Step 2", "Some entries are wrong:\n\n" + "\n".join(msgs))

    def _check_step3(self):
        exp = self._expected_step3()
        all_ok = True
        msgs = []
        for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
            DL_e, LL_e, U_e = exp[pid]
            DL_u = parse(self.entry_dl[pid][0].get())
            LL_u = parse(self.entry_ll3[pid][0].get())
            U_u = parse(self.entry_u[pid][0].get())
            dl_ok = DL_u is not None and close(DL_u, DL_e)
            ll_ok = LL_u is not None and close(LL_u, LL_e)
            u_ok  = U_u  is not None and close(U_u,  U_e)
            self._mark(self.entry_dl[pid][1],  dl_ok)
            self._mark(self.entry_ll3[pid][1], ll_ok)
            self._mark(self.entry_u[pid][1],   u_ok)
            if not dl_ok:
                all_ok = False; msgs.append(f"{label} DL: expected {fmt(DL_e)} (got {DL_u})")
            if not ll_ok:
                all_ok = False; msgs.append(f"{label} LL: expected {fmt(LL_e)} (got {LL_u})")
            if not u_ok:
                all_ok = False; msgs.append(f"{label} U: expected {fmt(U_e)} (got {U_u})")
        if all_ok:
            self._set_status("✓ Step 3 correct!", "#0a7a0a")
            self.log("Step 3: DL, LL, U per panel correct.", "green")
            self.state["passed"].add(3)
            self.state["revealed"].discard(3)
        else:
            self._set_status("✗ Step 3 has errors.", "#a00")
            self.log("Step 3 attempted — errors:", "yellow")
            for m in msgs:
                self.log("  " + m, "yellow")
            messagebox.showwarning("Step 3", "Some entries are wrong:\n\n" + "\n".join(msgs[:8]))

    def _check_step4(self):
        exp = self._expected_step4()
        all_ok = True
        msgs = []
        for key in ["A1", "A2", "A3", "A4"]:
            e = exp[key]
            u = parse(self.entry_areas[key][0].get())
            ok = u is not None and close(u, e)
            self._mark(self.entry_areas[key][1], ok)
            if not ok:
                all_ok = False
                msgs.append(f"{key}: expected {fmt(e)} m² (got {u})")
        if all_ok:
            self._set_status("✓ Step 4 correct!", "#0a7a0a")
            self.log("Step 4: tributary areas correct.", "green")
            self.state["passed"].add(4)
            self.state["revealed"].discard(4)
        else:
            self._set_status("✗ Step 4 has errors.", "#a00")
            self.log("Step 4 attempted — errors:", "yellow")
            for m in msgs:
                self.log("  " + m, "yellow")
            messagebox.showwarning("Step 4", "Some entries are wrong:\n\n" + "\n".join(msgs))

    def _check_step5(self):
        exp = self._expected_step5()
        keys = ["udl1", "udl2", "udl_12_slab", "udl_12_total",
                "udl3", "udl4", "udl_34_slab", "udl_34_total"]
        all_ok = True
        msgs = []
        for k in keys:
            e = exp[k]
            u = parse(self.entry_udl[k][0].get())
            ok = u is not None and close(u, e)
            self._mark(self.entry_udl[k][1], ok)
            if not ok:
                all_ok = False
                msgs.append(f"{k}: expected {fmt(e)} kN/m (got {u})")
        if all_ok:
            self._set_status("✓ Step 5 correct!", "#0a7a0a")
            self.log("Step 5: UDL per span correct.", "green")
            self.state["passed"].add(5)
            self.state["revealed"].discard(5)
        else:
            self._set_status("✗ Step 5 has errors.", "#a00")
            self.log("Step 5 attempted — errors:", "yellow")
            for m in msgs:
                self.log("  " + m, "yellow")
            messagebox.showwarning("Step 5", "Some entries are wrong:\n\n" + "\n".join(msgs))

    def _check_step6(self):
        exp = self._expected_step6()
        all_ok = True
        msgs = []
        v_u = parse(self.entry_v[0].get())
        m_u = parse(self.entry_mu[0].get())
        v_ok = v_u is not None and close(v_u, exp["V"])
        m_ok = m_u is not None and close(m_u, exp["M"])
        self._mark(self.entry_v[1], v_ok)
        self._mark(self.entry_mu[1], m_ok)
        if not v_ok:
            all_ok = False; msgs.append(f"V_max: expected {fmt(exp['V'])} kN (got {v_u})")
        if not m_ok:
            all_ok = False; msgs.append(f"M_u: expected {fmt(exp['M'])} kN·m (got {m_u})")
        if all_ok:
            self._set_status("✓ Step 6 correct!", "#0a7a0a")
            self.log(f"Step 6: V_max={fmt(exp['V'])} kN, M_u={fmt(exp['M'])} kN·m correct.", "green")
            self.state["passed"].add(6)
            self.state["revealed"].discard(6)
        else:
            self._set_status("✗ Step 6 has errors.", "#a00")
            self.log("Step 6 attempted — errors:", "yellow")
            for m in msgs:
                self.log("  " + m, "yellow")
            messagebox.showwarning("Step 6", "Some entries are wrong:\n\n" + "\n".join(msgs))

    def _set_entry(self, pair, value_str):
        var, entry = pair
        var.set(value_str)
        try:
            entry.delete(0, "end")
            entry.insert(0, value_str)
            entry.configure(bg="#e0ffe0")
        except tk.TclError:
            pass

    def reveal_current(self):
        p = self.page
        if p == 2:
            exp = self._expected_step2()
            for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
                m_exp, cls_exp = exp[pid]
                self._set_entry(self.entry_m[pid], fmt(m_exp, 4))
                self.combo_class[pid].set(cls_exp)
            self.log("Step 2 revealed.", "yellow")
        elif p == 3:
            exp = self._expected_step3()
            for pid, label, ff, c, ll in PANEL_LOAD_TABLE:
                DL_e, LL_e, U_e = exp[pid]
                self._set_entry(self.entry_dl[pid], fmt(DL_e))
                self._set_entry(self.entry_ll3[pid], fmt(LL_e))
                self._set_entry(self.entry_u[pid], fmt(U_e))
            self.log("Step 3 revealed.", "yellow")
        elif p == 4:
            exp = self._expected_step4()
            for k in exp:
                self._set_entry(self.entry_areas[k], fmt(exp[k]))
            self.log("Step 4 revealed.", "yellow")
        elif p == 5:
            exp = self._expected_step5()
            for k in self.entry_udl:
                self._set_entry(self.entry_udl[k], fmt(exp[k]))
            self.log("Step 5 revealed.", "yellow")
        elif p == 6:
            exp = self._expected_step6()
            self._set_entry(self.entry_v, fmt(exp["V"]))
            self._set_entry(self.entry_mu, fmt(exp["M"]))
            self.log("Step 6 revealed.", "yellow")
        self.state["revealed"].add(p)
        self._set_status("Answers revealed (marked yellow in history).", "#a67c00")

    # ==============================================================
    # COPY SUMMARY
    # ==============================================================
    def copy_summary(self):
        exp5 = self._expected_step5()
        exp6 = self._expected_step6()
        lines = [
            "RCD Reviewer — Summary",
            "=" * 40,
            f"γ_c = {GAMMA_C} kN/m³",
            f"Slab t = {self.state['t_slab_mm']} mm",
            f"Beam = {self.state['beam_b_mm']} × {self.state['beam_h_mm']} mm",
            f"Slab self-weight = {fmt(self._slab_self_weight())} kPa",
            "",
            f"Beam self-weight (nominal) = {fmt(exp5['w_beam_nom'])} kN/m",
            f"Beam self-weight (factored) = {fmt(exp5['w_beam_factored'])} kN/m",
            "",
            f"UDL 1-2 (slab only) = {fmt(exp5['udl_12_slab'])} kN/m",
            f"UDL 1-2 (total)     = {fmt(exp5['udl_12_total'])} kN/m",
            f"UDL 3-4 (slab only) = {fmt(exp5['udl_34_slab'])} kN/m",
            f"UDL 3-4 (total)     = {fmt(exp5['udl_34_total'])} kN/m",
            "",
            f"V_max = {fmt(exp6['V'])} kN",
            f"M_u   = {fmt(exp6['M'])} kN·m",
        ]
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Summary copied to clipboard.", "#0a7a0a")
        self.log("Summary copied to clipboard.", "gray")


if __name__ == "__main__":
    app = RCDReviewer()
    app.mainloop()