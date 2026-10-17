"""
TBA4.py — True T-Beam Reviewer (Case 2 Only)

Features:
  - Mode banner in the top bar immediately tells you the Case (always 2 here)
    and whether it's SRB or DRB.
  - History button remembers the last 3 generated givens so you can undo
    an accidental reset.
  - Strict top-bar unlock (answers only appear after Check/Reveal).
  - Handles both SRB and DRB cases for True T-Beams.
  - Strict progression (Check required before Next).
  - Clean UI matching the modern architecture.
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

    def load_problem(self, givens: dict):
        """Loads a specific set of givens (used by the History button)."""
        self.givens = dict(givens)
        self.state = dict(self.givens)
        self.current_step_id = self.workflow.start_step
        self.states = {sid: StepState(step_id=sid) for sid in self.workflow.steps}
        self.history = [self.workflow.start_step]

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
class TBeamSolver:
    @staticmethod
    def calculate_phi(fs, fy):
        if fs >= 1000: return 0.90
        if fy < fs < 1000: return 0.65 + 0.25 * (fs - fy) / (1000 - fy)
        return 0.65

    @staticmethod
    def generate_basic(force_drb=None):
        max_attempts = 200
        for _ in range(max_attempts):
            bw = random.choice([250, 300, 350, 400])
            tf = random.randint(80, 120)
            d = random.randint(400, 500)
            bf = random.choice([700, 800, 900, 1000])
            fc = random.choice([21, 24, 28])
            fy = random.choice([345, 414])
            d_prime = 50
            As = random.randint(4000, 9000)
            
            if 17 < fc < 28: beta1 = 0.85
            elif 28 <= fc <= 55: beta1 = 0.85 - (0.05 * (fc - 28) / 7)
            else: beta1 = 0.65
            
            A_conc = (As * fy) / (0.85 * fc)
            flange_area = bf * tf
            
            if A_conc <= flange_area:
                # Force Case 2
                min_As_case2 = (flange_area * 0.85 * fc / fy) + 100
                As = random.randint(int(min_As_case2), 9000)
                A_conc = (As * fy) / (0.85 * fc)
            
            if A_conc > flange_area:
                a = tf + (A_conc - flange_area) / bw
                c = a / beta1
                fs = 600 * (d - c) / c if c < d else 0
                
                rho_min = max(1.4 / fy, 0.25 * math.sqrt(fc) / fy)
                rho_act = As / (bw * d)
                rho_max = (3.0 / 8.0) * (0.85 * beta1 * fc / fy)
                is_drb = rho_act > rho_max
                
                if force_drb is True and not is_drb:
                    min_As_drb = rho_max * bw * d + 500
                    if min_As_drb >= 9000: continue
                    As = random.randint(int(min_As_drb), 9000)
                    A_conc = (As * fy) / (0.85 * fc)
                    a = tf + (A_conc - flange_area) / bw
                    c = a / beta1
                    fs = 600 * (d - c) / c if c < d else 0
                    rho_act = As / (bw * d)
                    is_drb = rho_act > rho_max
                    if not is_drb: continue
                        
                elif force_drb is False and is_drb:
                    max_As_srb = rho_max * bw * d - 100
                    min_As_case2 = (flange_area * 0.85 * fc / fy) + 100
                    if min_As_case2 >= max_As_srb: continue
                    As = random.randint(int(min_As_case2), int(max_As_srb))
                    A_conc = (As * fy) / (0.85 * fc)
                    a = tf + (A_conc - flange_area) / bw
                    c = a / beta1
                    fs = 600 * (d - c) / c if c < d else 0
                    rho_act = As / (bw * d)
                    is_drb = rho_act > rho_max
                    if is_drb: continue
                
                return dict(
                    bw=bw, tf=tf, d=d, bf=bf, fc=fc, fy=fy, d_prime=d_prime, As=As, force_drb=force_drb
                )
                
        # Fallback
        return dict(bw=300, tf=100, d=435, bf=800, fc=28, fy=345, d_prime=50, As=6000, force_drb=force_drb)

    @staticmethod
    def compute_solution(givens):
        bw = givens["bw"]; tf = givens["tf"]; d = givens["d"]; bf = givens["bf"]
        fc = givens["fc"]; fy = givens["fy"]; As = givens["As"]; d_prime = givens["d_prime"]
        
        if 17 < fc < 28: beta1 = 0.85
        elif 28 <= fc <= 55: beta1 = 0.85 - (0.05 * (fc - 28) / 7)
        else: beta1 = 0.65
        
        A_conc = (As * fy) / (0.85 * fc)
        flange_area = bf * tf
        a_initial = tf + (A_conc - flange_area) / bw
        c_initial = a_initial / beta1
        fs_initial = 600 * (d - c_initial) / c_initial if c_initial < d else 0
        
        rho_min = max(1.4 / fy, 0.25 * math.sqrt(fc) / fy)
        rho_act = As / (bw * d)
        rho_max = (3.0 / 8.0) * (0.85 * beta1 * fc / fy)
        is_drb = rho_act > rho_max
        
        if is_drb:
            As1 = rho_max * bw * d
            As2 = As - As1
            a_rev = (As1 * fy) / (0.85 * fc * bw)
            c_rev = a_rev / beta1
            fs_rev = 600 * (d - c_rev) / c_rev
            fs_prime = 600 * (c_rev - d_prime) / c_rev
            
            phi1 = TBeamSolver.calculate_phi(fs_rev, fy)
            phi2 = TBeamSolver.calculate_phi(fs_prime, fy)
            
            Mn1 = phi1 * As1 * fy * (d - a_rev / 2) / 1000000
            Mn2 = phi1 * As2 * fy * (d - d_prime) / 1000000
            Mu = Mn1 + Mn2
        else:
            As1 = As; As2 = 0
            a_rev = a_initial; c_rev = c_initial; fs_rev = fs_initial; fs_prime = 0
            phi1 = TBeamSolver.calculate_phi(fs_rev, fy); phi2 = 0
            Mn1 = phi1 * As * fy * (d - a_rev / 2) / 1000000
            Mn2 = 0
            Mu = Mn1
            
        return dict(
            beta1=beta1, A_conc=A_conc, flange_area=flange_area, 
            a_initial=a_initial, c_initial=c_initial, fs_initial=fs_initial,
            rho_min=rho_min, rho_act=rho_act, rho_max=rho_max, is_drb=is_drb,
            As1=As1, As2=As2, a_revised=a_rev, c_revised=c_rev, 
            fs_revised=fs_rev, fs_prime=fs_prime, phi1=phi1, phi2=phi2,
            Mn1=Mn1, Mn2=Mn2, Mu=Mu
        )


# ====================================================================
# SECTION 6 — WORKFLOW DEFINITION
# ====================================================================
def _build_tbeam_case2_workflow() -> Workflow:
    def _gen(force_drb=None) -> dict:
        return TBeamSolver.generate_basic(force_drb)

    def _moments_text(s):
        return "Compute φMn1 and Mu." if not s.get("is_drb") else "Compute φMn1, φMn2, and Mu."

    return Workflow(
        id="tbeam_case2",
        name="T-Beam Analysis (Case 2: True T)",
        description="T-Beam Reviewer — Case 2 (Compression block extends into web)",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(id="start", title="Given Beam Properties", content="", next_step="step_conc"),
            "step_conc": Step(
                id="step_conc", title="Step 1: Concrete Compression Area & T-Beam Case",
                content="C = T → 0.85f'c×A_conc = As×fy\n\nVerify Case 2: A_conc > bf×tf",
                question="Enter A_conc and bf×tf.",
                next_step="step_yield"
            ),
            "step_yield": Step(
                id="step_yield", title="Step 2: Check Steel Yielding",
                content="a = tf + (A_conc - bf×tf) / bw\n\nc = a / β1\nfs = 600(d - c) / c",
                question="Enter a, c, and fs.",
                next_step="step_rho"
            ),
            "step_rho": Step(
                id="step_rho", title="Step 3: Reinforcement Condition & Decoupling",
                content="ρmin = max(1.4/fy, 0.25√f'c / fy)\nρact = As / (bw·d)\nρmax = (3/8)·(0.85 β1 f'c / fy)\n\nIf ρact > ρmax, enter As1 and As2.",
                question="Enter ρmin, ρact, ρmax, and (if DRB) As1, As2.",
                branches={"srb": "step_moments", "drb": "step_stresses"}
            ),
            "step_stresses": Step(
                id="step_stresses", title="Step 4: Recalculate Block Depth & Stresses",
                content="a = As1·fy / (0.85 f'c · bw)      c = a/β1\n\nfs = 600(d − c)/c      f's = 600(c − d')/c  (≤ fy)",
                question="Enter a, c, fs, f's, φ1, φ2.",
                next_step="step_moments"
            ),
            "step_moments": Step(
                id="step_moments", title="Step 5: Ultimate Moment Capacity (Mu)",
                content=_moments_text,
                question=lambda s: "Enter φMn1, φMn2, and Mu." if s.get("is_drb") else "Enter φMn1 and Mu.",
                is_terminal=True
            ),
        }
    )

TBEAM_CASE2_WORKFLOW = _build_tbeam_case2_workflow()
ALL_WORKFLOWS = [TBEAM_CASE2_WORKFLOW]


# ====================================================================
# SECTION 7 — MAIN WINDOW
# ====================================================================
_LABELS = {
    "bw": ("bw", "mm"), "bf": ("bf", "mm"), "tf": ("tf", "mm"),
    "d": ("d", "mm"), "d_prime": ("d'", "mm"),
    "fc": ("f'c", "MPa"), "fy": ("fy", "MPa"), "As": ("As", "mm²"),
    "beta1": ("β1", ""), "A_conc": ("A_conc", "mm²"), "flange_area": ("bf×tf", "mm²"),
    "a_initial": ("a", "mm"), "c_initial": ("c", "mm"), "fs_initial": ("fs", "MPa"),
    "rho_min": ("ρmin", ""), "rho_act": ("ρact", ""), "rho_max": ("ρmax", ""),
    "As1": ("As1", "mm²"), "As2": ("As2", "mm²"),
    "a_revised": ("a_rev", "mm"), "c_revised": ("c_rev", "mm"), 
    "fs_revised": ("fs_rev", "MPa"), "fs_prime": ("f's", "MPa"), 
    "phi1": ("φ1", ""), "phi2": ("φ2", ""),
    "Mn1": ("φMn1", "kN·m"), "Mn2": ("φMn2", "kN·m"), "Mu": ("Mu", "kN·m"),
}

_UNLOCK_BY_STEP = {
    "step_conc": ["A_conc", "flange_area"],
    "step_yield": ["beta1", "a_initial", "c_initial", "fs_initial"],
    "step_rho": ["rho_min", "rho_act", "rho_max", "As1", "As2"],
    "step_stresses": ["a_revised", "c_revised", "fs_revised", "fs_prime", "phi1", "phi2"],
    "step_moments": ["Mn1", "Mn2", "Mu"],
}

_MULTI_FIELDS = {
    "step_conc": [("A_conc", "A_conc", "mm²", 1.0), ("flange_area", "bf×tf", "mm²", 1.0)],
    "step_yield": [("a_initial", "a", "mm", 1.0), ("c_initial", "c", "mm", 1.0), ("fs_initial", "fs", "MPa", 1.0)],
    "step_rho": None, # Dynamic
    "step_stresses": [("a_revised", "a_rev", "mm", 1.0), ("c_revised", "c_rev", "mm", 1.0), ("fs_revised", "fs", "MPa", 1.0), ("fs_prime", "f's", "MPa", 1.0), ("phi1", "φ1", "", 0.005), ("phi2", "φ2", "", 0.005)],
    "step_moments": None, # Dynamic
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


class TBeamMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("True T-Beam Reviewer (Case 2)")
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
        
        # NEW: queue for saved givens (up to 3)
        self.givens_history: list[dict] = []

        self.user_inputs: dict[str, tk.StringVar] = {}
        self.multi_entries: dict[str, tuple[tk.StringVar, tk.Entry]] = {}
        self._resize_job = None

        self.mode_var = tk.StringVar(value="random")
        
        self._build_layout()
        self._start_workflow(0)

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)
        self.bind_all("<Return>", self._on_enter)

    def _build_layout(self):
        self.topbar = tk.Frame(self, bg=BG_TOP_BAR, highlightthickness=1, highlightbackground=BORDER_MAIN)
        self.topbar.pack(side="top", fill="x")

        # Mode banner row
        self.banner_frame = tk.Frame(self.topbar, bg=BG_TOP_BAR)
        self.banner_frame.pack(fill="x", padx=10, pady=(6, 0))
        self.banner_lbl = tk.Label(self.banner_frame, text="", font=FONT_LABEL_B, bg=BG_TOP_BAR, fg=FG_LABEL, anchor="w")
        self.banner_lbl.pack(side="left")

        # Properties row
        tk.Label(self.topbar, text="GIVEN  /  PROPERTIES", font=FONT_LABEL_B, bg=BG_TOP_BAR, fg=FG_LABEL, anchor="w").pack(fill="x", padx=10, pady=(2, 0))
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
        
        # NEW: History button
        self.btn_hist = tk.Button(bar, text="History ⏪", width=9, command=self._on_history)
        self.btn_hist.pack(side="left", padx=2)

        self.status_lbl = tk.Label(bar, text="", bg=BG_BOTTOM, anchor="w", font=("Segoe UI", 9, "italic"), fg=FG_HINT)
        self.status_lbl.pack(side="left", padx=8, fill="x", expand=True)

        tk.Button(bar, text="Log", width=9, command=self._toggle_history).pack(side="right", padx=2)

        middle = tk.Frame(self, bg=BG_MAIN)
        middle.pack(side="top", fill="both", expand=True)

        self.history = tk.Frame(middle, width=280, bg=BG_HISTORY, highlightthickness=1, highlightbackground=BORDER_PANEL)
        self.history.pack_propagate(False)
        if self._history_visible:
            self.history.pack(side="right", fill="y")
        
        tk.Label(self.history, text="HISTORY LOG", font=FONT_SECTION, bg=BG_HISTORY, fg=FG_HEAD).pack(anchor="w", padx=8, pady=(8, 4))
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

        self.case_frame = tk.Frame(toolbar, bg=BG_MAIN)
        tk.Label(self.case_frame, text="Mode:", bg=BG_MAIN, font=FONT_LABEL).pack(side="left")
        for label, val in [("Random", "random"), ("Force SRB", "srb"), ("Force DRB", "drb")]:
            tk.Radiobutton(self.case_frame, text=label, value=val, variable=self.mode_var, bg=BG_MAIN, font=FONT_LABEL).pack(side="left", padx=(6, 0))
        self.case_frame.pack(side="left", padx=(12, 0))

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

        # Update the Mode Banner
        sol = TBeamSolver.compute_solution(self.session.givens)
        is_drb = sol["is_drb"]
        mode_str = "DRB" if is_drb else "SRB"
        self.banner_lbl.config(
            text=f"▶ CASE 2 (True T-Beam)  |  Design Type: {mode_str}",
            fg=FG_WARN if is_drb else FG_OK
        )

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
        self._update_history_btn()

    def _on_new_problem(self):
        if self.session is None: return
        mode = self.mode_var.get()
        force_drb = None if mode == "random" else (True if mode == "drb" else False)
        
        self._save_to_history()
        self.user_inputs.clear()
        self.session.new_problem(force_drb=force_drb)
        
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", f"— New problem ({mode}) —\n", "head")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("New problem generated.", FG_WARN)
        self._update_history_btn()

    def _save_to_history(self):
        """Saves the current givens into a rolling queue of 3."""
        if self.session is not None and self.session.givens:
            # Check to not save exact duplicates consecutively
            if not self.givens_history or self.givens_history[-1] != self.session.givens:
                self.givens_history.append(dict(self.session.givens))
                if len(self.givens_history) > 3:
                    self.givens_history.pop(0)

    def _on_history(self):
        """Restores the last saved givens."""
        if not self.givens_history:
            self._set_status("No previous problems in history.", FG_WARN)
            return
            
        prev_givens = self.givens_history.pop()
        self.user_inputs.clear()
        self.session.load_problem(prev_givens)
        
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", "— Restored previous problem —\n", "head")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("Restored previous problem.", FG_OK)
        self._update_history_btn()

    def _update_history_btn(self):
        if not self.givens_history:
            self.btn_hist.configure(state="disabled", text="History (0) ⏪")
        else:
            self.btn_hist.configure(state="normal", text=f"History ({len(self.givens_history)}) ⏪")

    def _multi_field_specs(self, step_id: str):
        if step_id == "step_rho":
            specs = [
                ("rho_min", "ρmin", "", 0.0001),
                ("rho_act", "ρact", "", 0.0001),
                ("rho_max", "ρmax", "", 0.0001)
            ]
            sol = TBeamSolver.compute_solution(self.session.givens)
            if sol["is_drb"]:
                specs.append(("As1", "As1", "mm²", 1.0))
                specs.append(("As2", "As2", "mm²", 1.0))
            return specs
            
        if step_id == "step_moments":
            specs = [("Mn1", "φMn1", "kN·m", 0.5)]
            sol = TBeamSolver.compute_solution(self.session.givens)
            if sol["is_drb"]: specs.append(("Mn2", "φMn2", "kN·m", 0.5))
            specs.append(("Mu", "Mu", "kN·m", 0.5))
            return specs
            
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
        sol = TBeamSolver.compute_solution(self.session.givens)
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
        sol = TBeamSolver.compute_solution(self.session.givens)
        
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

        is_multi = step.id in _MULTI_FIELDS or step.id in ("step_rho", "step_moments")
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
        if step.id in _MULTI_FIELDS or step.id in ("step_rho", "step_moments"):
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
        if step.id in _MULTI_FIELDS or step.id in ("step_rho", "step_moments"):
            self._multi_reveal(step.id)
            self._refresh_topbar()
            self._render_step()

    def _on_next(self):
        if self.session is None or not self.session.can_advance(): return
        
        step = self.session.current_step
        branch = None
        
        if step.id == "step_rho":
            sol = TBeamSolver.compute_solution(self.session.givens)
            branch = "drb" if sol["is_drb"] else "srb"
            
        nxt = self.session.advance(branch)
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
        mode = self.mode_var.get()
        force_drb = None if mode == "random" else (True if mode == "drb" else False)
        
        self._save_to_history()
        self.user_inputs.clear()
        self.session.new_problem(force_drb=force_drb)

        self.hist_text.configure(state="normal")
        self.hist_text.delete("1.0", "end")
        self.hist_text.insert("end", "— Reset —\n", "head")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("Reset. Fresh problem loaded.", FG_WARN)
        self._update_history_btn()

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
        tk.Label(f, text="📋 T-Beam Analysis Summary", font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w").pack(fill="x", pady=(0, 8))
        
        s = self.session.state
        sol = TBeamSolver.compute_solution(self.session.givens)
        s.update(sol)
        
        case_str = "CASE 2 (True T-Beam, DRB)" if s["is_drb"] else "CASE 2 (True T-Beam, SRB)"
        
        box = tk.Frame(f, bg=BG_PANEL, highlightthickness=2, highlightbackground=FG_OK)
        box.pack(anchor="w", pady=8)
        tk.Label(box, text=case_str, font=FONT_TITLE, bg=BG_PANEL, fg=FG_OK).pack(padx=16, pady=(12, 6))
        
        def _row(lbl, val):
            row = tk.Frame(box, bg=BG_PANEL)
            row.pack(anchor="w", padx=16, pady=2)
            tk.Label(row, text=lbl, font=FONT_LABEL, bg=BG_PANEL, width=24, anchor="e").pack(side="left")
            tk.Label(row, text=val, font=("Consolas", 11, "bold"), fg=FG_OK, bg=BG_PANEL).pack(side="left", padx=8)
            
        _row("Moment Capacity Mu:", f"{s['Mu']:.2f} kN·m")
        tk.Frame(box, bg=BG_PANEL, height=6).pack()

        lines = [
            "GIVEN",
            f"  bw = {s['bw']} mm   bf = {s['bf']} mm   tf = {s['tf']} mm",
            f"  d = {s['d']} mm    d' = {s['d_prime']} mm",
            f"  f'c = {s['fc']} MPa   fy = {s['fy']} MPa   As = {s['As']} mm²",
            "",
            "STEP 1 — COMPRESSION BLOCK",
            f"  A_conc = {s['A_conc']:.2f} mm²",
            f"  bf×tf  = {s['flange_area']:.2f} mm²",
            "",
            "STEP 2 — DEPTHS & STRESS",
            f"  β1 = {s['beta1']:.4f}",
            f"  a  = {s['a_initial']:.2f} mm",
            f"  c  = {s['c_initial']:.2f} mm",
            f"  fs = {s['fs_initial']:.2f} MPa",
            "",
            "STEP 3 — RATIOS",
            f"  ρmin = {s['rho_min']:.5f}",
            f"  ρact = {s['rho_act']:.5f}",
            f"  ρmax = {s['rho_max']:.5f}",
        ]
        if s["is_drb"]:
            lines += [
                "  DECOUPLING:",
                f"  As1 = {s['As1']:.0f} mm²",
                f"  As2 = A's = {s['As2']:.0f} mm²",
                "",
                "STEP 4 — REVISED VALUES",
                f"  a_rev = {s['a_revised']:.2f} mm",
                f"  c_rev = {s['c_revised']:.2f} mm",
                f"  fs    = {s['fs_revised']:.2f} MPa",
                f"  f's   = {s['fs_prime']:.2f} MPa",
                f"  φ1    = {s['phi1']:.4f}",
                f"  φ2    = {s['phi2']:.4f}",
            ]
            
        lines += [
            "",
            "FINAL — MOMENT CAPACITY",
            f"  φMn1 = {s['Mn1']:.2f} kN·m",
        ]
        if s["is_drb"]:
            lines.append(f"  φMn2 = {s['Mn2']:.2f} kN·m")
        lines.append(f"  Mu   = {s['Mu']:.2f} kN·m")

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
    app = TBeamMasterApp()
    app.mainloop()


if __name__ == "__main__":
    main()