"""
S (spiral spacing) — randomized practice.

Formula:
    S = 4 · as · (Dc − db) / (ρs · Dc²)
where:
    as = π/4 · db²
    Dc = D − 2·cc
    ρs is given

Answer with the RAW S (before rounding to 10 mm).
The tool shows the rounded value in the feedback.

Run: python spacing_practice.py
"""
import tkinter as tk
import random
import math

PI = math.pi

D_OPTS = [400, 450, 500, 550, 600, 650, 700]
CC_OPTS = [40, 50]
DB_OPTS = [10, 12, 16]
RHO_S_OPTS = [0.012, 0.013, 0.014, 0.015, 0.016, 0.018, 0.020, 0.022, 0.025]


def new_givens():
    D = random.choice(D_OPTS)
    cc = random.choice(CC_OPTS)
    db = random.choice(DB_OPTS)
    rho_s = random.choice(RHO_S_OPTS)
    Dc = D - 2 * cc
    as_bar = PI / 4 * db ** 2
    S = 4 * as_bar * (Dc - db) / (rho_s * Dc ** 2)
    S_rounded = math.floor(S / 10) * 10
    return {
        "D": D, "cc": cc, "db": db, "rho_s": rho_s,
        "Dc": Dc, "as": as_bar, "S": S, "S_rounded": S_rounded,
    }


class App:
    def __init__(self, root):
        self.root = root
        root.title("Practice — S (spiral spacing)")
        root.configure(bg="#f4f4f4")

        self.givens = new_givens()

        frame = tk.Frame(root, padx=24, pady=20, bg="#f4f4f4")
        frame.pack()

        tk.Label(
            frame,
            text="S = 4 · as · (Dc − db) / (ρs · Dc²)",
            font=("Consolas", 12, "bold"),
            bg="#f4f4f4",
        ).pack()
        tk.Label(
            frame,
            text="as = π/4·db²    Dc = D − 2·cc",
            font=("Segoe UI", 9, "italic"),
            fg="#555555", bg="#f4f4f4",
        ).pack(pady=(2, 16))

        # Givens box
        self.givens_lbl = tk.Label(
            frame, font=("Consolas", 11), bg="#ffffff",
            justify="left", anchor="w", relief="solid", bd=1,
            padx=18, pady=14,
        )
        self.givens_lbl.pack(fill="x")

        # Answer row
        ans_row = tk.Frame(frame, bg="#f4f4f4")
        ans_row.pack(pady=(18, 6))
        tk.Label(ans_row, text="S =", font=("Consolas", 12, "bold"),
                 bg="#f4f4f4").pack(side="left")
        self.entry = tk.Entry(ans_row, width=16, font=("Consolas", 12),
                              justify="center")
        self.entry.pack(side="left", padx=8)
        tk.Label(ans_row, text="mm", font=("Consolas", 11),
                 bg="#f4f4f4").pack(side="left")
        self.entry.bind("<Return>", lambda e: self.check())

        # Buttons
        btn_row = tk.Frame(frame, bg="#f4f4f4")
        btn_row.pack(pady=(4, 8))
        tk.Button(btn_row, text="Check (Enter)", width=16,
                  bg="#cde8cd", command=self.check).pack(side="left", padx=4)
        tk.Button(btn_row, text="New Problem", width=16,
                  bg="#c9daf8", command=self.new_problem).pack(side="left", padx=4)

        # Feedback
        self.feedback = tk.Label(
            frame, text="", font=("Segoe UI", 10, "bold"),
            bg="#f4f4f4", fg="#666666", wraplength=420, justify="left",
        )
        self.feedback.pack(pady=(6, 0))

        self._refresh()
        self.entry.focus_set()

    def _refresh(self):
        g = self.givens
        text = (
            f"D    = {g['D']} mm\n"
            f"cc   = {g['cc']} mm\n"
            f"db   = {g['db']} mm\n"
            f"ρs   = {g['rho_s']}"
        )
        self.givens_lbl.configure(text=text)

    def new_problem(self):
        self.givens = new_givens()
        self.entry.delete(0, tk.END)
        self.feedback.configure(text="", fg="#666666")
        self._refresh()
        self.entry.focus_set()

    def check(self):
        raw = self.entry.get().strip().replace(",", "")
        try:
            user = float(raw)
        except ValueError:
            self.feedback.configure(text="Enter a number.", fg="#a00000")
            return

        expected = self.givens["S"]
        tol = 0.02  # 2% relative

        if abs(user - expected) / expected <= tol:
            rounded = self.givens["S_rounded"]
            self.feedback.configure(
                text=(f"✓ Correct!\n"
                      f"Raw S = {expected:.2f} mm\n"
                      f"Rounded (down) = {rounded} mm"),
                fg="#0a7a0a",
            )
        else:
            self.feedback.configure(
                text="✗ Not quite. Try again.",
                fg="#a00000",
            )


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()