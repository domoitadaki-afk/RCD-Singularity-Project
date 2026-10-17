import tkinter as tk
from tkinter import messagebox
import random

# Global variables to track current problem and score
current_fy = 0
current_fs = 0
correct_answer = ""
correct_phi = 0.0
score_class_correct = 0
score_phi_correct = 0
score_total = 0

def generate_problem():
    global current_fy, current_fs, correct_answer, correct_phi
    
    # Generate randomized values
    current_fy = random.randint(250, 550)
    current_fs = random.randint(100, 1500)
    
    # Calculate the correct answer
    if current_fs <= current_fy:
        correct_answer = "Compression-controlled"
        correct_phi = 0.65
    elif current_fs > 1000:
        correct_answer = "Tension-controlled"
        correct_phi = 0.90
    else:
        correct_answer = "Transition"
        # Professor's equation: 0.25(fs-fy)/(1000-fy) + 0.65
        correct_phi = 0.65 + (0.25 * (current_fs - current_fy) / (1000 - current_fy))
        correct_phi = round(correct_phi, 4)

    # Update UI
    label_fy.config(text=f"fy = {current_fy} MPa")
    label_fs.config(text=f"fs = {current_fs} MPa")
    
    entry_class.delete(0, tk.END)
    entry_phi.delete(0, tk.END)
    result_label.config(text="Type your answers and press ENTER", fg="black")
    answer_reveal_label.config(text="")
    update_score()
    
    # Focus on the first input box to start typing immediately
    entry_class.focus()

def check_answer():
    global score_class_correct, score_phi_correct, score_total
    
    if current_fy == 0:
        messagebox.showinfo("Start", "Please click 'Generate New Problem' first!")
        return

    user_class = entry_class.get().strip()
    user_phi_str = entry_phi.get().strip()
    
    if not user_class or not user_phi_str:
        messagebox.showwarning("Missing Input", "Please enter both the Classification and the Phi value.")
        return
    
    score_total += 1
    
    # Validate Classification
    is_class_correct = user_class.lower() == correct_answer.lower()
    
    # Validate Phi
    try:
        user_phi = float(user_phi_str)
        is_phi_correct = abs(user_phi - correct_phi) <= 0.001
    except ValueError:
        is_phi_correct = False

    if is_class_correct: score_class_correct += 1
    if is_phi_correct: score_phi_correct += 1

    class_result_text = "✅ Correct" if is_class_correct else "❌ Incorrect"
    phi_result_text = "✅ Correct" if is_phi_correct else f"❌ Incorrect. Correct value: {correct_phi}"
    
    result_label.config(text=f"Classification: {class_result_text}  |  Phi (φ): {phi_result_text}", fg="black")
    answer_reveal_label.config(text=f"Correct Class: {correct_answer}", fg="blue")
    
    update_score()

def show_hint():
    # Displaying the equation with Unicode subscripts to look like LaTeX
    hint_text = (
        "Transition Zone Formula:\n\n"
        "φ = 0.65 + [ 0.25(fₛ - fᵧ) ] / ( 1000 - fᵧ )\n\n"
        "Where:\n"
        "- fₛ = Steel stress (fs)\n"
        "- fᵧ = Yield strength (fy)\n\n"
        "This equation applies ONLY when:\nfᵧ < fₛ < 1000"
    )
    messagebox.showinfo("📐 Equation Hint", hint_text)

def update_score():
    score_label.config(text=f"Class Score: {score_class_correct}/{score_total}  |  Phi Score: {score_phi_correct}/{score_total}")

# --- GUI Setup ---
root = tk.Tk()
root.title("RC Beam Classification - Fill in the Blank")
root.geometry("540x480") # Slightly wider to fit the hint button nicely
root.resizable(False, False)

# BINDING THE ENTER KEY TO THE CHECK FUNCTION
root.bind('<Return>', lambda event: check_answer())

# 1. Header
tk.Label(root, text="Reinforced Concrete Beam Self-Quiz", font=("Arial", 14, "bold")).pack(pady=10)

# 2. Generate Button
btn_generate = tk.Button(root, text="🔄 Generate New Problem", command=generate_problem, bg="#ececec", font=("Arial", 10, "bold"))
btn_generate.pack(pady=10)

# 3. Display Values
frame_values = tk.Frame(root)
frame_values.pack(pady=10)
label_fy = tk.Label(frame_values, text="fy = -", font=("Arial", 12))
label_fy.pack()
label_fs = tk.Label(frame_values, text="fs = -", font=("Arial", 12))
label_fs.pack()

# 4. User Input Fields
frame_inputs = tk.LabelFrame(root, text="Your Answers", padx=10, pady=10)
frame_inputs.pack(pady=15)

tk.Label(frame_inputs, text="Classification:").grid(row=0, column=0, pady=5, sticky="e")
entry_class = tk.Entry(frame_inputs, width=25)
entry_class.grid(row=0, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(Compression, Transition, or Tension)", font=("Arial", 8), fg="gray").grid(row=0, column=2, pady=5, sticky="w")

tk.Label(frame_inputs, text="Phi (φ):").grid(row=1, column=0, pady=5, sticky="e")
entry_phi = tk.Entry(frame_inputs, width=25)
entry_phi.grid(row=1, column=1, pady=5, padx=5)
tk.Label(frame_inputs, text="(Type the decimal value)", font=("Arial", 8), fg="gray").grid(row=1, column=2, pady=5, sticky="w")

# 5. Action Buttons (Check & Hint)
frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=10)

btn_check = tk.Button(frame_buttons, text="✅ Show Answer / Check", command=check_answer, bg="#b3d9ff", font=("Arial", 10, "bold"))
btn_check.pack(side="left", padx=5)

btn_hint = tk.Button(frame_buttons, text="💡 Hint: Transition Eq", command=show_hint, bg="#fff3cd", font=("Arial", 10, "bold"))
btn_hint.pack(side="left", padx=5)

# 6. Results & Score
frame_results = tk.Frame(root)
frame_results.pack(pady=10)

result_label = tk.Label(frame_results, text="", font=("Arial", 11))
result_label.pack()

answer_reveal_label = tk.Label(frame_results, text="", font=("Arial", 11, "bold"))
answer_reveal_label.pack()

score_label = tk.Label(root, text="Class Score: 0 / 0  |  Phi Score: 0 / 0", font=("Arial", 10, "bold"))
score_label.pack(side="bottom", pady=10)

# Initialize a problem when the app starts
generate_problem()

root.mainloop()