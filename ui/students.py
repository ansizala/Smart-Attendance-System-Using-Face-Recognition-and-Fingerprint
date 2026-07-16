"""Student directory pages for listing, editing, and reviewing profiles."""

import csv
import os
import shutil
from collections import defaultdict
from tkinter import messagebox

import ttkbootstrap as tb
from PIL import Image, ImageTk

from services.esp32_service import notify_fingerprint_register
from services.google_service import get_sheet_data
from ui.theme import COLORS, build_scrollable_page, create_card, create_empty_state, create_key_value_row, create_scrollable_body

DATASET_PATH = "dataset"
CSV_FILE = "student_info.csv"
IMAGE_RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


def load_students():
    """Load student records from the local CSV file keyed by student ID."""

    students = {}

    if not os.path.exists(CSV_FILE):
        return students

    with open(CSV_FILE) as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            students[row["ID"]] = {
                "name": row["Name"],
                "enrollment": row["Enrollment"],
                "phone": row["ParentPhone"],
            }

    return students


def find_student_folder(student_id):
    """Locate the dataset folder that belongs to the given student ID."""

    if not os.path.exists(DATASET_PATH):
        return None

    suffix = f"_{student_id}"

    for folder_name in os.listdir(DATASET_PATH):
        folder_path = os.path.join(DATASET_PATH, folder_name)
        if os.path.isdir(folder_path) and folder_name.endswith(suffix):
            return folder_path

    return None


def list_student_records():
    """Combine student CSV records with dataset folder and sample metadata."""

    students = load_students()
    records = []

    for student_id, student in students.items():
        folder_path = find_student_folder(student_id)
        sample_count = 0

        if folder_path and os.path.exists(folder_path):
            sample_count = sum(
                1 for file_name in os.listdir(folder_path)
                if file_name.lower().endswith(".jpg")
            )

        records.append(
            {
                "student_id": student_id,
                "name": student["name"],
                "enrollment": student["enrollment"],
                "phone": student["phone"],
                "folder_path": folder_path,
                "sample_count": sample_count,
            }
        )

    return sorted(records, key=lambda item: item["name"].lower())


def load_thumbnail(folder_path, size):
    """Load the first saved face sample as a square thumbnail image."""

    if not folder_path or not os.path.exists(folder_path):
        return None

    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(".jpg"):
            img_path = os.path.join(folder_path, file_name)
            image = Image.open(img_path)
            image = image.resize((size, size), IMAGE_RESAMPLE)
            return ImageTk.PhotoImage(image)

    return None


def reenroll_fingerprint(student_id, name):
    """Re-enroll the fingerprint template for an existing student ID."""

    confirm = messagebox.askyesno(
        "Re-enroll Fingerprint",
        f"Re-enroll fingerprint for {name} (ID {student_id})?\n\n"
        "Use this when the ESP32 sensor reports a different stored ID than the local student record.",
    )

    if not confirm:
        return

    try:
        numeric_id = int(student_id)
    except ValueError:
        messagebox.showerror("Fingerprint Error", f"Invalid student ID: {student_id}")
        return

    messagebox.showinfo(
        "Fingerprint",
        f"Place the same finger on the sensor twice.\nID: {numeric_id}",
    )

    success = notify_fingerprint_register(numeric_id)

    if success:
        messagebox.showinfo(
            "Fingerprint Updated",
            f"Fingerprint re-enrolled for {name} (ID {numeric_id}).",
        )
    else:
        messagebox.showerror(
            "Fingerprint Error",
            "Fingerprint re-enrollment failed.\n\n"
            "If the sensor IDs are out of sync, clear the fingerprint database from the dashboard and try again.",
        )


def delete_student(student_id, name, refresh_ui):
    """Delete a student record and its saved dataset after confirmation."""

    confirm = messagebox.askyesno(
        "Confirm",
        f"Delete {name}?\n\n"
        "This removes the local profile and face samples only. "
        "Fingerprint data on the ESP32 sensor is not deleted automatically.",
    )

    if not confirm:
        return

    rows = []

    with open(CSV_FILE, "r") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            if row["ID"] != student_id:
                rows.append(row)

    with open(CSV_FILE, "w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["ID", "Name", "Enrollment", "ParentPhone"],
        )
        writer.writeheader()
        writer.writerows(rows)

    folder_path = find_student_folder(student_id)
    if folder_path and os.path.exists(folder_path):
        shutil.rmtree(folder_path)

    messagebox.showinfo("Deleted", f"{name} removed successfully")
    refresh_ui()


def edit_student(student_id, student_data, refresh_ui):
    """Open the student edit dialog and persist any confirmed updates."""

    win = tb.Toplevel()
    win.title("Edit Student")
    win.geometry("540x560")
    win.minsize(460, 420)
    win.resizable(True, True)
    win.configure(background=COLORS["bg"])

    wrapper = tb.Frame(win, style="App.TFrame", padding=(24, 24, 24, 24))
    wrapper.pack(fill="both", expand=True)

    content_area = tb.Frame(wrapper, style="App.TFrame")
    content_area.pack(fill="both", expand=True)

    body = create_scrollable_body(content_area)

    tb.Label(body, text="Edit Student", style="PageTitle.TLabel").pack(anchor="w")
    tb.Label(
        body,
        text="Update the student record while keeping the profile aligned with the refreshed design system.",
        style="PageSubtitle.TLabel",
        justify="left",
        wraplength=430,
    ).pack(anchor="w", pady=(6, 18))

    form_card = create_card(body, padding=20)
    form_card.pack(fill="x")

    tb.Label(form_card, text="Student Name", style="SectionTitle.TLabel").pack(anchor="w")
    name_entry = tb.Entry(form_card, style="App.TEntry")
    name_entry.insert(0, student_data["name"])
    name_entry.pack(fill="x", pady=(6, 14))

    tb.Label(form_card, text="Enrollment Number", style="SectionTitle.TLabel").pack(anchor="w")
    enroll_entry = tb.Entry(form_card, style="App.TEntry")
    enroll_entry.insert(0, student_data["enrollment"])
    enroll_entry.pack(fill="x", pady=(6, 14))

    tb.Label(form_card, text="Parent Phone Number", style="SectionTitle.TLabel").pack(anchor="w")
    phone_entry = tb.Entry(form_card, style="App.TEntry")
    phone_entry.insert(0, student_data["phone"])
    phone_entry.pack(fill="x", pady=(6, 0))

    def save():
        new_name = name_entry.get().strip()
        new_enroll = enroll_entry.get().strip()
        new_phone = phone_entry.get().strip()

        if not new_name or not new_enroll:
            messagebox.showerror("Error", "Name and enrollment are required")
            return

        rows = []

        with open(CSV_FILE, "r") as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                if row["ID"] == student_id:
                    row["Name"] = new_name
                    row["Enrollment"] = new_enroll
                    row["ParentPhone"] = new_phone
                rows.append(row)

        with open(CSV_FILE, "w", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=["ID", "Name", "Enrollment", "ParentPhone"],
            )
            writer.writeheader()
            writer.writerows(rows)

        old_folder_path = find_student_folder(student_id)
        if old_folder_path:
            new_folder_path = os.path.join(DATASET_PATH, f"{new_name}_{student_id}")
            if old_folder_path != new_folder_path and not os.path.exists(new_folder_path):
                os.rename(old_folder_path, new_folder_path)

        messagebox.showinfo("Updated", "Student updated successfully")
        win.destroy()
        refresh_ui()

    actions = tb.Frame(wrapper, style="App.TFrame")
    actions.pack(fill="x", pady=(18, 0))

    tb.Button(actions, text="Cancel", bootstyle="secondary-outline", command=win.destroy).pack(side="right", padx=(10, 0))
    tb.Button(actions, text="Save Changes", bootstyle="primary", command=save).pack(side="right")


def view_students(content):
    """Render the searchable student directory page."""

    _page, body = build_scrollable_page(
        content,
        "Student Directory",
        "Manage every registered student from one consistent view with cleaner cards, spacing, and actions.",
    )

    records = list_student_records()

    summary = tb.Frame(body, style="App.TFrame")
    summary.pack(fill="x", pady=(0, 18))
    summary.columnconfigure(0, weight=1)
    summary.columnconfigure(1, weight=1)
    summary.columnconfigure(2, weight=1)

    total_card = create_card(summary, padding=20)
    total_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    tb.Label(total_card, text="Registered Students", style="MetricTitle.TLabel", foreground=COLORS["accent"]).pack(anchor="w")
    tb.Label(total_card, text=str(len(records)), style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))

    dataset_card = create_card(summary, padding=20)
    dataset_card.grid(row=0, column=1, sticky="nsew", padx=10)
    dataset_count = sum(1 for record in records if record["folder_path"])
    tb.Label(dataset_card, text="Dataset Profiles", style="MetricTitle.TLabel", foreground=COLORS["success"]).pack(anchor="w")
    tb.Label(dataset_card, text=str(dataset_count), style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))

    visible_card = create_card(summary, padding=20)
    visible_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
    tb.Label(visible_card, text="Visible Results", style="MetricTitle.TLabel", foreground=COLORS["warning"]).pack(anchor="w")
    visible_value = tb.Label(visible_card, text=str(len(records)), style="MetricValue.TLabel")
    visible_value.pack(anchor="w", pady=(8, 0))

    search_card = create_card(body, padding=20)
    search_card.pack(fill="x", pady=(0, 18))

    tb.Label(search_card, text="Search Students", style="SectionTitle.TLabel").pack(anchor="w")
    tb.Label(
        search_card,
        text="Find by name, enrollment number, student ID, or parent phone number.",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(6, 12))

    search_var = tb.StringVar()
    search_entry = tb.Entry(search_card, textvariable=search_var, style="App.TEntry")
    search_entry.pack(fill="x")

    list_container = tb.Frame(body, style="App.TFrame")
    list_container.pack(fill="x", pady=(0, 10))
    list_container.image_refs = []

    def render_students(filter_text=""):
        for widget in list_container.winfo_children():
            widget.destroy()

        list_container.image_refs = []
        keyword = filter_text.strip().lower()

        filtered_records = [
            record for record in records
            if not keyword
            or keyword in record["name"].lower()
            or keyword in record["enrollment"].lower()
            or keyword in record["student_id"].lower()
            or keyword in record["phone"].lower()
        ]

        visible_value.configure(text=str(len(filtered_records)))

        if not filtered_records:
            empty = create_empty_state(
                list_container,
                "No matching students",
                "Try a different name, enrollment number, or student ID to find the profile you need.",
            )
            empty.pack(fill="x", pady=10)
            return

        for record in filtered_records:
            student_card = create_card(list_container, padding=18)
            student_card.pack(fill="x", pady=8)

            top_row = tb.Frame(student_card, style="Card.TFrame")
            top_row.pack(fill="x")

            photo = load_thumbnail(record["folder_path"], 74)
            if photo:
                avatar = tb.Label(top_row, image=photo, background=COLORS["surface"])
                avatar.image = photo
                list_container.image_refs.append(photo)
                avatar.pack(side="left", padx=(0, 16))
            else:
                initials = "".join(part[:1].upper() for part in record["name"].split()[:2]) or "NA"
                placeholder = tb.Label(
                    top_row,
                    text=initials,
                    background=COLORS["accent_soft"],
                    foreground=COLORS["accent"],
                    font=("Segoe UI", 15, "bold"),
                    width=6,
                    padding=(12, 18),
                )
                placeholder.pack(side="left", padx=(0, 16))

            detail_frame = tb.Frame(top_row, style="Card.TFrame")
            detail_frame.pack(side="left", fill="x", expand=True)

            tb.Label(detail_frame, text=record["name"], style="SectionTitle.TLabel").pack(anchor="w")
            tb.Label(
                detail_frame,
                text=f"Enrollment: {record['enrollment']}   |   Student ID: {record['student_id']}",
                style="Muted.TLabel",
            ).pack(anchor="w", pady=(4, 4))
            tb.Label(
                detail_frame,
                text=f"Parent phone: {record['phone'] or 'Not provided'}   |   Face samples: {record['sample_count']}",
                style="Body.TLabel",
            ).pack(anchor="w")

            action_frame = tb.Frame(top_row, style="Card.TFrame")
            action_frame.pack(side="right", padx=(16, 0))

            tb.Button(
                action_frame,
                text="View Profile",
                bootstyle="primary",
                command=lambda sid=record["student_id"]: show_student_profile(content, sid),
            ).pack(side="left", padx=5)
            tb.Button(
                action_frame,
                text="Edit",
                bootstyle="secondary-outline",
                command=lambda sid=record["student_id"], data=record: edit_student(
                    sid,
                    {"name": data["name"], "enrollment": data["enrollment"], "phone": data["phone"]},
                    lambda: view_students(content),
                ),
            ).pack(side="left", padx=5)
            tb.Button(
                action_frame,
                text="Delete",
                bootstyle="danger-outline",
                command=lambda sid=record["student_id"], name=record["name"]: delete_student(sid, name, lambda: view_students(content)),
            ).pack(side="left", padx=5)

    search_var.trace_add("write", lambda *_: render_students(search_var.get()))
    render_students()


def show_student_profile(content, student_id):
    """Render the profile page for a single registered student."""

    students_db = load_students()
    student = students_db.get(student_id)

    if not student:
        messagebox.showerror("Missing Student", "The selected student record could not be found.")
        return

    name = student["name"]
    enrollment = student["enrollment"]
    folder_path = find_student_folder(student_id)

    _page, body = build_scrollable_page(
        content,
        name,
        "Student profile, attendance progress, and history details.",
        lambda: view_students(content),
    )

    profile_card = create_card(body, padding=24)
    profile_card.pack(fill="x", pady=(0, 20))

    photo = load_thumbnail(folder_path, 140)

    media = tb.Frame(profile_card, style="Card.TFrame")
    media.pack(side="left", padx=(0, 22))

    if photo:
        image_label = tb.Label(media, image=photo, background=COLORS["surface"])
        image_label.image = photo
        image_label.pack()
    else:
        initials = "".join(part[:1].upper() for part in name.split()[:2]) or "NA"
        tb.Label(
            media,
            text=initials,
            background=COLORS["accent_soft"],
            foreground=COLORS["accent"],
            font=("Segoe UI", 28, "bold"),
            width=8,
            padding=(18, 42),
        ).pack()

    details = tb.Frame(profile_card, style="Card.TFrame")
    details.pack(side="left", fill="both", expand=True)

    tb.Label(details, text=name, style="PageTitle.TLabel", background=COLORS["surface"]).pack(anchor="w")
    tb.Label(
        details,
        text=f"Enrollment: {enrollment}   |   Student ID: {student_id}",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(4, 8))

    create_key_value_row(details, "Parent phone", student["phone"] or "Not provided")
    create_key_value_row(details, "Dataset samples", str(_count_samples(folder_path)))

    fingerprint_actions = tb.Frame(details, style="Card.TFrame")
    fingerprint_actions.pack(anchor="w", pady=(14, 0))

    tb.Button(
        fingerprint_actions,
        text="Re-enroll Fingerprint",
        bootstyle="secondary-outline",
        command=lambda: reenroll_fingerprint(student_id, name),
    ).pack(side="left")

    tb.Label(
        details,
        text="Use this if attendance says the sensor matched a different fingerprint ID than this profile expects.",
        style="Muted.TLabel",
        justify="left",
        wraplength=520,
    ).pack(anchor="w", pady=(10, 0))

    data = get_sheet_data()
    rows = data[1:] if len(data) > 1 else []

    attendance_count = defaultdict(int)
    unique_dates = set()

    for row in rows:
        if len(row) < 2:
            continue
        unique_dates.add(row[0])
        attendance_count[row[1]] += 1

    working_days = len(unique_dates)
    present_days = attendance_count[enrollment]
    percentage = (present_days / working_days) * 100 if working_days else 0

    stats_row = tb.Frame(body, style="App.TFrame")
    stats_row.pack(fill="x", pady=(0, 20))
    stats_row.columnconfigure(0, weight=1)
    stats_row.columnconfigure(1, weight=1)
    stats_row.columnconfigure(2, weight=1)

    present_card = create_card(stats_row, padding=20)
    present_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    tb.Label(present_card, text="Present Days", style="MetricTitle.TLabel", foreground=COLORS["success"]).pack(anchor="w")
    tb.Label(present_card, text=str(present_days), style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))

    days_card = create_card(stats_row, padding=20)
    days_card.grid(row=0, column=1, sticky="nsew", padx=10)
    tb.Label(days_card, text="Working Days", style="MetricTitle.TLabel", foreground=COLORS["warning"]).pack(anchor="w")
    tb.Label(days_card, text=str(working_days), style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))

    percent_card = create_card(stats_row, padding=20)
    percent_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
    tb.Label(percent_card, text="Attendance", style="MetricTitle.TLabel", foreground=COLORS["accent"]).pack(anchor="w")
    tb.Label(percent_card, text=f"{percentage:.1f}%", style="MetricValue.TLabel").pack(anchor="w", pady=(8, 6))
    tb.Progressbar(percent_card, style="App.Horizontal.TProgressbar", value=percentage).pack(fill="x", pady=(6, 0))

    history_card = create_card(body, padding=22)
    history_card.pack(fill="x")

    tb.Label(history_card, text="Attendance History", style="SectionTitle.TLabel").pack(anchor="w")
    tb.Label(
        history_card,
        text="Recorded attendance events for the selected student.",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(6, 14))

    history_rows = [
        row for row in rows
        if len(row) >= 4 and row[1] == enrollment
    ]

    if not history_rows:
        empty = create_empty_state(
            history_card,
            "No attendance history yet",
            "Attendance records will appear here once the student is recognized and verified.",
        )
        empty.pack(fill="x")
        return

    table_frame = tb.Frame(history_card, style="Card.TFrame", height=320)
    table_frame.pack(fill="x")
    table_frame.pack_propagate(False)

    tree = tb.Treeview(
        table_frame,
        columns=("Date", "Time"),
        show="headings",
        style="Data.Treeview",
    )
    tree.heading("Date", text="Date")
    tree.heading("Time", text="Time")
    tree.column("Date", anchor="center", width=180)
    tree.column("Time", anchor="center", width=180)

    scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    sorted_rows = sorted(history_rows, key=lambda row: (row[0], row[3]), reverse=True)
    for row in sorted_rows:
        tree.insert("", "end", values=(row[0], row[3]))


def _count_samples(folder_path):
    """Count the number of saved face samples inside a student folder."""

    if not folder_path or not os.path.exists(folder_path):
        return 0

    return sum(
        1 for file_name in os.listdir(folder_path)
        if file_name.lower().endswith(".jpg")
    )
