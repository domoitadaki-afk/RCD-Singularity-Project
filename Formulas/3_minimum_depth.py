import tkinter as tk
from tkinter import messagebox
import random

# Global Variables
current_support = ""
current_span_mm = 0.0
current_fy = 0
correct_base_h = 0.0
correct_modifier = 0.0
correct_final_h = 0.0
score_base = 0
score_mod = 0
score_final = 0
score_total = 0

def generate_problem():
    global current_support, current_span_mm, current_fy, correct_base_h, correct_modifier, correct_final_h
    
    # 1. Randomize Support Condition
    supports = ["Simply supported", "One end continuous", "Both ends continuous", "Cantilever"]
    current_support = random.choice(supports)
    
    # 2. Randomize Span (2.0m to 10.0m) converted to mm
    span_m = round(random.uniform(2.0, 10.0), 2)
    current_span_mm = span_m * 1000
    
    # 3. Randomize fy (between 300 and 600 MPa)
    current_fy = random.randint(300, 600)

    # 4. Calculate Correct Answers
    # Step 1: Base h (Assuming 420 MPa and normal weight)
    if current_support == "Simply supported":
        correct_base_h = current_span_mm / 16
    elif current_support == "One end continuous":
        correct_base_h = current_span_mm / 18.5
    elif current_support == "Both ends continuous":
        correct_base_h = current_span_mm / 21
    else: # Cantilever
        correct_base_h = current_span_mm / 8

    # Step 2: Modifier
    correct_modifier = 0.4 + (current_fy / 700)
    
    # Step 3: Final h
    correct_final_h = correct_base_h * correct_modifier

    # Update UI
    label_support.config(text=f"Support Condition: {current_support}")
    label_span.config(text=f"Span (ℓ): {int(current_span_mm)} mm")
    label_fy.config(text=f"Steel Yield (fy): {current_fy} MPa")

    # Clear inputs
    entry_base.delete(0, tk.END)
    entry_modifier.delete(0, tk.END)
    entry_final.delete(0, tk.END)

    result_label.config(text="Fill in the 3 values below and press ENTER", fg="black")
    detail_feedback.config(text="")
    update_score()

    # Focus on Base input
    entry_base.focus()

def check_answer():
    global score_base, score_mod, score_final, score_total
    
    if current_span_mm == 0.0:
        messagebox.showinfo("Start", "Please click 'Generate New Beam' first!")
        return

    try:
        user_base = float(entry_base.get().strip())
        user_mod = float(entry_modifier.get().strip())
        user_final = float(entry_final.get().strip())
    except ValueError:
        messagebox.showwarning("Input Error", "Please enter valid decimal numbers in all 3 fields.")
        return
        
    score_total += 1
    
    # Check each part individually and update scores
    feedback_text = []
    
    # Check Base h
    if abs(user_base - correct_base_h) <= 1.0: # Allow 1mm variance
        score_base += 1
        feedback_text.append("✅ Base h")
    else:
        feedback_text.append(f"❌ Base h (Correct: {round(correct_base_h, 1)} mm)")
        
    # Check Modifier
    if abs(user_mod - correct_modifier) <= 0.001:
        score_mod += 1
        feedback_text.append("✅ Modifier")
    else:
        feedback_text.append(f"❌ Modifier (Correct: {round(correct_modifier, 4)})")
        
    # Check Final h
    if abs(user_final - correct_final_h) <= 1.0:
        score_final += 1
        feedback_text.append("✅ Final h")
    else:
        feedback_text.append(f"❌ Final h (Correct: {round(correct_final_h, 1)} mm)")

    result_label.config(text=" | ".join(feedback_text), fg="black")
    detail_feedback.config(
        text=f"Formula Check: Base = ℓ / {16 if current_support == 'Simply supported' else 18.5 if current_support == 'One end continuous' else 21 if current_support == 'Both ends continuous' else 8} | Mod = 0.4 + fy/700", 
        fg="gray"
    )
    update_score()

def show_hint():
    hint_text = (
        "How to solve this problem step-by-step:\n\n"
        "1. Find the BASE Minimum h using the table 409.3.1.1:\n"
        "    - Simply supported: ℓ / 16\n"
        "    - One end continuous: ℓ / 18.5\n"
        "    - Both ends continuous: ℓ / 21\n"
        "    - Cantilever: ℓ / 8\n"
        "   * (Assume normal weight concrete)\n\n"
        "2. Calculate the MODIFIER from Section 409.3.1.1.1:\n"
        "    - Modifier = 0.4 + (fy / 700)\n\n"
        "3. Calculate the FINAL Minimum Depth:\n"
        "    - Final h = Base h × Modifier\n"
        "    - (Round up to nearest whole mm if needed)"
    )
    messagebox.showinfo("📐 Step-by-Step Hint", hint_text)

def update_score():
    if score_total == 0:
        score_label.config(text="Score: 0 / 0")
    else:
        score_label.config(text=f"Base: {score_base}/{score_total} | Mod: {score_mod}/{score_total} | Final: {score_final}/{score_total}")

# --- GUI Setup ---
root = tk.Tk()
root.title("Beam Minimum Depth Reviewer (ACI 318)")
root.geometry("650x520")
root.resizable(False, False)

root.bind('<Return>', lambda event: check_answer())

# 1. Header
tk.Label(root, text="Non-Prestressed Beam Depth Reviewer", font=("Arial", 14, "bold")).pack(pady=10)

# 2. Generate Button
btn_generate = tk.Button(root, text="🔄 Generate New Beam", command=generate_problem, bg="#ececec", font=("Arial", 10, "bold"))
btn_generate.pack(pady=10)

# 3. Display Problem Values
frame_values = tk.Frame(root)
frame_values.pack(pady=10)
label_support = tk.Label(frame_values, text="Support Condition: -", font=("Arial", 11))
label_support.pack()
label_span = tk.Label(frame_values, text="Span (ℓ): - mm", font=("Arial", 11))
label_span.pack()
label_fy = tk.Label(frame_values, text="Steel Yield (fy): - MPa", font=("Arial", 11))
label_fy.pack()

# 4. User Input Fields
frame_inputs = tk.LabelFrame(root, text="Your Calculations", padx=10, pady=10)
frame_inputs.pack(pady=15)

tk.Label(frame_inputs, text="Base Minimum h (mm):").grid(row=0, column=0, pady=5, sticky="e")
entry_base = tk.Entry(frame_inputs, width=15)
entry_base.grid(row=0, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(Assume fy=420 MPa, Table 409)", font=("Arial", 8), fg="gray").grid(row=0, column=2, pady=5, sticky="w")

tk.Label(frame_inputs, text="Modifier Factor:").grid(row=1, column=0, pady=5, sticky="e")
entry_modifier = tk.Entry(frame_inputs, width=15)
entry_modifier.grid(row=1, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(0.4 + fy/700)", font=("Arial", 8), fg="gray").grid(row=1, column=2, pady=5, sticky="w")

tk.Label(frame_inputs, text="Final Minimum h (mm):").grid(row=2, column=0, pady=5, sticky="e")
entry_final = tk.Entry(frame_inputs, width=15)
entry_final.grid(row=2, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(Base h x Modifier)", font=("Arial", 8), fg="gray").grid(row=2, column=2, pady=5, sticky="w")

# 5. Action Buttons
frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=15)

btn_check = tk.Button(frame_buttons, text="✅ Check My Answers", command=check_answer, bg="#b3d9ff", font=("Arial", 10, "bold"), width=15)
btn_check.pack(side="left", padx=5)

btn_hint = tk.Button(frame_buttons, text="💡 How to Solve", command=show_hint, bg="#fff3cd", font=("Arial", 10, "bold"), width=15)
btn_hint.pack(side="left", padx=5)

# 6. Results & Score
frame_results = tk.Frame(root)
frame_results.pack(pady=10)

result_label = tk.Label(frame_results, text="", font=("Arial", 11, "bold"))
result_label.pack()

detail_feedback = tk.Label(frame_results, text="", font=("Arial", 9), fg="gray")
detail_feedback.pack(pady=2)

score_label = tk.Label(root, text="Score: 0 / 0", font=("Arial", 10, "bold"))
score_label.pack(side="bottom", pady=10)

# Initialize a problem on launch
generate_problem()

root.mainloop()