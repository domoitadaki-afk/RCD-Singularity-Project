"""
rcd_interactive_reviewer.py — RCD Interactive Reviewer (single-file build).

Merged from:
    engine/{__init__,models,session,validator}.py
    ui/{__init__,app,history,renderer,theme}.py
    workflows/{__init__,pure_axial,tied_column,spiral_column,eccentric_column}.py
    main.py

External deps actually used: sympy (optional — only for FORMULA answers).

Run with:  python rcd_interactive_reviewer.py
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
# SECTION 1 — THEME                       (was ui/theme.py)
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

FONT_TITLE    = ("Segoe UI", 12, "bold")
FONT_SECTION  = ("Segoe UI", 10, "bold")
FONT_LABEL    = ("Segoe UI", 9)
FONT_LABEL_B  = ("Segoe UI", 9, "bold")
FONT_ENTRY    = ("Consolas", 10)
FONT_VALUE    = ("Consolas", 10)
FONT_HIST     = ("Consolas", 9)
FONT_CONTENT  = ("Consolas", 10)
FONT_QUESTION = ("Segoe UI", 10, "bold")


# ====================================================================
# SECTION 2 — ENGINE / MODELS             (was engine/models.py)
# ====================================================================
class AnswerType(str, Enum):
    NONE = "none"
    TEXT = "text"
    NUMERIC = "numeric"
    FORMULA = "formula"
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
    display_divisor: float = 1.0

    next_step: Optional[str] = None
    branches: dict[str, str] = field(default_factory=dict)
    is_terminal: bool = False

    def resolve_content(self, state: dict) -> str:
        return self.content(state) if callable(self.content) else self.content

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
    # NEW: declare that the generator accepts a `target_case=` kwarg.
    # Avoids string-matching workflow.id in _current_case_kwargs().
    generator_supports_cases: bool = False


@dataclass
class Attempt:
    step_id: str
    answer: str
    correct: bool
    timestamp: float


# ====================================================================
# SECTION 3 — ENGINE / VALIDATOR          (was engine/validator.py)
# ====================================================================
def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("$$", "").replace("$", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = re.sub(r"[\{\}\\]", "", s)
    s = re.sub(r"\s+", "", s)
    return s


def _sanitize_for_sympy(s: str) -> str:
    s = s.replace("$$", "").replace("$", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = s.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", s)
    s = s.replace("f'c", "fc").replace("f’c", "fc")
    s = s.replace("f'_c", "fc").replace("f’_c", "fc")
    s = s.replace("f'_{c}", "fc")
    s = s.replace("d'", "dp").replace("d’", "dp")
    s = s.replace("\\", "")
    return s


# FIX (#6): _try_number now returns (value, unit) so callers can detect
# a wrong-unit answer. `unit` is the trailing unit token if found, else None.
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
        s2 = (s.replace("×10^", "e")
                .replace("x10^", "e")
                .replace("*10^", "e")
                .replace("·10^", "e"))
        try:
            return float(s2), unit
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

    # ----- CHOICE -----
    if step.answer_type == AnswerType.CHOICE:
        if expected_value is not None and isinstance(expected_value, str):
            if user == expected_value:
                return True, ""
            return False, "Not the correct case for these givens."
        if step.branches:
            if user in step.branches:
                return True, ""
            return False, f"Choose one of: {', '.join(step.branches.keys())}"
        choices = step.resolve_choices(state or {})
        return False, f"Choose one of: {', '.join(choices)}"

    # ----- NUMERIC -----
    if step.answer_type == AnswerType.NUMERIC:
        if expected_value is None:
            return False, "Internal error: no expected value."
        e = float(expected_value)
        u, unit = _try_number(user)
        if u is None:
            return False, "That doesn't look like a number. Try again."

        # FIX (#6): detect a wrong-unit answer instead of pretending it's
        # just a wrong magnitude. Only fire when a unit was actually typed
        # AND the step declared a display unit.
        if unit is not None and step.display_unit:
            expected_unit = step.display_unit.strip().lower()
            if unit != expected_unit:
                return False, (
                    f"That value looks like it's in {unit}, but the answer "
                    f"is expected in {step.display_unit}."
                )

        tol = abs(step.tolerance)
        # FIX (#8): relative tolerance is brittle when the expected value is
        # tiny. Use an absolute floor that scales with the magnitude, so
        # near-zero expected values are still checkable.
        if e == 0:
            return (True, "") if abs(u) <= tol else (False, "Not quite.")
        rel_err = abs(u - e) / abs(e)
        abs_floor = max(abs(e) * tol, 1e-9)
        if rel_err <= tol or abs(u - e) <= abs_floor:
            return True, ""
        return False, "Not quite. Double-check your calculation."

    # ----- FORMULA -----
    # FIX (#7): sympy is no longer silently swallowed. Missing sympy is a
    # *configuration* error, not a wrong answer. And if sympy is present but
    # the student's expression fails to parse, we say so.
    if step.answer_type == AnswerType.FORMULA:
        if expected_value is None:
            return False, "Internal error: no expected formula."
        try:
            import sympy as sp
            from sympy.parsing.sympy_parser import (
                parse_expr, standard_transformations,
                implicit_multiplication_application,
            )
        except ImportError:
            return False, (
                "Formula checking requires sympy. "
                "Install it with: pip install sympy"
            )
        transforms = standard_transformations + (implicit_multiplication_application,)
        try:
            exp_expr = parse_expr(_sanitize_for_sympy(str(expected_value)),
                                  transformations=transforms)
        except Exception:
            return False, "Internal error: expected formula failed to parse."
        try:
            usr_expr = parse_expr(_sanitize_for_sympy(user),
                                  transformations=transforms)
        except Exception:
            return False, "Couldn't parse that expression. Check your syntax."
        try:
            if sp.simplify(exp_expr - usr_expr) == 0:
                return True, ""
            return False, "The expressions aren't equivalent. Check your work."
        except Exception:
            return False, "Not quite. Try again."

    # ----- TEXT -----
    if _normalize_text(str(expected_value)) == _normalize_text(user):
        return True, ""
    return False, "Not quite. Try again."


# ====================================================================
# SECTION 4 — ENGINE / SESSION            (was engine/session.py)
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
        # FIX (#12): avoid growing history on a cycle (A→B→A→B). We only
        # append if the step isn't already the last *or* the second-to-last
        # entry (the latter catches the simplest back-and-forth cycle).
        if (not self.history
                or self.history[-1] != nxt
                and (len(self.history) < 2 or self.history[-2] != nxt)):
            self.history.append(nxt)
        return nxt

    def uncomplete_current(self) -> None:
        """FIX (#1): used by Back. Clear completed/final_answer and remove the
        solved var from `state` so downstream solvers don't see a stale value."""
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
# SECTION 5 — UI / RENDERER               (was ui/renderer.py)
# ====================================================================
_GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\iota": "ι", r"\kappa": "κ", r"\lambda": "λ",
    r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ",
    r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Phi": "Φ",
    r"\Psi": "Ψ", r"\Omega": "Ω",
}

_SYMBOLS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷",
    r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
    r"\ne": "≠", r"\neq": "≠", r"\approx": "≈",
    r"\pm": "±", r"\mp": "∓", r"\infty": "∞",
    r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\therefore": "∴", r"\because": "∵",
}

_SUBSCRIPTS = str.maketrans(
    "0123456789+-=()aeoxhklmnpst",
    "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ",
)
_SUPERSCRIPTS = str.maketrans(
    "0123456789+-=()n",
    "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ",
)


def _degrade_subscripts(s: str) -> str:
    def repl_braced(m):
        base, sub = m.group(1), m.group(2)
        uni = sub.translate(_SUBSCRIPTS)
        if uni != sub:
            return base + uni
        return f"{base}_{sub}"
    s = re.sub(r"([A-Za-z])_\{([^{}]+)\}", repl_braced, s)
    s = re.sub(r"([A-Za-z])_([0-9])",
               lambda m: m.group(1) + m.group(2).translate(_SUBSCRIPTS), s)
    return s


def _degrade_superscripts(s: str) -> str:
    def repl(m):
        base, sup = m.group(1), m.group(2)
        uni = sup.translate(_SUPERSCRIPTS)
        if uni != sup:
            return base + uni
        return f"{base}^{sup}"
    s = re.sub(r"([A-Za-z0-9])\^\{([^{}]+)\}", repl, s)
    s = re.sub(r"([A-Za-z0-9])\^([0-9n])",
               lambda m: m.group(1) + m.group(2).translate(_SUPERSCRIPTS), s)
    return s


def _convert_frac(s: str) -> str:
    pat = re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}")
    while pat.search(s):
        s = pat.sub(lambda m: f"({m.group(1)})/({m.group(2)})", s)
    return s


def _convert_sqrt(s: str) -> str:
    pat = re.compile(r"\\sqrt\{([^{}]*)\}")
    while pat.search(s):
        s = pat.sub(lambda m: f"√({m.group(1)})", s)
    return s


def _clean_latex(expr: str) -> str:
    expr = re.sub(r"\\text\{([^{}]*)\}", r"\1", expr)
    expr = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", expr)
    expr = re.sub(r"\\mathbf\{([^{}]*)\}", r"\1", expr)
    expr = expr.replace(r"\left", "").replace(r"\right", "")
    for cmd in (r"\,", r"\;", r"\:", r"\quad", r"\qquad"):
        expr = expr.replace(cmd, " ")
    expr = expr.replace(r"\!", "")
    expr = _convert_frac(expr)
    expr = _convert_sqrt(expr)
    for k, v in _GREEK.items():
        expr = expr.replace(k, v)
    for k, v in _SYMBOLS.items():
        expr = expr.replace(k, v)
    for fn in ("min", "max", "sin", "cos", "tan", "log", "ln", "exp", "sqrt"):
        expr = re.sub(r"\\" + fn + r"\b", fn, expr)
    expr = _degrade_subscripts(expr)
    expr = _degrade_superscripts(expr)
    expr = re.sub(r"\\([A-Za-z]+)", r"\1", expr)
    expr = re.sub(r"\{([^{}]*)\}", r"\1", expr)
    expr = re.sub(r"[ \t]+", " ", expr).strip()
    return expr


def latex_to_unicode(text: str) -> str:
    """Convert simple markdown+LaTeX to plain text with Unicode math."""
    def repl_display(m):
        return "  " + _clean_latex(m.group(1)) + "  "
    text = re.sub(r"\$\$(.+?)\$\$", repl_display, text, flags=re.DOTALL)
    text = re.sub(r"\$(.+?)\$",
                  lambda m: _clean_latex(m.group(1)), text, flags=re.DOTALL)
    return text


def parse_content(text: str) -> list[tuple[str, str]]:
    """Return list of (tag, content) tuples for Tkinter Text widget."""
    text = latex_to_unicode(text)
    result: list[tuple[str, str]] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.startswith("### "):
            result.append(("h3", line[4:]))
        elif line.startswith("## "):
            result.append(("h2", line[3:]))
        elif line.startswith("# "):
            result.append(("h1", line[2:]))
        elif line.startswith("- "):
            result.append(("bullet", "• " + line[2:]))
        elif line.strip() == "---":
            result.append(("sep", "─" * 40))
        elif line.strip() == "":
            result.append(("blank", ""))
        else:
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            result.append(("normal", line))
    return result


# ====================================================================
# SECTION 6 — UI / HISTORY PANEL          (was ui/history.py)
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
# SECTION 7 — WORKFLOWS                   (were workflows/*.py)
# Each workflow file is wrapped in a builder function so its private
# helpers (_gen, _start_text, _ag_solver, ...) stay scoped and don't
# collide with same-named helpers in the other workflows.
# ====================================================================

# ---- 7a. Pure Axial (was workflows/pure_axial.py) ----
def _build_pure_axial_workflow():
    PI = math.pi

    BAR_ARRANGEMENTS = [(4, 16), (4, 20), (6, 20), (6, 25),
                        (8, 20), (8, 25), (10, 20), (12, 20)]
    SIZES = [300, 350, 400, 450, 500]
    FPC = [21, 24, 28, 30, 35]
    FY = [275, 345, 415, 420]

    def _gen():
        b = random.choice(SIZES)
        n, dia = random.choice(BAR_ARRANGEMENTS)
        Ast = n * PI / 4 * dia ** 2
        fc = random.choice(FPC)
        fy = random.choice(FY)
        return {"b": b, "h": b, "n": n, "dia": dia, "Ast": Ast, "fc": fc, "fy": fy}

    def _start_text(s):
        return (
            "### GIVENS\n\n"
            f"- $b = {s['b']}\\text{{ mm}}$\n"
            f"- $h = {s['h']}\\text{{ mm}}$\n"
            f"- Bars: ${s['n']} \\times {s['dia']}\\text{{ mm}}\\phi$\n"
            f"- $A_{{st}} = {s['Ast']:.2f}\\text{{ mm}}^2$\n"
            f"- $f'_c = {s['fc']}\\text{{ MPa}}$\n"
            f"- $f_y = {s['fy']}\\text{{ MPa}}$"
        )

    return Workflow(
        id="pure_axial",
        name="Pure Axial Analysis",
        description="Compute nominal pure axial strength and design axial load.",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(
                id="start",
                title="START",
                content=_start_text,
                next_step="ag",
            ),
            "ag": Step(
                id="ag",
                title="Gross Area",
                content=r"### GROSS AREA OF CONCRETE" "\n\n" r"$$A_g = b \cdot h$$",
                question=r"Compute $A_g$ in mm².",
                solver=lambda s: s["b"] * s["h"],
                var_name="Ag",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm²", display_divisor=1,
                hints=["It's just base times height.", "Ag = b × h"],
                next_step="p0",
            ),
            "p0": Step(
                id="p0",
                title="Nominal Pure Axial Strength",
                content=(
                    r"### THE NOMINAL LOAD"
                    "\n\n"
                    r"$$P_0 = 0.85 f'_c (A_g - A_{st}) + f_y A_{st}$$"
                ),
                question=r"Compute $P_0$ in kN.",
                solver=lambda s: (0.85 * s["fc"] * (s["Ag"] - s["Ast"])
                                  + s["fy"] * s["Ast"]) / 1000,
                var_name="P0_kN",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="kN", display_divisor=1,
                hints=[
                    "Two terms: concrete on net area, plus steel.",
                    "0.85 × f'c × (Ag − Ast) + fy × Ast",
                    "Divide the result by 1000 to get kN.",
                ],
                next_step="column_type",
            ),
            "column_type": Step(
                id="column_type",
                title="Column Type?",
                content=r"**Column type?**",
                question="Pick tied or spiral — the φ and cap differ.",
                answer_type=AnswerType.CHOICE,
                branches={"Tied": "tied_end", "Spiral": "spiral_end"},
                hints=[
                    "Tied: φ = 0.65, cap = 0.80",
                    "Spiral: φ = 0.75, cap = 0.85",
                ],
            ),
            "tied_end": Step(
                id="tied_end",
                title="Design Load — Tied",
                content=(
                    r"**Tied Column** ($\phi = 0.65$)"
                    "\n\n"
                    r"$$P_u = 0.80 \, \phi \, P_0$$"
                ),
                question=r"Compute $P_u$ in kN.",
                solver=lambda s: 0.80 * 0.65 * s["P0_kN"],
                var_name="Pu_kN",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="kN", display_divisor=1,
                hints=["Pu = 0.80 × 0.65 × P0."],
                is_terminal=True,
            ),
            "spiral_end": Step(
                id="spiral_end",
                title="Design Load — Spiral",
                content=(
                    r"**Spiral Column** ($\phi = 0.75$)"
                    "\n\n"
                    r"$$P_u = 0.85 \, \phi \, P_0$$"
                ),
                question=r"Compute $P_u$ in kN.",
                solver=lambda s: 0.85 * 0.75 * s["P0_kN"],
                var_name="Pu_kN",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="kN", display_divisor=1,
                hints=["Pu = 0.85 × 0.75 × P0."],
                is_terminal=True,
            ),
        },
    )


# ---- 7b. Tied Column (was workflows/tied_column.py) ----
def _build_tied_column_workflow():
    PI = math.pi
    FPC = [21, 24, 28, 30, 35]
    FY = [275, 345, 415, 420]

    def _gen():
        DL = random.randrange(300, 951, 50)
        LL = random.randrange(400, 1401, 50)
        fc = random.choice(FPC)
        fy = random.choice(FY)
        return {"DL": DL, "LL": LL, "fc": fc, "fy": fy}

    def _start_text(s):
        return (
            "### GIVENS\n\n"
            f"- Dead Load: $DL = {s['DL']}\\text{{ kN}}$\n"
            f"- Live Load: $LL = {s['LL']}\\text{{ kN}}$\n"
            f"- $f'_c = {s['fc']}\\text{{ MPa}}$\n"
            f"- $f_y = {s['fy']}\\text{{ MPa}}$\n"
            f"- Square tied column, assume $\\rho_g = 0.02$"
        )

    def _ag_solver(s):
        pu = s["Pu"]
        fc = s["fc"]
        fy = s["fy"]
        rho = 0.02
        return pu / (0.65 * 0.80 * (0.85 * fc * (1 - rho) + rho * fy))

    def _b_solver(s):
        return math.sqrt(s["Ag"])

    def _b_final_solver(s):
        return math.ceil(s["b"] / 10) * 10

    def _ag_final_solver(s):
        return s["b_final"] ** 2

    def _ast_solver(s):
        pu = s["Pu"]
        fc = s["fc"]
        fy = s["fy"]
        ag = s["Ag_final"]
        k = pu / (0.65 * 0.80)
        return (k - 0.85 * fc * ag) / (fy - 0.85 * fc)

    def _rho_actual(s):
        return s["Ast"] / s["Ag_final"]

    def _nb_solver(s):
        Ab = PI / 4 * 25 ** 2
        raw = s["Ast"] / Ab
        n = math.ceil(raw)
        if n % 2 == 1:
            n += 1
        return n

    def _tie_spacing(s):
        return min(16 * 25, 48 * 10, s["b_final"])

    return Workflow(
        id="tied_column",
        name="Tied Column Design",
        description="Design a square tied column for a factored axial load.",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(
                id="start",
                title="START",
                content=_start_text,
                next_step="pu",
            ),
            "pu": Step(
                id="pu",
                title="Factored Load",
                content=r"### LOAD COMBINATION" "\n\n" r"$$P_u = 1.2\,DL + 1.6\,LL$$",
                question=r"Compute $P_u$ in kN.",
                solver=lambda s: 1.2 * s["DL"] + 1.6 * s["LL"],
                var_name="Pu_kN",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="kN", display_divisor=1,
                hints=["1.2 × DL + 1.6 × LL", "Units: kN"],
                next_step="pu_n",
            ),
            "pu_n": Step(
                id="pu_n",
                title="Convert to N",
                content=r"Convert $P_u$ to N (multiply by 1000).",
                question=r"$P_u$ in N.",
                solver=lambda s: s["Pu_kN"] * 1000,
                var_name="Pu",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="N", display_divisor=1,
                hints=["Multiply by 1000.", "kN × 1000 = N"],
                next_step="ag",
            ),
            "ag": Step(
                id="ag",
                title="Required Ag",
                content=(
                    r"### SOLVE FOR Ag" "\n\n"
                    r"$$P_u = 0.65(0.80)\left[0.85 f'_c (A_g - A_{st}) + A_{st} f_y\right]$$"
                    "\n\n"
                    r"with $A_{st} = 0.02 A_g$"
                ),
                question=r"Solve for required $A_g$ in mm².",
                solver=_ag_solver,
                var_name="Ag",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm²", display_divisor=1,
                hints=[
                    "Substitute Ast = 0.02 Ag, then isolate Ag.",
                    "Ag = Pu / [0.52 × (0.85·f'c·0.98 + 0.02·fy)]  (Pu in N)",
                ],
                next_step="b",
            ),
            "b": Step(
                id="b",
                title="Column Dimension",
                content=r"$$b = \sqrt{A_g}$$",
                question=r"Compute $b$ in mm (before rounding).",
                solver=_b_solver,
                var_name="b",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm", display_divisor=1,
                hints=["Take the square root of Ag."],
                next_step="b_final",
            ),
            "b_final": Step(
                id="b_final",
                title="Round Up",
                content=r"Round up to the nearest $10\text{ mm}$.",
                question=r"Rounded $b$ in mm.",
                solver=_b_final_solver,
                var_name="b_final",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm", display_divisor=1,
                hints=["Ceil to the next multiple of 10."],
                next_step="ag_final",
            ),
            "ag_final": Step(
                id="ag_final",
                title="Actual Ag",
                content=r"$$A_g = b_{\text{final}}^2$$",
                question=r"Actual $A_g$ in mm².",
                solver=_ag_final_solver,
                var_name="Ag_final",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm²", display_divisor=1,
                hints=["Square the rounded b."],
                next_step="ast",
            ),
            "ast": Step(
                id="ast",
                title="Required Ast",
                content=(
                    r"### RECOMPUTE Ast" "\n\n"
                    r"$$P_u = 0.65(0.80)\left[0.85 f'_c (A_g - A_{st}) + A_{st} f_y\right]$$"
                ),
                question=r"Solve for $A_{st}$ in mm².",
                solver=_ast_solver,
                var_name="Ast",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm²", display_divisor=1,
                hints=[
                    "Isolate Ast from the equilibrium.",
                    "Ast = (Pu / 0.52 − 0.85·f'c·Ag) / (fy − 0.85·f'c)",
                ],
                next_step="rho_check",
            ),
            "rho_check": Step(
                id="rho_check",
                title="Check ρg",
                content=r"$$0.01 \le \rho_g \le 0.08$$",
                question=r"Compute actual $\rho_g$.",
                solver=_rho_actual,
                var_name="rho",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.03,
                display_unit="", display_divisor=1,
                hints=["ρg = Ast / Ag_final", "Should fall between 0.01 and 0.08."],
                next_step="nb",
            ),
            "nb": Step(
                id="nb",
                title="Number of Bars",
                content=(
                    r"### NUMBER OF BARS" "\n\n"
                    r"$$n_b = \frac{A_{st}}{A_b}$$"
                    "\n\n"
                    r"Round up to the next **even** count (symmetric layout)."
                ),
                question=r"How many $25\text{ mm}\phi$ bars?",
                solver=_nb_solver,
                var_name="nb",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="", display_divisor=1,
                hints=[
                    "One 25 mm bar has area = π/4 × 25² ≈ 490.87 mm².",
                    "nb = ceil(Ast / 490.87), then round up to even.",
                ],
                next_step="tie",
            ),
            "tie": Step(
                id="tie",
                title="Tie Spacing",
                content=(
                    r"### TIE SPACING" "\n\n"
                    r"$$s = \min\left(16 d_b,\ 48 d_{\text{tie}},\ \text{least dim}\right)$$"
                    "\n\n"
                    r"Use $10\text{ mm}\phi$ ties."
                ),
                question=r"Compute tie spacing $s$ in mm.",
                solver=_tie_spacing,
                var_name="s",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm", display_divisor=1,
                hints=[
                    "16 × 25 = 400 mm.",
                    "48 × 10 = 480 mm.",
                    "Least dimension = b_final.",
                    "Take the smallest of the three.",
                ],
                is_terminal=True,
            ),
        },
    )


# ---- 7c. Spiral Column (was workflows/spiral_column.py) ----
def _build_spiral_column_workflow():
    PI = math.pi
    FPC = [21, 24, 28, 30, 35]
    FY = [275, 345, 415, 420]

    def _gen():
        DL = random.randrange(600, 1501, 100)
        LL = random.randrange(800, 2001, 100)
        fc = random.choice(FPC)
        fy = random.choice(FY)
        return {"DL": DL, "LL": LL, "fc": fc, "fy": fy, "cc": 40}

    def _start_text(s):
        return (
            "### GIVENS\n\n"
            f"- Dead Load: $DL = {s['DL']}\\text{{ kN}}$\n"
            f"- Live Load: $LL = {s['LL']}\\text{{ kN}}$\n"
            f"- $f'_c = {s['fc']}\\text{{ MPa}}$\n"
            f"- $f_y = {s['fy']}\\text{{ MPa}}$\n"
            f"- Clear cover: $cc = {s['cc']}\\text{{ mm}}$\n"
            f"- Spiral bar diameter: $d_b = 10\\text{{ mm}}$"
        )

    def _ag_solver(s):
        pu = s["Pu"]
        fc = s["fc"]
        fy = s["fy"]
        rho = 0.02
        return pu / (0.75 * 0.85 * (0.85 * fc * (1 - rho) + rho * fy))

    def _d_solver(s):
        return math.sqrt(4 * s["Ag"] / PI)

    def _d_final_solver(s):
        return math.ceil(s["D"] / 10) * 10

    def _ag_final_solver(s):
        return PI / 4 * s["D_final"] ** 2

    def _ast_solver(s):
        pu = s["Pu"]
        fc = s["fc"]
        fy = s["fy"]
        ag = s["Ag_final"]
        k = pu / (0.75 * 0.85)
        return (k - 0.85 * fc * ag) / (fy - 0.85 * fc)

    def _rho_actual(s):
        return s["Ast"] / s["Ag_final"]

    def _nb_solver(s):
        Ab = PI / 4 * 25 ** 2
        return max(6, math.ceil(s["Ast"] / Ab))

    def _dc_solver(s):
        return s["D_final"] - 2 * s["cc"]

    def _rho_s_min(s):
        ag = s["Ag_final"]
        ach = PI / 4 * s["Dc"] ** 2
        return 0.45 * (ag / ach - 1) * s["fc"] / s["fy"]

    def _s_solver(s):
        as_bar = PI / 4 * 10 ** 2
        dc = s["Dc"]
        rho_s = s["rho_s_min"]
        S = 4 * as_bar * (dc - 10) / (rho_s * dc ** 2)
        return math.floor(S / 10) * 10

    return Workflow(
        id="spiral_column",
        name="Spiral Column Design",
        description="Design a round spiral column for a factored axial load.",
        generator=_gen,
        start_step="start",
        steps={
            "start": Step(
                id="start",
                title="START",
                content=_start_text,
                next_step="pu",
            ),
            "pu": Step(
                id="pu",
                title="Factored Load",
                content=r"$$P_u = 1.2\,DL + 1.6\,LL$$",
                question=r"Compute $P_u$ in kN.",
                solver=lambda s: 1.2 * s["DL"] + 1.6 * s["LL"],
                var_name="Pu_kN",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="kN", display_divisor=1,
                hints=["1.2 × DL + 1.6 × LL"],
                next_step="pu_n",
            ),
            "pu_n": Step(
                id="pu_n",
                title="Convert to N",
                content=r"Convert $P_u$ to N.",
                question=r"$P_u$ in N.",
                solver=lambda s: s["Pu_kN"] * 1000,
                var_name="Pu",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="N", display_divisor=1,
                hints=["× 1000"],
                next_step="ag",
            ),
            "ag": Step(
                id="ag",
                title="Required Ag",
                content=(
                    r"$$P_u = 0.75(0.85)\left[0.85 f'_c (A_g - A_{st}) + A_{st} f_y\right]$$"
                    "\n\n"
                    r"with $A_{st} = 0.02 A_g$"
                ),
                question=r"Solve for required $A_g$ in mm².",
                solver=_ag_solver,
                var_name="Ag",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm²", display_divisor=1,
                hints=[
                    "Ag = Pu / [0.6375 × (0.85·f'c·0.98 + 0.02·fy)]  (Pu in N)",
                ],
                next_step="d",
            ),
            "d": Step(
                id="d",
                title="Diameter",
                content=r"$$D = \sqrt{\frac{4 A_g}{\pi}}$$",
                question=r"Compute $D$ in mm (before rounding).",
                solver=_d_solver,
                var_name="D",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm", display_divisor=1,
                hints=["Take the square root of 4·Ag/π."],
                next_step="d_final",
            ),
            "d_final": Step(
                id="d_final",
                title="Round Up",
                content=r"Round up to the nearest $10\text{ mm}$.",
                question=r"Rounded $D$ in mm.",
                solver=_d_final_solver,
                var_name="D_final",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm", display_divisor=1,
                hints=["Ceil to next multiple of 10."],
                next_step="ag_final",
            ),
            "ag_final": Step(
                id="ag_final",
                title="Actual Ag",
                content=r"$$A_g = \frac{\pi}{4} D_{\text{final}}^2$$",
                question=r"Actual $A_g$ in mm².",
                solver=_ag_final_solver,
                var_name="Ag_final",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm²", display_divisor=1,
                hints=["π/4 × D²"],
                next_step="ast",
            ),
            "ast": Step(
                id="ast",
                title="Required Ast",
                content=r"Recompute $A_{st}$ with the actual $A_g$.",
                question=r"Solve for $A_{st}$ in mm².",
                solver=_ast_solver,
                var_name="Ast",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm²", display_divisor=1,
                hints=["Ast = (Pu / 0.6375 − 0.85·f'c·Ag) / (fy − 0.85·f'c)"],
                next_step="rho_check",
            ),
            "rho_check": Step(
                id="rho_check",
                title="Check ρg",
                content=r"$$0.01 \le \rho_g \le 0.08$$",
                question=r"Compute actual $\rho_g$.",
                solver=_rho_actual,
                var_name="rho",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.03,
                display_unit="", display_divisor=1,
                hints=["ρg = Ast / Ag_final"],
                next_step="nb",
            ),
            "nb": Step(
                id="nb",
                title="Number of Bars",
                content=r"Round up, minimum 6 bars of $25\text{ mm}\phi$.",
                question=r"How many bars?",
                solver=_nb_solver,
                var_name="nb",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="", display_divisor=1,
                hints=["Ast / 490.87, round up, min 6."],
                next_step="dc",
            ),
            "dc": Step(
                id="dc",
                title="Core Diameter",
                content=r"$$D_c = D - 2(cc)$$",
                question=r"Compute $D_c$ in mm.",
                solver=_dc_solver,
                var_name="Dc",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.001,
                display_unit="mm", display_divisor=1,
                hints=["Subtract twice the clear cover."],
                next_step="rho_s",
            ),
            "rho_s": Step(
                id="rho_s",
                title="Min Spiral Ratio",
                content=(
                    r"$$\rho_{s,\min} = 0.45\left(\frac{A_g}{A_{ch}} - 1\right)\frac{f'_c}{f_{yt}}$$"
                    "\n\n"
                    r"with $f_{yt} = f_y$"
                ),
                question=r"Compute $\rho_{s,\min}$.",
                solver=_rho_s_min,
                var_name="rho_s_min",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.03,
                display_unit="", display_divisor=1,
                hints=["Ach = π/4 × Dc²."],
                next_step="spacing",
            ),
            "spacing": Step(
                id="spacing",
                title="Spiral Spacing",
                content=(
                    r"$$S = \frac{4 a_s (D_c - d_b)}{\rho_s D_c^2}$$"
                    "\n\n"
                    r"Then round **down** to the nearest $10\text{ mm}$."
                ),
                question=r"Compute $S$ in mm (rounded down).",
                solver=_s_solver,
                var_name="S",
                answer_type=AnswerType.NUMERIC,
                tolerance=0.02,
                display_unit="mm", display_divisor=1,
                hints=["as = π/4 × 10² = 78.54 mm²."],
                is_terminal=True,
            ),
        },
    )


# ---- 7d. Eccentric Column (was workflows/eccentric_column.py) ----
def _build_eccentric_column_workflow():
    PI = math.pi
    FPC = [21, 24, 27, 28, 30]
    FY = [275, 345, 415, 420]
    B_OPTS = [300, 350, 400]
    H_OPTS = [400, 450, 500, 550, 600]
    BAR_ARRANGEMENTS = [(6, 20), (6, 25), (8, 20), (8, 25)]

    def _beta1(fc):
        if fc <= 28:
            return 0.85
        return max(0.65, 0.85 - 0.05 * (fc - 28) / 7)

    def _compute_ebal(b, h, d, dp, As, Asp, fc, fy):
        b1 = _beta1(fc)
        cbal = 600 * d / (600 + fy)
        abal = b1 * cbal
        fsp = min(600 * (cbal - dp) / cbal, fy)
        Cc = 0.85 * fc * abal * b
        Cs = Asp * (fsp - 0.85 * fc)
        Ts = As * fy
        Pb = Cc + Cs - Ts
        if Pb <= 0:
            return None
        Mnb = (
            Cc * (h / 2 - abal / 2)
            + Cs * (h / 2 - dp)
            + Ts * (d - h / 2)
        )
        return Mnb / Pb

    def _gen(target_case=None):
        for _ in range(60):
            b = random.choice(B_OPTS)
            h = random.choice(H_OPTS)
            n, dia = random.choice(BAR_ARRANGEMENTS)
            Ast = n * PI / 4 * dia ** 2
            As = Asp = Ast / 2
            fc = random.choice(FPC)
            fy = random.choice(FY)
            d = h - 60
            dp = 60

            ebal = _compute_ebal(b, h, d, dp, As, Asp, fc, fy)
            if ebal is None or not (80 <= ebal <= 1200):
                continue

            if target_case is None:
                e = random.randrange(100, 351, 10)
            elif target_case == "Case 1":
                e = max(50, round(ebal))
            elif target_case == "Case 2":
                e = max(50, round(ebal * random.uniform(0.45, 0.88)))
            elif target_case == "Case 3":
                e = round(ebal * random.uniform(1.15, 2.0))
            else:
                e = random.randrange(100, 351, 10)

            return {
                "b": b, "h": h, "d": d, "dp": dp, "n": n, "dia": dia,
                "Ast": Ast, "As": As, "Asp": Asp, "fc": fc, "fy": fy, "e": e,
            }

        return {
            "b": 350, "h": 500, "d": 440, "dp": 60, "n": 6, "dia": 20,
            "Ast": 6 * PI / 4 * 400, "As": 3 * PI / 4 * 400,
            "Asp": 3 * PI / 4 * 400, "fc": 28, "fy": 415, "e": 150,
        }

    def _start_text(s):
        return (
            "### GIVENS\n\n"
            f"- $b = {s['b']}\\text{{ mm}}$\n"
            f"- $h = {s['h']}\\text{{ mm}}$\n"
            f"- $d = {s['d']}\\text{{ mm}}$\n"
            f"- $d' = {s['dp']}\\text{{ mm}}$\n"
            f"- Bars: ${s['n']} \\times {s['dia']}\\text{{ mm}}\\phi$, symmetric\n"
            f"- $A_s = A'_s = {s['As']:.2f}\\text{{ mm}}^2$\n"
            f"- $f'_c = {s['fc']}\\text{{ MPa}}$\n"
            f"- $f_y = {s['fy']}\\text{{ MPa}}$\n"
            f"- Eccentricity: $e = {s['e']}\\text{{ mm}}$"
        )

    # ---------- shared solvers ----------
    def _ag(s): return s["b"] * s["h"]
    def _cbal(s): return 600 * s["d"] / (600 + s["fy"])
    def _abal(s): return _beta1(s["fc"]) * s["cbal"]
    def _fsp_bal(s): return 600 * (s["cbal"] - s["dp"]) / s["cbal"]
    def _cc(s): return 0.85 * s["fc"] * s["abal"] * s["b"]

    def _cs(s):
        fsp = min(s["fsp_bal"], s["fy"])
        return s["Asp"] * (fsp - 0.85 * s["fc"])

    def _ts(s): return s["As"] * s["fy"]
    def _pb(s): return s["Cc"] + s["Cs"] - s["Ts"]

    def _mnb(s):
        h = s["h"]
        return (
            s["Cc"] * (h / 2 - s["abal"] / 2)
            + s["Cs"] * (h / 2 - s["dp"])
            + s["Ts"] * (s["d"] - h / 2)
        )

    def _ebal(s): return s["Mnb"] / s["Pb"]

    def _case(s):
        e = s["e"]
        ebal = s["ebal"]
        if abs(e - ebal) / ebal < 0.02:
            return "Case 1"
        if e < ebal:
            return "Case 2"
        return "Case 3"

    # ---------- Case 2 ----------
    def _case2_c(s):
        b, h, d, dp = s["b"], s["h"], s["d"], s["dp"]
        As, Asp = s["As"], s["Asp"]
        fc, fy, e = s["fc"], s["fy"], s["e"]
        b1 = _beta1(fc)

        def eq(c):
            a = b1 * c
            Cc = 0.85 * fc * a * b
            Cs = Asp * (fy - 0.85 * fc)
            fs = 600 * (d - c) / c
            Ts = As * fs
            Pn = Cc + Cs - Ts
            Mn = Cc * (h / 2 - a / 2) + Cs * (h / 2 - dp) + Ts * (d - h / 2)
            return Pn * e - Mn

        cbal = 600 * d / (600 + fy)
        lo = cbal
        hi = 4 * d

        f_lo, f_hi = eq(lo), eq(hi)
        if f_lo * f_hi > 0:
            hi = 8 * d
            f_hi = eq(hi)
            if f_lo * f_hi > 0:
                lo = cbal * 0.95
                f_lo = eq(lo)
                if f_lo * f_hi > 0:
                    return None

        for _ in range(300):
            mid = (lo + hi) / 2
            f_mid = eq(mid)
            if abs(f_mid) < 1 or (hi - lo) < 1e-6:
                return mid
            if f_lo * f_mid < 0:
                hi, f_hi = mid, f_mid
            else:
                lo, f_lo = mid, f_mid
        return (lo + hi) / 2

    def _case2_pn(s):
        c = s["case2_c"]
        b, d = s["b"], s["d"]
        fc, fy = s["fc"], s["fy"]
        As, Asp = s["As"], s["Asp"]
        b1 = _beta1(fc)
        a = b1 * c
        Cc = 0.85 * fc * a * b
        Cs = Asp * (fy - 0.85 * fc)
        fs = 600 * (d - c) / c
        Ts = As * fs
        return Cc + Cs - Ts

    def _phi_from_c(s, c):
        Es = 200000
        ey = s["fy"] / Es
        et = 0.003 * (s["d"] - c) / c
        if et <= ey:
            return 0.65
        if et >= 0.005:
            return 0.90
        return 0.65 + 0.25 * (et - ey) / (0.005 - ey)

    def _case2_phi(s):
        return _phi_from_c(s, s["case2_c"])

    # ---------- Case 3 ----------
    def _case3_c(s):
        b, h, d, dp = s["b"], s["h"], s["d"], s["dp"]
        As, Asp = s["As"], s["Asp"]
        fc, fy, e = s["fc"], s["fy"], s["e"]
        b1 = _beta1(fc)

        def eq(c):
            a = b1 * c
            Cc = 0.85 * fc * a * b
            fsp = 600 * (c - dp) / c
            fsp = min(fsp, fy)
            Cs = Asp * (fsp - 0.85 * fc)
            Ts = As * fy
            Pn = Cc + Cs - Ts
            Mn = Cc * (h / 2 - a / 2) + Cs * (h / 2 - dp) + Ts * (d - h / 2)
            return Pn * e - Mn

        cbal = 600 * d / (600 + fy)
        lo = 1.0
        hi = cbal

        f_lo, f_hi = eq(lo), eq(hi)
        if f_lo * f_hi > 0:
            lo = 0.1
            f_lo = eq(lo)
            if f_lo * f_hi > 0:
                return None

        for _ in range(300):
            mid = (lo + hi) / 2
            f_mid = eq(mid)
            if abs(f_mid) < 1 or (hi - lo) < 1e-6:
                return mid
            if f_lo * f_mid < 0:
                hi, f_hi = mid, f_mid
            else:
                lo, f_lo = mid, f_mid
        return (lo + hi) / 2

    def _case3_pn(s):
        c = s["case3_c"]
        b, dp = s["b"], s["dp"]
        fc, fy = s["fc"], s["fy"]
        As, Asp = s["As"], s["Asp"]
        b1 = _beta1(fc)
        a = b1 * c
        Cc = 0.85 * fc * a * b
        fsp = 600 * (c - dp) / c
        fsp_capped = min(fsp, fy)
        Cs = Asp * (fsp_capped - 0.85 * fc)
        Ts = As * fy
        return Cc + Cs - Ts

    def _case3_phi(s):
        return _phi_from_c(s, s["case3_c"])

    # ---------- Case 1 ----------
    def _case1_pn(s): return s["Pb"]
    def _case1_phi(s): return 0.65

    return Workflow(
        id="eccentric_column",
        name="Eccentric Column Analysis",
        description="Compute balanced condition, classify, and solve for Pn.",
        generator=_gen,
        start_step="start",
        # NEW: declare case support so _current_case_kwargs() doesn't need
        # to string-match the workflow id.
        generator_supports_cases=True,
        steps={
            "start": Step(id="start", title="START", content=_start_text, next_step="ag"),
            "ag": Step(
                id="ag", title="Gross Area",
                content=r"$$A_g = b \cdot h$$",
                question=r"Compute $A_g$ in mm².",
                solver=_ag, var_name="Ag",
                answer_type=AnswerType.NUMERIC, tolerance=0.001,
                hints=["b × h."],
                next_step="cbal",
            ),
            "cbal": Step(
                id="cbal", title="Balanced Neutral Axis",
                content=r"$$c_{bal} = \frac{600 d}{600 + f_y}$$",
                question=r"Compute $c_{bal}$ in mm.",
                solver=_cbal, var_name="cbal",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["600 × d / (600 + fy)"],
                next_step="abal",
            ),
            "abal": Step(
                id="abal", title="Balanced Stress Block",
                content=r"$$a_{bal} = \beta_1 c_{bal}$$",
                question=r"Compute $a_{bal}$ in mm.",
                solver=_abal, var_name="abal",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["β1 = 0.85 for f'c ≤ 28 MPa."],
                next_step="fsp",
            ),
            "fsp": Step(
                id="fsp", title="Compression Steel Stress",
                content=r"$$f'_s = 600\left(\frac{c_{bal} - d'}{c_{bal}}\right)$$",
                question=r"Compute $f'_s$ at balanced condition in MPa.",
                solver=_fsp_bal, var_name="fsp_bal",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["Plug in cbal and d'."],
                next_step="cc",
            ),
            "cc": Step(
                id="cc", title="Concrete Compression",
                content=r"$$C_c = 0.85 f'_c \, a_{bal} \, b$$",
                question=r"Compute $C_c$ in N.",
                solver=_cc, var_name="Cc",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["0.85 × f'c × abal × b"],
                next_step="cs",
            ),
            "cs": Step(
                id="cs", title="Steel Compression",
                content=(
                    r"$$C_s = A'_s (f'_s - 0.85 f'_c)$$"
                    "\n\n"
                    r"Use the **smaller** of $f'_s$ and $f_y$."
                ),
                question=r"Compute $C_s$ in N.",
                solver=_cs, var_name="Cs",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["f's is capped at fy."],
                next_step="ts",
            ),
            "ts": Step(
                id="ts", title="Steel Tension",
                content=r"$$T_s = A_s f_y$$",
                question=r"Compute $T_s$ in N.",
                solver=_ts, var_name="Ts",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["At balanced, tension steel yields."],
                next_step="pb",
            ),
            "pb": Step(
                id="pb", title="Balanced Load",
                content=r"$$P_b = C_c + C_s - T_s$$",
                question=r"Compute $P_b$ in N.",
                solver=_pb, var_name="Pb",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["Cc + Cs − Ts"],
                next_step="mnb",
            ),
            "mnb": Step(
                id="mnb", title="Balanced Moment",
                content=(
                    r"$$M_{nb} = C_c\left(\frac{h}{2} - \frac{a_{bal}}{2}\right)"
                    r"+ C_s\left(\frac{h}{2} - d'\right)"
                    r"+ T_s\left(d - \frac{h}{2}\right)$$"
                ),
                question=r"Compute $M_{nb}$ in N·mm.",
                solver=_mnb, var_name="Mnb",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=["Moment about the plastic centroid at h/2."],
                next_step="ebal",
            ),
            "ebal": Step(
                id="ebal", title="Balanced Eccentricity",
                content=r"$$e_{bal} = \frac{M_{nb}}{P_b}$$",
                question=r"Compute $e_{bal}$ in mm.",
                solver=_ebal, var_name="ebal",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=["Mnb / Pb"],
                next_step="case",
            ),
            "case": Step(
                id="case", title="Classify",
                content=(
                    r"Compare $e$ to $e_{bal}$."
                    "\n\n"
                    r"- $e = e_{bal}$ → Case 1 (balanced)"
                    "\n\n"
                    r"- $e < e_{bal}$ → Case 2 (compression-controlled)"
                    "\n\n"
                    r"- $e > e_{bal}$ → Case 3 (transition / tension-controlled)"
                ),
                question="Which case applies?",
                solver=_case, var_name="case",
                answer_type=AnswerType.CHOICE,
                branches={"Case 1": "case1", "Case 2": "case2", "Case 3": "case3"},
                hints=["Compare e to ebal directly."],
            ),
            "case1": Step(
                id="case1", title="Case 1: Balanced — Setup",
                content=(
                    r"**Balanced condition.** The section is at the boundary between "
                    "compression-controlled and tension-controlled behaviour."
                    "\n\n"
                    r"At balance, tension steel just yields ($f_s = f_y$) and "
                    r"$\varepsilon_t = \varepsilon_y$."
                    "\n\n"
                    r"$$P_n = P_b \quad \text{(already computed)}$$"
                ),
                next_step="case1_pn",
            ),
            "case1_pn": Step(
                id="case1_pn", title="Nominal Load",
                content=r"$$P_n = P_b$$",
                question=r"Compute $P_n$ in N.",
                solver=_case1_pn, var_name="Pn",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["Pn = Pb."],
                next_step="case1_phi",
            ),
            "case1_phi": Step(
                id="case1_phi", title="Strength Reduction Factor",
                content=(
                    r"At balance, $\varepsilon_t = \varepsilon_y$."
                    "\n\n"
                    r"For **tied** columns: $\phi = 0.65$"
                ),
                question=r"Compute $\phi$.",
                solver=_case1_phi, var_name="phi",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["At et = ey, φ = 0.65 (tied)."],
                next_step="case1_end",
            ),
            "case1_end": Step(
                id="case1_end", title="Case 1 — Result",
                content=r"**Done.** $\phi P_n$ is the design strength.",
                is_terminal=True,
            ),
            "case2": Step(
                id="case2", title="Case 2: Compression-Controlled — Setup",
                content=(
                    r"**Assume compression steel yields:** $f'_s = f_y$"
                    "\n\n"
                    r"**Tension steel is elastic:** $f_s = 600\dfrac{d - c}{c}$"
                    "\n\n"
                    r"$$C_c = 0.85 f'_c \beta_1 c b$$"
                    "\n\n"
                    r"$$C_s = A'_s (f_y - 0.85 f'_c)$$"
                    "\n\n"
                    r"$$T_s = A_s \cdot 600\dfrac{d - c}{c}$$"
                    "\n\n"
                    r"Equilibrium: $P_n = C_c + C_s - T_s$"
                    "\n\n"
                    r"Moment about plastic centroid: $P_n e = C_c(\tfrac{h}{2} - \tfrac{a}{2}) + C_s(\tfrac{h}{2} - d') + T_s(d - \tfrac{h}{2})$"
                    "\n\n"
                    r"Solve the resulting **cubic in $c$**."
                ),
                next_step="case2_c",
            ),
            "case2_c": Step(
                id="case2_c", title="Solve for c",
                content=r"Solve $P_n(c) \cdot e = M_n(c)$ for $c$.",
                question=r"Compute $c$ in mm.",
                solver=_case2_c, var_name="case2_c",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=[
                    "Bisection between cbal and 4d.",
                    "Iterate until Pn·e ≈ Mn.",
                ],
                next_step="case2_pn",
            ),
            "case2_pn": Step(
                id="case2_pn", title="Nominal Load Pn",
                content=r"$$P_n = C_c + C_s - T_s$$",
                question=r"Compute $P_n$ in N.",
                solver=_case2_pn, var_name="Pn",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=["Use the c you solved for."],
                next_step="case2_phi",
            ),
            "case2_phi": Step(
                id="case2_phi", title="Strength Reduction Factor",
                content=(
                    r"Compute $\varepsilon_t = 0.003\dfrac{d - c}{c}$, then pick $\phi$."
                    "\n\n"
                    r"Since this is compression-controlled: $\varepsilon_t < \varepsilon_y \Rightarrow \phi = 0.65$ (tied)."
                ),
                question=r"Compute $\phi$.",
                solver=_case2_phi, var_name="phi",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["Compression-controlled → φ = 0.65 for tied."],
                next_step="case2_end",
            ),
            "case2_end": Step(
                id="case2_end", title="Case 2 — Result",
                content=r"**Done.** $\phi P_n$ is the design strength for Case 2.",
                is_terminal=True,
            ),
            "case3": Step(
                id="case3", title="Case 3: Tension-Controlled — Setup",
                content=(
                    r"**Assume tension steel yields:** $f_s = f_y$"
                    "\n\n"
                    r"**Compression steel stress:** $f'_s = 600\dfrac{c - d'}{c}$ (cap at $f_y$)"
                    "\n\n"
                    r"$$C_c = 0.85 f'_c \beta_1 c b$$"
                    "\n\n"
                    r"$$C_s = A'_s (f'_s - 0.85 f'_c)$$"
                    "\n\n"
                    r"$$T_s = A_s f_y$$"
                    "\n\n"
                    r"Equilibrium: $P_n = C_c + C_s - T_s$"
                    "\n\n"
                    r"Moment: $P_n e = C_c(\tfrac{h}{2} - \tfrac{a}{2}) + C_s(\tfrac{h}{2} - d') + T_s(d - \tfrac{h}{2})$"
                    "\n\n"
                    r"Solve the resulting **cubic in $c$**."
                ),
                next_step="case3_c",
            ),
            "case3_c": Step(
                id="case3_c", title="Solve for c",
                content=r"Solve $P_n(c) \cdot e = M_n(c)$ for $c$.",
                question=r"Compute $c$ in mm.",
                solver=_case3_c, var_name="case3_c",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=[
                    "Bisection between 0 and cbal.",
                    "Iterate until Pn·e ≈ Mn.",
                ],
                next_step="case3_pn",
            ),
            "case3_pn": Step(
                id="case3_pn", title="Nominal Load Pn",
                content=r"$$P_n = C_c + C_s - T_s$$",
                question=r"Compute $P_n$ in N.",
                solver=_case3_pn, var_name="Pn",
                answer_type=AnswerType.NUMERIC, tolerance=0.03,
                hints=["Use the c you solved for."],
                next_step="case3_phi",
            ),
            "case3_phi": Step(
                id="case3_phi", title="Strength Reduction Factor",
                content=(
                    r"Compute $\varepsilon_t = 0.003\dfrac{d - c}{c}$, then pick $\phi$."
                    "\n\n"
                    r"- $\varepsilon_t \le \varepsilon_y$: $\phi = 0.65$"
                    "\n\n"
                    r"- $\varepsilon_y < \varepsilon_t < 0.005$: $\phi = 0.65 + 0.25\dfrac{\varepsilon_t - \varepsilon_y}{0.005 - \varepsilon_y}$"
                    "\n\n"
                    r"- $\varepsilon_t \ge 0.005$: $\phi = 0.90$"
                ),
                question=r"Compute $\phi$.",
                solver=_case3_phi, var_name="phi",
                answer_type=AnswerType.NUMERIC, tolerance=0.02,
                hints=["Check whether et is in the transition zone or ≥ 0.005."],
                next_step="case3_end",
            ),
            "case3_end": Step(
                id="case3_end", title="Case 3 — Result",
                content=r"**Done.** $\phi P_n$ is the design strength for Case 3.",
                is_terminal=True,
            ),
        },
    )


# ---- Build the workflow registry ----
PURE_AXIAL = _build_pure_axial_workflow()
TIED_COLUMN = _build_tied_column_workflow()
SPIRAL_COLUMN = _build_spiral_column_workflow()
ECCENTRIC_COLUMN = _build_eccentric_column_workflow()

ALL_WORKFLOWS = [PURE_AXIAL, TIED_COLUMN, SPIRAL_COLUMN, ECCENTRIC_COLUMN]


# ====================================================================
# SECTION 8 — MAIN WINDOW                  (was ui/app.py)
# ====================================================================
# FIX (#14): Ag and Ag_final previously both rendered as "Ag" in the top
# bar, producing two identical labels with different values. Ag_final is
# now labeled "Ag (actual)" so they can be told apart.
_LABELS = {
    "b":   ("b",   "mm"),
    "h":   ("h",   "mm"),
    "d":   ("d",   "mm"),
    "dp":  ("d'",  "mm"),
    "DL":  ("DL",  "kN"),
    "LL":  ("LL",  "kN"),
    "fc":  ("f'c", "MPa"),
    "fy":  ("fy",  "MPa"),
    "Ast": ("Ast", "mm²"),
    "As":  ("As",  "mm²"),
    "Asp": ("A's", "mm²"),
    "n":   ("n",   ""),
    "dia": ("db",  "mm"),
    "e":   ("e",   "mm"),
    "cc":  ("cc",  "mm"),
    "Pu_kN": ("Pu",    "kN"),
    "Pu":    ("Pu",    "N"),
    "Ag":       ("Ag",           "mm²"),
    "Ag_final": ("Ag (actual)",  "mm²"),
    "b_final": ("b",   "mm"),
    "D":     ("D",     "mm"),
    "D_final": ("D",   "mm"),
    "Dc":    ("Dc",    "mm"),
    "rho":   ("ρg",    ""),
    "rho_s_min": ("ρs,min", ""),
    "nb":    ("nb",    ""),
    "s":     ("s",     "mm"),
    "S":     ("S",     "mm"),
    "P0":    ("P0",    "N"),
    "cbal":  ("cbal",  "mm"),
    "abal":  ("abal",  "mm"),
    "fsp_bal": ("f's", "MPa"),
    "Cc":    ("Cc",    "N"),
    "Cs":    ("Cs",    "N"),
    "Ts":    ("Ts",    "N"),
    "Pb":    ("Pb",    "N"),
    "Mnb":   ("Mnb",   "N·mm"),
    "ebal":  ("ebal",  "mm"),
    "case":  ("case",  ""),
}

_GIVEN_KEYS = {
    "b", "h", "d", "dp", "DL", "LL", "fc", "fy",
    "n", "dia", "e", "cc", "As", "Asp", "Ast",
}


# FIX (#9): one formatter. Prior version mixed .4f / .2f / .4g formats
# depending on magnitude, which produced inconsistent displays and could
# truncate significant digits (e.g. 1234.5 → "1234"). Now: 4 significant
# figures always, thousands separators only for values >= 10,000 so small
# values like 490.9 stay readable.
def _fmt(v):
    if isinstance(v, float):
        if v == int(v):
            return f"{int(v):,}"
        if abs(v) < 1:
            return f"{v:.4f}"
        if abs(v) >= 10000:
            return f"{v:,.1f}"
        return f"{v:.4g}"
    return str(v)


class RCDReviewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RCD Interactive Reviewer")
        self.configure(bg=BG_MAIN)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(960, min(1320, sw - 40))
        h = max(620, min(880, sh - 100))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(900, 600)

        self.session: Session | None = None
        self._history_visible = True
        self.answer_var = tk.StringVar()
        self.answer_widget = None
        self.hint_lbl = None

        # FIX (#4): guards the Enter→Check→Enter race. Set True for a short
        # moment after a successful Check so a fast double-Enter doesn't
        # immediately submit an empty answer on the next step.
        self._suppress_enter_until = 0.0
        # FIX (#3): persistent "your last answer was wrong" flag so the red
        # background survives _render_step().
        self._last_answer_wrong = False

        self._build_layout()
        self._start_workflow(0)

        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)
        self.bind_all("<Return>", self._on_enter)
        self.bind_all("<KP_Enter>", self._on_enter)

    # ================================================================
    # Layout
    # ================================================================
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

        self.btn_back = tk.Button(bar, text="◀ Back", width=8,
                                  command=self._on_back)
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
        self.workflow_combo.bind("<<ComboboxSelected>>",
                                 self._on_workflow_change)

        self.case_frame = tk.Frame(toolbar, bg=BG_MAIN)
        tk.Label(self.case_frame, text="Study case:", bg=BG_MAIN,
                 font=FONT_LABEL).pack(side="left")
        self.case_var = tk.StringVar(value="Random")
        self.case_combo = ttk.Combobox(
            self.case_frame, textvariable=self.case_var,
            values=["Random", "Case 1", "Case 2", "Case 3"],
            state="readonly", width=10,
        )
        self.case_combo.pack(side="left", padx=(4, 0))

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

    # ================================================================
    # Top bar
    # ================================================================
    def _refresh_topbar(self):
        for w in self.given_row.winfo_children():
            w.destroy()
        if self.session is None:
            return

        state = self.session.state
        givens_keys = set(self.session.givens.keys())

        given_items = [(k, v) for k, v in state.items() if k in givens_keys]
        extra_items = [(k, v) for k, v in state.items() if k not in givens_keys]
        items = [(k, v, True) for k, v in given_items] + \
                [(k, v, False) for k, v in extra_items]

        cols = 8
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

    # ================================================================
    # Workflow
    # ================================================================
    def _start_workflow(self, idx):
        self.session = Session(ALL_WORKFLOWS[idx])
        self.workflow_combo.set(ALL_WORKFLOWS[idx].name)
        self._update_case_picker()
        self.history.clear()
        self.history.log(f"— {ALL_WORKFLOWS[idx].name} —", "head")
        self.history.log("Review started.", "gray")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("Ready. Solve the step, then click Check.", FG_HINT)

    def _update_case_picker(self):
        # FIX (#5): consult the workflow's declared flag instead of
        # string-matching its id. Adding a second case-supporting workflow
        # now only requires setting generator_supports_cases=True.
        is_eccentric = (self.session is not None
                        and self.session.workflow.generator_supports_cases)
        if is_eccentric and not self.case_frame.winfo_ismapped():
            self.case_frame.pack(side="left", padx=(12, 0))
        elif not is_eccentric and self.case_frame.winfo_ismapped():
            self.case_frame.pack_forget()

    def _current_case_kwargs(self):
        kwargs = {}
        if (self.session is not None
                and self.session.workflow.generator_supports_cases):
            target = self.case_var.get()
            if target in ("Case 1", "Case 2", "Case 3"):
                kwargs["target_case"] = target
        return kwargs

    def _on_workflow_change(self, event=None):
        idx = self.workflow_combo.current()
        if idx < 0:
            return
        self._start_workflow(idx)

    def _on_new_problem(self):
        if self.session is None:
            return
        kwargs = self._current_case_kwargs()
        self.session.new_problem(**kwargs)
        tag_msg = f" ({kwargs['target_case']})" if kwargs else ""
        self.history.log(f"— New problem —{tag_msg}", "head")
        self._refresh_topbar()
        self._last_answer_wrong = False
        self._render_step()
        self._set_status("New problem generated.", FG_WARN)

    # ================================================================
    # Step rendering
    # ================================================================
    def _clear_content(self):
        for w in self.content_frame.winfo_children():
            w.destroy()
        self.answer_widget = None
        self.answer_var.set("")
        self.hint_lbl = None

    def _render_step(self):
        self._clear_content()
        if self.session is None:
            return

        step = self.session.current_step
        state = self.session.current_state

        if step.answer_type == AnswerType.NONE:
            state.completed = True
            if state.final_answer is None:
                state.final_answer = "(read)"

        f = self.content_frame

        tk.Label(f, text=step.title, font=FONT_TITLE,
                 bg=BG_MAIN, fg=FG_HEAD, anchor="w"
                 ).pack(fill="x", pady=(0, 6))

        parsed = parse_content(step.resolve_content(self.session.state))
        n_lines = max(3, min(len(parsed), 18))
        txt = tk.Text(f, height=n_lines, wrap="word",
                      bg=BG_PANEL, relief="solid", bd=1,
                      font=FONT_CONTENT, fg=FG_VALUE,
                      padx=8, pady=6, highlightthickness=0)
        txt.pack(fill="x", pady=(0, 8))

        txt.tag_config("h1", font=("Segoe UI", 12, "bold"), foreground=FG_HEAD,
                       spacing1=6, spacing3=2)
        txt.tag_config("h2", font=("Segoe UI", 11, "bold"), foreground=FG_HEAD,
                       spacing1=5, spacing3=2)
        txt.tag_config("h3", font=("Segoe UI", 10, "bold"), foreground=FG_HEAD,
                       spacing1=4, spacing3=2)
        txt.tag_config("bullet", font=FONT_CONTENT, foreground=FG_VALUE,
                       lmargin1=16, lmargin2=28)
        txt.tag_config("normal", font=FONT_CONTENT, foreground=FG_VALUE)
        txt.tag_config("blank", font=("Segoe UI", 4))
        txt.tag_config("sep", foreground="#cccccc")

        for tag, content in parsed:
            txt.insert("end", content + "\n", tag)

        txt.configure(state="disabled")

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

        q = step.resolve_question(self.session.state)
        q_text = latex_to_unicode(q) if q else "(No question — click Next to continue.)"
        tk.Label(box, text=q_text, bg=BG_MAIN, fg=FG_LABEL,
                 font=FONT_QUESTION, anchor="w", justify="left",
                 wraplength=700
                 ).pack(fill="x", pady=(0, 6))

        is_question = step.answer_type != AnswerType.NONE
        is_choice = step.answer_type == AnswerType.CHOICE
        already_done = state.completed and state.final_answer

        if is_choice:
            choices = (list(step.branches.keys()) if step.branches
                       else step.resolve_choices(self.session.state))
            self.answer_var.set(choices[0] if choices else "")
            w = ttk.Combobox(box, textvariable=self.answer_var,
                             values=choices, state="readonly", width=40)
            w.pack(anchor="w")
            if not already_done:
                w.bind("<<ComboboxSelected>>", lambda e: self._on_check())
            else:
                w.configure(state="disabled")
            self.answer_widget = w
        elif is_question:
            w = tk.Entry(box, textvariable=self.answer_var, width=50,
                         font=FONT_ENTRY, justify="left")
            w.pack(anchor="w")
            # FIX (#3): persistent wrong-answer background survives the
            # re-render that _on_check triggers on a failed submission.
            if self._last_answer_wrong and not already_done:
                w.configure(bg=BG_INPUT_ERR)
            if already_done:
                w.configure(bg=BG_INPUT_OK, state="disabled",
                            disabledforeground=FG_OK)
            self.answer_widget = w
        else:
            self.answer_widget = None

        if already_done and self.answer_widget is not None:
            self.answer_var.set(state.final_answer or "")

        hint_row = tk.Frame(box, bg=BG_MAIN)
        hint_row.pack(fill="x", pady=(6, 0))
        self.hint_btn = tk.Button(hint_row, text="💡 Hint",
                                  bg=BG_BTN_WARM,
                                  command=self._on_hint)
        self.hint_btn.pack(side="right")
        n_hints = len(step.resolve_hints(self.session.state))
        self.hint_btn.configure(state=("normal" if n_hints > 0 else "disabled"))

        checkable = is_question and not already_done
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))
        self.btn_next.configure(state=("normal" if state.completed else "disabled"))
        self.btn_next.configure(
            text=("Finish ✓" if step.is_terminal else "Next ▶"))
        self.btn_back.configure(
            state=("normal" if len(self.session.history) > 1 else "disabled"))

        try:
            self.content_canvas.yview_moveto(0)
        except Exception:
            pass

    # ================================================================
    # Check / Reveal / Next / Back
    # ================================================================
    def _on_enter(self, event=None):
        if self.session is None:
            return
        # FIX (#4): swallow Enter for a brief window after a successful
        # Check so a fast double-tap doesn't submit an empty answer on the
        # step that was just rendered.
        if time.time() < self._suppress_enter_until:
            return "break"

        focused = self.focus_get()

        if focused in (getattr(self, "workflow_combo", None),
                       getattr(self, "case_combo", None)):
            return

        if isinstance(focused, (tk.Button, ttk.Button)):
            return

        state = self.session.current_state
        if state.completed:
            self._on_next()
        else:
            self._on_check()
        return "break"

    def _on_check(self):
        if self.session is None or self.answer_widget is None:
            return
        step = self.session.current_step

        if step.answer_type == AnswerType.NONE:
            self.session.current_state.completed = True
            self._render_step()
            return

        answer = self.answer_var.get()
        ok, msg = self.session.submit(answer)

        if ok:
            self._last_answer_wrong = False
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

            msg_clean = latex_to_unicode(msg)

            expected = self.session.expected_for_current()
            if expected is not None and step.answer_type == AnswerType.NUMERIC:
                try:
                    exp_val = float(expected)
                    msg_clean += f"  (expected ≈ {_fmt(exp_val)}"
                    if step.unit:
                        msg_clean += f" {step.unit}"
                    msg_clean += ")"
                except (TypeError, ValueError):
                    pass

            self.history.log(f"✗ {step.title} — {msg_clean}", "yellow")
            self._set_status(f"✗ {msg_clean}", FG_ERR)

    def _on_reveal(self):
        if self.session is None:
            return
        step = self.session.current_step

        if step.answer_type == AnswerType.CHOICE:
            correct = self.session.expected_for_current()
            if correct is None:
                correct = (next(iter(step.branches.keys()))
                           if step.branches else "")
            if not correct:
                self._set_status("Nothing to reveal on this step.", FG_WARN)
                return
            self.answer_var.set(correct)
            st = self.session.states[step.id]
            st.completed = True
            st.final_answer = correct
            self._last_answer_wrong = False
            self.history.log(f"Revealed {step.title} → {correct}", "yellow")
            self._set_status("Answer revealed.", FG_WARN)
            self._refresh_topbar()
            self._render_step()
            return

        expected = self.session.expected_for_current()
        if expected is None:
            self._set_status("Nothing to reveal on this step.", FG_WARN)
            return

        if step.answer_type == AnswerType.NUMERIC:
            text = f"{float(expected):.4g}"
        else:
            text = str(expected)

        self.answer_var.set(text)
        st = self.session.states[step.id]
        st.completed = True
        st.final_answer = text
        if step.var_name is not None:
            self.session.state[step.var_name] = expected

        self._last_answer_wrong = False
        self.history.log(f"Revealed {step.title} → {text}", "yellow")
        self._set_status("Answer revealed.", FG_WARN)
        self._refresh_topbar()
        self._render_step()

    def _on_next(self):
        if self.session is None:
            return
        if not self.session.can_advance():
            return
        step = self.session.current_step
        branch = None
        if step.branches:
            chosen = self.answer_var.get()
            if chosen in step.branches:
                branch = chosen
        nxt = self.session.advance(branch)
        if nxt is None:
            self._show_summary()
        else:
            # FIX (#4): moving forward resets the wrong-answer flash and
            # arms the Enter-suppression window.
            self._last_answer_wrong = False
            self._suppress_enter_until = time.time() + 0.25
            self._render_step()

    def _on_back(self):
        if self.session is None:
            return
        if len(self.session.history) <= 1:
            return
        # FIX (#1): un-complete the step we're leaving so the re-rendered
        # step is interactive again and downstream solvers don't see a
        # stale value in `state`.
        self.session.uncomplete_current()
        self.session.history.pop()
        self.session.current_step_id = self.session.history[-1]
        self._last_answer_wrong = False
        self._render_step()

    def _on_reset(self):
        if self.session is None:
            return
        if not messagebox.askyesno("Reset",
                                   "Clear all progress for this problem?"):
            return
        kwargs = self._current_case_kwargs()
        self.session.new_problem(**kwargs)
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
            self.hint_lbl.configure(text=f"💡 {latex_to_unicode(hint)}")
        if not self.hint_lbl.winfo_ismapped():
            self.hint_lbl.pack(fill="x", pady=(6, 0))

    def _toggle_history(self):
        if self._history_visible:
            self.history.pack_forget()
            self._history_visible = False
        else:
            self.history.pack(side="right", fill="y")
            self._history_visible = True

    def _on_copy(self):
        if self.session is None:
            return
        lines = [f"RCD Reviewer — {self.session.workflow.name}", "=" * 50, ""]
        lines.append("GIVENS")
        lines.append("-" * 50)
        for k, v in self.session.givens.items():
            if isinstance(v, float):
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

    # ================================================================
    # Summary
    # ================================================================
    def _show_summary(self):
        self._clear_content()
        if self.session is None:
            return

        f = self.content_frame

        tk.Label(f, text=f"📋 {self.session.workflow.name} — Summary",
                 font=FONT_TITLE, bg=BG_MAIN, fg=FG_HEAD, anchor="w"
                 ).pack(fill="x", pady=(0, 8))

        given_box = tk.LabelFrame(f, text="Givens", font=FONT_LABEL_B,
                                  bg=BG_PANEL, fg=FG_LABEL, bd=1, relief="solid",
                                  padx=8, pady=6)
        given_box.pack(fill="x", pady=(0, 8))
        for k, v in self.session.givens.items():
            label, unit = _LABELS.get(k, (k, ""))
            line = f"  {label} = {_fmt(v)}"
            if unit:
                line += f" {unit}"
            tk.Label(given_box, text=line, bg=BG_PANEL, fg=FG_VALUE,
                     font=FONT_CONTENT, anchor="w"
                     ).pack(fill="x")

        done, total = self.session.progress()
        tk.Label(f, text=f"Completed: {done}/{total} steps",
                 bg=BG_MAIN, fg=FG_HEAD, font=FONT_SECTION, anchor="w"
                 ).pack(fill="x", pady=(4, 6))

        for sid, step in self.session.workflow.steps.items():
            st = self.session.states[sid]
            mark = "✓" if st.completed else "○"
            color = FG_OK if st.completed else FG_HINT

            row = tk.Frame(f, bg=BG_MAIN)
            row.pack(fill="x", anchor="w", pady=2)

            tk.Label(row, text=f"{mark} {step.title}", bg=BG_MAIN, fg=color,
                     font=FONT_LABEL_B, anchor="w"
                     ).pack(side="left")

            if st.final_answer:
                tk.Label(row, text=f"→ {st.final_answer}", bg=BG_MAIN,
                         fg=FG_VALUE, font=FONT_ENTRY, anchor="w"
                         ).pack(side="left", padx=8)

        self._set_status("Problem complete! 🎉", FG_OK)
        self.btn_next.configure(state="disabled")
        self.btn_check.configure(state="disabled")
        self.btn_reveal.configure(state="disabled")
        # FIX (#2): Back stays enabled so the user can still review the
        # last step (it now correctly un-completes on click).
        self.btn_back.configure(
            state=("normal" if len(self.session.history) > 1 else "disabled"))
        self._last_answer_wrong = False

    # ================================================================
    # Mouse wheel
    # ================================================================
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


# ====================================================================
# SECTION 9 — ENTRY POINT                 (was main.py)
# ====================================================================
def main():
    app = RCDReviewer()
    app.mainloop()


if __name__ == "__main__":
    main()