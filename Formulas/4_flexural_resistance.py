import tkinter as tk
from tkinter import messagebox
import random
import math

# ==========================================
# GLOBAL VARIABLES
# ==========================================
current_b = 0
current_d = 0
current_fc = 0.0
current_fy = 0
current_phi = 0.0
current_Mu = 0.0

correct_R = 0.0
correct_rho = 0.0
score_R = 0
score_rho = 0
score_total = 0

# ==========================================
# APP LOGIC
# ==========================================
def generate_rho_problem():
    global current_b, current_d, current_fc, current_fy, current_phi, current_Mu, correct_R, correct_rho
    
    # Generate random beam properties
    current_b = random.randint(200, 400)
    current_d = random.randint(300, 600)
    current_fc = random.randint(21, 42)   # MPa (Normal strength)
    current_fy = random.choice([276, 345, 414, 550])  # MPa
    current_phi = random.choice([0.65, 0.75, 0.80, 0.90])
    
    # Generate a realistic Mu (kN-m) so the beam never fails in compression mathematically
    target_R = random.uniform(2.0, 6.0)  # Normal target flexural resistance
    current_Mu = round(target_R * current_b * (current_d ** 2) / 1000000, 3)

    # 1. Calculate Correct R
    correct_R = (current_Mu * 1000000) / (current_b * (current_d ** 2))
    correct_R = round(correct_R, 4)

    # 2. Calculate Correct Rho_act
    # Equation: R = φ * rho * fy * (1 - (rho*fy)/(1.7*fc))
    # Use quadratic formula: Let X = rho * fy
    # X^2 - 1.7fc*X + (1.7fc*R)/phi = 0
    A_coeff = 1
    B_coeff = - (1.7 * current_fc)
    C_coeff = (1.7 * current_fc * correct_R) / current_phi
    
    discriminant = (B_coeff ** 2) - (4 * A_coeff * C_coeff)
    
    if discriminant < 0:
        # If the math fails for some extreme random (highly unlikely), just regenerate
        generate_rho_problem()
        return
        
    X_root = (-B_coeff - math.sqrt(discriminant)) / (2 * A_coeff)
    correct_rho = X_root / current_fy
    correct_rho = round(correct_rho, 5)

    # Update UI
    label_b.config(text=f"Width (b) = {current_b} mm")
    label_d.config(text=f"Eff. Depth (d) = {current_d} mm")
    label_fc.config(text=f"Concrete (f'c) = {current_fc} MPa")
    label_fy.config(text=f"Steel (fy) = {current_fy} MPa")
    label_phi.config(text=f"Strength Factor (φ) = {current_phi}")
    label_mu.config(text=f"Moment (Mu) = {current_Mu} kN-m")

    entry_R.delete(0, tk.END)
    entry_rho.delete(0, tk.END)
    result_lbl.config(text="Type your answers and press ENTER", fg="black")
    update_score()
    entry_R.focus()

def check_rho(event=None):
    global score_R, score_rho, score_total
    if current_Mu == 0.0:
        messagebox.showinfo("Start", "Please click 'Generate Random Beam' first!")
        return
    
    user_R_str = entry_R.get().strip()
    user_rho_str = entry_rho.get().strip()
    
    if not user_R_str or not user_rho_str:
        messagebox.showwarning("Missing Input", "Enter both 'R' and 'ρ' values.")
        return
        
    score_total += 1
    
    try:
        user_R = float(user_R_str)
        is_R_correct = abs(user_R - correct_R) <= 0.001
    except ValueError:
        is_R_correct = False
        
    try:
        user_rho = float(user_rho_str)
        is_rho_correct = abs(user_rho - correct_rho) <= 0.00001
    except ValueError:
        is_rho_correct = False

    if is_R_correct: score_R += 1
    if is_rho_correct: score_rho += 1

    R_text = "✅ Correct" if is_R_correct else f"❌ Incorrect. Correct: {correct_R}"
    rho_text = "✅ Correct" if is_rho_correct else f"❌ Incorrect. Correct: {correct_rho}"
    
    result_lbl.config(text=f"Resistance Factor (R): {R_text} | Rho (ρ): {rho_text}", fg="black")
    update_score()

def show_rho_hint():
    hint = (
        "Step 1: Calculate Flexural Resistance Factor (R):\n"
        "   R = Mu(N-mm) / (b * d²)\n\n"
        "Step 2: Solve for Actual Rho (ρ) using:\n"
        "   R = φ ρ fy (1 - (ρ fy) / (1.7 f'c))\n\n"
        "Derived Quadratic to solve for ρ:\n"
        "   Let X = ρ fy, then:\n"
        "   X = [1.7fc - √(2.89fc² - (6.8fcR)/φ)] / 2\n"
        "   ρ = X / fy\n\n"
        "*Make sure to convert Mu (kN-m) to N-mm (Multiply by 10⁶)*"
    )
    messagebox.showinfo("📐 R & ρ Step-by-Step Hint", hint)

def update_score():
    if score_total == 0:
        score_lbl.config(text="Score: 0 / 0")
    else:
        score_lbl.config(text=f"R Score: {score_R}/{score_total} | Rho Score: {score_rho}/{score_total}")


# ==========================================
# GUI SETUP
# ==========================================

def main():
    global current_b, current_d, current_fc, current_fy, current_phi, current_Mu, correct_R, correct_rho, score_R, score_rho, score_total, root, frame_props, label_b, label_d, label_fc, label_fy, label_phi, label_mu, frame_in, entry_R, entry_rho, frame_btns, btn_check, btn_hint, result_lbl, score_lbl
    root = tk.Tk()
    root.title("Flexural Resistance & Rho Solver")
    root.geometry("650x550")
    root.resizable(False, False)

    # Bind the Enter key to check answers
    root.bind('<Return>', check_rho)

    # 1. Header
    tk.Label(root, text="Flexural Resistance (R) & Rho Solver", font=("Arial", 14, "bold")).pack(pady=10)

    # 2. Generate Button
    tk.Button(root, text="🔄 Generate Random Beam", command=generate_rho_problem, bg="#ececec", font=("Arial", 10)).pack(pady=10)

    # 3. Beam Properties Box
    frame_props = tk.LabelFrame(root, text="Beam Properties", padx=10, pady=10)
    frame_props.pack(pady=10)

    label_b = tk.Label(frame_props, text="Width (b) = - mm", font=("Arial", 10))
    label_b.pack()
    label_d = tk.Label(frame_props, text="Eff. Depth (d) = - mm", font=("Arial", 10))
    label_d.pack()
    label_fc = tk.Label(frame_props, text="Concrete (f'c) = - MPa", font=("Arial", 10))
    label_fc.pack()
    label_fy = tk.Label(frame_props, text="Steel (fy) = - MPa", font=("Arial", 10))
    label_fy.pack()
    label_phi = tk.Label(frame_props, text="Strength Factor (φ) = -", font=("Arial", 10))
    label_phi.pack()
    label_mu = tk.Label(frame_props, text="Moment (Mu) = - kN-m", font=("Arial", 10, "bold"))
    label_mu.pack(pady=(5,0))

    # 4. User Input Fields
    frame_in = tk.LabelFrame(root, text="Your Calculations", padx=10, pady=10)
    frame_in.pack(pady=15)

    tk.Label(frame_in, text="Resistance Factor (R):").grid(row=0, column=0, pady=5, sticky="e")
    entry_R = tk.Entry(frame_in, width=15)
    entry_R.grid(row=0, column=1, pady=5, padx=5)

    tk.Label(frame_in, text="Actual Rho (ρ):").grid(row=1, column=0, pady=5, sticky="e")
    entry_rho = tk.Entry(frame_in, width=15)
    entry_rho.grid(row=1, column=1, pady=5, padx=5)

    # 5. Action Buttons
    frame_btns = tk.Frame(root)
    frame_btns.pack(pady=10)

    btn_check = tk.Button(frame_btns, text="✅ Check My Answers", command=check_rho, bg="#b3d9ff", font=("Arial", 10))
    btn_check.pack(side="left", padx=5)

    btn_hint = tk.Button(frame_btns, text="💡 Show Hint", command=show_rho_hint, bg="#fff3cd", font=("Arial", 10))
    btn_hint.pack(side="left", padx=5)

    # 6. Results and Score
    result_lbl = tk.Label(root, text="", font=("Arial", 10))
    result_lbl.pack(pady=5)

    score_lbl = tk.Label(root, text="Score: 0 / 0", font=("Arial", 10, "bold"))
    score_lbl.pack(pady=5)

    # Initial Generation
    generate_rho_problem()

    # Run the main loop
    root.mainloop()


if __name__ == "__main__":
    main()
