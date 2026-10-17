import tkinter as tk
from tkinter import messagebox
import random

# ==========================================
# GLOBAL VARIABLES
# ==========================================
b = 0.0
cc = 0.0
nb = 0
db = 0.0
dagg = 0.0
has_stirrups = False
dv = 0.0

corr_rebar_S = 0.0
corr_agg_S = 0.0
corr_final_S = 0.0

score_rebar = 0
score_agg = 0
score_final = 0
score_total = 0

# ==========================================
# APP LOGIC
# ==========================================
def generate_problem():
    global b, cc, nb, db, dagg, has_stirrups, dv
    global corr_rebar_S, corr_agg_S, corr_final_S
    
    # 1. Randomize Beam Properties (make sure the size works)
    while True:
        b = random.randint(250, 600)       # Beam width
        cc = random.choice([40, 50, 60, 75]) # Concrete cover
        nb = random.randint(3, 7)          # Number of bars
        db = random.choice([16, 20, 25, 28, 32, 36]) # Bar diameter
        
        # Ensure b - 2*cc - nb*db is positive (otherwise bars can't fit)
        # Add a small safety buffer of 30mm
        if b - 2 * cc - nb * db > 30:
            break
    
    # 2. Generate Stirrup Status
    has_stirrups = random.choice([True, False])
    if has_stirrups:
        dv = random.choice([8, 10, 12]) # Stirrup diameter (mm)
    else:
        dv = 0

    # 3. Max Aggregate Size (dagg)
    dagg = random.choice([9.5, 12.5, 19.0, 25.0]) 
    
    # 4. Calculate Correct Answers
    # --- Rule 4: Rebar Spacing ---
    if has_stirrups:
        # Formula for Stirrups Present: S = [b - 2cc - 2dv - nb(db)] / (nb - 1)
        corr_rebar_S = (b - 2*cc - 2*dv - nb*db) / (nb - 1)
    else:
        # Default Formula (No Stirrups): S = [b - 2cc - nb(db)] / (nb - 1)
        corr_rebar_S = (b - 2*cc - nb*db) / (nb - 1)
    corr_rebar_S = round(corr_rebar_S, 2)

    # --- Rule 3: Aggregate Spacing ---
    corr_agg_S = round((4 / 3) * dagg, 2)

    # --- Final Clear Spacing (MAX of 4 rules) ---
    # Rule 1: 50mm, Rule 2: db, Rule 3: corr_agg_S, Rule 4: corr_rebar_S
    corr_final_S = max(50.0, db, corr_agg_S, corr_rebar_S)
    corr_final_S = round(corr_final_S, 2)

    # Update UI
    label_b.config(text=f"Beam Width (b): {b} mm")
    label_cc.config(text=f"Concrete Cover (cc): {cc} mm")
    label_nb.config(text=f"Number of Rebars (nb): {nb}")
    label_db.config(text=f"Rebar Diameter (db): {db} mm")
    label_dagg.config(text=f"Max Aggregate Size (dagg): {dagg} mm")
    
    if has_stirrups:
        label_stirrup.config(text=f"Stirrups Present? YES (dv = {dv} mm)", fg="blue")
    else:
        label_stirrup.config(text=f"Stirrups Present? NO (Use Default Formula)", fg="green")

    # Clear inputs
    entry_rebar_S.delete(0, tk.END)
    entry_agg_S.delete(0, tk.END)
    entry_final_S.delete(0, tk.END)
    result_lbl.config(text="Fill in all 3 answers below and press ENTER", fg="black")
    update_score()
    entry_rebar_S.focus()

def check_answers(event=None):
    global score_rebar, score_agg, score_final, score_total
    
    if b == 0:
        messagebox.showinfo("Start", "Click 'Generate New Problem' first!")
        return
        
    try:
        u_rebar_S = float(entry_rebar_S.get().strip())
        u_agg_S = float(entry_agg_S.get().strip())
        u_final_S = float(entry_final_S.get().strip())
    except ValueError:
        messagebox.showwarning("Input Error", "Please enter valid numbers in all 3 fields.")
        return
        
    score_total += 1
    
    # Check Rebar Spacing
    is_rebar_correct = abs(u_rebar_S - corr_rebar_S) <= 0.01
    # Check Aggregate Spacing
    is_agg_correct = abs(u_agg_S - corr_agg_S) <= 0.01
    # Check Final Spacing
    is_final_correct = abs(u_final_S - corr_final_S) <= 0.01

    if is_rebar_correct: score_rebar += 1
    if is_agg_correct: score_agg += 1
    if is_final_correct: score_final += 1

    rebar_text = "✅ Correct" if is_rebar_correct else f"❌ Incorrect. Correct: {corr_rebar_S} mm"
    agg_text = "✅ Correct" if is_agg_correct else f"❌ Incorrect. Correct: {corr_agg_S} mm"
    final_text = "✅ Correct" if is_final_correct else f"❌ Incorrect. Correct: {corr_final_S} mm"
    
    result_lbl.config(
        text=f"Rebar Spacing: {rebar_text} | Agg Spacing: {agg_text} | Final Clear Spacing: {final_text}",
        fg="black"
    )
    update_score()

def show_hint():
    hint = (
        "Step-by-Step Guide (The 4 Rules):\n\n"
        "Rule 1: Minimum Spacing = 50 mm\n"
        "Rule 2: Minimum Spacing = db (Bar Diameter)\n\n"
        "Rule 3: Aggregate Spacing = (4/3) * dagg\n\n"
        "Rule 4: Rebar Spacing (Depends on stirrups):\n"
        "   - If Stirrups are NOT considered (Default):\n"
        "       S = (b - 2cc - nb*db) / (nb - 1)\n"
        "   - If Stirrups ARE considered:\n"
        "       S = (b - 2cc - 2dv - nb*db) / (nb - 1)\n\n"
        "Final Answer:\n"
        "Final Spacing = MAXIMUM ( Rule 1, Rule 2, Rule 3, Rule 4 )"
    )
    messagebox.showinfo("📐 4-Rule Clear Spacing Hint", hint)

def update_score():
    if score_total == 0:
        score_lbl.config(text="Score: 0 / 0")
    else:
        score_lbl.config(text=f"RebarSp: {score_rebar}/{score_total} | AggSp: {score_agg}/{score_total} | Final: {score_final}/{score_total}")

# ==========================================
# GUI SETUP
# ==========================================

def main():
    global b, cc, nb, db, dagg, has_stirrups, dv, corr_rebar_S, corr_agg_S, corr_final_S, score_rebar, score_agg, score_final, score_total, root, frame_props, label_b, label_cc, label_nb, label_db, label_dagg, label_stirrup, frame_in, entry_rebar_S, entry_agg_S, entry_final_S, frame_btns, btn_check, btn_hint, result_lbl, score_lbl
    root = tk.Tk()
    root.title("Stirrup Spacing & 4-Rule Max (Section 425.2.1)")
    root.geometry("720x650")
    root.resizable(False, False)

    root.bind('<Return>', check_answers)

    # 1. Header
    tk.Label(root, text="Stirrup Spacing & Final Spacing Practice", font=("Arial", 14, "bold")).pack(pady=10)

    # 2. Generate Button
    tk.Button(root, text="🔄 Generate New Problem", command=generate_problem, bg="#ececec", font=("Arial", 10)).pack(pady=5)

    # 3. Beam Properties Box
    frame_props = tk.LabelFrame(root, text="Beam Properties & Conditions", padx=10, pady=10)
    frame_props.pack(pady=10)

    label_b = tk.Label(frame_props, text="Beam Width (b): - mm", font=("Arial", 10))
    label_b.pack()
    label_cc = tk.Label(frame_props, text="Concrete Cover (cc): - mm", font=("Arial", 10))
    label_cc.pack()
    label_nb = tk.Label(frame_props, text="Number of Rebars (nb): -", font=("Arial", 10))
    label_nb.pack()
    label_db = tk.Label(frame_props, text="Rebar Diameter (db): - mm", font=("Arial", 10))
    label_db.pack()
    label_dagg = tk.Label(frame_props, text="Max Aggregate Size (dagg): - mm", font=("Arial", 10))
    label_dagg.pack()
    label_stirrup = tk.Label(frame_props, text="Stirrups Present? -", font=("Arial", 10, "bold"))
    label_stirrup.pack(pady=(5, 0))

    # 4. User Input Fields
    frame_in = tk.LabelFrame(root, text="Your Answers", padx=10, pady=10)
    frame_in.pack(pady=15)

    tk.Label(frame_in, text="Rule 4: Rebar Spacing (mm):").grid(row=0, column=0, pady=5, sticky="e")
    entry_rebar_S = tk.Entry(frame_in, width=15)
    entry_rebar_S.grid(row=0, column=1, pady=5, padx=5)

    tk.Label(frame_in, text="Rule 3: Aggregate Spacing (mm):").grid(row=1, column=0, pady=5, sticky="e")
    entry_agg_S = tk.Entry(frame_in, width=15)
    entry_agg_S.grid(row=1, column=1, pady=5, padx=5)

    tk.Label(frame_in, text="Final Clear Spacing (mm):").grid(row=2, column=0, pady=5, sticky="e")
    entry_final_S = tk.Entry(frame_in, width=15)
    entry_final_S.grid(row=2, column=1, pady=5, padx=5)

    # 5. Action Buttons
    frame_btns = tk.Frame(root)
    frame_btns.pack(pady=10)

    btn_check = tk.Button(frame_btns, text="✅ Check My Answers", command=check_answers, bg="#b3d9ff", font=("Arial", 10))
    btn_check.pack(side="left", padx=5)

    btn_hint = tk.Button(frame_btns, text="💡 4-Rule Step-by-Step", command=show_hint, bg="#fff3cd", font=("Arial", 10))
    btn_hint.pack(side="left", padx=5)

    # 6. Results and Score
    result_lbl = tk.Label(root, text="", font=("Arial", 10))
    result_lbl.pack(pady=5)

    score_lbl = tk.Label(root, text="Score: 0 / 0", font=("Arial", 10, "bold"))
    score_lbl.pack(pady=5)

    # Initial Generation
    generate_problem()

    root.mainloop()


if __name__ == "__main__":
    main()
