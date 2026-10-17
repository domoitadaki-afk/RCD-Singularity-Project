"""
6_t-beams_design.py — T-Beam Design Reviewer (Find As)

Fixed:
  - Top bar ONLY shows the 8 basic givens initially.
  - Derived values (bf, A_conc, a, c, fs, y_bar, As) appear in the top bar
    ONLY after the corresponding step is successfully checked or revealed.
"""

import math
import random
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox

from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from enum import Enum

# ====================================================================
# SECTION 1 — THEME
# ====================================================================
BG_MAIN        = "#f4f4f4"
BG_TOP_BAR     = "#eef3fa"
BG_BOTTOM      = "#e8e8e8"
BG_HISTORY     = "#fafafa"
BG_PANEL       = "#ffffff"
BG_INPUT_OK    = "#e0ffe0"
BG_INPUT_ERR   = "#ffe0e0"
BG_BTN_WARM    = "#ffe9b3"
BG_BTN_GO      = "#cde8cd"
BG_BTN_NEU     = "#c9daf8"

FG_HEAD   = "#1a1a1a"
FG_LABEL  = "#334455"
FG_VALUE  = "#112233"
FG_EXTRA  = "#0055aa"
FG_HINT   = "#666666"
FG_OK     = "#0a7a0a"
FG_WARN   = "#a67c00"
FG_ERR    = "#a00000"

BORDER_MAIN  = "#b8c4d6"
BORDER_PANEL = "#cccccc"

FONT_TITLE    = ("Segoe UI", 13, "bold")
FONT_SECTION  = ("Segoe UI", 10, "bold")
FONT_LABEL    = ("Segoe UI", 9)
FONT_LABEL_B  = ("Segoe UI", 9, "bold")
FONT_ENTRY    = ("Consolas", 10)
FONT_VALUE    = ("Consolas", 10)
FONT_HIST     = ("Consolas", 9)
FONT_QUESTION = ("Segoe UI", 10, "bold")

# ====================================================================
# SECTION 2 — ENGINE / MODELS
# ====================================================================
class AnswerType(str, Enum):
    NONE = "none"
    NUMERIC = "numeric"

@dataclass
class Step:
    id: str
    title: str
    content: str | Callable[[dict], str]
    question: Optional[str | Callable[[dict], str]] = None
    solver: Optional[Callable[[dict], Any]] = None
    var_name: Optional[str] = None
    answer_type: AnswerType = AnswerType.NONE
    hints: list[str] | Callable[[dict], list[str]] = field(default_factory=list)
    next_step: Optional[str] = None
    branches: dict[str, str] = field(default_factory=dict)
    is_terminal: bool = False

    def resolve_question(self, state: dict) -> Optional[str]:
        if self.question is None: return None
        return self.question(state) if callable(self.question) else self.question

@dataclass
class Workflow:
    id: str
    name: str
    description: str
    generator: Callable[..., dict]
    steps: dict[str, Step]
    start_step: str

# ====================================================================
# SECTION 3 — ENGINE / VALIDATOR
# ====================================================================
_UNIT_RE = re.compile(r"(kn\.?m|knm|kn|n|mm2|mm²|mm|cm|m|mpa|kpa|pa|%)\s*$", re.IGNORECASE)

def _try_number(s: str) -> tuple[Optional[float], Optional[str]]:
    s = s.strip()
    unit_match = _UNIT_RE.search(s)
    unit = unit_match.group(1).lower() if unit_match else None
    if unit_match:
        s = s[: unit_match.start()]
    s = s.replace(",", "").replace(" ", "").strip()
    try:
        return float(s), unit
    except ValueError:
        return None, unit

# ====================================================================
# SECTION 4 — ENGINE / SESSION
# ====================================================================
@dataclass
class StepState:
    step_id: str
    completed: bool = False
    final_answer: Optional[str] = None

class Session:
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.givens: dict = {}
        self.state: dict = {}
        self.current_step_id = workflow.start_step
        self.states: dict[str, StepState] = {}
        self.history: list[str] = []
        self._new_problem()

    def _new_problem(self, **kwargs) -> None:
        self.givens = self.workflow.generator(**kwargs)
        self.state = dict(self.givens)
        self.current_step_id = self.workflow.start_step
        self.states = {sid: StepState(step_id=sid) for sid in self.workflow.steps}
        self.history = [self.workflow.start_step]

    def new_problem(self, **kwargs) -> None:
        self._new_problem(**kwargs)

    @property
    def current_step(self) -> Step:
        return self.workflow.steps[self.current_step_id]

    @property
    def current_state(self) -> StepState:
        return self.states[self.current_step_id]

    def can_advance(self) -> bool:
        return self.current_state.completed

    def advance(self, branch_label: Optional[str] = None) -> Optional[str]:
        if not self.can_advance(): return None
        step = self.current_step
        if step.is_terminal: return None
            
        nxt = None
        if step.branches:
            if branch_label and branch_label in step.branches:
                nxt = step.branches[branch_label]
            else:
                nxt = next(iter(step.branches.values()))
        else:
            nxt = step.next_step
            
        if not nxt: return None
            
        self.current_step_id = nxt
        if (not self.history or self.history[-1] != nxt and (len(self.history) < 2 or self.history[-2] != nxt)):
            self.history.append(nxt)
        return nxt

    def uncomplete_current(self) -> None:
        self.current_state.completed = False
        self.current_state.final_answer = None

# ====================================================================
# SECTION 5 — SOLVER ENGINE
# ====================================================================
class TBeamDesignSolver:
    @staticmethod
    def generate_basic():
        """Generates ONLY the basic given properties."""
        max_attempts = 100
        for _ in range(max_attempts):
            tf = random.choice([100, 120, 150])
            S = random.choice([2500, 3000, 3500, 4000])
            Ln = random.randint(5000, 8000)
            bw = random.choice([250, 300, 350, 400])
            d = random.randint(500, 700)
            fc = random.choice([21, 24, 27.6, 28, 34])
            fy = random.choice([345, 414])
            
            bf1 = bw + 16 * tf
            bf2 = bw + S
            bf3 = bw + Ln / 4
            bf4 = 4 * bw
            bf = min(bf1, bf2, bf3, bf4)
            
            A_flange = bf * tf
            Mu_at_flange = 0.90 * 0.85 * fc * A_flange * (d - tf/2) / 1000000
            Mu = round(random.uniform(Mu_at_flange * 1.05, Mu_at_flange * 2.5), 0)
            
            if 17 < fc < 28: beta1 = 0.85
            elif 28 <= fc <= 55: beta1 = 0.85 - (0.05 * (fc - 28) / 7)
            else: beta1 = 0.65
            
            phi_assumed = 0.90
            A_conc = (Mu * 1000000) / (phi_assumed * 0.85 * fc * (d - tf/2))
            flange_area = bf * tf
            is_true_t = A_conc > flange_area
            
            if is_true_t:
                a = tf + (A_conc - flange_area) / bw
                c = a / beta1
                fs = 600 * (d - c) / c if c < d else 0
                
                if fs > fy:
                    A1 = bf * tf
                    y1 = tf / 2
                    A2 = (a - tf) * bw
                    y2 = tf + (a - tf) / 2
                    y_bar = (A1 * y1 + A2 * y2) / A_conc
                    
                    phi = 0.90
                    As = (Mu * 1000000) / (phi * fy * (d - y_bar))
                    
                    if 1000 < As < 15000:
                        return dict(
                            tf=tf, S=S, Ln=Ln, bw=bw, d=d, Mu=Mu, fc=fc, fy=fy
                        )
        
        return dict(
            tf=100, S=3000, Ln=6000, bw=300, d=600, Mu=1440, fc=27.6, fy=414
        )

    @staticmethod
    def compute_solution(givens):
        """Calculates all derived values on the fly given the basic inputs."""
        tf = givens["tf"]; S = givens["S"]; Ln = givens["Ln"]; bw = givens["bw"]
        d = givens["d"]; Mu = givens["Mu"]; fc = givens["fc"]; fy = givens["fy"]
        
        bf1 = bw + 16 * tf
        bf2 = bw + S
        bf3 = bw + Ln / 4
        bf4 = 4 * bw
        bf = min(bf1, bf2, bf3, bf4)
        
        if 17 < fc < 28: beta1 = 0.85
        elif 28 <= fc <= 55: beta1 = 0.85 - (0.05 * (fc - 28) / 7)
        else: beta1 = 0.65
        
        A_conc = (Mu * 1000000) / (0.90 * 0.85 * fc * (d - tf/2))
        flange_area = bf * tf
        is_true_t = A_conc > flange_area
        
        a = tf + (A_conc - flange_area) / bw
        c = a / beta1
        fs = 600 * (d - c) / c if c < d else 0
        
        A1 = bf * tf
        y1 = tf / 2
        A2 = (a - tf) * bw
        y2 = tf + (a - tf) / 2
        y_bar = (A1 * y1 + A2 * y2) / A_conc
        
        As = (Mu * 1000000) / (0.90 * fy * (d - y_bar))
        
        return dict(
            bf1=bf1, bf2=bf2, bf3=bf3, bf4=bf4, bf=bf,
            beta1=beta1, A_conc=A_conc, flange_area=flange_area, is_true_t=is_true_t,
            a=a, c=c, fs=fs, y_bar=y_bar, phi=0.90, As=As
        )

# ====================================================================
# SECTION 6 — WORKFLOW DEFINITION
# ====================================================================
def _build_tbeam_design_workflow() -> Workflow:
    def _gen() -> dict:
        return TBeamDesignSolver.generate_basic()

    return Workflow(
        id="tbeam_design",
        name="T-Beam Design (Find As)",
        description="T-Beam Design Reviewer",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(id="start", title="Given Beam Properties", content="", next_step="step_bf"),
            "step_bf": Step(
                id="step_bf", title="Step 1: Effective Flange Width (bf)",
                content="bf1 = bw+16tf\nbf2 = bw+S\nbf3 = bw+Ln/4\nbf = min of the above (and 4bw)",
                question="Enter bf1, bf2, bf3, and final bf.",
                next_step="step_conc"
            ),
            "step_conc": Step(
                id="step_conc", title="Step 2: Check if True T-beam",
                content="Assume a = tf, find required A_conc:\nMu = φ(0.85f'c)A_conc(d - tf/2)",
                question="Enter A_conc and bf×tf.",
                next_step="step_yield"
            ),
            "step_yield": Step(
                id="step_yield", title="Step 3: Check Steel Yielding",
                content="A_conc = bf×tf + bw(a - tf)\n\nc = a / β1\nfs = 600(d - c) / c",
                question="Enter a, c, and fs.",
                next_step="step_centroid"
            ),
            "step_centroid": Step(
                id="step_centroid", title="Step 4: Centroid of Compression Block (y-bar)",
                content="A_T × y_bar = A1×y1 + A2×y2",
                question="Enter y_bar.",
                next_step="step_as"
            ),
            "step_as": Step(
                id="step_as", title="Step 5: Required Tension Steel Area (As)",
                content="As = Mu / [φ × fy × (d - y_bar)]",
                question="Enter As.",
                is_terminal=True
            ),
        }
    )

TBEAM_DESIGN_WORKFLOW = _build_tbeam_design_workflow()
ALL_WORKFLOWS = [TBEAM_DESIGN_WORKFLOW]

# ====================================================================
# SECTION 7 — MAIN WINDOW
# ====================================================================
_LABELS = {
    "tf": ("tf", "mm"), "S": ("S", "mm"), "Ln": ("Ln", "mm"),
    "bw": ("bw", "mm"), "d": ("d", "mm"), "Mu": ("Mu", "kN·m"),
    "fc": ("f'c", "MPa"), "fy": ("fy", "MPa"),
    "bf1": ("bf1", "mm"), "bf2": ("bf2", "mm"), "bf3": ("bf3", "mm"),
    "bf": ("bf", "mm"), "beta1": ("β1", ""),
    "A_conc": ("A_conc", "mm²"), "flange_area": ("bf×tf", "mm²"),
    "a": ("a", "mm"), "c": ("c", "mm"), "fs": ("fs", "MPa"),
    "y_bar": ("y_bar", "mm"), "As": ("As", "mm²"),
}

_UNLOCK_BY_STEP = {
    "step_bf": ["bf1", "bf2", "bf3", "bf"],
    "step_conc": ["A_conc", "flange_area", "is_true_t"],
    "step_yield": ["beta1", "a", "c", "fs"],
    "step_centroid": ["y_bar"],
    "step_as": ["As"],
}

_MULTI_FIELDS = {
    "step_bf": [
        ("bf1", "bf1 (bw+16tf)", "mm", 0.5),
        ("bf2", "bf2 (bw+S)", "mm", 0.5),
        ("bf3", "bf3 (bw+Ln/4)", "mm", 0.5),
        ("bf", "bf (final)", "mm", 0.5),
    ],
    "step_conc": [
        ("A_conc", "A_conc", "mm²", 1.0),
        ("flange_area", "bf×tf", "mm²", 1.0),
    ],
    "step_yield": [
        ("a", "a", "mm", 1.0),
        ("c", "c", "mm", 1.0),
        ("fs", "fs", "MPa", 1.0),
    ],
    "step_centroid": [("y_bar", "y_bar", "mm", 0.5)],
    "step_as": [("As", "As", "mm²", 1.0)],
}

def _fmt(v):
    if isinstance(v, bool): return "Yes" if v else "No"
    if isinstance(v, str): return v
    if isinstance(v, float):
        if v == int(v): return f"{int(v):,}"
        if abs(v) < 1: return f"{v:.4f}"
        if abs(v) >= 10000: return f"{v:,.1f}"
        return f"{v:.4g}"
    return str(v)

class TBeamDesignApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("T-Beam Design Reviewer")
        self.configure(bg=BG_MAIN)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(760, min(1300, sw - 40))
        h = max(520, min(860, sh - 120))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(760, w), min(520, h))

        self.session: Session | None = None
        self._history_visible = w >= 1120
        self._suppress_enter_until = 0.0
        self._last_answer_wrong = False

        self.user_inputs: dict[str, tk.StringVar] = {}
        self.multi_entries: dict[str, tuple[tk.StringVar, tk.Entry]] = {}
        self._resize_job = None

        self._build_layout()
        self._start_workflow(0)

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)
        self.bind_all("<Return>", self._on_enter)

    def _build_layout(self):
        self.topbar = tk.Frame(self, bg=BG_TOP_BAR, highlightthickness=1, highlightbackground=BORDER_MAIN)
        self.topbar.pack(side="top", fill="x")

        tk.Label(self.topbar, text="GIVEN  /  PROPERTIES", font=FONT_LABEL_B, bg=BG_TOP_BAR, fg=FG_LABEL, anchor="w").pack(fill="x", padx=10, pady=(6, 0))
        self.given_row = tk.Frame(self.topbar, bg=BG_TOP_BAR)
        self.given_row.pack(fill="x", padx=10, pady=(0, 6))

        self.bottombar = tk.Frame(self, bg=BG_BOTTOM, highlightthickness=1, highlightbackground="#bbbbbb")
        self.bottombar.pack(side="bottom", fill="x")

        bar = tk.Frame(self.bottombar, bg=BG_BOTTOM)
        bar.pack(fill="x", padx=8, pady=6)

        self.btn_back = tk.Button(bar, text="◀ Back", width=8, command=self._on_back)
        self.btn_back.pack(side="left", padx=2)

        self.btn_check = tk.Button(bar, text="✓ Check", width=8, bg=BG_BTN_GO, command=self._on_check)
        self.btn_check.pack(side="left", padx=2)

        self.btn_reveal = tk.Button(bar, text="Reveal", width=8, bg=BG_BTN_WARM, command=self._on_reveal)
        self.btn_reveal.pack(side="left", padx=2)

        self.btn_next = tk.Button(bar, text="Next ▶", width=8, bg=BG_BTN_NEU, command=self._on_next)
        self.btn_next.pack(side="left", padx=2)

        tk.Button(bar, text="Reset", width=8, command=self._on_reset).pack(side="left", padx=(10, 2))

        self.status_lbl = tk.Label(bar, text="", bg=BG_BOTTOM, anchor="w", font=("Segoe UI", 9, "italic"), fg=FG_HINT)
        self.status_lbl.pack(side="left", padx=8, fill="x", expand=True)

        tk.Button(bar, text="History", width=9, command=self._toggle_history).pack(side="right", padx=2)

        middle = tk.Frame(self, bg=BG_MAIN)
        middle.pack(side="top", fill="both", expand=True)

        self.history = tk.Frame(middle, width=280, bg=BG_HISTORY, highlightthickness=1, highlightbackground=BORDER_PANEL)
        self.history.pack_propagate(False)
        if self._history_visible:
            self.history.pack(side="right", fill="y")
        
        tk.Label(self.history, text="HISTORY", font=FONT_SECTION, bg=BG_HISTORY, fg=FG_HEAD).pack(anchor="w", padx=8, pady=(8, 4))
        wrap = tk.Frame(self.history, bg=BG_HISTORY)
        wrap.pack(fill="both", expand=True, padx=4, pady=4)
        self.hist_text = tk.Text(wrap, width=32, wrap="word", bg=BG_PANEL, relief="flat", font=FONT_HIST, highlightthickness=1, highlightbackground=BORDER_PANEL)
        sb = ttk.Scrollbar(wrap, command=self.hist_text.yview)
        self.hist_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.hist_text.pack(side="left", fill="both", expand=True)
        self.hist_text.tag_config("green",  foreground=FG_OK)
        self.hist_text.tag_config("yellow", foreground=FG_WARN)
        self.hist_text.tag_config("gray",   foreground=FG_HINT)
        self.hist_text.tag_config("red",    foreground=FG_ERR)
        self.hist_text.tag_config("head",   foreground=FG_HEAD, font=("Consolas", 9, "bold"))
        self.hist_text.configure(state="disabled")

        main = tk.Frame(middle, bg=BG_MAIN)
        main.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(main, bg=BG_MAIN)
        toolbar.pack(side="top", fill="x", padx=8, pady=(6, 2))

        tk.Label(toolbar, text="Workflow:", bg=BG_MAIN, font=FONT_LABEL).pack(side="left")
        self.workflow_combo = ttk.Combobox(toolbar, width=28, state="readonly", values=[wf.name for wf in ALL_WORKFLOWS])
        self.workflow_combo.pack(side="left", padx=6)
        self.workflow_combo.current(0)

        tk.Button(toolbar, text="🎲 New Problem", bg=BG_BTN_NEU, command=self._on_new_problem).pack(side="right", padx=2)

        canvas_wrap = tk.Frame(main, bg=BG_MAIN)
        canvas_wrap.pack(side="top", fill="both", expand=True)

        self.content_canvas = tk.Canvas(canvas_wrap, bg=BG_MAIN, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.content_canvas.yview)
        self.content_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)

        self.content_frame = tk.Frame(self.content_canvas, bg=BG_MAIN)
        self._content_win = self.content_canvas.create_window((10, 6), window=self.content_frame, anchor="nw")
        self.content_frame.bind("<Configure>", lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.bind("<Configure>", lambda e: self.content_canvas.itemconfigure(self._content_win, width=max(200, e.width - 20)))

        self.bind("<Configure>", self._on_root_resize)

    def _refresh_topbar(self):
        for w in self.given_row.winfo_children():
            w.destroy()
        if self.session is None: return

        state = self.session.state
        givens_keys = set(self.session.givens.keys())
        unlocked_keys: set[str] = set()
        for sid, st in self.session.states.items():
            if st.completed:
                unlocked_keys.update(_UNLOCK_BY_STEP.get(sid, []))

        given_items = [(k, v) for k, v in state.items() if k in givens_keys]
        extra_items = [(k, v) for k, v in state.items() if k not in givens_keys and k in unlocked_keys]
        items = [(k, v, True) for k, v in given_items] + [(k, v, False) for k, v in extra_items]

        width = self.winfo_width() or self.winfo_screenwidth()
        usable = width - (280 if self._history_visible else 40)
        cols = max(4, min(len(items), max(400, usable) // 118)) or 1

        for i, (key, value, is_given) in enumerate(items):
            r, c = divmod(i, cols)
            label, unit = _LABELS.get(key, (key, ""))
            val_str = _fmt(value)
            if unit: val_str = f"{val_str} {unit}"
            fg = FG_VALUE if is_given else FG_EXTRA
            fg_lbl = FG_LABEL if is_given else FG_EXTRA
            box = tk.Frame(self.given_row, bg=BG_TOP_BAR)
            box.grid(row=r, column=c, padx=4, pady=1, sticky="w")
            tk.Label(box, text=label, font=FONT_LABEL_B, bg=BG_TOP_BAR, fg=fg_lbl).pack(anchor="w")
            tk.Label(box, text=val_str, font=FONT_VALUE, bg=BG_TOP_BAR, fg=fg).pack(anchor="w")

    def _on_root_resize(self, event):
        if event.widget is not self: return
        if self._resize_job:
            try: self.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self.after(180, self._refresh_topbar)

    def _start_workflow(self, idx):
        self.session = Session(ALL_WORKFLOWS[idx])
        self.workflow_combo.set(ALL_WORKFLOWS[idx].name)
        self.hist_text.configure(state="normal")
        self.hist_text.delete("1.0", "end")
        self.hist_text.insert("end", f"— {ALL_WORKFLOWS[idx].name} —\n", "head")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._render_step()
        self._set_status("Ready. Solve the step, then click Check.", FG_HINT)

    def _on_new_problem(self):
        if self.session is None: return
        self.user_inputs.clear()
        self.session.new_problem()
        
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", "— New problem —\n", "head")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("New problem generated.", FG_WARN)

    def _multi_field_specs(self, step_id: str):
        return _MULTI_FIELDS.get(step_id, [])

    def _mk_var(self, key: str, default: str = "") -> tk.StringVar:
        if key in self.user_inputs: return self.user_inputs[key]
        v = tk.StringVar(value=default)
        v.trace_add("write", lambda *a, _k=key, _v=v: self.user_inputs.update({_k: _v}))
        self.user_inputs[key] = v
        return v

    def _render_multi_fields(self, parent, step_id: str):
        specs = self._multi_field_specs(step_id)
        self.multi_entries = {}
        grid = tk.Frame(parent, bg=BG_MAIN)
        grid.pack(fill="x", pady=(0, 6))
        for i, (field_key, label, unit, _tol) in enumerate(specs):
            r, c = divmod(i, 2)
            key = f"{step_id}.{field_key}"
            tk.Label(grid, text=label, bg=BG_MAIN, font=FONT_LABEL, width=14, anchor="e").grid(row=r, column=c * 3, sticky="e", padx=(0, 6), pady=3)
            var = self._mk_var(key, "")
            ent = tk.Entry(grid, textvariable=var, width=14, justify="center", font=FONT_ENTRY)
            ent.grid(row=r, column=c * 3 + 1, sticky="w", pady=3)
            if unit: tk.Label(grid, text=unit, bg=BG_MAIN, font=FONT_LABEL, fg=FG_HINT).grid(row=r, column=c * 3 + 2, sticky="w", padx=(4, 20))
            self.multi_entries[field_key] = (var, ent)
        if self._last_answer_wrong:
            for var, ent in self.multi_entries.values():
                try: ent.configure(bg=BG_INPUT_ERR)
                except tk.TclError: pass

    def _multi_check(self, step_id: str) -> bool:
        specs = self._multi_field_specs(step_id)
        sol = TBeamDesignSolver.compute_solution(self.session.givens)
        errors: list[str] = []
        all_ok = True

        for field_key, label, unit, tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None: continue
            var, ent = var_ent
            raw = var.get().strip()
            expected = sol.get(field_key)
            u, typed_unit = _try_number(raw)
            
            if u is None or expected is None:
                ok = False
            else:
                e = float(expected)
                t = float(tol)
                ok = abs(u - e) <= t if t > 0 else (abs(u - e) < 1e-9)

            try: ent.configure(bg=BG_INPUT_OK if ok else BG_INPUT_ERR)
            except tk.TclError: pass

            if not ok:
                all_ok = False
                expected_str = _fmt(expected) if expected is not None else "?"
                errors.append(f"{label}: expected {expected_str} (got {raw or '—'})")

        if all_ok:
            st = self.session.states[step_id]
            st.completed = True
            if st.final_answer is None: st.final_answer = "(all fields correct)"
            
            # Inject the newly computed values into the state so the top bar sees them
            self.session.state.update(sol)
            
            self.hist_text.configure(state="normal")
            self.hist_text.insert("end", f"✓ {self.session.workflow.steps[step_id].title} — correct\n", "green")
            self.hist_text.see("end")
            self.hist_text.configure(state="disabled")
            self._set_status("✓ Correct! Click Next to continue.", FG_OK)
            return True

        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", f"✗ {self.session.workflow.steps[step_id].title} — errors:\n", "yellow")
        for m in errors: self.hist_text.insert("end", "  " + m + "\n", "yellow")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._set_status("✗ Some fields are wrong.", FG_ERR)
        messagebox.showwarning("Check", "\n".join(errors))
        return False

    def _multi_reveal(self, step_id: str):
        specs = self._multi_field_specs(step_id)
        sol = TBeamDesignSolver.compute_solution(self.session.givens)
        
        for field_key, _label, _unit, _tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None: continue
            var, ent = var_ent
            val = sol.get(field_key)
            if val is None: continue
            value_str = f"{val:.4g}" if isinstance(val, float) else str(val)
            try:
                var.set(value_str)
                ent.delete(0, "end")
                ent.insert(0, value_str)
                ent.configure(bg=BG_INPUT_OK)
            except tk.TclError: pass
        st = self.session.states[step_id]
        st.completed = True
        st.final_answer = st.final_answer or "(revealed)"
        
        # Inject values into state for top bar
        self.session.state.update(sol)
        
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", f"Revealed {self.session.workflow.steps[step_id].title}\n", "yellow")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._set_status("Answers revealed.", FG_WARN)

    def _clear_content(self):
        for w in self.content_frame.winfo_children(): w.destroy()
        self.multi_entries = {}

    def _render_step(self):
        self._clear_content()
        if self.session is None: return
        step = self.session.current_step
        state = self.session.current_state

        # Read-only auto-complete for the start page
        if step.id == "start":
            state.completed = True
            if state.final_answer is None: state.final_answer = "(read)"

        f = self.content_frame
        tk.Label(f, text=step.title, font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w").pack(fill="x", pady=(0, 8))

        box = tk.LabelFrame(f, text="Answer", font=FONT_LABEL_B, bg=BG_MAIN, fg=FG_LABEL, bd=1, relief="solid", labelanchor="nw", padx=8, pady=8)
        box.pack(fill="x", pady=(4, 0))

        is_multi = step.id in _MULTI_FIELDS
        already_done = state.completed

        if is_multi:
            q = step.resolve_question(self.session.state) or "Enter the values below."
            tk.Label(box, text=q, bg=BG_MAIN, fg=FG_LABEL, font=FONT_QUESTION, anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(0, 4))
            self._render_multi_fields(box, step.id)

        if already_done and is_multi:
            for var, ent in self.multi_entries.values():
                try: ent.configure(bg=BG_INPUT_OK, state="disabled", disabledforeground=FG_OK)
                except tk.TclError: pass
        
        checkable = is_multi and not already_done
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))
        self.btn_next.configure(state=("normal" if state.completed else "disabled"))
        self.btn_next.configure(text=("Finish ✓" if step.is_terminal else "Next ▶"))
        self.btn_back.configure(state=("normal" if len(self.session.history) > 1 else "disabled"))

        try: self.content_canvas.yview_moveto(0)
        except Exception: pass

    def _on_enter(self, event=None):
        if self.session is None or time.time() < self._suppress_enter_until: return
        focused = self.focus_get()
        if isinstance(focused, (tk.Button, ttk.Button, ttk.Combobox)): return
        if self.session.current_state.completed: self._on_next()
        else: self._on_check()
        return "break"

    def _on_check(self):
        if self.session is None: return
        step = self.session.current_step
        if step.id in _MULTI_FIELDS:
            ok = self._multi_check(step.id)
            if ok:
                self._last_answer_wrong = False
                self._suppress_enter_until = time.time() + 0.25
            else:
                self._last_answer_wrong = True
            self._refresh_topbar()
            self._render_step()

    def _on_reveal(self):
        if self.session is None: return
        step = self.session.current_step
        if step.id in _MULTI_FIELDS:
            self._multi_reveal(step.id)
            self._refresh_topbar()
            self._render_step()

    def _on_next(self):
        if self.session is None or not self.session.can_advance(): return
        
        step = self.session.current_step
        nxt = self.session.advance()
        if nxt is None: 
            self._show_summary()
        else:
            self._last_answer_wrong = False
            self._suppress_enter_until = time.time() + 0.25
            self._render_step()

    def _on_back(self):
        if self.session is None or len(self.session.history) <= 1: return
        self.session.uncomplete_current()
        self.session.history.pop()
        self.session.current_step_id = self.session.history[-1]
        self._last_answer_wrong = False
        self._render_step()
        self._refresh_topbar()

    def _on_reset(self):
        if self.session is None: return
        if not messagebox.askyesno("Reset", "Clear all progress for this problem?"): return
        self.user_inputs.clear()
        self.session.new_problem()

        self.hist_text.configure(state="normal")
        self.hist_text.delete("1.0", "end")
        self.hist_text.insert("end", "— Reset —\n", "head")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("Reset. Fresh problem loaded.", FG_WARN)

    def _toggle_history(self):
        if self._history_visible:
            self.history.pack_forget()
            self._history_visible = False
        else:
            self.history.pack(side="right", fill="y")
            self._history_visible = True
        self._refresh_topbar()

    def _set_status(self, msg, color=FG_HINT):
        try: self.status_lbl.configure(text=msg, fg=color)
        except tk.TclError: pass

    def _show_summary(self):
        self._clear_content()
        if self.session is None: return
        f = self.content_frame
        tk.Label(f, text="📋 T-Beam Design Summary", font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w").pack(fill="x", pady=(0, 8))
        
        s = self.session.state
        # Fallback if topbar calculation missed it, ensure computed for summary
        if "As" not in s:
            s.update(TBeamDesignSolver.compute_solution(self.session.givens))
        
        box = tk.Frame(f, bg=BG_PANEL, highlightthickness=2, highlightbackground=FG_OK)
        box.pack(anchor="w", pady=8)
        tk.Label(box, text="TRUE T-BEAM DESIGN COMPLETE", font=FONT_TITLE, bg=BG_PANEL, fg=FG_OK).pack(padx=16, pady=(12, 6))
        
        def _row(lbl, val):
            row = tk.Frame(box, bg=BG_PANEL)
            row.pack(anchor="w", padx=16, pady=2)
            tk.Label(row, text=lbl, font=FONT_LABEL, bg=BG_PANEL, width=24, anchor="e").pack(side="left")
            tk.Label(row, text=val, font=("Consolas", 11, "bold"), fg=FG_OK, bg=BG_PANEL).pack(side="left", padx=8)
            
        _row("Effective Width bf:", f"{s.get('bf', 0):.0f} mm")
        _row("Required Steel As:", f"{s.get('As', 0):.2f} mm²")
        tk.Frame(box, bg=BG_PANEL, height=6).pack()

        lines = [
            "GIVEN",
            f"  tf = {s['tf']} mm   S = {s['S']} mm   Ln = {s['Ln']} mm",
            f"  bw = {s['bw']} mm   d = {s['d']} mm",
            f"  Mu = {s['Mu']:.0f} kN·m   f'c = {s['fc']} MPa   fy = {s['fy']} MPa",
            "",
            "STEP 1 — EFFECTIVE WIDTH",
            f"  bf1 = {s.get('bf1', 0):.0f} mm",
            f"  bf2 = {s.get('bf2', 0):.0f} mm",
            f"  bf3 = {s.get('bf3', 0):.0f} mm",
            f"  bf  = {s.get('bf', 0):.0f} mm (min of the above and 4bw)",
            "",
            "STEP 2 — COMPRESSION BLOCK",
            f"  A_conc = {s.get('A_conc', 0):.2f} mm²",
            f"  bf×tf  = {s.get('flange_area', 0):.2f} mm²",
            f"  TRUE T-BEAM",
            "",
            "STEP 3 — DEPTHS & STRESS",
            f"  β1 = {s.get('beta1', 0):.4f}",
            f"  a  = {s.get('a', 0):.2f} mm",
            f"  c  = {s.get('c', 0):.2f} mm",
            f"  fs = {s.get('fs', 0):.2f} MPa > fy = {s['fy']} MPa",
            f"  STEEL YIELDS",
            "",
            "STEP 4 — CENTROID",
            f"  y_bar = {s.get('y_bar', 0):.2f} mm",
            "",
            "STEP 5 — REQUIRED STEEL",
            f"  As = {s.get('As', 0):.2f} mm²",
        ]

        recap = tk.Text(f, width=72, height=min(24, len(lines) + 2), font=("Consolas", 9), bg=BG_PANEL)
        recap.pack(anchor="w", fill="x")
        for ln in lines: recap.insert("end", ln + "\n")
        recap.configure(state="disabled")

        self._set_status("Problem complete! 🎉", FG_OK)
        self.btn_next.configure(state="disabled")
        self.btn_check.configure(state="disabled")
        self.btn_reveal.configure(state="disabled")
        self.btn_back.configure(state=("normal" if len(self.session.history) > 1 else "disabled"))

    def _on_wheel(self, event):
        try: w = self.winfo_containing(event.x_root, event.y_root)
        except Exception: w = None
        node = w
        while node is not None:
            if node is self.content_canvas: break
            try: node = node.master
            except Exception: node = None
        if node is not self.content_canvas: return
        
        if getattr(event, "num", None) == 4: delta = -1
        elif getattr(event, "num", None) == 5: delta = 1
        else: delta = int(-event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        self.content_canvas.yview_scroll(delta, "units")


def main():
    app = TBeamDesignApp()
    app.mainloop()


if __name__ == "__main__":
    main()