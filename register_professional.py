"""Modern registration window built on top of the shared capture workflow."""

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as tb

from register import capture_faces, generate_new_id
from ui.theme import COLORS, apply_app_theme, create_card


def open_register_window():
    """Open the themed student registration window used by the dashboard."""

    app = tb.Window(themename="litera")
    apply_app_theme()
    app.title("Register Student")
    app.geometry("620x640")
    app.minsize(520, 480)
    app.resizable(True, True)
    app.configure(background=COLORS["bg"])

    student_id_state = {"value": generate_new_id()}
    student_id_text = tk.StringVar(value=f"Student ID: {student_id_state['value']}")

    wrapper = tb.Frame(app, style="App.TFrame", padding=(24, 24, 24, 20))
    wrapper.pack(fill="both", expand=True)

    scroll_shell = tb.Frame(wrapper, style="App.TFrame")
    scroll_shell.pack(fill="both", expand=True)

    canvas = tk.Canvas(
        scroll_shell,
        background=COLORS["bg"],
        highlightthickness=0,
        bd=0,
    )
    scrollbar = tb.Scrollbar(scroll_shell, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    body = tb.Frame(canvas, style="App.TFrame")
    body_window = canvas.create_window((0, 0), window=body, anchor="nw")

    def sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def fit_body_width(event):
        canvas.itemconfigure(body_window, width=event.width)

    def on_mousewheel(event):
        canvas.yview_scroll(-int(event.delta / 120), "units")

    def bind_mousewheel(_event=None):
        canvas.bind_all("<MouseWheel>", on_mousewheel)

    def unbind_mousewheel(_event=None):
        canvas.unbind_all("<MouseWheel>")

    body.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", fit_body_width)
    scroll_shell.bind("<Enter>", bind_mousewheel)
    scroll_shell.bind("<Leave>", unbind_mousewheel)
    scroll_shell.bind("<Destroy>", unbind_mousewheel)

    intro_card = create_card(body, padding=18, style="SoftCard.TFrame")
    intro_card.pack(fill="x", pady=(0, 16))

    tb.Label(intro_card, text="Student Registration", style="SectionTitleAlt.TLabel").pack(anchor="w")
    tb.Label(
        intro_card,
        text="Enter student details, then start face capture and fingerprint registration. "
             "This window stays open so you can add multiple students in one session.",
        style="MutedAlt.TLabel",
        wraplength=520,
        justify="left",
    ).pack(anchor="w", pady=(6, 0))

    form_card = create_card(body, padding=22)
    form_card.pack(fill="x")

    tb.Label(form_card, textvariable=student_id_text, style="SectionTitle.TLabel").pack(anchor="w")
    tb.Label(
        form_card,
        text="Enter the student details below before starting the face and fingerprint capture workflow.",
        style="Muted.TLabel",
        wraplength=500,
        justify="left",
    ).pack(anchor="w", pady=(6, 16))

    tb.Label(form_card, text="Student Name", style="SectionTitle.TLabel").pack(anchor="w")
    name_entry = tb.Entry(form_card, width=34, style="App.TEntry")
    name_entry.pack(fill="x", pady=(6, 14))

    tb.Label(form_card, text="Enrollment Number", style="SectionTitle.TLabel").pack(anchor="w")
    enroll_entry = tb.Entry(form_card, width=34, style="App.TEntry")
    enroll_entry.pack(fill="x", pady=(6, 14))

    tb.Label(form_card, text="Parent Phone Number", style="SectionTitle.TLabel").pack(anchor="w")
    phone_entry = tb.Entry(form_card, width=34, style="App.TEntry")
    phone_entry.pack(fill="x", pady=(6, 0))

    def focus_name_field():
        app.after(50, name_entry.focus_set)

    def set_form_enabled(enabled):
        state = "normal" if enabled else "disabled"
        start_button.configure(state=state)
        close_button.configure(state=state)

    def prepare_next_student():
        student_id_state["value"] = generate_new_id()
        student_id_text.set(f"Student ID: {student_id_state['value']}")

        for entry in (name_entry, enroll_entry, phone_entry):
            entry.delete(0, "end")

        focus_name_field()

    def start():
        name = name_entry.get().strip()
        enrollment = enroll_entry.get().strip()
        phone = phone_entry.get().strip()

        if not name or not enrollment:
            messagebox.showerror("Error", "Name and enrollment are required")
            return

        set_form_enabled(False)
        app.update_idletasks()

        try:
            success = capture_faces(student_id_state["value"], name, enrollment, phone)
        finally:
            set_form_enabled(True)
            app.update_idletasks()

        if success:
            prepare_next_student()
        else:
            focus_name_field()

    actions = tb.Frame(wrapper, style="App.TFrame")
    actions.pack(fill="x", pady=(16, 0))

    close_button = tb.Button(
        actions,
        text="Close",
        bootstyle="secondary-outline",
        command=app.destroy,
    )
    close_button.pack(side="right", padx=(10, 0))

    start_button = tb.Button(
        actions,
        text="Start Registration",
        bootstyle="primary",
        width=20,
        command=start,
    )
    start_button.pack(side="right")

    focus_name_field()

    app.mainloop()


if __name__ == "__main__":
    open_register_window()
