"""
ρs,min (minimum spiral reinforcement ratio) — randomized practice.

Formula:
    ρs,min = 0.45 · (Ag/Ach − 1) · (f'c / fyt)
where:
    Dc  = D − 2·cc
    Ag  = π/4 · D²
    Ach = π/4 · Dc²

Run: python psmin_practice.py
"""
import tkinter as tk
import random
import math

PI = math.pi

D_OPTS = [400, 450, 500, 550, 600, 650, 700]
CC_OPTS = [40, 50]
FC_OPTS = [21, 24, 27, 28, 30, 35]
FYT_OPTS = [275, 345, 415, 420]


def new_givens():
    D = random.choice(D_OPTS)
    cc = random.choice(CC_OPTS)
    fc = random.choice(FC_OPTS)
    fyt = random.choice(FYT_OPTS)
    Dc = D - 2 * cc
    Ag = PI / 4 * D ** 2
    Ach = PI / 4 * Dc ** 2
    rho_s = 0.45 * (Ag / Ach - 1) * fc / fyt
    return {
        "D": D, "cc": cc, "fc": fc, "fyt": fyt, "Dc": Dc,
        "Ag": Ag, "Ach": Ach, "rho_s": rho_s,
    }


class App:
    def __init__(self, root):
        self.root = root
        root.title("Practice — ρs,min (minimum spiral ratio)")
        root.configure(bg="#f4f4f4")

        self.givens = new_givens()

        frame = tk.Frame(root, padx=24, pady=20, bg="#f4f4f4")
        frame.pack()

        tk.Label(
            frame,
            text="ρs,min = 0.45 (Ag/Ach − 1) · (f'c / fyt)",
            font=("Consolas", 12, "bold"),
            bg="#f4f4f4",
        ).pack()
        tk.Label(
            frame,
            text="Dc = D − 2·cc    Ag = π/4·D²    Ach = π/4·Dc²",
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
        tk.Label(ans_row, text="ρs,min =", font=("Consolas", 12, "bold"),
                 bg="#f4f4f4").pack(side="left")
        self.entry = tk.Entry(ans_row, width=16, font=("Consolas", 12),
                              justify="center")
        self.entry.pack(side="left", padx=8)
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
            f"f'c  = {g['fc']} MPa\n"
            f"fyt  = {g['fyt']} MPa"
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

        expected = self.givens["rho_s"]
        tol = 0.02  # 2% relative

        if abs(user - expected) / expected <= tol:
            self.feedback.configure(
                text=f"✓ Correct!\nρs,min = {expected:.5f}",
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