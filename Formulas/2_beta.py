import tkinter as tk
from tkinter import messagebox
import random

# Global variables
current_fc = 0.0
correct_condition = ""
correct_beta = 0.0
score_cond_correct = 0
score_beta_correct = 0
score_total = 0

def generate_problem():
    global current_fc, correct_condition, correct_beta
    
    # --- WEIGHTED RANDOM GENERATOR ---
    # This ensures 28 <= fc' <= 55 appears roughly 75% of the time for equation practice
    rand_choice = random.random() # 0.0 to 1.0
    
    if rand_choice < 0.125: # 12.5% chance for low strength (17 < fc' < 28)
        current_fc = round(random.uniform(17.1, 27.9), 1)
    elif rand_choice < 0.875: # 75% chance for middle strength (28 <= fc' <= 55) - Frequent practice!
        current_fc = round(random.uniform(28.0, 55.0), 1)
    else: # 12.5% chance for high strength (fc' > 55)
        current_fc = round(random.uniform(55.1, 100.0), 1)
    # ----------------------------------

    # Calculate correct answers based on the notes
    if 17 < current_fc < 28:
        correct_condition = "17 < fc' < 28"
        correct_beta = 0.85
    elif 28 <= current_fc <= 55:
        correct_condition = "28 <= fc' <= 55"
        correct_beta = 0.85 - (0.05 * (current_fc - 28) / 7)
        correct_beta = round(correct_beta, 5)
    elif current_fc > 55:
        correct_condition = "fc' > 55"
        correct_beta = 0.65
    else:
        correct_condition = "Invalid (fc' <= 17)"
        correct_beta = 0.0

    # Update UI
    label_fc.config(text=f"f'c = {current_fc} MPa")
    
    entry_condition.delete(0, tk.END)
    entry_beta.delete(0, tk.END)
    result_label.config(text="Type your answers and press ENTER", fg="black")
    answer_reveal_label.config(text="")
    update_score()
    
    entry_condition.focus()

def check_answer():
    global score_cond_correct, score_beta_correct, score_total
    
    if current_fc == 0.0:
        messagebox.showinfo("Start", "Please click 'Generate New Problem' first!")
        return

    user_condition = entry_condition.get().strip()
    user_beta_str = entry_beta.get().strip()
    
    if not user_condition or not user_beta_str:
        messagebox.showwarning("Missing Input", "Please enter both the Condition and the Beta value.")
        return
    
    score_total += 1
    
    is_cond_correct = user_condition.lower() == correct_condition.lower()
    
    try:
        user_beta = float(user_beta_str)
        is_beta_correct = abs(user_beta - correct_beta) <= 0.001 
    except ValueError:
        is_beta_correct = False

    if is_cond_correct: score_cond_correct += 1
    if is_beta_correct: score_beta_correct += 1

    cond_result_text = "✅ Correct" if is_cond_correct else f"❌ Incorrect. Correct: '{correct_condition}'"
    beta_result_text = "✅ Correct" if is_beta_correct else f"❌ Incorrect. Correct: {correct_beta}"
    
    result_label.config(text=f"Condition: {cond_result_text}  |  Beta (β₁): {beta_result_text}", fg="black")
    answer_reveal_label.config(text="")
    
    update_score()

def show_hint():
    hint_text = (
        "Values for β₁ based on f'c:\n\n"
        "• For 17 < f'c < 28 MPa:\n"
        "        β₁ = 0.85\n\n"
        "• For 28 ≤ f'c ≤ 55 MPa:\n"
        "        β₁ = 0.85 - [ 0.05(f'c - 28) / 7 ]\n\n"
        "• For f'c > 55 MPa:\n"
        "        β₁ = 0.65"
    )
    messagebox.showinfo("📐 Beta 1 Hint", hint_text)

def update_score():
    score_label.config(text=f"Condition Score: {score_cond_correct}/{score_total}  |  Beta Score: {score_beta_correct}/{score_total}")

# --- GUI Setup ---
root = tk.Tk()
root.title("Beta 1 (β₁) Determination Practice")
root.geometry("580x480")
root.resizable(False, False)

root.bind('<Return>', lambda event: check_answer())

# 1. Header
tk.Label(root, text="Beta 1 Calculation Practice (ACI 318)", font=("Arial", 14, "bold")).pack(pady=10)

# 2. Generate Button
btn_generate = tk.Button(root, text="🔄 Generate New f'c", command=generate_problem, bg="#ececec", font=("Arial", 10, "bold"))
btn_generate.pack(pady=10)

# 3. Display Values
frame_values = tk.Frame(root)
frame_values.pack(pady=10)
label_fc = tk.Label(frame_values, text="f'c = - MPa", font=("Arial", 12))
label_fc.pack()

# 4. User Input Fields
frame_inputs = tk.LabelFrame(root, text="Your Answers", padx=10, pady=10)
frame_inputs.pack(pady=15)

tk.Label(frame_inputs, text="Condition/Range:").grid(row=0, column=0, pady=5, sticky="e")
entry_condition = tk.Entry(frame_inputs, width=25)
entry_condition.grid(row=0, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(e.g. x < fc' < y)", font=("Arial", 8), fg="gray").grid(row=0, column=2, pady=5, sticky="w")

tk.Label(frame_inputs, text="Beta 1 (β₁):").grid(row=1, column=0, pady=5, sticky="e")
entry_beta = tk.Entry(frame_inputs, width=25)
entry_beta.grid(row=1, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(Type the calculated decimal)", font=("Arial", 8), fg="gray").grid(row=1, column=2, pady=5, sticky="w")

# 5. Action Buttons
frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

btn_check = tk.Button(frame_buttons, text="✅ Show Answer / Check", command=check_answer, bg="#b3d9ff", font=("Arial", 10, "bold"))
btn_check.pack(side="left", padx=5)

btn_hint = tk.Button(frame_buttons, text="💡 Hint: Beta 1 Eq", command=show_hint, bg="#fff3cd", font=("Arial", 10, "bold"))
btn_hint.pack(side="left", padx=5)

# 6. Results & Score
frame_results = tk.Frame(root)
frame_results.pack(pady=10)

result_label = tk.Label(frame_results, text="", font=("Arial", 11))
result_label.pack()

answer_reveal_label = tk.Label(frame_results, text="", font=("Arial", 11, "bold"))
answer_reveal_label.pack()

score_label = tk.Label(root, text="Condition Score: 0 / 0  |  Beta Score: 0 / 0", font=("Arial", 10, "bold"))
score_label.pack(side="bottom", pady=10)

generate_problem()
root.mainloop()