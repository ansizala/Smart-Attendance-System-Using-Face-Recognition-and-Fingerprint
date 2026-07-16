"""Analytics views for attendance trends, distribution, and daily counts."""

from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import ttkbootstrap as tb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from services.google_service import get_sheet_data
from ui.theme import CHART_COLORS, COLORS, build_scrollable_page, create_card, create_empty_state


def filter_data(data, mode):
    """Filter sheet rows to the requested reporting window."""

    if mode == "All":
        return data

    today = datetime.now()
    filtered = [data[0]]

    for row in data[1:]:
        try:
            row_date = datetime.strptime(row[0], "%d-%m-%Y")
        except Exception:
            continue

        if mode == "Today" and row_date.date() == today.date():
            filtered.append(row)
        elif mode == "Last 7 Days" and row_date >= today - timedelta(days=7):
            filtered.append(row)

    return filtered


def show_charts(content):
    """Render the analytics page inside the shared dashboard content area."""

    _page, body = build_scrollable_page(
        content,
        "Attendance Analytics",
        "View daily attendance patterns, distribution, and trends with the same professional theme used across the rest of the application.",
    )

    data = get_sheet_data()

    if len(data) <= 1:
        empty = create_empty_state(
            body,
            "No analytics available",
            "Attendance charts will appear here as soon as data is written to the attendance sheet.",
        )
        empty.pack(fill="x", pady=18)
        return

    filter_card = create_card(body, padding=20)
    filter_card.pack(fill="x", pady=(0, 18))

    filter_var = tb.StringVar(value="All")

    tb.Label(filter_card, text="Filter Window", style="SectionTitle.TLabel").pack(anchor="w")
    tb.Label(
        filter_card,
        text="Focus the analytics on all data, the current day, or the most recent seven-day period.",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(6, 12))

    filter_box = tb.Combobox(
        filter_card,
        textvariable=filter_var,
        values=["All", "Today", "Last 7 Days"],
        width=18,
        state="readonly",
        style="App.TCombobox",
    )
    filter_box.pack(anchor="w")

    card_frame = tb.Frame(body, style="App.TFrame")
    card_frame.pack(fill="x", pady=(0, 18))
    card_frame.columnconfigure(0, weight=1)
    card_frame.columnconfigure(1, weight=1)
    card_frame.columnconfigure(2, weight=1)

    def update_cards(filtered_data):
        for widget in card_frame.winfo_children():
            widget.destroy()

        total_entries = len(filtered_data) - 1
        unique_students = {row[1] for row in filtered_data[1:] if len(row) >= 2}
        unique_dates = {row[0] for row in filtered_data[1:] if row}

        metric_specs = [
            ("Records", total_entries, COLORS["accent"], (0, 10), 0),
            ("Students", len(unique_students), COLORS["success"], 10, 1),
            ("Days", len(unique_dates), COLORS["warning"], (10, 0), 2),
        ]

        for title, value, color, padx, column in metric_specs:
            metric_card = create_card(card_frame, padding=20)
            metric_card.grid(row=0, column=column, sticky="nsew", padx=padx)
            tb.Label(metric_card, text=title, style="MetricTitle.TLabel", foreground=color).pack(anchor="w")
            tb.Label(metric_card, text=str(value), style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))

    notebook = tb.Notebook(body, style="App.TNotebook", height=560)
    notebook.pack(fill="x", pady=(0, 10))

    daily_tab = tb.Frame(notebook, style="App.TFrame")
    pie_tab = tb.Frame(notebook, style="App.TFrame")
    trend_tab = tb.Frame(notebook, style="App.TFrame")

    notebook.add(daily_tab, text="Daily")
    notebook.add(pie_tab, text="Distribution")
    notebook.add(trend_tab, text="Trend")

    def update_all():
        filtered = filter_data(data, filter_var.get())
        update_cards(filtered)
        generate_daily_chart(daily_tab, filtered)
        generate_pie_chart(pie_tab, filtered)
        generate_line_chart(trend_tab, filtered)

    filter_box.bind("<<ComboboxSelected>>", lambda _event: update_all())
    update_all()


def generate_daily_chart(content, data):
    for widget in content.winfo_children():
        widget.destroy()

    date_count = defaultdict(int)

    for row in data[1:]:
        date_count[row[0]] += 1

    if not date_count:
        empty = create_empty_state(
            content,
            "No daily attendance data",
            "No rows matched the selected filter for the daily overview chart.",
        )
        empty.pack(fill="x", pady=18)
        return

    sorted_items = sorted(date_count.items(), key=lambda item: datetime.strptime(item[0], "%d-%m-%Y"))
    dates = [item[0] for item in sorted_items]
    counts = [item[1] for item in sorted_items]

    fig, ax = create_chart_figure((8, 4))
    ax.bar(dates, counts, color=CHART_COLORS[0], width=0.55)
    ax.set_title("Daily Attendance Overview", color=COLORS["text"], fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", color=COLORS["muted"])
    ax.set_ylabel("Students Present", color=COLORS["muted"])
    ax.grid(axis="y", linestyle="--", alpha=0.35, color=COLORS["border"])

    plt.xticks(rotation=45)
    plt.tight_layout()
    display_chart(content, fig)


def generate_pie_chart(content, data):
    for widget in content.winfo_children():
        widget.destroy()

    student_count = defaultdict(int)

    for row in data[1:]:
        student_count[row[2]] += 1

    if not student_count:
        empty = create_empty_state(
            content,
            "No distribution data",
            "No student attendance records matched the selected filter for the distribution chart.",
        )
        empty.pack(fill="x", pady=18)
        return

    labels = list(student_count.keys())
    values = list(student_count.values())

    fig, ax = create_chart_figure((5, 4.5))
    pie_colors = CHART_COLORS[:len(values)]
    ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=pie_colors,
        wedgeprops={"linewidth": 1, "edgecolor": COLORS["surface"]},
        textprops={"color": COLORS["text"], "fontsize": 9},
    )
    ax.set_title("Student Distribution", color=COLORS["text"], fontsize=14, fontweight="bold")

    plt.tight_layout()
    display_chart(content, fig)


def generate_line_chart(content, data):
    for widget in content.winfo_children():
        widget.destroy()

    date_count = defaultdict(int)

    for row in data[1:]:
        date_count[row[0]] += 1

    if not date_count:
        empty = create_empty_state(
            content,
            "No trend data",
            "No rows matched the selected filter for the attendance trend chart.",
        )
        empty.pack(fill="x", pady=18)
        return

    sorted_items = sorted(date_count.items(), key=lambda item: datetime.strptime(item[0], "%d-%m-%Y"))
    dates = [item[0] for item in sorted_items]
    counts = [item[1] for item in sorted_items]

    fig, ax = create_chart_figure((8, 4))
    ax.plot(dates, counts, marker="o", color=CHART_COLORS[1], linewidth=2.5, markersize=6)
    ax.fill_between(dates, counts, color=COLORS["success_soft"], alpha=0.8)
    ax.set_title("Attendance Trend", color=COLORS["text"], fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", color=COLORS["muted"])
    ax.set_ylabel("Students", color=COLORS["muted"])
    ax.grid(axis="y", linestyle="--", alpha=0.35, color=COLORS["border"])

    plt.xticks(rotation=45)
    plt.tight_layout()
    display_chart(content, fig)


def display_chart(content, fig):
    wrapper = create_card(content, padding=18)
    wrapper.pack(fill="both", expand=True, pady=18)

    canvas = FigureCanvasTkAgg(fig, master=wrapper)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    plt.close(fig)


def create_chart_figure(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(COLORS["surface"])
    ax.set_facecolor(COLORS["surface"])

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["border"])
    ax.spines["bottom"].set_color(COLORS["border"])
    ax.tick_params(axis="x", colors=COLORS["muted"])
    ax.tick_params(axis="y", colors=COLORS["muted"])
    return fig, ax
