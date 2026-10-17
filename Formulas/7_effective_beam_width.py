import tkinter as tk
from tkinter import messagebox
import random

# ==========================================
# SOLVER ENGINE (Hidden Math Logic)
# ==========================================
class TBeamSolver:
    def __init__(self):
        # Given Variables
        self.bw = 0
        self.tf = 0
        self.SL1 = 0
        self.SL2 = 0
        self.Ln = 0
        
        # Correct Answers for the 4 rules
        self.corr_rule1 = 0.0
        self.corr_rule2 = 0.0
        self.corr_rule3 = 0.0
        self.corr_rule4 = 0.0
        self.corr_bf_final = 0.0

    def generate(self):
        # Randomize beam and slab properties
        self.bw = random.choice([250, 300, 350, 400])
        self.tf = random.randint(100, 200)
        
        # Spacing between beams (mm)
        self.SL1 = random.randint(2000, 6000)
        self.SL2 = random.randint(2000, 6000)
        
        # Clear span of the beam (mm)
        self.Ln = random.randint(4000, 10000)

        # Calculate the 4 rules
        # Rule 1: bw + 16*tf
        self.corr_rule1 = self.bw + 16 * self.tf
        
        # Rule 2: bw + SL1/2 + SL2/2
        self.corr_rule2 = self.bw + (self.SL1 / 2) + (self.SL2 / 2)
        
        # Rule 3: bw + Ln/4
        self.corr_rule3 = self.bw + (self.Ln / 4)
        
        # Rule 4: 4*bw
        self.corr_rule4 = 4 * self.bw

        # Final bf is the LEAST of the 4
        self.corr_bf_final = min(self.corr_rule1, self.corr_rule2, self.corr_rule3, self.corr_rule4)
        self.corr_bf_final = round(self.corr_bf_final, 1)

# ==========================================
# MAIN APPLICATION CLASS
# ==========================================
class TBeamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("T-Beam Effective Flange Width (bf) Reviewer")
        self.root.geometry("520x520")
        self.root.resizable(False, False)
        
        self.solver = TBeamSolver()
        self.score = 0
        self.total_tries = 0
        
        self.setup_ui()
        self.new_problem()

    def setup_ui(self):
        # Header
        tk.Label(self.root, text="Compute bf (Least Of Rule)", font=("Arial", 16, "bold"), pady=10).pack()

        # Given Values Frame
        frame_given = tk.LabelFrame(self.root, text="Given Beam Properties", padx=15, pady=10)
        frame_given.pack(pady=10, fill="x", padx=20)
        
        self.lbl_given = tk.Label(frame_given, text="", font=("Arial", 11), justify="left")
        self.lbl_given.pack()

        # Result Frame (User Input)
        frame_input = tk.LabelFrame(self.root, text="Your Calculation", padx=15, pady=10)
        frame_input.pack(pady=10, fill="x", padx=20)
        
        tk.Label(frame_input, text="Final bf (mm):", font=("Arial", 11, "bold")).pack(side="left")
        self.entry_bf = tk.Entry(frame_input, width=15, font=("Arial", 11))
        self.entry_bf.pack(side="left", padx=10)

        # Buttons Frame
        frame_buttons = tk.Frame(self.root)
        frame_buttons.pack(pady=15)
        
        tk.Button(frame_buttons, text="✅ Check Answer", command=self.check_answer, width=15, bg="#b3d9ff", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        tk.Button(frame_buttons, text="💡 Show Hint", command=self.show_hint, width=15, bg="#fff3cd", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        tk.Button(frame_buttons, text="🔄 New Problem", command=self.new_problem, width=15, bg="#ececec", font=("Arial", 10)).pack(side="left", padx=5)

        # Result Label
        self.lbl_result = tk.Label(self.root, text="", font=("Arial", 11))
        self.lbl_result.pack(pady=5)

        # Score Label
        self.lbl_score = tk.Label(self.root, text="Score: 0 / 0", font=("Arial", 10, "bold"))
        self.lbl_score.pack(side="bottom", pady=10)

        # Bind Enter key
        self.root.bind('<Return>', lambda event: self.check_answer())

    def new_problem(self):
        self.solver.generate()
        
        self.lbl_given.config(text=(
            f"Web Width (bw) = {self.solver.bw} mm\n"
            f"Flange Thickness (tf) = {self.solver.tf} mm\n"
            f"Left Clear Spacing (SL1) = {self.solver.SL1} mm\n"
            f"Right Clear Spacing (SL2) = {self.solver.SL2} mm\n"
            f"Clear Span (Ln) = {self.solver.Ln} mm"
        ))
        
        self.entry_bf.delete(0, tk.END)
        self.lbl_result.config(text="Calculate the 4 rules and enter the least value.", fg="black")
        self.entry_bf.focus()

    def show_hint(self):
        hint_text = (
            "Step-by-Step Guide to Compute bf:\n\n"
            "You need to calculate all 4 rules and take the LEAST value:\n\n"
            f"1. bw + 16*tf:\n"
            f"   = {self.solver.bw} + 16({self.solver.tf})\n"
            f"   = {self.solver.corr_rule1} mm\n\n"
            
            f"2. bw + SL1/2 + SL2/2:\n"
            f"   = {self.solver.bw} + ({self.solver.SL1}/2) + ({self.solver.SL2}/2)\n"
            f"   = {self.solver.corr_rule2} mm\n\n"
            
            f"3. bw + Ln/4:\n"
            f"   = {self.solver.bw} + ({self.solver.Ln}/4)\n"
            f"   = {self.solver.corr_rule3} mm\n\n"
            
            f"4. 4*bw:\n"
            f"   = 4 * {self.solver.bw}\n"
            f"   = {self.solver.corr_rule4} mm\n\n"
            
            f"FINAL bf = Minimum of the 4 values above."
        )
        messagebox.showinfo("📐 bf Formula Hint", hint_text)

    def check_answer(self):
        if self.solver.bw == 0:
            messagebox.showinfo("Start", "Please click 'New Problem' first!")
            return
        
        try:
            user_bf = float(self.entry_bf.get().strip())
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter a valid number for bf.")
            return
            
        self.total_tries += 1
        
        if abs(user_bf - self.solver.corr_bf_final) <= 0.5:
            self.score += 1
            self.lbl_result.config(
                text=f"✅ CORRECT! bf = {self.solver.corr_bf_final} mm", 
                fg="green"
            )
        else:
            self.lbl_result.config(
                text=f"❌ WRONG. Correct bf = {self.solver.corr_bf_final} mm", 
                fg="red"
            )
        
        self.lbl_score.config(text=f"Score: {self.score} / {self.total_tries}")

# ==========================================
# RUN THE APP
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    app = TBeamApp(root)
    root.mainloop()