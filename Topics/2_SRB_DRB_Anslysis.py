"""
2_SRB_DRB_Anslysis.py — RCD SRB/DRB Beam Analysis Reviewer (single-file build).

Strict behavior enforced:
  - Initial load ONLY shows basic Givens (b, d, d', As, f'c, fy).
  - Derived values (a, c, rho, Mn, etc.) will NOT appear in the top bar
    until you click "Check" (and get it right) or "Reveal".
  - You cannot advance to the next step without completing the current one.
  - Resetting or making a new problem CLEARS all typed answers.
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
    unit: Optional[str] = None
    answer_type: AnswerType = AnswerType.NONE
    choices: list[str] | Callable[[dict], list[str]] = field(default_factory=list)
    tolerance: float = 0.02
    hints: list[str] | Callable[[dict], list[str]] = field(default_factory=list)

    display_unit: Optional[str] = None

    next_step: Optional[str] = None
    branches: dict[str, str] = field(default_factory=dict)
    is_terminal: bool = False

    def resolve_question(self, state: dict) -> Optional[str]:
        if self.question is None:
            return None
        return self.question(state) if callable(self.question) else self.question

    def resolve_choices(self, state: dict) -> list[str]:
        return self.choices(state) if callable(self.choices) else self.choices

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


@dataclass
class Attempt:
    step_id: str
    answer: str
    correct: bool
    timestamp: float


# ====================================================================
# SECTION 3 — ENGINE / VALIDATOR
# ====================================================================
def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("$$", "").replace("$", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = re.sub(r"[\{\}\\]", "", s)
    s = re.sub(r"\s+", "", s)
    return s

_UNIT_RE = re.compile(
    r"(kn\.?m|knm|kn|n|mm2|mm²|mm|cm|m|mpa|kpa|pa|%)\s*$",
    re.IGNORECASE,
)

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

def validate_answer(
    step: Step,
    user_answer: str,
    expected_value: Any = None,
    state: Optional[dict] = None,
) -> tuple[bool, str]:
    if step.answer_type == AnswerType.NONE:
        return True, ""

    user = (user_answer or "").strip()
    if not user:
        return False, "Please enter an answer."

    if step.answer_type == AnswerType.CHOICE:
        if expected_value is not None and isinstance(expected_value, str):
            if user == expected_value:
                return True, ""
            return False, "Not the correct choice."
        if step.branches:
            if user in step.branches:
                return True, ""
            return False, f"Choose one of: {', '.join(step.branches.keys())}"
        choices = step.resolve_choices(state or {})
        return False, f"Choose one of: {', '.join(choices)}"

    if step.answer_type == AnswerType.NUMERIC:
        if expected_value is None:
            return False, "Internal error: no expected value."
        e = float(expected_value)
        u, unit = _try_number(user)
        if u is None:
            return False, "That doesn't look like a number."

        if unit is not None and step.display_unit:
            expected_unit = step.display_unit.strip().lower()
            if unit != expected_unit:
                return False, f"Value looks like {unit}, but expected {step.display_unit}."

        tol = abs(step.tolerance)
        if e == 0:
            return (True, "") if abs(u) <= tol else (False, "Not quite.")
        
        rel_err = abs(u - e) / abs(e)
        abs_floor = max(abs(e) * tol, 1e-9)
        if rel_err <= tol or abs(u - e) <= abs_floor:
            return True, ""
        return False, "Not quite. Double-check your calculation."

    if _normalize_text(str(expected_value)) == _normalize_text(user):
        return True, ""
    return False, "Not quite. Try again."


# ====================================================================
# SECTION 4 — ENGINE / SESSION
# ====================================================================
@dataclass
class StepState:
    step_id: str
    attempts: list[Attempt] = field(default_factory=list)
    completed: bool = False
    hints_used: int = 0
    final_answer: Optional[str] = None
    expected_value: Optional[Any] = None


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

    def expected_for_current(self) -> Any:
        step = self.current_step
        if step.solver is None:
            return None
        return step.solver(self.state)

    def submit(self, answer: str) -> tuple[bool, str]:
        step = self.current_step
        st = self.current_state
        expected = self.expected_for_current()
        ok, msg = validate_answer(step, answer, expected, self.state)
        st.attempts.append(Attempt(step.id, answer, ok, time.time()))
        if ok:
            st.completed = True
            st.final_answer = answer
            st.expected_value = expected
            if step.var_name is not None and expected is not None:
                self.state[step.var_name] = expected
        return ok, msg

    def reveal_next_hint(self) -> Optional[str]:
        step = self.current_step
        st = self.current_state
        hints = step.resolve_hints(self.state)
        if st.hints_used < len(hints):
            h = hints[st.hints_used]
            st.hints_used += 1
            return h
        return None

    def can_advance(self) -> bool:
        return self.current_state.completed

    def advance(self, branch_label: Optional[str] = None) -> Optional[str]:
        if not self.can_advance():
            return None
        step = self.current_step
        if step.is_terminal:
            return None
        if step.branches:
            if branch_label and branch_label in step.branches:
                nxt = step.branches[branch_label]
            elif step.next_step:
                nxt = step.next_step
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
        step = self.current_step
        st = self.current_state
        st.completed = False
        st.final_answer = None
        st.expected_value = None
        if step.var_name is not None:
            self.state.pop(step.var_name, None)

    def progress(self) -> tuple[int, int]:
        total = len(self.workflow.steps)
        done = sum(1 for s in self.states.values() if s.completed)
        return done, total


# ====================================================================
# SECTION 5 — UI / HISTORY PANEL
# ====================================================================
class HistoryPanel(tk.Frame):
    def __init__(self, parent, width=280):
        super().__init__(parent, width=width, bg=BG_HISTORY,
                         highlightthickness=1, highlightbackground=BORDER_PANEL)
        self.pack_propagate(False)

        tk.Label(self, text="HISTORY", font=FONT_SECTION,
                 bg=BG_HISTORY, fg=FG_HEAD).pack(anchor="w", padx=8, pady=(8, 4))

        wrap = tk.Frame(self, bg=BG_HISTORY)
        wrap.pack(fill="both", expand=True, padx=4, pady=4)

        self.text = tk.Text(wrap, width=32, wrap="word", bg=BG_PANEL,
                            relief="flat", font=FONT_HIST,
                            highlightthickness=1, highlightbackground=BORDER_PANEL)
        sb = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_config("green",  foreground=FG_OK)
        self.text.tag_config("yellow", foreground=FG_WARN)
        self.text.tag_config("gray",   foreground=FG_HINT)
        self.text.tag_config("red",    foreground=FG_ERR)
        self.text.tag_config("blue",   foreground=FG_EXTRA)
        self.text.tag_config("head",   foreground=FG_HEAD,
                             font=("Consolas", 9, "bold"))
        self.text.configure(state="disabled")

    def log(self, message: str, tag: str = "gray"):
        self.text.configure(state="normal")
        self.text.insert("end", message + "\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# ====================================================================
# SECTION 6 — SOLVER
# ====================================================================
def _beta1(fc: float) -> float:
    if 17 < fc < 28:
        return 0.85
    if 28 <= fc <= 55:
        return 0.85 - (0.05 * (fc - 28) / 7)
    return 0.65

def _phi_from_fs(fs: float, fy: float) -> float:
    if fs >= 1000:
        return 0.90
    if fy < fs < 1000:
        return 0.65 + (0.25 * (fs - fy) / (1000 - fy))
    return 0.65

def _make_problem(mode: str) -> dict:
    b = random.randint(250, 400)
    d = random.randint(400, 650)
    fc = random.randint(21, 45)
    fy = random.choice([276, 345, 414])
    if mode == "srb":
        As = random.randint(1500, 3500)
    elif mode == "drb":
        As = random.randint(4500, 8000)
    else:
        As = random.randint(1500, 8000)
    return {
        "b": float(b), "d": float(d),
        "d_prime": 50.0, "As": float(As),
        "fc": float(fc), "fy": float(fy),
        "mode": mode,
    }

def _solve(state: dict) -> dict:
    b = state["b"]; d = state["d"]; As = state["As"]
    fc = state["fc"]; fy = state["fy"]; d_prime = state["d_prime"]
    Es = 200000.0; eps_cu = 0.003

    out: dict = {}

    # Step 1
    a_fict = (As * fy) / (0.85 * fc * b)
    b1 = _beta1(fc)
    c = a_fict / b1
    fs = 600.0 * ((d - c) / c) if c < d else 0.0
    did_yield = fs > fy

    c_recalc = c
    a_recalc = a_fict
    fs_recalc = fs
    if not did_yield:
        C_eq = 0.85 * fc * b * b1
        A_ = C_eq
        B_ = As * Es * eps_cu
        C_ = -(As * Es * eps_cu * d)
        disc = B_ * B_ - 4 * A_ * C_
        if disc >= 0:
            c_recalc = (-B_ + math.sqrt(disc)) / (2 * A_)
            a_recalc = b1 * c_recalc
            fs_recalc = Es * eps_cu * ((d - c_recalc) / c_recalc)

    out.update({
        "a_fict": a_fict, "beta1": b1, "c": c, "fs": fs,
        "did_yield": did_yield,
        "c_recalc": c_recalc, "a_recalc": a_recalc, "fs_recalc": fs_recalc,
    })

    # Step 2
    r1 = 1.4 / fy
    r2 = 0.25 * math.sqrt(fc) / fy
    rho_min = max(r1, r2)
    rho_act = As / (b * d)
    if fs > 1000:
        rho_max = (3 / 8) * (0.85 * b1 * fc / fy)
    else:
        rho_max = (3 / 7) * (0.85 * b1 * fc / fy)
    is_singly = (rho_min < rho_act < rho_max)
    out.update({
        "rho_min": rho_min, "rho_act": rho_act, "rho_max": rho_max,
        "is_singly": is_singly,
    })

    # Step 3
    if is_singly:
        if did_yield:
            steel_force = As * fy
            a_used = a_fict
        else:
            steel_force = As * fs_recalc
            a_used = a_recalc
        Mn = (steel_force * (d - (a_used / 2))) / 1_000_000
        phi = _phi_from_fs(fs if did_yield else fs_recalc, fy)
        out.update({
            "Mn": round(Mn, 3), "phi": phi,
            "Mu": round(phi * Mn, 3),
        })
    else:
        As1 = rho_max * b * d
        As2 = As - As1
        a_drb = (As1 * fy) / (0.85 * fc * b)
        c_drb = a_drb / b1
        fs_drb = 600 * (d - c_drb) / c_drb
        fs_prime_drb = 600 * (c_drb - d_prime) / c_drb
        phi = _phi_from_fs(fs_drb, fy)
        Mn1 = (As1 * fy * (d - a_drb / 2)) / 1_000_000
        Mn2 = (As2 * fs_prime_drb * (d - d_prime)) / 1_000_000
        Mn_drb = Mn1 + Mn2
        out.update({
            "As1": As1, "As2": As2,
            "a_drb": a_drb, "c_drb": c_drb,
            "fs_drb": fs_drb, "fs_prime_drb": fs_prime_drb,
            "Mn1": Mn1, "Mn2": Mn2, "Mn_drb": Mn_drb,
            "phi": phi, "Mu_drb": round(phi * Mn_drb, 3),
        })

    return out


# ====================================================================
# SECTION 7 — WORKFLOW DEFINITION
# ====================================================================
def _build_srb_drb_workflow() -> Workflow:
    def _gen(mode: str = "random") -> dict:
        return _make_problem(mode)

    step1 = Step(
        id="step1",
        title="Step 1 — Check if Steel Yields",
        content="",
        question="Enter the computed value for each field below.",
        solver=None, 
        answer_type=AnswerType.NONE,
        hints=[
            "a = As·fy / (0.85·f'c·b)",
            "β1 = 0.85 for f'c ≤ 28 MPa, then decreases 0.05 per 7 MPa to 0.65",
            "c = a / β1",
            "fs = 600·(d − c) / c",
            "Yielding check: fs > fy ?",
            "If not yielded: solve the quadratic for c, then a = β1·c.",
        ],
        next_step="step2",
    )

    step2 = Step(
        id="step2",
        title="Step 2 — SRB or DRB?",
        content="",
        question="Which classification applies?",
        answer_type=AnswerType.CHOICE,
        branches={
            "Singly Reinforced (In-Between)": "step3_singly",
            "Doubly Reinforced (Above rho_max)": "step3_doubly",
        },
        hints=[
            "ρmin uses the larger of 1.4/fy and 0.25√f'c/fy.",
            "ρmax is (3/8)·(0.85 β1 f'c / fy) when fs > 1000 MPa.",
            "Singly = between ρmin and ρmax. Else doubly.",
        ],
    )

    step3_singly = Step(
        id="step3_singly",
        title="Step 3 (Singly) — Moment Capacity",
        content="",
        question="Enter Mn, φ, and Mu.",
        solver=None,
        answer_type=AnswerType.NONE,
        hints=[
            "Mn = Ts·(d − a/2) / 1e6",
            "Use fs (yielded) or fs_recalc (not yielded) for Ts.",
            "φ from 0.65 → 0.90 transition based on fs.",
            "Mu = φ · Mn",
        ],
        is_terminal=True,
    )

    step3_doubly = Step(
        id="step3_doubly",
        title="Step 3 (Doubly) — Decouple Steel & Solve",
        content="",
        question="Enter As1, As2, a, c, Mn1, Mn2, and Mu.",
        solver=None,
        answer_type=AnswerType.NONE,
        hints=[
            "As1 = ρmax · b · d",
            "As2 = As − As1",
            "a and c are for the *decoupled* steel As1 (not the original).",
            "f's from strain compatibility at the compression steel.",
            "φ from fs_drb (tension steel stress at the decoupled depth).",
            "Mu = φ · (Mn1 + Mn2)",
        ],
        is_terminal=True,
    )

    return Workflow(
        id="srb_drb_analysis",
        name="SRB / DRB Beam Analysis",
        description="Step-by-step ultimate strength analysis of a rectangular RC beam.",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(
                id="start",
                title="Given Beam Properties",
                content="",
                next_step="step1",
            ),
            "step1": step1,
            "step2": step2,
            "step3_singly": step3_singly,
            "step3_doubly": step3_doubly,
        },
    )


SRB_DRB_WORKFLOW = _build_srb_drb_workflow()
ALL_WORKFLOWS = [SRB_DRB_WORKFLOW]


# ====================================================================
# SECTION 8 — MAIN WINDOW
# ====================================================================
_LABELS = {
    "b": ("b", "mm"), "d": ("d", "mm"), "d_prime": ("d'", "mm"),
    "As": ("As", "mm²"), "fc": ("f'c", "MPa"), "fy": ("fy", "MPa"),
    "mode": ("mode", ""),
    "a_fict": ("a", "mm"), "beta1": ("β1", ""),
    "c": ("c", "mm"), "fs": ("fs", "MPa"),
    "did_yield": ("yielded", ""),
    "c_recalc": ("c (recalc)", "mm"),
    "rho_min": ("ρmin", ""), "rho_act": ("ρact", ""), "rho_max": ("ρmax", ""),
    "is_singly": ("SRB?", ""),
    "Mn": ("Mn", "kN·m"), "phi": ("φ", ""), "Mu": ("Mu", "kN·m"),
    "As1": ("As1", "mm²"), "As2": ("As2", "mm²"),
    "a_drb": ("a (DRB)", "mm"), "c_drb": ("c (DRB)", "mm"),
    "Mn1": ("Mn1", "kN·m"), "Mn2": ("Mn2", "kN·m"),
    "Mu_drb": ("Mu (DRB)", "kN·m"),
}

_UNLOCK_BY_STEP = {
    "step1":       ["a_fict", "beta1", "c", "fs", "did_yield", "c_recalc"],
    "step2":       ["rho_min", "rho_act", "rho_max", "is_singly"],
    "step3_singly": ["Mn", "phi", "Mu"],
    "step3_doubly": ["As1", "As2", "a_drb", "c_drb", "Mn1", "Mn2", "Mu_drb"],
}

_MULTI_FIELDS = {
    "step1": [
        ("a_fict",  "a",       "mm",   0.1),
        ("beta1",   "β1",      "",     0.001),
        ("c",       "c",       "mm",   0.1),
        ("fs",      "fs",      "MPa",  0.5),
        ("did_yield", "Yielded? (Yes/No)", "", 0.0),
        ("c_recalc", "c (recalc)", "mm", 0.5),
    ],
    "step3_singly": [
        ("Mn",  "Mn",  "kN·m", 0.1),
        ("phi", "φ",   "",     0.001),
        ("Mu",  "Mu",  "kN·m", 0.1),
    ],
    "step3_doubly": [
        ("As1",  "As1", "mm²", 1.0),
        ("As2",  "As2", "mm²", 1.0),
        ("a_drb", "a", "mm", 0.5),
        ("c_drb", "c", "mm", 0.5),
        ("Mn1",  "Mn1", "kN·m", 0.5),
        ("Mn2",  "Mn2", "kN·m", 0.5),
        ("Mu_drb", "Mu", "kN·m", 0.5),
    ],
}

def _fmt(v):
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        if v == int(v):
            return f"{int(v):,}"
        if abs(v) < 1:
            return f"{v:.4f}"
        if abs(v) >= 10000:
            return f"{v:,.1f}"
        return f"{v:.4g}"
    return str(v)


class SRBDRBReviewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD SRB / DRB Beam Analysis Reviewer")
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
        self.answer_var = tk.StringVar()
        self.answer_widget = None
        self.hint_lbl = None
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
        self.bind_all("<KP_Enter>", self._on_enter)

    def _build_layout(self):
        self.topbar = tk.Frame(self, bg=BG_TOP_BAR,
                               highlightthickness=1,
                               highlightbackground=BORDER_MAIN)
        self.topbar.pack(side="top", fill="x")

        tk.Label(self.topbar, text="GIVEN  /  PROPERTIES",
                 font=FONT_LABEL_B, bg=BG_TOP_BAR, fg=FG_LABEL, anchor="w"
                 ).pack(fill="x", padx=10, pady=(6, 0))

        self.given_row = tk.Frame(self.topbar, bg=BG_TOP_BAR)
        self.given_row.pack(fill="x", padx=10, pady=(0, 6))

        self.bottombar = tk.Frame(self, bg=BG_BOTTOM,
                                  highlightthickness=1,
                                  highlightbackground="#bbbbbb")
        self.bottombar.pack(side="bottom", fill="x")

        bar = tk.Frame(self.bottombar, bg=BG_BOTTOM)
        bar.pack(fill="x", padx=8, pady=6)

        self.btn_back = tk.Button(bar, text="◀ Back", width=8, command=self._on_back)
        self.btn_back.pack(side="left", padx=2)

        self.btn_check = tk.Button(bar, text="✓ Check", width=8,
                                   bg=BG_BTN_GO, command=self._on_check)
        self.btn_check.pack(side="left", padx=2)

        self.btn_reveal = tk.Button(bar, text="Reveal", width=8,
                                    bg=BG_BTN_WARM, command=self._on_reveal)
        self.btn_reveal.pack(side="left", padx=2)

        self.btn_next = tk.Button(bar, text="Next ▶", width=8,
                                  bg=BG_BTN_NEU, command=self._on_next)
        self.btn_next.pack(side="left", padx=2)

        tk.Button(bar, text="Reset", width=8,
                  command=self._on_reset).pack(side="left", padx=(10, 2))

        self.status_lbl = tk.Label(bar, text="", bg=BG_BOTTOM,
                                   anchor="w", font=("Segoe UI", 9, "italic"),
                                   fg=FG_HINT)
        self.status_lbl.pack(side="left", padx=8, fill="x", expand=True)

        tk.Button(bar, text="History", width=9,
                  command=self._toggle_history).pack(side="right", padx=2)
        tk.Button(bar, text="Copy", width=9,
                  command=self._on_copy).pack(side="right", padx=2)

        middle = tk.Frame(self, bg=BG_MAIN)
        middle.pack(side="top", fill="both", expand=True)

        self.history = HistoryPanel(middle, width=280)
        if self._history_visible:
            self.history.pack(side="right", fill="y")

        main = tk.Frame(middle, bg=BG_MAIN)
        main.pack(side="left", fill="both", expand=True)

        toolbar = tk.Frame(main, bg=BG_MAIN)
        toolbar.pack(side="top", fill="x", padx=8, pady=(6, 2))

        tk.Label(toolbar, text="Workflow:", bg=BG_MAIN,
                 font=FONT_LABEL).pack(side="left")

        self.workflow_combo = ttk.Combobox(
            toolbar, width=28, state="readonly",
            values=[wf.name for wf in ALL_WORKFLOWS],
        )
        self.workflow_combo.pack(side="left", padx=6)
        self.workflow_combo.current(0)
        self.workflow_combo.bind("<<ComboboxSelected>>", self._on_workflow_change)

        self.case_frame = tk.Frame(toolbar, bg=BG_MAIN)
        tk.Label(self.case_frame, text="Mode:", bg=BG_MAIN,
                 font=FONT_LABEL).pack(side="left")
        self.mode_var = tk.StringVar(value="random")
        for label, val in [("True Random", "random"), ("SRB", "srb"), ("DRB", "drb")]:
            tk.Radiobutton(self.case_frame, text=label, value=val,
                           variable=self.mode_var, bg=BG_MAIN, font=FONT_LABEL,
                           ).pack(side="left", padx=(6, 0))
        self.case_frame.pack(side="left", padx=(12, 0))

        tk.Button(toolbar, text="🎲 New Problem", bg=BG_BTN_NEU,
                  command=self._on_new_problem).pack(side="right", padx=2)

        canvas_wrap = tk.Frame(main, bg=BG_MAIN)
        canvas_wrap.pack(side="top", fill="both", expand=True)

        self.content_canvas = tk.Canvas(canvas_wrap, bg=BG_MAIN,
                                        highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(canvas_wrap, orient="vertical",
                            command=self.content_canvas.yview)
        self.content_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.content_canvas.pack(side="left", fill="both", expand=True)

        self.content_frame = tk.Frame(self.content_canvas, bg=BG_MAIN)
        self._content_win = self.content_canvas.create_window(
            (10, 6), window=self.content_frame, anchor="nw")

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(
                scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.bind(
            "<Configure>",
            lambda e: self.content_canvas.itemconfigure(
                self._content_win, width=max(200, e.width - 20)))

        self.bind("<Configure>", self._on_root_resize)

    def _refresh_topbar(self):
        for w in self.given_row.winfo_children():
            w.destroy()
        if self.session is None:
            return

        state = self.session.state
        givens_keys = set(self.session.givens.keys())

        # Only show a derived value once the step that produces it is completed.
        unlocked_keys: set[str] = set()
        for sid, st in self.session.states.items():
            if st.completed:
                unlocked_keys.update(_UNLOCK_BY_STEP.get(sid, []))

        given_items = [(k, v) for k, v in state.items() if k in givens_keys]
        extra_items = [(k, v) for k, v in state.items()
                       if k not in givens_keys and k in unlocked_keys]
        items = [(k, v, True) for k, v in given_items] + \
                [(k, v, False) for k, v in extra_items]

        width = self.winfo_width() or self.winfo_screenwidth()
        usable = width - (280 if self._history_visible else 40)
        usable = max(400, usable)
        cols = max(4, min(len(items), usable // 118)) or 1

        for i, (key, value, is_given) in enumerate(items):
            r, c = divmod(i, cols)
            label, unit = _LABELS.get(key, (key, ""))
            val_str = _fmt(value)
            if unit:
                val_str = f"{val_str} {unit}"

            fg = FG_VALUE if is_given else FG_EXTRA
            fg_lbl = FG_LABEL if is_given else FG_EXTRA

            box = tk.Frame(self.given_row, bg=BG_TOP_BAR)
            box.grid(row=r, column=c, padx=4, pady=1, sticky="w")
            tk.Label(box, text=label, font=FONT_LABEL_B, bg=BG_TOP_BAR,
                     fg=fg_lbl).pack(anchor="w")
            tk.Label(box, text=val_str, font=FONT_VALUE, bg=BG_TOP_BAR,
                     fg=fg).pack(anchor="w")

    def _on_root_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(180, self._refresh_topbar)

    def _start_workflow(self, idx):
        self.session = Session(ALL_WORKFLOWS[idx])
        self.workflow_combo.set(ALL_WORKFLOWS[idx].name)
        self.history.clear()
        self.history.log(f"— {ALL_WORKFLOWS[idx].name} —", "head")
        self.history.log("Review started.", "gray")
        self._refresh_topbar()
        self._render_step()
        self._set_status("Ready. Solve the step, then click Check.", FG_HINT)

    def _on_workflow_change(self, event=None):
        idx = self.workflow_combo.current()
        if idx < 0:
            return
        self._start_workflow(idx)

    def _on_new_problem(self):
        if self.session is None:
            return
        mode = self.mode_var.get()
        
        # Clear user inputs so the entries are blank
        self.user_inputs.clear()
        
        self.session.new_problem(mode=mode)
        tag = ""
        if mode == "srb":
            tag = " [Forced SRB]"
        elif mode == "drb":
            tag = " [Forced DRB]"
        self.history.log(f"— New problem —{tag}", "head")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("New problem generated.", FG_WARN)

    def _multi_field_specs(self, step_id: str):
        specs = _MULTI_FIELDS.get(step_id, [])
        if step_id == "step1":
            solved = _solve(self.session.state)
            did_yield = bool(solved.get("did_yield", True))
            specs = [s for s in specs if s[0] != "c_recalc" or not did_yield]
        return specs

    def _mk_var(self, key: str, default: str = "") -> tk.StringVar:
        if key in self.user_inputs:
            return self.user_inputs[key]
        v = tk.StringVar(value=default)
        def _cb(*a, _k=key, _v=v):
            self.user_inputs[_k] = _v
        v.trace_add("write", _cb)
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
            tk.Label(grid, text=label, bg=BG_MAIN, font=FONT_LABEL,
                     width=14, anchor="e"
                     ).grid(row=r, column=c * 3, sticky="e", padx=(0, 6), pady=3)
            var = self._mk_var(key, "")
            ent = tk.Entry(grid, textvariable=var, width=14,
                           justify="center", font=FONT_ENTRY)
            ent.grid(row=r, column=c * 3 + 1, sticky="w", pady=3)
            if unit:
                tk.Label(grid, text=unit, bg=BG_MAIN, font=FONT_LABEL,
                         fg=FG_HINT
                         ).grid(row=r, column=c * 3 + 2, sticky="w", padx=(4, 20))
            self.multi_entries[field_key] = (var, ent)

        if self._last_answer_wrong:
            for var, ent in self.multi_entries.values():
                try:
                    ent.configure(bg=BG_INPUT_ERR)
                except tk.TclError:
                    pass

    def _multi_check(self, step_id: str) -> bool:
        specs = self._multi_field_specs(step_id)
        solved = _solve(self.session.state)
        errors: list[str] = []
        all_ok = True

        for field_key, label, unit, tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None:
                continue
            var, ent = var_ent
            raw = var.get().strip()

            if field_key == "did_yield":
                expected = "Yes" if solved.get("did_yield") else "No"
                ok = raw == expected
            else:
                expected = solved.get(field_key)
                u, typed_unit = _try_number(raw)
                if u is None:
                    ok = False
                elif typed_unit is not None and unit and typed_unit != unit.strip().lower():
                    ok = False
                elif expected is None:
                    ok = False
                else:
                    e = float(expected)
                    t = float(tol)
                    ok = abs(u - e) <= t if t > 0 else (abs(u - e) < 1e-9)

            try:
                ent.configure(bg=BG_INPUT_OK if ok else BG_INPUT_ERR)
            except tk.TclError:
                pass

            if not ok:
                all_ok = False
                expected_str = solved.get(field_key, "?")
                if field_key == "did_yield":
                    expected_str = "Yes" if expected_str else "No"
                errors.append(f"{label}: expected {_fmt(expected_str)} (got {raw or '—'})")

        if all_ok:
            st = self.session.states[step_id]
            st.completed = True
            if st.final_answer is None:
                st.final_answer = "(all fields correct)"
            
            # Inject the solved values into state so they show up in the top bar
            for k, v in solved.items():
                if k not in self.session.givens:
                    self.session.state[k] = v
                    
            self.history.log(f"✓ {self.session.workflow.steps[step_id].title} — correct", "green")
            self._set_status("✓ Correct! Click Next to continue.", FG_OK)
            return True

        self.history.log(f"✗ {self.session.workflow.steps[step_id].title} — errors:", "yellow")
        for m in errors:
            self.history.log("  " + m, "yellow")
        self._set_status("✗ Some fields are wrong. Fix and re-check.", FG_ERR)
        messagebox.showwarning("Check", "\n".join(errors))
        return False

    def _multi_reveal(self, step_id: str):
        specs = self._multi_field_specs(step_id)
        solved = _solve(self.session.state)
        for field_key, _label, _unit, _tol in specs:
            var_ent = self.multi_entries.get(field_key)
            if var_ent is None:
                continue
            var, ent = var_ent
            if field_key == "did_yield":
                value_str = "Yes" if solved.get("did_yield") else "No"
            else:
                val = solved.get(field_key)
                if val is None:
                    continue
                value_str = f"{val:.4g}" if isinstance(val, float) else str(val)
            try:
                var.set(value_str)
                ent.delete(0, "end")
                ent.insert(0, value_str)
                ent.configure(bg=BG_INPUT_OK)
            except tk.TclError:
                pass

        st = self.session.states[step_id]
        st.completed = True
        st.final_answer = st.final_answer or "(revealed)"
        
        # Inject the solved values into state so they show up in the top bar
        for k, v in solved.items():
            if k not in self.session.givens:
                self.session.state[k] = v
                
        self.history.log(f"Revealed {self.session.workflow.steps[step_id].title}", "yellow")
        self._set_status("Answers revealed.", FG_WARN)

    def _clear_content(self):
        for w in self.content_frame.winfo_children():
            w.destroy()
        self.answer_widget = None
        self.answer_var.set("")
        self.hint_lbl = None
        self.multi_entries = {}

    def _render_step(self):
        self._clear_content()
        if self.session is None:
            return

        step = self.session.current_step
        state = self.session.current_state

        # READ-ONLY STEPS should advance automatically on Next,
        # but we don't mark them completed until the user is actually
        # interacting with the flow. However, for simplicity we will mark the
        # start page as completed immediately so you can click Next.
        if step.answer_type == AnswerType.NONE and step.solver is None and step.id not in _MULTI_FIELDS:
            state.completed = True
            if state.final_answer is None:
                state.final_answer = "(read)"

        f = self.content_frame

        tk.Label(f, text=step.title, font=FONT_TITLE,
                 bg=BG_MAIN, fg=FG_HEAD, anchor="w"
                 ).pack(fill="x", pady=(0, 8))

        self.hint_lbl = tk.Label(f, text="", bg=BG_BTN_WARM, fg="#5a4300",
                                 font=FONT_LABEL, anchor="w",
                                 justify="left", wraplength=700,
                                 padx=10, pady=6,
                                 highlightthickness=1,
                                 highlightbackground="#e0c060")

        box = tk.LabelFrame(f, text="Answer", font=FONT_LABEL_B,
                            bg=BG_MAIN, fg=FG_LABEL, bd=1, relief="solid",
                            labelanchor="nw", padx=8, pady=8)
        box.pack(fill="x", pady=(4, 0))

        is_multi = step.id in _MULTI_FIELDS
        is_choice = step.answer_type == AnswerType.CHOICE
        is_numeric = step.answer_type == AnswerType.NUMERIC
        already_done = state.completed and state.final_answer

        if is_multi:
            q = step.resolve_question(self.session.state) or "Enter the values below."
            tk.Label(box, text=q, bg=BG_MAIN, fg=FG_LABEL,
                     font=FONT_QUESTION, anchor="w", justify="left",
                     wraplength=700
                     ).pack(fill="x", pady=(0, 4))
            self._render_multi_fields(box, step.id)
        else:
            q = step.resolve_question(self.session.state)
            q_text = q if q else "(No question — click Next to continue.)"
            tk.Label(box, text=q_text, bg=BG_MAIN, fg=FG_LABEL,
                     font=FONT_QUESTION, anchor="w", justify="left",
                     wraplength=700
                     ).pack(fill="x", pady=(0, 6))

            if is_choice:
                choices = list(step.branches.keys()) if step.branches else step.resolve_choices(self.session.state)
                self.answer_var.set(choices[0] if choices else "")
                w = ttk.Combobox(box, textvariable=self.answer_var,
                                 values=choices, state="readonly", width=42)
                w.pack(anchor="w")
                if not already_done:
                    w.bind("<<ComboboxSelected>>", lambda e: self._on_check())
                else:
                    w.configure(state="disabled")
                self.answer_widget = w
            elif is_numeric:
                w = tk.Entry(box, textvariable=self.answer_var, width=50,
                             font=FONT_ENTRY, justify="left")
                w.pack(anchor="w")
                if self._last_answer_wrong and not already_done:
                    w.configure(bg=BG_INPUT_ERR)
                if already_done:
                    w.configure(bg=BG_INPUT_OK, state="disabled",
                                disabledforeground=FG_OK)
                self.answer_widget = w

        if already_done and not is_multi and self.answer_widget is not None:
            self.answer_var.set(state.final_answer or "")

        hint_row = tk.Frame(box, bg=BG_MAIN)
        hint_row.pack(fill="x", pady=(6, 0))
        self.hint_btn = tk.Button(hint_row, text="💡 Hint",
                                  bg=BG_BTN_WARM,
                                  command=self._on_hint)
        self.hint_btn.pack(side="right")
        n_hints = len(step.resolve_hints(self.session.state))
        self.hint_btn.configure(state=("normal" if n_hints > 0 else "disabled"))

        checkable = (is_multi or is_choice or is_numeric) and not already_done
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))
        
        # STRICT RULE: You cannot advance unless the state is completed.
        self.btn_next.configure(state=("normal" if state.completed else "disabled"))
        self.btn_next.configure(
            text=("Finish ✓" if step.is_terminal else "Next ▶"))
        self.btn_back.configure(
            state=("normal" if len(self.session.history) > 1 else "disabled"))

        try:
            self.content_canvas.yview_moveto(0)
        except Exception:
            pass

    def _on_enter(self, event=None):
        if self.session is None:
            return
        if time.time() < self._suppress_enter_until:
            return "break"

        focused = self.focus_get()
        if focused in (getattr(self, "workflow_combo", None),
                       getattr(self, "case_combo", None)):
            return
        if isinstance(focused, (tk.Button, ttk.Button, ttk.Combobox)):
            return

        state = self.session.current_state
        if state.completed:
            self._on_next()
        else:
            self._on_check()
        return "break"

    def _on_check(self):
        if self.session is None:
            return
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
            return

        if self.answer_widget is None:
            return

        answer = self.answer_var.get()
        
        # For non-multi steps, we need to grab the solved values and update state
        solved = _solve(self.session.state)
        
        if step.id == "step2":
            correct_choice = "Singly Reinforced (In-Between)" if solved.get("is_singly") else "Doubly Reinforced (Above rho_max)"
            ok = (answer == correct_choice)
            msg = "" if ok else "Not the correct choice."
        else:
            # Should not happen, but safeguard
            ok = False
            msg = "Error."

        if ok:
            self._last_answer_wrong = False
            self.session.current_state.completed = True
            self.session.current_state.final_answer = answer
            
            # Inject solved values into state
            for k, v in solved.items():
                if k not in self.session.givens:
                    self.session.state[k] = v
            
            self.history.log(f"✓ {step.title} — correct", "green")
            self._set_status(f"✓ {step.title} correct!", FG_OK)
            self._refresh_topbar()
            self._suppress_enter_until = time.time() + 0.25
            self._render_step()
        else:
            self._last_answer_wrong = True
            if isinstance(self.answer_widget, tk.Entry):
                try:
                    self.answer_widget.configure(bg=BG_INPUT_ERR)
                except tk.TclError:
                    pass

            msg_clean = msg
            self.history.log(f"✗ {step.title} — {msg_clean}", "yellow")
            self._set_status(f"✗ {msg_clean}", FG_ERR)

    def _on_reveal(self):
        if self.session is None:
            return
        step = self.session.current_step

        if step.id in _MULTI_FIELDS:
            self._multi_reveal(step.id)
            self._refresh_topbar()
            self._render_step()
            return

        solved = _solve(self.session.state)
        if step.id == "step2":
            correct = "Singly Reinforced (In-Between)" if solved.get("is_singly") else "Doubly Reinforced (Above rho_max)"
            self.answer_var.set(correct)
            st = self.session.states[step.id]
            st.completed = True
            st.final_answer = correct
            
            # Inject solved values into state
            for k, v in solved.items():
                if k not in self.session.givens:
                    self.session.state[k] = v
                    
            self.history.log(f"Revealed {step.title} → {correct}", "yellow")
            self._set_status("Answer revealed.", FG_WARN)
            self._refresh_topbar()
            self._render_step()
            return

    def _on_next(self):
        if self.session is None:
            return
        
        # This is now strictly enforced by the button state, but we add a
        # safeguard in case someone triggers it via code.
        if not self.session.can_advance():
            messagebox.showwarning("Not Checked", "You must click Check (or Reveal) before proceeding to the next step.")
            return
            
        step = self.session.current_step
        branch = None
        if step.branches:
            chosen = self.answer_var.get()
            if chosen in step.branches:
                branch = chosen
            else:
                solved = _solve(self.session.state)
                if solved.get("is_singly") is True:
                    branch = "Singly Reinforced (In-Between)"
                elif solved.get("is_singly") is False:
                    branch = "Doubly Reinforced (Above rho_max)"

        nxt = self.session.advance(branch)
        if nxt is None:
            self._show_summary()
        else:
            self._last_answer_wrong = False
            self._suppress_enter_until = time.time() + 0.25
            self._render_step()

    def _on_back(self):
        if self.session is None:
            return
        if len(self.session.history) <= 1:
            return
        self.session.uncomplete_current()
        self.session.history.pop()
        self.session.current_step_id = self.session.history[-1]
        self._last_answer_wrong = False
        self._render_step()
        self._refresh_topbar()

    def _on_reset(self):
        if self.session is None:
            return
        if not messagebox.askyesno("Reset",
                                   "Clear all progress for this problem?"):
            return
        mode = self.mode_var.get()
        
        # Clear user inputs so the entries are blank
        self.user_inputs.clear()
        
        self.session.new_problem(mode=mode)
        self.history.clear()
        self.history.log("— Reset —", "head")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("Reset. Fresh problem loaded.", FG_WARN)

    def _on_hint(self):
        if self.session is None or self.hint_lbl is None:
            return
        hint = self.session.reveal_next_hint()
        if hint is None:
            self.hint_lbl.configure(text="No more hints available.")
        else:
            self.hint_lbl.configure(text=f"💡 {hint}")
        if not self.hint_lbl.winfo_ismapped():
            self.hint_lbl.pack(fill="x", pady=(6, 0))

    def _toggle_history(self):
        if self._history_visible:
            self.history.pack_forget()
            self._history_visible = False
        else:
            self.history.pack(side="right", fill="y")
            self._history_visible = True
        self._refresh_topbar()

    def _on_copy(self):
        if self.session is None:
            return
        lines = [f"RCD Reviewer — {self.session.workflow.name}", "=" * 50, ""]
        lines.append("GIVENS")
        lines.append("-" * 50)
        for k, v in self.session.givens.items():
            if k in ("mode",):
                lines.append(f"  {k} = {v}")
            elif isinstance(v, bool):
                lines.append(f"  {k} = {'Yes' if v else 'No'}")
            elif isinstance(v, float):
                lines.append(f"  {k} = {v:.6g}")
            else:
                lines.append(f"  {k} = {v}")
        lines.append("")
        lines.append("STEPS")
        lines.append("-" * 50)
        for sid, step in self.session.workflow.steps.items():
            st = self.session.states[sid]
            mark = "✓" if st.completed else "○"
            val = st.final_answer or "(unanswered)"
            lines.append(f"  {mark} {step.title}: {val}")
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self._set_status("Summary copied to clipboard.", FG_OK)

    def _set_status(self, msg, color=FG_HINT):
        try:
            self.status_lbl.configure(text=msg, fg=color)
        except tk.TclError:
            pass

    def _show_summary(self):
        self._clear_content()
        if self.session is None:
            return

        f = self.content_frame

        tk.Label(f, text=f"📋 {self.session.workflow.name} — Summary",
                 font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w"
                 ).pack(fill="x", pady=(0, 8))

        s = _solve(self.session.givens)
        if s.get("is_singly"):
            box = tk.Frame(f, bg=BG_PANEL, highlightthickness=2,
                           highlightbackground=FG_OK)
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="SINGLY REINFORCED — MOMENT CAPACITY",
                     font=FONT_TITLE, bg=BG_PANEL, fg=FG_OK
                     ).pack(padx=16, pady=(12, 6))
            def _row(lbl, val):
                row = tk.Frame(box, bg=BG_PANEL)
                row.pack(anchor="w", padx=16, pady=2)
                tk.Label(row, text=lbl, font=FONT_LABEL, bg=BG_PANEL,
                         width=24, anchor="e").pack(side="left")
                tk.Label(row, text=val, font=("Consolas", 11, "bold"),
                         fg=FG_OK, bg=BG_PANEL).pack(side="left", padx=8)
            _row("Mn:",       f"{s.get('Mn', 0):.3f} kN·m")
            _row("φ:",        f"{s.get('phi', 0):.4f}")
            _row("Mu:",       f"{s.get('Mu', 0):.3f} kN·m")
            tk.Frame(box, bg=BG_PANEL, height=6).pack()
        else:
            box = tk.Frame(f, bg=BG_PANEL, highlightthickness=2,
                           highlightbackground=FG_WARN)
            box.pack(anchor="w", pady=8)
            tk.Label(box, text="DOUBLY REINFORCED — DECOUPLED SOLUTION",
                     font=FONT_TITLE, bg=BG_PANEL, fg=FG_WARN
                     ).pack(padx=16, pady=(12, 6))
            def _row(lbl, val):
                row = tk.Frame(box, bg=BG_PANEL)
                row.pack(anchor="w", padx=16, pady=2)
                tk.Label(row, text=lbl, font=FONT_LABEL, bg=BG_PANEL,
                         width=24, anchor="e").pack(side="left")
                tk.Label(row, text=val, font=("Consolas", 11, "bold"),
                         fg=FG_WARN, bg=BG_PANEL).pack(side="left", padx=8)
            _row("As1:",           f"{s.get('As1', 0):.0f} mm²")
            _row("As2:",           f"{s.get('As2', 0):.0f} mm²")
            _row("a (decoupled):", f"{s.get('a_drb', 0):.2f} mm")
            _row("c (decoupled):", f"{s.get('c_drb', 0):.2f} mm")
            _row("Mn1:",           f"{s.get('Mn1', 0):.2f} kN·m")
            _row("Mn2:",           f"{s.get('Mn2', 0):.2f} kN·m")
            _row("φ:",             f"{s.get('phi', 0):.4f}")
            _row("Mu:",            f"{s.get('Mu_drb', 0):.3f} kN·m")
            tk.Frame(box, bg=BG_PANEL, height=6).pack()

        recap_lines = [
            "GIVEN",
            f"  b = {self.session.givens['b']:.0f} mm   d = {self.session.givens['d']:.0f} mm   d' = {self.session.givens['d_prime']:.0f} mm",
            f"  As = {self.session.givens['As']:.0f} mm²   f'c = {self.session.givens['fc']:.0f} MPa   fy = {self.session.givens['fy']:.0f} MPa",
            "",
            "STEP 1 — YIELDING",
            f"  a = {s.get('a_fict', 0):.2f} mm   β1 = {s.get('beta1', 0):.4f}",
            f"  c = {s.get('c', 0):.2f} mm   fs = {s.get('fs', 0):.2f} MPa",
            f"  yielded? {'Yes' if s.get('did_yield') else 'No'}",
        ]
        if not s.get("did_yield"):
            recap_lines.append(f"  c_recalc = {s.get('c_recalc', 0):.2f} mm")
        recap_lines += [
            "",
            "STEP 2 — SRB / DRB",
            f"  ρmin = {s.get('rho_min', 0):.5f}",
            f"  ρact = {s.get('rho_act', 0):.5f}",
            f"  ρmax = {s.get('rho_max', 0):.5f}",
            f"  classification = {'Singly Reinforced' if s.get('is_singly') else 'Doubly Reinforced'}",
        ]

        recap = tk.Text(f, width=72, height=min(24, len(recap_lines) + 2),
                        font=("Consolas", 9), bg=BG_PANEL)
        recap.pack(anchor="w", fill="x")
        for ln in recap_lines:
            recap.insert("end", ln + "\n")
        recap.configure(state="disabled")

        self._set_status("Problem complete! 🎉", FG_OK)
        self.btn_next.configure(state="disabled")
        self.btn_check.configure(state="disabled")
        self.btn_reveal.configure(state="disabled")
        self.btn_back.configure(
            state=("normal" if len(self.session.history) > 1 else "disabled"))
        self._last_answer_wrong = False

    def _on_wheel(self, event):
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            w = None
        node = w
        inside = False
        while node is not None:
            if node is self.content_canvas:
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
            delta = int(-d / 120) if abs(d) >= 120 else (-1 if d > 0 else 1)
        self.content_canvas.yview_scroll(delta, "units")


def main():
    app = SRBDRBReviewer()
    app.mainloop()


if __name__ == "__main__":
    main()