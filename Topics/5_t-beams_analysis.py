"""
5_t-beams_analysis.py — T-Beam Master Reviewer (NSCP 2015)

Fixed:
  - Removed the invisible "Branching" step that caused a dead-end.
  - Branching now happens immediately after Step 4 (Ratios).
  - Top bar only shows basic givens initially; derived values unlock as
    steps are completed.
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
    CHOICE = "choice"


@dataclass
class Step:
    id: str
    title: str
    content: str | Callable[[dict], str]

    question: Optional[str | Callable[[dict], str]] = None
    solver: Optional[Callable[[dict], Any]] = None
    var_name: Optional[str] = None
    answer_type: AnswerType = AnswerType.NONE
    choices: list[str] | Callable[[dict], list[str]] = field(default_factory=list)
    hints: list[str] | Callable[[dict], list[str]] = field(default_factory=list)

    next_step: Optional[str] = None
    branches: dict[str, str] = field(default_factory=dict)
    is_terminal: bool = False

    def resolve_question(self, state: dict) -> Optional[str]:
        if self.question is None:
            return None
        return self.question(state) if callable(self.question) else self.question

    def resolve_hints(self, state: dict) -> list[str]:
        return self.hints(state) if callable(self.hints) else self.hints


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
        if not self.can_advance():
            return None
        step = self.current_step
        if step.is_terminal:
            return None
            
        nxt = None
        if step.branches:
            if branch_label and branch_label in step.branches:
                nxt = step.branches[branch_label]
            else:
                nxt = next(iter(step.branches.values()))
        else:
            nxt = step.next_step
            
        if not nxt:
            return None
            
        self.current_step_id = nxt
        if (not self.history
                or self.history[-1] != nxt
                and (len(self.history) < 2 or self.history[-2] != nxt)):
            self.history.append(nxt)
        return nxt

    def uncomplete_current(self) -> None:
        self.current_state.completed = False
        self.current_state.final_answer = None

# ====================================================================
# SECTION 5 — SOLVER ENGINE
# ====================================================================
class TBeamSolver:
    MODES = ("random", "case1", "case2_srb", "case2_drb")

    @staticmethod
    def generate(mode="random"):
        if mode not in TBeamSolver.MODES:
            mode = "random"

        if mode == "random":
            p = TBeamSolver._gen_random()
        elif mode == "case1":
            p = TBeamSolver._gen_case1()
        elif mode == "case2_srb":
            p = TBeamSolver._gen_case2_srb()
        elif mode == "case2_drb":
            p = TBeamSolver._gen_case2_drb()

        p["mode"] = mode
        return p

    @staticmethod
    def _beta1(fc):
        if 17 < fc < 28: return 0.85
        elif 28 <= fc <= 55: return 0.85 - 0.05 * (fc - 28) / 7
        else: return 0.65

    @staticmethod
    def _gen_case2_srb():
        tf = random.choice([90, 100, 110])
        bw = random.choice([250, 300, 350])
        d = random.choice([550, 600, 650])
        fc = random.choice([24, 27.6, 28])
        fy = random.choice([345, 414])
        d_prime = 50
        bf = random.choice([1100, 1200, 1300])
        SL1 = 3000; SL2 = 3000; Ln = 6000

        beta1 = TBeamSolver._beta1(fc)
        flange_area = bf * tf
        rho_max = (3.0 / 8.0) * (0.85 * beta1 * fc / fy)
        
        min_as = (0.85 * fc * flange_area) / fy + 100
        max_as = (0.85 * fc / fy) * (rho_max * bw * d)
        As = int((min_as + max_as) / 2)

        p = dict(tf=tf, bw=bw, d=d, fc=fc, fy=fy, d_prime=d_prime, 
                 bf=bf, SL1=SL1, SL2=SL2, Ln=Ln, As=As)
        
        sol = TBeamSolver._calc_intermediate(p)
        if not sol["is_true_t"]:
            p["As"] = int(min_as + 500)
            
        return p

    @staticmethod
    def _gen_case2_drb():
        tf = random.choice([90, 100, 110])
        bw = random.choice([250, 300, 350])
        d = random.choice([400, 435, 450])
        fc = 28; fy = 345; d_prime = 50
        bf = random.choice([800, 900, 1000])
        SL1 = 3000; SL2 = 3000; Ln = 6000
        As = random.choice([5500, 6000, 6500, 7000])

        p = dict(tf=tf, bw=bw, d=d, fc=fc, fy=fy, d_prime=d_prime, 
                 bf=bf, SL1=SL1, SL2=SL2, Ln=Ln, As=As)
                 
        sol = TBeamSolver._calc_intermediate(p)
        if sol["rho_act"] <= sol["rho_max"]:
            p["As"] = int(sol["rho_max"] * bw * d + 1500)
            
        return p

    @staticmethod
    def _gen_case1():
        fc = random.choice([21, 24, 28, 34])
        fy = random.choice([276, 345, 414])
        d_prime = 50
        bw = random.choice([250, 300, 350, 400])
        tf = random.randint(100, 150)
        d = random.randint(400, 600)
        SL1 = random.randint(2000, 4000)
        SL2 = random.randint(2000, 4000)
        Ln = random.randint(4000, 6000)
        
        r1 = bw + 16 * tf
        r2 = bw + (SL1 / 2) + (SL2 / 2)
        r3 = bw + (Ln / 4)
        r4 = 4 * bw
        bf = round(min(r1, r2, r3, r4), 1)

        max_as = (0.85 * fc * bf * tf) / fy
        As = random.randint(1000, int(max_as * 0.8))
        
        return dict(tf=tf, bw=bw, d=d, fc=fc, fy=fy, d_prime=d_prime, 
                    bf=bf, SL1=SL1, SL2=SL2, Ln=Ln, As=As)

    @staticmethod
    def _gen_random():
        fc = random.choice([21, 24, 28, 34])
        fy = random.choice([276, 345, 414])
        d_prime = 50
        bw = random.choice([250, 300, 350, 400, 450])
        tf = random.randint(80, 150)
        d = random.randint(400, 700)
        SL1 = random.randint(2000, 5000)
        SL2 = random.randint(2000, 5000)
        Ln = random.randint(4000, 8000)
        As = random.randint(1000, 9000)
        
        r1 = bw + 16 * tf
        r2 = bw + (SL1 / 2) + (SL2 / 2)
        r3 = bw + (Ln / 4)
        r4 = 4 * bw
        bf = round(min(r1, r2, r3, r4), 1)
        
        return dict(tf=tf, bw=bw, d=d, fc=fc, fy=fy, d_prime=d_prime, 
                    bf=bf, SL1=SL1, SL2=SL2, Ln=Ln, As=As)

    @staticmethod
    def _calc_intermediate(p):
        bw = p["bw"]; tf = p["tf"]; d = p["d"]; fc = p["fc"]; fy = p["fy"]; As = p["As"]
        bf = p["bf"]
        
        beta1 = TBeamSolver._beta1(fc)
        A_conc = (As * fy) / (0.85 * fc)
        bf_tf = bf * tf
        is_true_t = A_conc > bf_tf

        if is_true_t:
            a_initial = tf + (A_conc - bf_tf) / bw
        else:
            a_initial = A_conc / bf

        c_initial = a_initial / beta1
        fs = 600 * (d - c_initial) / c_initial if (0 < c_initial < d) else 0
        
        rho_min = max(1.4 / fy, 0.25 * math.sqrt(fc) / fy)
        rho_act = As / (bw * d)
        rho_max = (3.0 / 8.0) * (0.85 * beta1 * fc / fy)

        return dict(beta1=beta1, A_conc=A_conc, bf_tf=bf_tf, is_true_t=is_true_t,
                    a_initial=a_initial, c_initial=c_initial, fs=fs,
                    rho_min=rho_min, rho_act=rho_act, rho_max=rho_max)

    @staticmethod
    def _compute_downstream(p):
        sol = TBeamSolver._calc_intermediate(p)
        is_true_t = sol["is_true_t"]
        rho_act = sol["rho_act"]
        rho_max = sol["rho_max"]
        
        case = 2 if is_true_t else 1
        reinf = "drb" if (case == 2 and rho_act > rho_max) else "srb"

        bw = p["bw"]; d = p["d"]; fy = p["fy"]; fc = p["fc"]; As = p["As"]; d_prime = p["d_prime"]
        beta1 = sol["beta1"]
        fs = sol["fs"]
        
        def _phi(fs_val):
            if fs_val >= 1000: return 0.90
            if fs_val <= fy: return 0.65
            return 0.65 + 0.25 * (fs_val - fy) / (1000 - fy)

        if case == 1 or reinf == "srb":
            a_rev = sol["a_initial"]
            c_rev = sol["c_initial"]
            fs_rev = fs
            phi1 = _phi(fs_rev)
            phi2 = 0.0
            Mn1 = phi1 * As * fy * (d - a_rev / 2) / 1e6
            Mn2 = 0.0
            Mn = Mn1
            Mu = Mn1
            As1 = 0.0; As2 = 0.0; fs_prime = 0.0
        else:
            As1 = rho_max * bw * d
            As2 = As - As1
            a_rev = (As1 * fy) / (0.85 * fc * bw)
            c_rev = a_rev / beta1
            
            fs_rev = 600 * (d - c_rev) / c_rev if (0 < c_rev < d) else 0
                
            if c_rev > 0:
                fs_prime = 600 * (c_rev - d_prime) / c_rev
                if fs_prime > fy: fs_prime = fy
            else:
                fs_prime = 0

            phi1 = _phi(fs_rev)
            phi2 = _phi(fs_prime)

            Mn1 = phi1 * As1 * fy * (d - a_rev / 2) / 1e6
            Mn2 = phi1 * As2 * fs_prime * (d - d_prime) / 1e6
            Mn = Mn1 + Mn2
            Mu = Mn

        sol.update(case=case, reinf=reinf, a_revised=a_rev, c_revised=c_rev,
                   fs_revised=fs_rev, fs_prime=fs_prime, phi1=phi1, phi2=phi2,
                   As1=As1, As2=As2, Mn1=Mn1, Mn2=Mn2, Mn=Mn, Mu=Mu)
        return sol


# ====================================================================
# SECTION 6 — WORKFLOW DEFINITION
# ====================================================================
def _build_tbeam_workflow() -> Workflow:
    def _gen(mode: str = "random") -> dict:
        return TBeamSolver.generate(mode)

    def _step_bf_text(s):
        return "bf = min of:  bw+16tf,  bw+SL1/2+SL2/2,  bw+Ln/4,  4bw"

    def _step_case_text(s):
        return "A_conc = As·fy / (0.85 f'c)   vs.   bf·tf\n\nA_conc ≤ bf·tf → CASE 1\nA_conc > bf·tf → CASE 2"

    def _step_a_text(s):
        eq = "a = tf + (A_conc − bf·tf) / bw" if s.get("is_true_t") else "a = A_conc / bf"
        return f"{eq}\n\nc = a / β1\nfs = 600(d − c) / c"

    def _step_rho_text(s):
        return "ρmin = max(1.4/fy, 0.25√f'c / fy)\nρact = As / (bw·d)\nρmax = (3/8)·(0.85 β1 f'c / fy)\n\n(ρact > ρmax → DRB decoupling required)"

    def _step_decouple_text(s):
        return "As1 = ρmax · bw · d\nAs2 = A's = As − As1"

    def _step_stresses_text(s):
        return "a = As1·fy / (0.85 f'c · bw)      c = a/β1\n\nfs = 600(d − c)/c      f's = 600(c − d')/c  (≤ fy)"

    def _step_moments_text(s):
        if s["case"] == 2 and s["reinf"] == "drb":
            return "φMn1 = φ1 · As1 · fy · (d − a/2)\n\nφMn2 = φ1 · A's · f's · (d − d')\n\nMu = φMn1 + φMn2"
        return "φMn = φ1 · As · fy · (d − a/2)\n\nMu = φMn"

    return Workflow(
        id="tbeam",
        name="T-Beam Analysis",
        description="T-Beam Master Reviewer — NSCP 2015",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(id="start", title="Given Beam Properties", content="", next_step="step_bf"),
            "step_bf": Step(
                id="step_bf", title="Step 1: Effective Flange Width, bf (NSCP 406.3)",
                content=_step_bf_text, question="Enter bf.",
                next_step="step_case"
            ),
            "step_case": Step(
                id="step_case", title="Step 2: Concrete Compression Area & T-Beam Case",
                content=_step_case_text, question="Enter A_conc and bf·tf.",
                next_step="step_a"
            ),
            "step_a": Step(
                id="step_a", title="Step 3: Block Depth a, Neutral Axis c, Steel Stress fs",
                content=_step_a_text, question="Enter a, c, and fs.",
                next_step="step_rho"
            ),
            "step_rho": Step(
                id="step_rho", title="Step 4: Reinforcement Ratio Condition",
                content=_step_rho_text, question="Enter ρmin, ρact, and ρmax.",
                branches={"case1": "step_moments", "case2": "step_decouple"}
            ),
            "step_decouple": Step(
                id="step_decouple", title="Step 5: Decouple Steel (As → As1 + As2)",
                content=_step_decouple_text, question="Enter As1 and As2.",
                next_step="step_stresses"
            ),
            "step_stresses": Step(
                id="step_stresses", title="Step 6: Revised a, c, fs, f's, φ1, φ2",
                content=_step_stresses_text, question="Enter a, c, fs, f's, φ1, φ2.",
                next_step="step_moments"
            ),
            "step_moments": Step(
                id="step_moments", title="Final: Moment Capacity",
                content=_step_moments_text, question="Enter φMn and Mu (or φMn1, φMn2, Mu for DRB).",
                is_terminal=True
            ),
        }
    )

TBEAM_WORKFLOW = _build_tbeam_workflow()
ALL_WORKFLOWS = [TBEAM_WORKFLOW]


# ====================================================================
# SECTION 7 — MAIN WINDOW
# ====================================================================
_LABELS = {
    "bw": ("bw", "mm"), "bf": ("bf", "mm"), "tf": ("tf", "mm"),
    "d": ("d", "mm"), "d_prime": ("d'", "mm"),
    "SL1": ("SL1", "mm"), "SL2": ("SL2", "mm"), "Ln": ("Ln", "mm"),
    "fc": ("f'c", "MPa"), "fy": ("fy", "MPa"), "As": ("As", "mm²"),
    "beta1": ("β1", ""), "A_conc": ("A_conc", "mm²"), "bf_tf": ("bf·tf", "mm²"),
    "a_initial": ("a", "mm"), "c_initial": ("c", "mm"), "fs": ("fs", "MPa"),
    "rho_min": ("ρmin", ""), "rho_act": ("ρact", ""), "rho_max": ("ρmax", ""),
    "As1": ("As1", "mm²"), "As2": ("As2", "mm²"),
    "a_revised": ("a_rev", "mm"), "c_revised": ("c_rev", "mm"), "fs_revised": ("fs_rev", "MPa"),
    "fs_prime": ("f's", "MPa"), "phi1": ("φ1", ""), "phi2": ("φ2", ""),
    "Mn1": ("φMn1", "kN·m"), "Mn2": ("φMn2", "kN·m"), "Mn": ("φMn", "kN·m"), "Mu": ("Mu", "kN·m"),
    "case": ("Case", ""), "reinf": ("Reinf", "")
}

_UNLOCK_BY_STEP = {
    "step_bf": ["bf"],
    "step_case": ["A_conc", "bf_tf", "is_true_t"],
    "step_a": ["beta1", "a_initial", "c_initial", "fs"],
    "step_rho": ["rho_min", "rho_act", "rho_max"],
    "step_decouple": ["As1", "As2"],
    "step_stresses": ["a_revised", "c_revised", "fs_revised", "fs_prime", "phi1", "phi2"],
    "step_moments": ["Mn1", "Mn2", "Mn", "Mu"],
}

_MULTI_FIELDS = {
    "step_bf": [("bf", "bf", "mm", 0.5)],
    "step_case": [("A_conc", "A_conc", "mm²", 1.0), ("bf_tf", "bf·tf", "mm²", 1.0)],
    "step_a": [("a_initial", "a", "mm", 1.0), ("c_initial", "c", "mm", 1.0), ("fs", "fs", "MPa", 2.0)],
    "step_rho": [("rho_min", "ρmin", "", 5e-5), ("rho_act", "ρact", "", 5e-5), ("rho_max", "ρmax", "", 5e-5)],
    "step_decouple": [("As1", "As1", "mm²", 1.0), ("As2", "As2", "mm²", 1.0)],
    "step_stresses": [("a_revised", "a_rev", "mm", 1.0), ("c_revised", "c_rev", "mm", 1.0), ("fs_revised", "fs", "MPa", 2.0), ("fs_prime", "f's", "MPa", 2.0), ("phi1", "φ1", "", 0.005), ("phi2", "φ2", "", 0.005)],
    "step_moments": None, # Dynamic based on case
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
        self.title("T-Beam Master Reviewer")
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

        self.case_frame = tk.Frame(toolbar, bg=BG_MAIN)
        tk.Label(self.case_frame, text="Mode:", bg=BG_MAIN, font=FONT_LABEL).pack(side="left")
        for label, val in [("Random", "random"), ("Case 1", "case1"), ("Case 2 SRB", "case2_srb"), ("Case 2 DRB", "case2_drb")]:
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
        mode = self.mode_var.get()
        self.user_inputs.clear()
        self.session.new_problem(mode=mode)
        
        sol = TBeamSolver._compute_downstream(self.session.state)
        self.session.state.update(sol)
        
        self.hist_text.configure(state="normal")
        self.hist_text.insert("end", f"— New problem ({mode}) —\n", "head")
        self.hist_text.see("end")
        self.hist_text.configure(state="disabled")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("New problem generated.", FG_WARN)

    def _multi_field_specs(self, step_id: str):
        if step_id == "step_moments":
            is_drb = (self.session.state.get("case") == 2 and self.session.state.get("reinf") == "drb")
            specs = [("Mn1", "φMn1", "kN·m", 0.5)]
            if is_drb: specs.append(("Mn2", "φMn2", "kN·m", 0.5))
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
        state = self.session.state
        errors: list[str] = []
        all_ok = True

        for field_key, label, unit, tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None: continue
            var, ent = var_ent
            raw = var.get().strip()
            expected = state.get(field_key)
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
        state = self.session.state
        for field_key, _label, _unit, _tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None: continue
            var, ent = var_ent
            val = state.get(field_key)
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

        # Read-only auto-complete
        if step.id not in _MULTI_FIELDS and not step.branches and step.id != "step_moments":
            state.completed = True
            if state.final_answer is None: state.final_answer = "(read)"

        f = self.content_frame
        tk.Label(f, text=step.title, font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w").pack(fill="x", pady=(0, 8))

        box = tk.LabelFrame(f, text="Answer", font=FONT_LABEL_B, bg=BG_MAIN, fg=FG_LABEL, bd=1, relief="solid", labelanchor="nw", padx=8, pady=8)
        box.pack(fill="x", pady=(4, 0))

        is_multi = step.id in _MULTI_FIELDS or step.id == "step_moments"
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
        if step.id in _MULTI_FIELDS or step.id == "step_moments":
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
        if step.id in _MULTI_FIELDS or step.id == "step_moments":
            self._multi_reveal(step.id)
            self._refresh_topbar()
            self._render_step()

    def _on_next(self):
        if self.session is None or not self.session.can_advance(): return
        
        step = self.session.current_step
        branch = None
        
        if step.id == "step_rho":
            if "case" not in self.session.state:
                sol = TBeamSolver._compute_downstream(self.session.state)
                self.session.state.update(sol)
            branch = "case2" if self.session.state.get("case") == 2 else "case1"
            
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
        self.user_inputs.clear()
        self.session.new_problem(mode=mode)
        
        sol = TBeamSolver._compute_downstream(self.session.state)
        self.session.state.update(sol)

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
        tk.Label(f, text=f"📋 T-Beam Analysis Summary", font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w").pack(fill="x", pady=(0, 8))
        
        s = self.session.state
        case_str = "CASE 1 (False T-Beam)" if s["case"] == 1 else ("CASE 2 (True T-Beam, SRB)" if s["reinf"] == "srb" else "CASE 2 (True T-Beam, DRB)")
        
        box = tk.Frame(f, bg=BG_PANEL, highlightthickness=2, highlightbackground=FG_OK)
        box.pack(anchor="w", pady=8)
        tk.Label(box, text=case_str, font=FONT_TITLE, bg=BG_PANEL, fg=FG_OK).pack(padx=16, pady=(12, 6))
        
        def _row(lbl, val):
            row = tk.Frame(box, bg=BG_PANEL)
            row.pack(anchor="w", padx=16, pady=2)
            tk.Label(row, text=lbl, font=FONT_LABEL, bg=BG_PANEL, width=24, anchor="e").pack(side="left")
            tk.Label(row, text=val, font=("Consolas", 11, "bold"), fg=FG_OK, bg=BG_PANEL).pack(side="left", padx=8)
            
        _row("Effective Width bf:", f"{s['bf']} mm")
        _row("Moment Capacity Mu:", f"{s['Mu']:.2f} kN·m")
        tk.Frame(box, bg=BG_PANEL, height=6).pack()

        lines = [
            "GIVEN",
            f"  bw = {s['bw']} mm   bf = {s['bf']} mm   tf = {s['tf']} mm",
            f"  d = {s['d']} mm    d' = {s['d_prime']} mm",
            f"  f'c = {s['fc']} MPa   fy = {s['fy']} MPa   As = {s['As']} mm²",
            "",
            "STEP 1 — EFFECTIVE WIDTH",
            f"  bf = {s['bf']} mm",
            "",
            "STEP 2 — COMPRESSION BLOCK",
            f"  A_conc = {s['A_conc']:.2f} mm²",
            f"  bf·tf  = {s['bf_tf']:.2f} mm²",
            f"  {case_str}",
            "",
            "STEP 3 — DEPTHS & STRESS",
            f"  β1 = {s['beta1']:.4f}",
            f"  a  = {s['a_initial']:.2f} mm",
            f"  c  = {s['c_initial']:.2f} mm",
            f"  fs = {s['fs']:.2f} MPa",
        ]
        if s["case"] == 2:
            lines += [
                "",
                "STEP 4 — RATIOS",
                f"  ρmin = {s['rho_min']:.5f}",
                f"  ρact = {s['rho_act']:.5f}",
                f"  ρmax = {s['rho_max']:.5f}",
            ]
        if s["case"] == 2 and s["reinf"] == "drb":
            lines += [
                "",
                "STEP 5 — DECOUPLING",
                f"  As1 = {s['As1']:.0f} mm²",
                f"  As2 = A's = {s['As2']:.0f} mm²",
                "",
                "STEP 6 — REVISED VALUES",
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
        if s["case"] == 2 and s["reinf"] == "drb":
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