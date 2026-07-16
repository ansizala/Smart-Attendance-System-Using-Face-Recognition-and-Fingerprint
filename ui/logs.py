"""Attendance log viewer for searching and opening student activity records."""

from datetime import datetime

import ttkbootstrap as tb

from services.google_service import get_sheet_data
from ui.students import load_students, show_student_profile
from ui.theme import COLORS, build_scrollable_page, create_card


def view_logs(content):
    """Render the searchable attendance log table."""

    _page, body = build_scrollable_page(
        content,
        "Attendance Logs",
        "Search, review, and open student activity records from a cleaner operational table.",
    )

    summary = tb.Frame(body, style="App.TFrame")
    summary.pack(fill="x", pady=(0, 18))
    summary.columnconfigure(0, weight=1)
    summary.columnconfigure(1, weight=1)
    summary.columnconfigure(2, weight=1)

    def build_summary_card(parent, title, accent, column, padx):
        card = create_card(parent, padding=20)
        card.grid(row=0, column=column, sticky="nsew", padx=padx)
        tb.Label(card, text=title, style="MetricTitle.TLabel", foreground=accent).pack(anchor="w")
        value_label = tb.Label(card, text="0", style="MetricValue.TLabel")
        value_label.pack(anchor="w", pady=(8, 0))
        return value_label

    total_label = build_summary_card(summary, "Total Records", COLORS["accent"], 0, (0, 10))
    today_label = build_summary_card(summary, "Today", COLORS["success"], 1, 10)
    student_label = build_summary_card(summary, "Students", COLORS["warning"], 2, (10, 0))

    toolbar = create_card(body, padding=20)
    toolbar.pack(fill="x", pady=(0, 18))

    tb.Label(toolbar, text="Search Records", style="SectionTitle.TLabel").pack(anchor="w")
    tb.Label(
        toolbar,
        text="Filter by date, enrollment, name, or time. Double-click a row to open the student profile.",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(6, 12))

    controls = tb.Frame(toolbar, style="Card.TFrame")
    controls.pack(fill="x")

    search_var = tb.StringVar()
    search_entry = tb.Entry(controls, textvariable=search_var, style="App.TEntry")
    search_entry.pack(side="left", fill="x", expand=True)

    results_note = tb.Label(controls, text="0 results", style="Muted.TLabel")
    results_note.pack(side="right", padx=(12, 0))

    table_card = create_card(body, padding=20)
    table_card.pack(fill="x", pady=(0, 10))

    table_header = tb.Frame(table_card, style="Card.TFrame")
    table_header.pack(fill="x", pady=(0, 12))

    tb.Label(table_header, text="Activity Table", style="SectionTitle.TLabel").pack(side="left")

    table_frame = tb.Frame(table_card, style="Card.TFrame", height=360)
    table_frame.pack(fill="x")
    table_frame.pack_propagate(False)

    tree = tb.Treeview(
        table_frame,
        columns=("Date", "Enrollment", "Name", "Time"),
        show="headings",
        style="Data.Treeview",
    )

    for col in ("Date", "Enrollment", "Name", "Time"):
        tree.heading(col, text=col)

    tree.column("Date", anchor="center", width=150)
    tree.column("Enrollment", anchor="center", width=170)
    tree.column("Name", anchor="w", width=220)
    tree.column("Time", anchor="center", width=150)

    scrollbar = tb.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    all_rows = []

    def render_rows(rows):
        tree.delete(*tree.get_children())

        for row in rows:
            tree.insert("", "end", values=row)

        total_label.configure(text=str(len(all_rows)))
        today_label.configure(text=str(len({row[1] for row in all_rows if len(row) >= 2 and row[0] == _today_string()})))
        student_label.configure(text=str(len({row[1] for row in all_rows if len(row) >= 2})))
        results_note.configure(text=f"{len(rows)} results")

    def current_filtered_rows():
        keyword = search_var.get().strip().lower()
        if not keyword:
            return all_rows

        return [
            row for row in all_rows
            if any(keyword in str(value).lower() for value in row)
        ]

    def refresh_data():
        nonlocal all_rows
        data = get_sheet_data()
        all_rows = data[1:] if len(data) > 1 else []
        render_rows(current_filtered_rows())

    refresh_button = tb.Button(table_header, text="Refresh Data", bootstyle="secondary-outline", command=refresh_data)
    refresh_button.pack(side="right")

    search_var.trace_add("write", lambda *_: render_rows(current_filtered_rows()))

    def open_selected_student(event):
        selected_item = tree.focus()
        if not selected_item:
            return

        values = tree.item(selected_item, "values")
        enrollment = values[1]

        students_db = load_students()
        for sid, student in students_db.items():
            if student["enrollment"] == enrollment:
                show_student_profile(content, sid)
                return

    tree.bind("<Double-1>", open_selected_student)
    refresh_data()


def _today_string():
    """Return today's date using the attendance sheet format."""

    return datetime.now().strftime("%d-%m-%Y")
