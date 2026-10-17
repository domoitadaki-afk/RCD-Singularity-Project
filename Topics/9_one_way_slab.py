"""
rcd_slab_reviewer.py — RCD One-Way Slab Reviewer (single-file build).

Merged from the original package layout:
    config.py, flow.py, utils.py, solver.py, randomizer.py, main.py,
    ui/theme.py, ui/history.py, ui/app.py,
    ui/pages/setup.py, ui/pages/generic.py, ui/pages/summary.py

Run with:  python rcd_slab_reviewer.py
"""

import math
import random
import tkinter as tk
from tkinter import ttk, messagebox


# ====================================================================
# SECTION 1 — CONFIG                        (was config.py)
# ====================================================================
APP_TITLE = "RCD One-Way Slab Reviewer"
APP_VERSION = "2.0"

# Modes
MODE_DESIGN   = "Design"
MODE_ANALYSIS = "Analysis"
MODES = [MODE_DESIGN, MODE_ANALYSIS]

# Factors
PHI_FLEX = 0.90

# Support conditions
SC_SS   = "Simply Supported"
SC_ONE  = "One End Continuous"
SC_BOTH = "Both End Continuous"
SC_CANT = "Cantilever"
SUPPORT_CONDITIONS = [SC_SS, SC_ONE, SC_BOTH, SC_CANT]

# Table 407.3.1.1 — min thickness denominators
THICKNESS_DENOM = {
    SC_SS: 20.0, SC_ONE: 24.0, SC_BOTH: 28.0, SC_CANT: 10.0,
}

# Table 406.5.2 — moment coefficients (positive_denom, negative_denom)
MOMENT_DENOM = {
    SC_SS:   (8.0,  None),
    SC_ONE:  (14.0, 10.0),
    SC_BOTH: (16.0, 10.0),
    SC_CANT: (None, 2.0),
}

# Moment type
MT_POS = "Positive (midspan)"
MT_NEG = "Negative (support)"
MOMENT_TYPES = [MT_POS, MT_NEG]

# Randomizer option pools
SPAN_OPTIONS     = [3000.0, 3500.0, 4000.0, 4500.0, 5000.0, 5500.0, 6000.0]
MAIN_BAR_OPTIONS = [10.0, 12.0, 16.0, 20.0]
TEMP_BAR_OPTIONS = [10.0, 12.0]
COVER_OPTIONS    = [20.0, 25.0]
FC_OPTIONS       = [21.0, 24.0, 28.0]
FY_MAIN_OPTIONS  = [275.0, 415.0]
FY_TEMP_OPTIONS  = [276.0, 415.0]
LL_RANGE         = (2.0, 8.0)
GAMMA_C_DEFAULT  = 23.6

# Default problem
DEFAULT_PROBLEM = {
    "l": 4000.0, "b": 1000.0,
    "fc": 21.0, "fy": 415.0, "fyt": 276.0,
    "db": 12.0, "dt": 10.0, "cc": 20.0,
    "gamma_c": GAMMA_C_DEFAULT, "LL": 4.0,
    "condition": SC_BOTH,
    # analysis-mode additions:
    "h": 150.0, "S": 200.0, "moment_type": MT_POS,
}


# ====================================================================
# SECTION 2 — THEME                         (was ui/theme.py)
# ====================================================================
BG_MAIN        = "#f4f4f4"
BG_TOP_BAR     = "#eef3fa"
BG_BOTTOM      = "#e8e8e8"
BG_HISTORY     = "#fafafa"
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

FONT_TITLE    = ("Segoe UI", 14, "bold")
FONT_SECTION  = ("Segoe UI", 10, "bold")
FONT_LABEL    = ("Segoe UI", 9)
FONT_LABEL_B  = ("Segoe UI", 9, "bold")
FONT_ENTRY    = ("Consolas", 10)
FONT_VALUE    = ("Consolas", 10)
FONT_HIST     = ("Consolas", 9)
FONT_BIG      = ("Segoe UI", 13, "bold")
FONT_MONO_BIG = ("Consolas", 13, "bold")


# ====================================================================
# SECTION 3 — UTILS                         (was utils.py)
# ====================================================================
def close(a, b, rel_tol=0.005, abs_tol=5e-5):
    if b == 0:
        return abs(a) <= abs_tol
    return abs(a - b) <= max(abs_tol, rel_tol * abs(b))


def fmt(x, n=3):
    if x is None:
        return "-"
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


def round_up_to(x, step):
    return math.ceil(x / step) * step


def beta1(fc):
    if fc <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)


# ====================================================================
# SECTION 4 — FLOW                          (was flow.py)
# ====================================================================
DESIGN_STEPS = [
    {
        "id": "d1",
        "title": "Step 1 — Minimum Slab Thickness",
        "notes": [
            "Table 407.3.1.1 — minimum h per support condition:",
            "   Simply Supported: l/20",
            "   One End Continuous: l/24",
            "   Both End Continuous: l/28",
            "   Cantilever: l/10",
            "For fy ≠ 420 MPa, multiply by (0.4 + fy/700).",
            "Round UP to nearest 25 mm.",
        ],
        "fields": [("h", "h", "mm", 0)],
    },
    {
        "id": "d2",
        "title": "Step 2 — Self Weight & Load Analysis",
        "notes": [
            "DL = γc · h / 1000   [kPa]",
            "Wu = 1.2 DL + 1.6 LL   [kN/m, per 1 m strip]",
        ],
        "fields": [("DL", "DL", "kPa", 3), ("Wu", "Wu", "kN/m", 3)],
    },
    {
        "id": "d3",
        "title": "Step 3 — Factored Moment (Table 406.5.2)",
        "notes": [
            "+Mu = Wu · l² / denom_pos",
            "−Mu = Wu · l² / denom_neg",
            "Design for the larger.",
        ],
        "fields": [
            ("Mu_pos", "+Mu (midspan)", "kN·m", 3),
            ("Mu_neg", "−Mu (support)",  "kN·m", 3),
        ],
    },
    {
        "id": "d4",
        "title": "Step 4 — Effective Depth",
        "notes": ["d = h − cc − db / 2"],
        "fields": [("d", "d", "mm", 0)],
    },
    {
        "id": "d5",
        "title": "Step 5 — Fictitious Depth (a)",
        "notes": [
            "Mu = φ Mn",
            "Mu = φ · 0.85 f'c · a · b · (d − a/2)",
            "Solve quadratic for a.",
        ],
        "fields": [("a", "a", "mm", 3)],
    },
    {
        "id": "d6",
        "title": "Step 6 — Neutral Axis & Steel Yielding",
        "notes": [
            "c = a / β1",
            "fs = 600 (d − c) / c",
            "Check fs > fy.",
        ],
        "fields": [("c", "c", "mm", 3), ("fs", "fs", "MPa", 3)],
    },
    {
        "id": "d7",
        "title": "Step 7 — Steel Area (C = T)",
        "notes": [
            "0.85 f'c · a · b = As · fy",
            "As = (0.85 f'c · a · b) / fy",
        ],
        "fields": [("As", "As", "mm²", 3)],
    },
    {
        "id": "d8",
        "title": "Step 8 — Reinforcement Ratio",
        "notes": [
            "ρact = As / (b·d)",
            "ρmin = max(1.4/fy, 0.25 √f'c / fy)",
            "ρmax = (3/8) · (0.85 β1 f'c / fy)",
            "If ρact < ρmin → use As = ρmin · b · d.",
        ],
        "fields": [
            ("rho_act", "ρact", "", 5),
            ("rho_min", "ρmin", "", 5),
            ("rho_max", "ρmax", "", 5),
            ("As_design", "As,design", "mm²", 3),
        ],
    },
    {
        "id": "d9",
        "title": "Step 9 — Main Bar Spacing",
        "notes": [
            "Abar = π/4 · db²",
            "Sreq = (Abar / As,design) × 1000",
            "Round DOWN to nearest 10 mm.",
        ],
        "fields": [
            ("Abar", "Abar", "mm²", 3),
            ("S_req_raw", "Sreq (raw)", "mm", 3),
            ("S_req", "Sreq (rounded)", "mm", 0),
        ],
    },
    {
        "id": "d10",
        "title": "Step 10 — Min & Max Spacing",
        "notes": [
            "Smin = ρ · a · b   (ρ = 0.0020; a = stress-block depth from Step 5)",
            "Smax = min(3h, 450)",
        ],
        "fields": [
            ("S_min", "Smin", "mm", 3),
            ("S_max", "Smax", "mm", 0),
        ],
    },
    {
        "id": "d11",
        "title": "Step 11 — Temperature Reinforcement",
        "notes": [
            "Table 424.3.2:",
            "   fyt < 420 MPa → ρt = 0.0020",
            "   fyt ≥ 420 MPa → ρt = max(0.0018·420/fyt, 0.0014)",
            "Ast = ρt · b · h",
            "St = (Abar,t / Ast) × 1000",
            "Smax,t = min(5h, 450)",
        ],
        "fields": [
            ("rho_t", "ρt", "", 5),
            ("As_t", "Ast", "mm²", 3),
            ("S_t_raw", "St (raw)", "mm", 3),
            ("S_t", "St (rounded)", "mm", 0),
            ("S_t_max", "Smax,t", "mm", 0),
        ],
    },
]


ANALYSIS_STEPS = [
    {
        "id": "a1",
        "title": "Step 1 — Steel Area from Bar Spacing",
        "notes": [
            "Abar = π/4 · db²",
            "As = (Abar / S) × 1000",
        ],
        "fields": [("Abar", "Abar", "mm²", 3), ("As", "As", "mm²", 3)],
    },
    {
        "id": "a2",
        "title": "Step 2 — Effective Depth",
        "notes": ["d = h − cc − db / 2"],
        "fields": [("d", "d", "mm", 0)],
    },
    {
        "id": "a3",
        "title": "Step 3 — Reinforcement Ratio",
        "notes": [
            "ρact = As / (b·d)",
            "ρmin = max(1.4/fy, 0.25 √f'c / fy)",
            "ρmax = (3/8) · (0.85 β1 f'c / fy)",
            "Check ρmin < ρact < ρmax.",
        ],
        "fields": [
            ("rho_act", "ρact", "", 5),
            ("rho_min", "ρmin", "", 5),
            ("rho_max", "ρmax", "", 5),
        ],
    },
    {
        "id": "a4",
        "title": "Step 4 — Fictitious Depth (a) from C = T",
        "notes": [
            "0.85 f'c · a · b = As · fy",
            "a = As · fy / (0.85 f'c · b)",
        ],
        "fields": [("a", "a", "mm", 3)],
    },
    {
        "id": "a5",
        "title": "Step 5 — Neutral Axis & Steel Yielding",
        "notes": [
            "c = a / β1",
            "fs = 600 (d − c) / c",
            "Check fs > fy.",
        ],
        "fields": [("c", "c", "mm", 3), ("fs", "fs", "MPa", 3)],
    },
    {
        "id": "a6",
        "title": "Step 6 — Flexural Capacity (Mu)",
        "notes": [
            "Mu = φ · As · fy · (d − a/2)",
            "φ = 0.90 if steel yields.",
        ],
        "fields": [("Mu", "Mu", "kN·m", 3)],
    },
    {
        "id": "a7",
        "title": "Step 7 — From Mu get Wu",
        "notes": [
            "Invert the moment coefficient:",
            "Wu = Mu · denom / l²",
        ],
        "fields": [("Wu", "Wu", "kN/m", 3)],
    },
    {
        "id": "a8",
        "title": "Step 8 — Live Load Capacity",
        "notes": [
            "Wu = 1.2 DL + 1.6 LL",
            "DL = γc · h / 1000",
            "Solve for LL.",
        ],
        "fields": [
            ("DL", "DL", "kPa", 3),
            ("LL", "LL", "kPa", 3),
        ],
    },
]


# ====================================================================
# SECTION 5 — SOLVER                        (was solver.py)
# ====================================================================
def _min_thickness(l, condition, fy):
    h = l / THICKNESS_DENOM[condition]
    if not (415.0 <= fy <= 420.0):
        h *= (0.4 + fy / 700.0)
    return round_up_to(h, 25.0)


def _solve_a_from_Mu(Mu_kNm, fc, b, d):
    """Solve Mu = phi*0.85*fc*a*b*(d - a/2) for a."""
    if Mu_kNm is None or Mu_kNm <= 0:
        return None
    K = Mu_kNm * 1e6 / (PHI_FLEX * 0.85 * fc * b)
    disc = d * d - 2.0 * K
    if disc < 0:
        return None
    return d - math.sqrt(disc)


def solve_design(p):
    l, b = p["l"], p["b"]
    fc, fy, fyt = p["fc"], p["fy"], p["fyt"]
    db, dt, cc = p["db"], p["dt"], p["cc"]
    gamma_c, LL = p["gamma_c"], p["LL"]
    cond = p["condition"]
    out = dict(p)

    # ---- Step 1 — Minimum thickness ----
    h = _min_thickness(l, cond, fy)
    out["h"] = h

    # ---- Step 2 — Self weight & factored load ----
    DL = gamma_c * h / 1000.0
    Wu = 1.2 * DL + 1.6 * LL
    out["DL"] = DL
    out["Wu"] = Wu

    # ---- Step 3 — Moments (Table 406.5.2) ----
    lm = l / 1000.0
    pos_d, neg_d = MOMENT_DENOM[cond]
    Mu_pos = Wu * lm * lm / pos_d if pos_d else None
    Mu_neg = Wu * lm * lm / neg_d if neg_d else None
    out["Mu_pos"] = Mu_pos
    out["Mu_neg"] = Mu_neg
    candidates = [m for m in (Mu_pos, Mu_neg) if m is not None]
    Mu_design = max(candidates) if candidates else 0.0
    out["Mu_design"] = Mu_design
    out["Mu_governs"] = ("negative (support)" if Mu_neg is not None
                         and Mu_neg == Mu_design else "positive (midspan)")

    # ---- Step 4 — Effective depth ----
    d = h - cc - db / 2.0
    out["d"] = d

    # ---- Step 5 — Fictitious depth a ----
    a = _solve_a_from_Mu(Mu_design, fc, b, d)
    out["a"] = a

    # ---- Step 6 — Neutral axis & steel yielding ----
    b1 = beta1(fc)
    c = a / b1 if a else None
    fs = 600.0 * (d - c) / c if c else None
    out["b1"] = b1
    out["c"] = c
    out["fs"] = fs
    out["yields"] = (fs is not None and fs > fy)

    # ---- Step 7 — Steel area (C = T) ----
    As = 0.85 * fc * a * b / fy if a else None
    out["As"] = As

    # ---- Step 8 — Reinforcement ratio & design As ----
    rho_act = As / (b * d) if As else 0.0
    rho_min = max(1.4 / fy, 0.25 * math.sqrt(fc) / fy)
    rho_max = (3.0 / 8.0) * (0.85 * b1 * fc / fy)
    out["rho_act"] = rho_act
    out["rho_min"] = rho_min
    out["rho_max"] = rho_max
    if rho_act < rho_min:
        As_design = rho_min * b * d
        out["governs"] = "min"
    elif rho_act > rho_max:
        As_design = rho_max * b * d
        out["governs"] = "max"
    else:
        As_design = As
        out["governs"] = "act"
    out["As_design"] = As_design

    # ---- Step 9 — Main bar spacing ----
    Abar = math.pi / 4.0 * db * db
    S_req_raw = Abar / As_design * 1000.0
    S_req = round_down_to(S_req_raw, 10.0)
    out["Abar"] = Abar
    out["S_req_raw"] = S_req_raw
    out["S_req"] = S_req

    # ---- Step 10 — Min & max spacing ----
    S_min = 0.0020 * (a if a is not None else 0.0) * b
    S_max = min(3.0 * h, 450.0)
    out["S_min"] = S_min
    out["S_max"] = S_max
    out["main_ok"] = S_req <= S_max

    # ---- Step 11 — Temperature reinforcement & spacing ----
    if fyt < 420.0:
        rho_t = 0.0020
    else:
        rho_t = max(0.0018 * 420.0 / fyt, 0.0014)
    As_t = rho_t * b * h
    Abar_t = math.pi / 4.0 * dt * dt
    S_t_raw = Abar_t / As_t * 1000.0
    S_t = round_down_to(S_t_raw, 10.0)
    S_t_max = min(5.0 * h, 450.0)
    out["rho_t"] = rho_t
    out["As_t"] = As_t
    out["Abar_t"] = Abar_t
    out["S_t_raw"] = S_t_raw
    out["S_t"] = S_t
    out["S_t_max"] = S_t_max
    out["temp_ok"] = S_t <= S_t_max

    return out


def solve_analysis(p):
    l, b = p["l"], p["b"]
    fc, fy = p["fc"], p["fy"]
    db, S, cc = p["db"], p["S"], p["cc"]
    gamma_c, h = p["gamma_c"], p["h"]
    cond = p["condition"]
    mtype = p.get("moment_type", "Positive (midspan)")
    out = dict(p)

    # ---- Step 1 — Steel area from bar spacing ----
    Abar = math.pi / 4.0 * db * db
    As = Abar / S * 1000.0
    out["Abar"] = Abar
    out["As"] = As

    # ---- Step 2 — Effective depth ----
    d = h - cc - db / 2.0
    out["d"] = d

    # ---- Step 3 — Reinforcement ratio ----
    rho_act = As / (b * d)
    rho_min = max(1.4 / fy, 0.25 * math.sqrt(fc) / fy)
    b1 = beta1(fc)
    rho_max = (3.0 / 8.0) * (0.85 * b1 * fc / fy)
    out["rho_act"] = rho_act
    out["rho_min"] = rho_min
    out["rho_max"] = rho_max
    out["b1"] = b1

    # ---- Step 4 — Fictitious depth a from C = T ----
    a = As * fy / (0.85 * fc * b)
    out["a"] = a

    # ---- Step 5 — Neutral axis & steel yielding ----
    c = a / b1
    fs = 600.0 * (d - c) / c if c else 0.0
    out["c"] = c
    out["fs"] = fs
    out["yields"] = fs > fy

    # ---- Step 6 — Flexural capacity ----
    Mu = PHI_FLEX * As * fy * (d - a / 2.0) / 1e6  # kN·m
    out["Mu"] = Mu

    # ---- Step 7 — Back out Wu from the coefficient ----
    pos_d, neg_d = MOMENT_DENOM[cond]
    denom = neg_d if mtype == MT_NEG and neg_d else pos_d
    out["denom_used"] = denom
    lm = l / 1000.0
    Wu = Mu * denom / (lm * lm)
    out["Wu"] = Wu

    # ---- Step 8 — Live load capacity ----
    DL = gamma_c * h / 1000.0
    LL = (Wu - 1.2 * DL) / 1.6
    out["DL"] = DL
    out["LL"] = LL

    return out


# ====================================================================
# SECTION 6 — RANDOMIZER                    (was randomizer.py)
# ====================================================================
def _sane_design(sol):
    if not (100.0 <= sol["h"] <= 400.0):
        return False
    if sol["d"] <= 40.0:
        return False
    if sol["a"] is None or sol["a"] <= 0 or sol["a"] >= sol["d"]:
        return False
    if sol["rho_act"] > sol["rho_max"]:
        return False
    return True


def random_design_problem(max_tries=400):
    for _ in range(max_tries):
        p = {
            "l":   random.choice(SPAN_OPTIONS),
            "b":   1000.0,
            "fc":  random.choice(FC_OPTIONS),
            "fy":  random.choice(FY_MAIN_OPTIONS),
            "fyt": random.choice(FY_TEMP_OPTIONS),
            "db":  random.choice(MAIN_BAR_OPTIONS),
            "dt":  random.choice(TEMP_BAR_OPTIONS),
            "cc":  random.choice(COVER_OPTIONS),
            "gamma_c": GAMMA_C_DEFAULT,
            "LL":  random.uniform(*LL_RANGE),
            "condition": random.choice(SUPPORT_CONDITIONS),
        }
        try:
            sol = solve_design(p)
        except Exception:
            continue
        if _sane_design(sol):
            return p
    # fallback
    return {
        "l": 4000.0, "b": 1000.0,
        "fc": 21.0, "fy": 415.0, "fyt": 276.0,
        "db": 12.0, "dt": 10.0, "cc": 20.0,
        "gamma_c": GAMMA_C_DEFAULT, "LL": 4.0,
        "condition": SC_SS,
    }


def random_analysis_problem(max_tries=400):
    """Generate a problem whose As lands in the valid range."""
    for _ in range(max_tries):
        base = random_design_problem()
        h = None
        try:
            d_sol = solve_design(base)
            h = d_sol["h"]
        except Exception:
            continue
        db = random.choice([10.0, 12.0, 16.0])
        d_eff = h - base["cc"] - db / 2.0
        rho_min = max(1.4 / base["fy"], 0.25 * (base["fc"] ** 0.5) / base["fy"])
        b1 = 0.85 if base["fc"] <= 28 else max(0.65, 0.85 - 0.05 * (base["fc"] - 28) / 7)
        rho_max = (3.0 / 8.0) * (0.85 * b1 * base["fc"] / base["fy"])
        rho_target = random.uniform(0.6 * rho_min, 0.85 * rho_max)
        As_target = rho_target * 1000.0 * d_eff
        Abar = 3.14159265 / 4.0 * db * db
        S = Abar / As_target * 1000.0
        if not (80.0 <= S <= 300.0):
            continue
        S = round(S / 10.0) * 10.0
        cond = random.choice(SUPPORT_CONDITIONS)
        if cond == SC_SS:
            mtype = MT_POS
        elif cond == SC_CANT:
            mtype = "Negative (support)"
        else:
            mtype = random.choice(MOMENT_TYPES)
        p = dict(base)
        p["db"] = db
        p["S"] = S
        p["h"] = h
        p["condition"] = cond
        p["moment_type"] = mtype
        try:
            sol = solve_analysis(p)
        except Exception:
            continue
        if sol["LL"] > 0.5 and sol["rho_act"] < sol["rho_max"]:
            return p
    # fallback
    return {
        "l": 4000.0, "b": 1000.0,
        "fc": 21.0, "fy": 415.0,
        "db": 12.0, "cc": 20.0,
        "gamma_c": GAMMA_C_DEFAULT,
        "h": 150.0, "S": 200.0,
        "condition": SC_SS, "moment_type": MT_POS,
    }


def random_problem(mode, branch=None):
    if mode == MODE_DESIGN:
        return random_design_problem()
    return random_analysis_problem()


# ====================================================================
# SECTION 7 — HISTORY PANEL                 (was ui/history.py)
# ====================================================================
class HistoryPanel(tk.Frame):
    def __init__(self, parent, width=260):
        super().__init__(parent, width=width, bg=BG_HISTORY,
                         highlightthickness=1, highlightbackground=BORDER_PANEL)
        self.pack_propagate(False)

        tk.Label(self, text="HISTORY", font=FONT_SECTION,
                 bg=BG_HISTORY).pack(anchor="w", padx=8, pady=(8, 4))

        wrap = tk.Frame(self, bg=BG_HISTORY)
        wrap.pack(fill="both", expand=True, padx=4, pady=4)

        self.text = tk.Text(wrap, width=32, wrap="word", bg="#ffffff",
                            relief="flat", font=FONT_HIST)
        sb = ttk.Scrollbar(wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_config("green",  foreground=FG_OK)
        self.text.tag_config("yellow", foreground=FG_WARN)
        self.text.tag_config("gray",   foreground=FG_HINT)
        self.text.tag_config("red",    foreground=FG_ERR)
        self.text.tag_config("head",   foreground=FG_HEAD,
                             font=("Consolas", 9, "bold"))
        self.text.configure(state="disabled")

    def log(self, text, tag="gray"):
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n", tag)
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# ====================================================================
# SECTION 8 — PAGES                         (were ui/pages/*.py)
# ====================================================================

# ----- 8a. Setup page (was ui/pages/setup.py) -----
class SetupPage:
    TITLE = "Setup — Given / Properties"

    @staticmethod
    def build(app):
        f = app.step_area

        top = tk.Frame(f, bg=BG_MAIN)
        top.pack(anchor="w", pady=(0, 10))

        tk.Label(top, text="Mode:", bg=BG_MAIN,
                 font=FONT_SECTION).pack(side="left")
        app.mode_var = app._mk_var("setup.mode", app.mode)
        cb = ttk.Combobox(top, textvariable=app.mode_var, values=MODES,
                          width=12, state="readonly")
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: app.on_mode_change())

        tk.Button(top, text="🎲 Randomize", bg=BG_BTN_WARM, width=13,
                  command=app._randomize).pack(side="left", padx=6)
        tk.Button(top, text="▶ Start Review", bg=BG_BTN_GO, width=13,
                  command=app._start_review).pack(side="left", padx=6)

        tk.Label(f, text="Given / Properties (editable)",
                 font=FONT_SECTION, bg=BG_MAIN).pack(anchor="w", pady=(6, 4))

        grid = tk.Frame(f, bg=BG_MAIN)
        grid.pack(anchor="w", pady=(0, 8))

        if app.mode == MODE_DESIGN:
            fields = [
                ("Span l (mm)",        "l"),
                ("Strip width b (mm)", "b"),
                ("f'c (MPa)",          "fc"),
                ("fy main (MPa)",      "fy"),
                ("fyt temp (MPa)",     "fyt"),
                ("db main (mm)",       "db"),
                ("dt temp (mm)",       "dt"),
                ("Cover cc (mm)",      "cc"),
                ("γc (kN/m³)",         "gamma_c"),
                ("LL (kPa)",           "LL"),
            ]
        else:
            fields = [
                ("Span l (mm)",           "l"),
                ("Strip width b (mm)",    "b"),
                ("Slab thickness h (mm)", "h"),
                ("f'c (MPa)",             "fc"),
                ("fy (MPa)",              "fy"),
                ("db bar (mm)",           "db"),
                ("Bar spacing S (mm)",    "S"),
                ("Cover cc (mm)",         "cc"),
                ("γc (kN/m³)",            "gamma_c"),
            ]

        app.prop_vars = {}
        for i, (label, key) in enumerate(fields):
            r, c = divmod(i, 2)
            tk.Label(grid, text=label, bg=BG_MAIN, font=FONT_LABEL
                     ).grid(row=r, column=c * 2, sticky="e", padx=(0, 6), pady=3)
            v = app._mk_var(f"prop.{key}", f"{app.problem[key]:.4g}")
            e = tk.Entry(grid, textvariable=v, width=14,
                         justify="center", font=FONT_ENTRY)
            e.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 20), pady=3)
            app.prop_vars[key] = v

        r = (len(fields) + 1) // 2
        tk.Label(grid, text="Support condition", bg=BG_MAIN, font=FONT_LABEL
                 ).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
        app.cond_var = app._mk_var("prop.condition", app.problem["condition"])
        cb2 = ttk.Combobox(grid, textvariable=app.cond_var,
                           values=SUPPORT_CONDITIONS, width=22, state="readonly")
        cb2.grid(row=r, column=1, columnspan=3, sticky="w", pady=3)

        if app.mode != MODE_DESIGN:
            r += 1
            tk.Label(grid, text="Moment type", bg=BG_MAIN, font=FONT_LABEL
                     ).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
            app.mt_var = app._mk_var("prop.moment_type", app.problem["moment_type"])
            cb3 = ttk.Combobox(grid, textvariable=app.mt_var,
                               values=MOMENT_TYPES, width=22, state="readonly")
            cb3.grid(row=r, column=1, columnspan=3, sticky="w", pady=3)

        tk.Label(f, text="Edit fields, then click Start Review. Or Randomize first.",
                 bg=BG_MAIN, fg=FG_HINT, font=("Segoe UI", 9, "italic")
                 ).pack(anchor="w", pady=(8, 0))


# ----- 8b. Generic step page (was ui/pages/generic.py) -----
class StepPage:
    TITLE = "Step"

    @staticmethod
    def _current_step(app):
        return app.current_step

    @staticmethod
    def build(app):
        step = StepPage._current_step(app)
        f = app.step_area
        f.winfo_children()[0].configure(text=step["title"])  # replace title label

        for note in step.get("notes", []):
            text = note(app) if callable(note) else note
            tk.Label(f, text=text, bg=BG_MAIN, fg=FG_LABEL,
                     anchor="w", justify="left").pack(anchor="w", pady=(0, 2))

        tk.Frame(f, bg=BG_MAIN, height=8).pack(anchor="w")

        for key, label, unit, _nd in step["fields"]:
            sol = app.solution or {}
            if key in sol and sol[key] is None:
                continue
            app.std_entry(f, f"{step['id']}.{key}", label + " =", unit)

    @staticmethod
    def check(app):
        step = StepPage._current_step(app)
        expected = {}
        for key, _lbl, _u, _nd in step["fields"]:
            sol = app.solution or {}
            if key in sol and sol[key] is not None:
                expected[f"{step['id']}.{key}"] = sol[key]
        ok, msgs = app.check_entries(expected, app.page)
        if ok:
            app._set_status(f"✓ {step['title']} correct!", FG_OK)
            app.history.log(f"{step['title']} correct.", "green")
            app.passed.add(app.page)
            app.revealed.discard(app.page)
        else:
            app._set_status(f"✗ {step['title']} has errors.", FG_ERR)
            app.history.log(f"{step['title']} attempted — errors:", "yellow")
            for m in msgs:
                app.history.log("  " + m, "yellow")
            messagebox.showwarning(step["title"], "\n".join(msgs))

    @staticmethod
    def reveal(app):
        step = StepPage._current_step(app)
        if step is None:
            app._set_status("No active step to reveal.", FG_ERR)
            return

        sol = app.solution or {}
        filled = 0
        missing = []

        for key, _lbl, _u, nd in step["fields"]:
            if key not in sol or sol[key] is None:
                continue
            entry_key = f"{step['id']}.{key}"
            ok = app._set_entry(entry_key, fmt(sol[key], nd))
            if ok:
                filled += 1
            else:
                missing.append(entry_key)

        if filled:
            app.revealed.add(app.page)
            app.history.log(f"{step['title']} revealed ({filled} field(s)).", "yellow")
            app._set_status("Answers revealed.", FG_WARN)
        else:
            app._set_status("Nothing to reveal on this step.", FG_WARN)

        for k in missing:
            app.history.log(f"  ! entry not found: {k}", "red")


# ----- 8c. Summary page (was ui/pages/summary.py) -----
def _recap(f, lines):
    tk.Label(f, text="Recap:", font=FONT_SECTION,
             bg=BG_MAIN).pack(anchor="w", pady=(14, 4))
    txt = tk.Text(f, width=82, height=min(26, len(lines) + 2),
                  font=("Consolas", 9), bg="#ffffff")
    txt.pack(anchor="w", fill="x")
    for ln in lines:
        txt.insert("end", ln + "\n")
    txt.configure(state="disabled")


class SummaryPage:
    TITLE = "Summary"

    @staticmethod
    def build(app):
        f = app.step_area
        s = app.solution
        if not s:
            tk.Label(f, text="No solution yet. Go to Setup and click Start Review.",
                     bg=BG_MAIN, fg=FG_ERR).pack(anchor="w")
            return

        if app.mode == MODE_DESIGN:
            SummaryPage._build_design_summary(app, f, s)
        else:
            SummaryPage._build_analysis_summary(app, f, s)

        tk.Button(f, text="Copy Summary to Clipboard", bg=BG_BTN_NEU,
                  command=app.copy_summary).pack(anchor="w", pady=(10, 0))

    @staticmethod
    def _build_design_summary(app, f, s):
        p = app.problem

        box = tk.Frame(f, bg="#ffffff", highlightthickness=2,
                       highlightbackground=FG_OK)
        box.pack(anchor="w", pady=8)
        tk.Label(box, text="FINAL DESIGN", font=FONT_BIG,
                 bg="#ffffff").pack(padx=16, pady=(12, 6))

        def line(lbl, val):
            row = tk.Frame(box, bg="#ffffff")
            row.pack(anchor="w", padx=16, pady=2)
            tk.Label(row, text=lbl, font=FONT_LABEL, bg="#ffffff",
                     width=24, anchor="e").pack(side="left")
            tk.Label(row, text=val, font=("Consolas", 11, "bold"),
                     fg=FG_OK, bg="#ffffff").pack(side="left", padx=8)

        line("Slab thickness h:",  f"{s['h']:.0f} mm")
        line("Governing moment:",  f"{s['Mu_governs']} = {s['Mu_design']:.3f} kN·m")
        line("Design governs by:", f"rho_{s['governs']}")
        line(f"Main bars ({p['db']:.0f} mm dia):",
             f"@ {s['S_req']:.0f} mm O.C.  (As = {s['As_design']:.1f} mm^2/m)")
        line(f"Temperature bars ({p['dt']:.0f} mm dia):",
             f"@ {s['S_t']:.0f} mm O.C.  (Ast = {s['As_t']:.1f} mm^2/m)")

        if not s["main_ok"]:
            tk.Label(f, text=f"Warning: main Sreq ({s['S_req']:.0f}) > Smax ({s['S_max']:.0f}).",
                     bg=BG_MAIN, fg=FG_WARN).pack(anchor="w", pady=(4, 0))
        if not s["temp_ok"]:
            tk.Label(f, text=f"Warning: temp St ({s['S_t']:.0f}) > Smax,t ({s['S_t_max']:.0f}).",
                     bg=BG_MAIN, fg=FG_WARN).pack(anchor="w", pady=(4, 0))

        mu_pos_str = f"{s['Mu_pos']:.3f}" if s["Mu_pos"] is not None else "(N/A)"
        mu_neg_str = f"{s['Mu_neg']:.3f}" if s["Mu_neg"] is not None else "(N/A)"
        pos_line = "+Mu = " + mu_pos_str + " kN.m"
        neg_line = "-Mu = " + mu_neg_str + " kN.m"

        _recap(f, [
            "DESIGN RECAP",
            f"l = {s['l']:.0f} mm   b = {s['b']:.0f} mm   condition = {s['condition']}",
            f"f'c = {s['fc']:.0f} MPa   fy = {s['fy']:.0f} MPa   fyt = {s['fyt']:.0f} MPa",
            f"db = {s['db']:.0f} mm   dt = {s['dt']:.0f} mm   cc = {s['cc']:.0f} mm",
            f"gamma_c = {s['gamma_c']:.2f} kN/m^3   LL = {s['LL']:.3f} kPa",
            "",
            f"h  = {s['h']:.0f} mm",
            f"DL = {s['DL']:.3f} kPa   Wu = {s['Wu']:.3f} kN/m",
            pos_line,
            neg_line,
            f"d  = {s['d']:.0f} mm   a = {s['a']:.3f}   c = {s['c']:.3f}",
            f"fs = {s['fs']:.1f} MPa   yields = {s['yields']}",
            f"As = {s['As']:.3f} mm^2   rho_act = {s['rho_act']:.5f}   "
            f"rho_min = {s['rho_min']:.5f}   rho_max = {s['rho_max']:.5f}",
            f"governs = {s['governs']}   As_design = {s['As_design']:.3f} mm^2",
            f"Sreq = {s['S_req']:.0f} mm   Smin = {s['S_min']:.3f}   Smax = {s['S_max']:.0f}",
            "",
            f"rho_t = {s['rho_t']:.5f}   Ast = {s['As_t']:.3f} mm^2",
            f"St = {s['S_t']:.0f} mm   Smax,t = {s['S_t_max']:.0f} mm",
        ])

    @staticmethod
    def _build_analysis_summary(app, f, s):
        p = app.problem

        box = tk.Frame(f, bg="#ffffff", highlightthickness=2,
                       highlightbackground=FG_OK)
        box.pack(anchor="w", pady=8)
        tk.Label(box, text="FINAL ANALYSIS", font=FONT_BIG,
                 bg="#ffffff").pack(padx=16, pady=(12, 6))

        def line(lbl, val):
            row = tk.Frame(box, bg="#ffffff")
            row.pack(anchor="w", padx=16, pady=2)
            tk.Label(row, text=lbl, font=FONT_LABEL, bg="#ffffff",
                     width=24, anchor="e").pack(side="left")
            tk.Label(row, text=val, font=("Consolas", 11, "bold"),
                     fg=FG_OK, bg="#ffffff").pack(side="left", padx=8)

        line("Moment capacity Mu:", f"{s['Mu']:.3f} kN.m")
        line("Factored load Wu:",   f"{s['Wu']:.3f} kN/m")
        line("Live load capacity:", f"{s['LL']:.3f} kPa")

        if not (s["rho_min"] <= s["rho_act"] <= s["rho_max"]):
            tk.Label(f, text="Warning: steel ratio is outside the recommended range.",
                     bg=BG_MAIN, fg=FG_WARN).pack(anchor="w", pady=(4, 0))

        _recap(f, [
            "ANALYSIS RECAP",
            f"l = {s['l']:.0f} mm   b = {s['b']:.0f} mm   h = {s['h']:.0f} mm",
            f"f'c = {s['fc']:.0f} MPa   fy = {s['fy']:.0f} MPa   cc = {s['cc']:.0f} mm",
            f"db = {s['db']:.0f} mm   S = {s['S']:.0f} mm O.C.",
            f"gamma_c = {s['gamma_c']:.2f} kN/m^3   condition = {s['condition']}",
            f"moment type = {s['moment_type']}   denom used = {s['denom_used']:.0f}",
            "",
            f"Abar = {s['Abar']:.3f} mm^2   As = {s['As']:.3f} mm^2",
            f"d  = {s['d']:.0f} mm",
            f"rho_act = {s['rho_act']:.5f}   rho_min = {s['rho_min']:.5f}   "
            f"rho_max = {s['rho_max']:.5f}",
            f"a = {s['a']:.3f} mm   c = {s['c']:.3f} mm   beta1 = {s['b1']:.3f}",
            f"fs = {s['fs']:.1f} MPa   yields = {s['yields']}",
            f"Mu = {s['Mu']:.3f} kN.m",
            f"Wu = {s['Wu']:.3f} kN/m   DL = {s['DL']:.3f} kPa",
            f"LL = {s['LL']:.3f} kPa",
        ])

    @staticmethod
    def check(app):
        pass

    @staticmethod
    def reveal(app):
        pass


# ====================================================================
# SECTION 9 — MAIN WINDOW                   (was ui/app.py)
# ====================================================================
_PROP_KEYS_DESIGN   = ["l", "b", "fc", "fy", "fyt", "db", "dt", "cc",
                       "gamma_c", "LL"]
_PROP_KEYS_ANALYSIS = ["l", "b", "h", "fc", "fy", "db", "S", "cc", "gamma_c"]


class SlabReviewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(860, min(1300, sw - 40))
        h = max(580, min(860, sh - 120))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(860, w), min(580, h))

        # ---- state ----
        self.problem = dict(DEFAULT_PROBLEM)
        self.mode = MODE_DESIGN
        self.steps = DESIGN_STEPS
        self.current_step = None
        self.solution = None
        self.page = 0
        self.entries = {}
        self.user_inputs = {}
        self.passed = set()
        self.revealed = set()
        self._hist_visible = w >= 1120

        self._build_layout()
        self._build_top_bar()
        self._build_nav()
        self._show_page(0)

        if not self._hist_visible:
            self.history.pack_forget()

        self.bind("<Configure>", lambda e: self.after(200, self._refresh_top_bar)
                  if e.widget is self else None)
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

    # ================================================================
    # layout
    # ================================================================
    def _build_layout(self):
        self.topbar = tk.Frame(self, bg=BG_TOP_BAR,
                               highlightthickness=1, highlightbackground=BORDER_MAIN)
        self.topbar.pack(side="top", fill="x")

        self.bottom = tk.Frame(self, bg=BG_BOTTOM,
                               highlightthickness=1, highlightbackground="#bbbbbb")
        self.bottom.pack(side="bottom", fill="x")

        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)

        self.left = tk.Frame(outer, bg=BG_MAIN)
        self.left.pack(side="left", fill="both", expand=True)

        self.history = HistoryPanel(outer, width=260)
        self.history.pack(side="right", fill="y")

        self.step_canvas = tk.Canvas(self.left, bg=BG_MAIN,
                                     highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(self.left, orient="vertical",
                            command=self.step_canvas.yview)
        self.step_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.step_canvas.pack(side="left", fill="both", expand=True)

        self.step_area = tk.Frame(self.step_canvas, bg=BG_MAIN)
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

    # ================================================================
    # top bar
    # ================================================================
    def _build_top_bar(self):
        tk.Label(self.topbar, text="GIVEN  /  PROPERTIES",
                 font=FONT_LABEL_B, bg=BG_TOP_BAR, anchor="w"
                 ).pack(fill="x", padx=10, pady=(6, 0))
        self.given_row = tk.Frame(self.topbar, bg=BG_TOP_BAR)
        self.given_row.pack(fill="x", padx=10, pady=(0, 6))
        self._refresh_top_bar()

    def _refresh_top_bar(self):
        for w in self.given_row.winfo_children():
            w.destroy()
        p = self.problem
        cond_abbrev = {
            "Simply Supported":    "SS",
            "One End Continuous":  "1-End Cont.",
            "Both End Continuous": "Both-End Cont.",
            "Cantilever":          "Cantilever",
        }.get(p.get("condition", ""), p.get("condition", ""))

        if self.mode == MODE_DESIGN:
            items = [
                ("l", f"{p['l']:.0f} mm"),
                ("b", f"{p['b']:.0f} mm"),
                ("f'c", f"{p['fc']:.0f} MPa"),
                ("fy", f"{p['fy']:.0f} MPa"),
                ("fyt", f"{p['fyt']:.0f} MPa"),
                ("db", f"{p['db']:.0f} mm"),
                ("dt", f"{p['dt']:.0f} mm"),
                ("cc", f"{p['cc']:.0f} mm"),
                ("γc", f"{p['gamma_c']:.1f}"),
                ("LL", f"{p['LL']:.3f} kPa"),
                ("Support", cond_abbrev),
            ]
        else:
            items = [
                ("l", f"{p['l']:.0f} mm"),
                ("b", f"{p['b']:.0f} mm"),
                ("h", f"{p['h']:.0f} mm"),
                ("f'c", f"{p['fc']:.0f} MPa"),
                ("fy", f"{p['fy']:.0f} MPa"),
                ("db", f"{p['db']:.0f} mm"),
                ("S", f"{p['S']:.0f} mm"),
                ("cc", f"{p['cc']:.0f} mm"),
                ("γc", f"{p['gamma_c']:.1f}"),
                ("Support", cond_abbrev),
                ("Moment", p.get("moment_type", "")),
            ]
        n_given = len(items)

        if self.solution:
            s = self.solution
            unlocked = self.passed | self.revealed
            extras = []
            if self.mode == MODE_DESIGN:
                for i, st in enumerate(self.steps, start=1):
                    if i not in unlocked:
                        continue
                    for key, _lbl, _u, _nd in st["fields"]:
                        if key in s and s[key] is not None:
                            extras.append((key, fmt(s[key],
                                0 if key in ("h", "d", "S_req", "S_max", "S_t", "S_t_max") else 3)))
            else:
                for i, st in enumerate(self.steps, start=1):
                    if i not in unlocked:
                        continue
                    for key, _lbl, _u, _nd in st["fields"]:
                        if key in s and s[key] is not None:
                            extras.append((key, fmt(s[key], 0 if key == "d" else 3)))
            items = items + extras

        width = self.winfo_width() or self.winfo_screenwidth()
        usable = width - (280 if self._hist_visible else 40)
        usable = max(400, usable)
        cols = max(4, min(len(items), usable // 118))

        for i, (label, val) in enumerate(items):
            r, c = divmod(i, cols)
            is_extra = i >= n_given
            fg_lbl = FG_EXTRA if is_extra else FG_LABEL
            fg_val = FG_EXTRA if is_extra else FG_VALUE
            box = tk.Frame(self.given_row, bg=BG_TOP_BAR)
            box.grid(row=r, column=c, padx=4, pady=1, sticky="w")
            tk.Label(box, text=label, font=FONT_LABEL_B, bg=BG_TOP_BAR,
                     fg=fg_lbl).pack(anchor="w")
            tk.Label(box, text=val,
                     font=(FONT_VALUE[0], FONT_VALUE[1],
                           "bold" if is_extra else "normal"),
                     bg=BG_TOP_BAR, fg=fg_val).pack(anchor="w")

    # ================================================================
    # nav bar
    # ================================================================
    def _build_nav(self):
        bar = tk.Frame(self.bottom, bg=BG_BOTTOM)
        bar.pack(fill="x", padx=8, pady=6)

        tk.Button(bar, text="History", width=9,
                  command=self.toggle_history).pack(side="right", padx=2)
        tk.Button(bar, text="Copy Summary", width=13,
                  command=self.copy_summary).pack(side="right", padx=2)

        self.btn_back = tk.Button(bar, text="◀ Back", width=8, command=self.go_back)
        self.btn_back.pack(side="left", padx=2)
        self.btn_check = tk.Button(bar, text="✓ Check", width=8,
                                   bg=BG_BTN_GO, command=self.check_current)
        self.btn_check.pack(side="left", padx=2)
        self.btn_reveal = tk.Button(bar, text="Reveal", width=8,
                                    bg=BG_BTN_WARM, command=self.reveal_current)
        self.btn_reveal.pack(side="left", padx=2)
        self.btn_next = tk.Button(bar, text="Next ▶", width=8,
                                  bg=BG_BTN_NEU, command=self.go_next)
        self.btn_next.pack(side="left", padx=2)
        tk.Button(bar, text="Reset", width=8,
                  command=self.reset_all).pack(side="left", padx=(10, 2))

        self.status = tk.Label(bar, text="", bg=BG_BOTTOM, anchor="w",
                               font=("Segoe UI", 9, "italic"))
        self.status.pack(side="left", padx=8, fill="x", expand=True)

    # ================================================================
    # page navigation
    # ================================================================
    def _clear_step_area(self):
        for w in self.step_area.winfo_children():
            w.destroy()
        self.entries.clear()

    def _total_pages(self):
        return 1 + len(self.steps) + 1  # setup + steps + summary

    def _show_page(self, n):
        self.page = n
        self._clear_step_area()
        self.current_step = None

        if n == 0:
            title = SetupPage.TITLE
            builder = SetupPage
        elif n == self._total_pages() - 1:
            title = SummaryPage.TITLE
            builder = SummaryPage
        else:
            self.current_step = self.steps[n - 1]
            title = self.current_step["title"]
            builder = StepPage

        tk.Label(self.step_area, text=title, font=FONT_TITLE,
                 bg=BG_MAIN, anchor="w").pack(anchor="w", pady=(0, 8))
        try:
            builder.build(self)
        except Exception as e:
            tk.Label(self.step_area, text=f"Error building page: {e}",
                     bg=BG_MAIN, fg=FG_ERR).pack(anchor="w")

        try:
            self.step_canvas.yview_moveto(0)
        except Exception:
            pass

        self.btn_back.configure(state=("normal" if n > 0 else "disabled"))
        self.btn_next.configure(
            state=("normal" if n < self._total_pages() - 1 else "disabled"))
        checkable = 1 <= n <= len(self.steps)
        self.btn_check.configure(state=("normal" if checkable else "disabled"))
        self.btn_reveal.configure(state=("normal" if checkable else "disabled"))

    def go_back(self):
        if self.page > 0:
            self._show_page(self.page - 1)

    def go_next(self):
        if 1 <= self.page <= len(self.steps):
            if self.page not in self.passed and self.page not in self.revealed:
                if not messagebox.askyesno("Skip check?",
                        "You haven't checked this step. Continue anyway?"):
                    return
        if self.page < self._total_pages() - 1:
            self._show_page(self.page + 1)

    # ================================================================
    # setup actions
    # ================================================================
    def on_mode_change(self):
        new_mode = self.mode_var.get()
        if new_mode == self.mode:
            return
        self.mode = new_mode
        self.steps = DESIGN_STEPS if new_mode == MODE_DESIGN else ANALYSIS_STEPS
        if new_mode == MODE_ANALYSIS:
            self.problem.setdefault("h", 150.0)
            self.problem.setdefault("S", 200.0)
            self.problem.setdefault("moment_type", "Positive (midspan)")
        self._show_page(0)

    def _randomize(self):
        try:
            p = random_problem(self.mode)
        except Exception as e:
            messagebox.showerror("Randomizer error", f"Could not generate: {e}")
            return
        self.problem.update(p)
        for key in self._active_prop_keys():
            if key in self.prop_vars:
                self.prop_vars[key].set(f"{p[key]:.4g}")
        if hasattr(self, "cond_var"):
            self.cond_var.set(p["condition"])
        if hasattr(self, "mt_var") and "moment_type" in p:
            self.mt_var.set(p["moment_type"])
        self.solution = None
        self._refresh_top_bar()
        self.history.log(f"Randomized ({self.mode}).", "gray")
        self._set_status("New problem generated. Click Start Review.", FG_EXTRA)

    def _active_prop_keys(self):
        return _PROP_KEYS_DESIGN if self.mode == MODE_DESIGN else _PROP_KEYS_ANALYSIS

    def _start_review(self):
        try:
            for key in self._active_prop_keys():
                self.problem[key] = float(self.prop_vars[key].get())
            self.problem["condition"] = self.cond_var.get()
            if self.mode == MODE_ANALYSIS and hasattr(self, "mt_var"):
                self.problem["moment_type"] = self.mt_var.get()
        except (ValueError, KeyError) as e:
            messagebox.showerror("Invalid", f"Properties must be numeric: {e}")
            return

        if self.mode == MODE_DESIGN:
            self.solution = solve_design(self.problem)
        else:
            self.solution = solve_analysis(self.problem)

        if self.solution["d"] <= 0:
            messagebox.showerror("Invalid",
                "Effective depth is not positive. Check h, cc, and db.")
            return

        for k in list(self.user_inputs.keys()):
            if len(k) > 2 and k[0] in ("d", "a") and k[1].isdigit():
                del self.user_inputs[k]

        self.passed.clear()
        self.revealed.clear()

        self.history.log("— Review started —", "head")
        self.history.log(f"Mode: {self.mode}", "gray")
        self.history.log(f"Support: {self.problem['condition']}", "gray")
        self._refresh_top_bar()
        self._show_page(1)

    def reset_all(self):
        if messagebox.askyesno("Reset", "Clear all progress and start fresh?"):
            self.user_inputs.clear()
            self.passed.clear()
            self.revealed.clear()
            self.history.clear()
            self.solution = None
            self._refresh_top_bar()
            self._show_page(0)

    # ================================================================
    # check / reveal
    # ================================================================
    def check_current(self):
        if not (1 <= self.page <= len(self.steps)):
            return
        StepPage.check(self)
        self._refresh_top_bar()

    def reveal_current(self):
        if not (1 <= self.page <= len(self.steps)):
            return
        StepPage.reveal(self)
        self._refresh_top_bar()

    def copy_summary(self):
        if not self.solution:
            messagebox.showinfo("Nothing to copy", "Start a review first.")
            return
        s = self.solution
        lines = [f"RCD One-Way Slab — {self.mode} Summary", "=" * 44]
        for k, v in s.items():
            if k in ("condition",):
                lines.append(f"{k}: {v}")
            elif isinstance(v, float):
                lines.append(f"{k} = {v:.6g}")
            elif v is None:
                lines.append(f"{k} = (N/A)")
            else:
                lines.append(f"{k}: {v}")
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        self._set_status("Summary copied to clipboard.", FG_OK)
        self.history.log("Summary copied to clipboard.", "gray")

    # ================================================================
    # helpers used by pages
    # ================================================================
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

    def _set_status(self, msg, color=FG_HEAD):
        try:
            self.status.configure(text=msg, fg=color)
        except tk.TclError:
            pass

    def _mark(self, widget, ok):
        try:
            widget.configure(bg=(BG_INPUT_OK if ok else BG_INPUT_ERR))
        except tk.TclError:
            pass

    def std_entry(self, parent, key, label, unit="", width=15):
        row = tk.Frame(parent, bg=BG_MAIN)
        row.pack(anchor="w", pady=2)
        tk.Label(row, text=label, bg=BG_MAIN, font=FONT_LABEL,
                 width=20, anchor="e").pack(side="left")
        var = self._mk_var(key, "")
        e = tk.Entry(row, textvariable=var, width=width,
                     justify="center", font=FONT_ENTRY)
        e.pack(side="left", padx=4)
        if unit:
            tk.Label(row, text=unit, bg=BG_MAIN, font=FONT_LABEL,
                     fg=FG_HINT, anchor="w").pack(side="left")
        self.entries[key] = (var, e)
        return var, e

    def _set_entry(self, key, value_str):
        """Set an entry's value via its StringVar. Returns True if found."""
        if key not in self.entries:
            return False
        var, widget = self.entries[key]
        try:
            var.set(value_str)
            widget.configure(textvariable=var, bg=BG_INPUT_OK)
            widget.update_idletasks()
        except tk.TclError:
            return False
        return True

    def check_entries(self, expected, page_num=0):
        all_ok = True
        msgs = []
        for k, exp in expected.items():
            if k not in self.entries:
                continue
            var, widget = self.entries[k]
            u = parse(var.get())
            ok = u is not None and close(u, exp)
            self._mark(widget, ok)
            if not ok:
                all_ok = False
                msgs.append(f"{k}: expected {fmt(exp)} (got {u})")
        return all_ok, msgs

    # ================================================================
    # window events
    # ================================================================
    def toggle_history(self):
        if self._hist_visible:
            self.history.pack_forget()
            self._hist_visible = False
        else:
            self.history.pack(side="right", fill="y")
            self._hist_visible = True
        self._refresh_top_bar()

    def _on_wheel(self, event):
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            w = None
        node = w
        inside = False
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
            delta = int(-d / 120) if abs(d) >= 120 else (-1 if d > 0 else 1)
        self.step_canvas.yview_scroll(delta, "units")


# ====================================================================
# SECTION 10 — ENTRY POINT                  (was main.py)
# ====================================================================
def main():
    SlabReviewer().mainloop()


if __name__ == "__main__":
    main()