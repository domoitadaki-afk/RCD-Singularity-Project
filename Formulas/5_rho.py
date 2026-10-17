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
current_beta1 = 0.0
current_fs = 0
is_As_given = False
current_As = 0
current_region = ""

c_rho_min = 0.0
c_rho_act = 0.0
c_rho_max = 0.0

score_min = 0
score_act = 0
score_max = 0
score_total = 0

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def calc_beta1(fc):
    # Strictly based on previous ACI 318 beta 1 notes
    if 17 < fc < 28:
        return 0.85
    elif 28 <= fc <= 55:
        beta = 0.85 - (0.05 * (fc - 28) / 7)
        return round(beta, 5)
    else:
        return 0.65

# ==========================================
# APP LOGIC
# ==========================================
def generate_problem():
    global current_b, current_d, current_fc, current_fy, current_beta1, current_fs
    global is_As_given, current_As, current_region
    global c_rho_min, c_rho_act, c_rho_max

    # 1. Randomize Beam Properties
    current_b = random.randint(200, 400)
    current_d = random.randint(350, 600)
    current_fc = random.uniform(21, 50)   # MPa
    current_fy = random.choice([276, 345, 414, 550])  # MPa
    current_beta1 = calc_beta1(current_fc)
    
    # Force fs to be greater than fy so we use the formulas given in the image
    # (Tension-Controlled: fs > 1000, Transition: fy < fs <= 1000)
    current_fs = random.randint(int(current_fy) + 10, 1500)

    # 2. Determine Region and Compute rho_max
    if current_fs > 1000:
        current_region = "Tension-Controlled (fs > 1000)"
        # Tension formula: 3/8 * (0.85*beta1*fc / fy)
        c_rho_max = (3 / 8) * (0.85 * current_beta1 * current_fc / current_fy)
    else:
        current_region = "Transition (fy < fs < 1000)"
        # Transition formula: 3/7 * (0.85*beta1*fc / fy)
        c_rho_max = (3 / 7) * (0.85 * current_beta1 * current_fc / current_fy)
    c_rho_max = round(c_rho_max, 5)

    # 3. Compute rho_min
    rho_min_1 = 1.4 / current_fy
    rho_min_2 = (0.25 * math.sqrt(current_fc)) / current_fy
    c_rho_min = max(rho_min_1, rho_min_2)
    c_rho_min = round(c_rho_min, 5)

    # 4. Compute rho_act
    is_As_given = random.choice([True, False])
    
    if is_As_given:
        # Generate a valid rho_act slightly above rho_min and below rho_max
        # Ensure we don't go out of bounds
        low_bound = c_rho_min + 0.001
        high_bound = c_rho_max - 0.001
        if low_bound >= high_bound:
            # Fallback if bounds are too tight, just pick a random small number
            rand_rho = round(random.uniform(0.005, 0.025), 5)
        else:
            rand_rho = round(random.uniform(low_bound, high_bound), 5)
            
        current_As = int(round(rand_rho * current_b * current_d, 0))
        c_rho_act = current_As / (current_b * current_d)
    else:
        # As is NOT given: rho_act = 0.75 rho_max
        c_rho_act = 0.75 * c_rho_max
        current_As = 0 # Indicate it's not provided

    c_rho_act = round(c_rho_act, 5)

    # Update UI Labels
    label_b.config(text=f"Width (b) = {current_b} mm")
    label_d.config(text=f"Eff. Depth (d) = {current_d} mm")
    label_fc.config(text=f"Concrete (f'c) = {int(current_fc)} MPa")
    label_fy.config(text=f"Steel (fy) = {current_fy} MPa")
    label_beta1.config(text=f"Beta 1 (β₁) = {current_beta1}")
    label_fs.config(text=f"Steel Stress (fs) = {current_fs} MPa")
    label_region.config(text=f"Region = {current_region}", fg="blue")
    
    if is_As_given:
        label_As.config(text=f"Area of Steel (As) = {current_As} mm²")
    else:
        label_As.config(text=f"Area of Steel (As) = NOT GIVEN")

    # Clear inputs and results
    entry_rho_min.delete(0, tk.END)
    entry_rho_act.delete(0, tk.END)
    entry_rho_max.delete(0, tk.END)
    result_lbl.config(text="Type answers and press ENTER", fg="black")
    update_score()
    entry_rho_min.focus()

def check_answers(event=None):
    global score_min, score_act, score_max, score_total
    
    if current_b == 0:
        messagebox.showinfo("Start", "Please click 'Generate New Problem' first!")
        return
    
    user_rho_min_str = entry_rho_min.get().strip()
    user_rho_act_str = entry_rho_act.get().strip()
    user_rho_max_str = entry_rho_max.get().strip()
    
    if not user_rho_min_str or not user_rho_act_str or not user_rho_max_str:
        messagebox.showwarning("Missing Input", "Please enter values for all 3 ratios.")
        return
        
    score_total += 1
    
    # Check rho_min
    try:
        u_rho_min = float(user_rho_min_str)
        is_min_correct = abs(u_rho_min - c_rho_min) <= 0.0001
    except ValueError:
        is_min_correct = False
        
    # Check rho_act
    try:
        u_rho_act = float(user_rho_act_str)
        is_act_correct = abs(u_rho_act - c_rho_act) <= 0.0001
    except ValueError:
        is_act_correct = False
        
    # Check rho_max
    try:
        u_rho_max = float(user_rho_max_str)
        is_max_correct = abs(u_rho_max - c_rho_max) <= 0.0001
    except ValueError:
        is_max_correct = False

    if is_min_correct: score_min += 1
    if is_act_correct: score_act += 1
    if is_max_correct: score_max += 1

    min_text = "✅ Correct" if is_min_correct else f"❌ Incorrect. Correct: {c_rho_min}"
    act_text = "✅ Correct" if is_act_correct else f"❌ Incorrect. Correct: {c_rho_act}"
    max_text = "✅ Correct" if is_max_correct else f"❌ Incorrect. Correct: {c_rho_max}"
    
    result_lbl.config(
        text=f"Min (ρ_min): {min_text} | Act (ρ_act): {act_text} | Max (ρ_max): {max_text}", 
        fg="black"
    )
    update_score()

def show_hint():
    hint = (
        "Calculating Reinforcement Ratios:\n\n"
        "1. Minimum Ratio (ρ_min):\n"
        "   ρ_min = MAX( 1.4/fy , 0.25√f'c / fy )\n\n"
        "2. Maximum Ratio (ρ_max):\n"
        "   - Transition Region (fy < fs < 1000):\n"
        "       3/7 * (0.85β₁f'c / fy)\n"
        "   - Tension-Controlled Region (fs > 1000):\n"
        "       3/8 * (0.85β₁f'c / fy)\n\n"
        "3. Actual Ratio (ρ_act):\n"
        "   - If As is given: As / (b*d)\n"
        "   - If As is NOT given: 0.75 * ρ_max"
    )
    messagebox.showinfo("📐 Reinforcement Ratios Hint", hint)

def update_score():
    if score_total == 0:
        score_lbl.config(text="Score: 0 / 0")
    else:
        score_lbl.config(text=f"Min: {score_min}/{score_total} | Act: {score_act}/{score_total} | Max: {score_max}/{score_total}")

# ==========================================
# GUI SETUP
# ==========================================
root = tk.Tk()
root.title("Reinforcement Ratios Practice")
root.geometry("650x620")
root.resizable(False, False)

# Bind Enter key
root.bind('<Return>', check_answers)

# 1. Header
tk.Label(root, text="Reinforcement Ratios (ρₘᵢₙ, ρₐ꜀ₜ, ρₘₐₓ)", font=("Arial", 14, "bold")).pack(pady=10)

# 2. Generate Button
tk.Button(root, text="🔄 Generate New Problem", command=generate_problem, bg="#ececec", font=("Arial", 10)).pack(pady=5)

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
label_beta1 = tk.Label(frame_props, text="Beta 1 (β₁) = -", font=("Arial", 10))
label_beta1.pack()
label_fs = tk.Label(frame_props, text="Steel Stress (fs) = - MPa", font=("Arial", 10))
label_fs.pack()
label_region = tk.Label(frame_props, text="Region = -", font=("Arial", 10, "bold"), fg="blue")
label_region.pack()
label_As = tk.Label(frame_props, text="Area of Steel (As) = -", font=("Arial", 10, "bold"))
label_As.pack(pady=(5,0))

# 4. User Input Fields
frame_in = tk.LabelFrame(root, text="Your Answers (Type the decimal)", padx=10, pady=10)
frame_in.pack(pady=15)

tk.Label(frame_in, text="Min Ratio (ρₘᵢₙ):").grid(row=0, column=0, pady=5, sticky="e")
entry_rho_min = tk.Entry(frame_in, width=15)
entry_rho_min.grid(row=0, column=1, pady=5, padx=5)

tk.Label(frame_in, text="Actual Ratio (ρₐ꜀ₜ):").grid(row=1, column=0, pady=5, sticky="e")
entry_rho_act = tk.Entry(frame_in, width=15)
entry_rho_act.grid(row=1, column=1, pady=5, padx=5)

tk.Label(frame_in, text="Max Ratio (ρₘₐₓ):").grid(row=2, column=0, pady=5, sticky="e")
entry_rho_max = tk.Entry(frame_in, width=15)
entry_rho_max.grid(row=2, column=1, pady=5, padx=5)

# 5. Action Buttons
frame_btns = tk.Frame(root)
frame_btns.pack(pady=10)

btn_check = tk.Button(frame_btns, text="✅ Check My Answers", command=check_answers, bg="#b3d9ff", font=("Arial", 10))
btn_check.pack(side="left", padx=5)

btn_hint = tk.Button(frame_btns, text="💡 Show Hint", command=show_hint, bg="#fff3cd", font=("Arial", 10))
btn_hint.pack(side="left", padx=5)

# 6. Results and Score
result_lbl = tk.Label(root, text="", font=("Arial", 10))
result_lbl.pack(pady=5)

score_lbl = tk.Label(root, text="Score: 0 / 0", font=("Arial", 10, "bold"))
score_lbl.pack(pady=5)

# Initial Generation
generate_problem()

# Run the main loop
root.mainloop()