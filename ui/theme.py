"""Shared design system helpers for the desktop attendance application."""

import tkinter as tk

import ttkbootstrap as tb

COLORS = {
    "bg": "#eef3f8",
    "surface": "#ffffff",
    "surface_alt": "#f8fbff",
    "border": "#d7e3f0",
    "text": "#112031",
    "muted": "#5f7388",
    "accent": "#1f4b7a",
    "accent_soft": "#dce9f8",
    "accent_strong": "#163a60",
    "success": "#127369",
    "success_soft": "#d9f2ee",
    "warning": "#b57415",
    "warning_soft": "#fff1d8",
    "danger": "#ba4d3e",
    "danger_soft": "#fde6e2",
    "nav": "#0f1c2e",
    "nav_panel": "#17263b",
    "nav_hover": "#21334d",
    "nav_active": "#2b4e73",
}

CHART_COLORS = [
    "#1f4b7a",
    "#127369",
    "#d28a1f",
    "#ba4d3e",
    "#4f5fc7",
    "#2a9bb8",
]

FONT = "Segoe UI"


def apply_app_theme():
    """Register the shared ttkbootstrap styles used throughout the app."""

    style = tb.Style()

    if getattr(style, "_smart_attendance_styles_ready", False):
        return style

    style._smart_attendance_styles_ready = True

    style.configure(".", font=(FONT, 10))

    style.configure("App.TFrame", background=COLORS["bg"])
    style.configure("Card.TFrame", background=COLORS["surface"], borderwidth=1, relief="solid", bordercolor=COLORS["border"])
    style.configure("SoftCard.TFrame", background=COLORS["surface_alt"], borderwidth=1, relief="solid", bordercolor=COLORS["border"])
    style.configure("Sidebar.TFrame", background=COLORS["nav"])
    style.configure("SidebarPanel.TFrame", background=COLORS["nav_panel"], borderwidth=1, relief="solid", bordercolor=COLORS["nav_hover"])

    style.configure("PageTitle.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=(FONT, 24, "bold"))
    style.configure("PageSubtitle.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=(FONT, 11))
    style.configure("SectionTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT, 12, "bold"))
    style.configure("SectionTitleAlt.TLabel", background=COLORS["surface_alt"], foreground=COLORS["text"], font=(FONT, 12, "bold"))
    style.configure("Body.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT, 10))
    style.configure("BodyAlt.TLabel", background=COLORS["surface_alt"], foreground=COLORS["text"], font=(FONT, 10))
    style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=(FONT, 10))
    style.configure("MutedAlt.TLabel", background=COLORS["surface_alt"], foreground=COLORS["muted"], font=(FONT, 10))
    style.configure("MetricTitle.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=(FONT, 10, "bold"))
    style.configure("MetricValue.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT, 24, "bold"))
    style.configure("MetricNote.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=(FONT, 9))
    style.configure("SidebarBrand.TLabel", background=COLORS["nav"], foreground="#ffffff", font=(FONT, 16, "bold"))
    style.configure("SidebarSubtitle.TLabel", background=COLORS["nav"], foreground="#b9c7d8", font=(FONT, 10))
    style.configure("SidebarFooterTitle.TLabel", background=COLORS["nav_panel"], foreground="#ffffff", font=(FONT, 11, "bold"))
    style.configure("SidebarFooterNote.TLabel", background=COLORS["nav_panel"], foreground="#b9c7d8", font=(FONT, 9))

    style.configure(
        "SidebarNav.TButton",
        font=(FONT, 10, "bold"),
        anchor="w",
        padding=(16, 11),
        borderwidth=0,
        relief="flat",
        background=COLORS["nav"],
        foreground="#d6e0ec",
    )
    style.map(
        "SidebarNav.TButton",
        background=[("active", COLORS["nav_hover"]), ("pressed", COLORS["nav_hover"])],
        foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
    )
    style.configure(
        "SidebarActive.TButton",
        font=(FONT, 10, "bold"),
        anchor="w",
        padding=(16, 11),
        borderwidth=0,
        relief="flat",
        background=COLORS["nav_active"],
        foreground="#ffffff",
    )
    style.map(
        "SidebarActive.TButton",
        background=[("active", COLORS["nav_active"]), ("pressed", COLORS["nav_active"])],
        foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
    )

    style.configure(
        "SecondaryAction.TButton",
        font=(FONT, 10, "bold"),
        padding=(16, 10),
    )

    style.configure(
        "App.TEntry",
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        insertcolor=COLORS["text"],
        padding=10,
    )
    style.configure(
        "App.TCombobox",
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=8,
    )
    style.map(
        "App.TCombobox",
        fieldbackground=[("readonly", COLORS["surface"])],
        foreground=[("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["surface"])],
        selectforeground=[("readonly", COLORS["text"])],
    )

    style.configure(
        "Data.Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        rowheight=34,
        relief="flat",
        font=(FONT, 10),
    )
    style.map(
        "Data.Treeview",
        background=[("selected", COLORS["accent_soft"])],
        foreground=[("selected", COLORS["text"])],
    )
    style.configure(
        "Data.Treeview.Heading",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        relief="flat",
        font=(FONT, 10, "bold"),
        padding=(10, 10),
    )
    style.map(
        "Data.Treeview.Heading",
        background=[("active", COLORS["surface_alt"])],
        foreground=[("active", COLORS["text"])],
    )

    style.configure(
        "App.Horizontal.TProgressbar",
        background=COLORS["success"],
        troughcolor=COLORS["accent_soft"],
        bordercolor=COLORS["accent_soft"],
        lightcolor=COLORS["success"],
        darkcolor=COLORS["success"],
    )

    style.configure("App.TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure(
        "App.TNotebook.Tab",
        font=(FONT, 10, "bold"),
        padding=(18, 10),
        background=COLORS["surface_alt"],
        foreground=COLORS["muted"],
    )
    style.map(
        "App.TNotebook.Tab",
        background=[("selected", COLORS["surface"]), ("active", COLORS["surface"])],
        foreground=[("selected", COLORS["accent"]), ("active", COLORS["text"])],
    )

    return style


def clear_container(container):
    """Remove all widgets from a page container before rendering a new view."""

    apply_app_theme()

    for widget in container.winfo_children():
        widget.destroy()

    container.configure(style="App.TFrame")


def build_page(container, title, subtitle="", back_command=None):
    """Create a standard page shell with the shared heading layout."""

    clear_container(container)

    page = tb.Frame(container, style="App.TFrame", padding=(32, 28, 32, 32))
    page.pack(fill="both", expand=True)

    header = tb.Frame(page, style="App.TFrame")
    header.pack(fill="x", pady=(0, 22))

    if back_command:
        tb.Button(
            header,
            text="Back",
            style="SecondaryAction.TButton",
            bootstyle="secondary-outline",
            command=back_command,
        ).pack(side="left", padx=(0, 16))

    title_group = tb.Frame(header, style="App.TFrame")
    title_group.pack(side="left", fill="x", expand=True)

    tb.Label(title_group, text=title, style="PageTitle.TLabel").pack(anchor="w")

    if subtitle:
        tb.Label(
            title_group,
            text=subtitle,
            style="PageSubtitle.TLabel",
            justify="left",
            wraplength=920,
        ).pack(anchor="w", pady=(6, 0))

    return page


def build_scrollable_page(container, title, subtitle="", back_command=None):
    """Create a standard page shell with a scrollable content body."""

    page = build_page(container, title, subtitle, back_command)
    body = create_scrollable_body(page)
    return page, body


def create_scrollable_body(parent):
    """Create a vertically scrollable body that matches the app theme."""

    shell = tb.Frame(parent, style="App.TFrame")
    shell.pack(fill="both", expand=True)

    canvas = tk.Canvas(
        shell,
        background=COLORS["bg"],
        highlightthickness=0,
        bd=0,
    )
    scrollbar = tb.Scrollbar(shell, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    body = tb.Frame(canvas, style="App.TFrame")
    window_id = canvas.create_window((0, 0), window=body, anchor="nw")

    def sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def fit_body_width(event):
        canvas.itemconfigure(window_id, width=event.width)

    def on_mousewheel(event):
        if event.delta == 0:
            return

        steps = max(1, int(abs(event.delta) / 120))
        direction = -1 if event.delta > 0 else 1
        canvas.yview_scroll(direction * steps, "units")

    def bind_mousewheel(_event=None):
        canvas.bind_all("<MouseWheel>", on_mousewheel)

    def unbind_mousewheel(_event=None):
        canvas.unbind_all("<MouseWheel>")

    body.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", fit_body_width)
    shell.bind("<Enter>", bind_mousewheel)
    shell.bind("<Leave>", unbind_mousewheel)
    shell.bind("<Destroy>", unbind_mousewheel)

    return body


def create_card(parent, padding=24, style="Card.TFrame"):
    """Return a themed card container for dashboard content."""

    return tb.Frame(parent, style=style, padding=padding)


def create_metric_card(parent, title, value, note, accent):
    """Create a summary metric card with a title, value, and note."""

    card = create_card(parent, padding=22)

    title_label = tb.Label(
        card,
        text=title.upper(),
        style="MetricTitle.TLabel",
        foreground=accent,
    )
    title_label.pack(anchor="w")

    value_label = tb.Label(card, text=value, style="MetricValue.TLabel")
    value_label.pack(anchor="w", pady=(10, 6))

    note_label = tb.Label(
        card,
        text=note,
        style="MetricNote.TLabel",
        justify="left",
        wraplength=220,
    )
    note_label.pack(anchor="w")

    card.title_label = title_label
    card.value_label = value_label
    card.note_label = note_label

    return card


def create_key_value_row(parent, label, value, style="Card.TFrame"):
    """Render a compact label-value row inside a themed container."""

    row = tb.Frame(parent, style=style)
    row.pack(fill="x", pady=4)

    label_style = "Body.TLabel" if style == "Card.TFrame" else "BodyAlt.TLabel"
    value_style = "Muted.TLabel" if style == "Card.TFrame" else "MutedAlt.TLabel"

    label_widget = tb.Label(row, text=label, style=label_style)
    label_widget.pack(side="left")
    value_widget = tb.Label(
        row,
        text=value,
        style=value_style,
        font=(FONT, 10, "bold"),
    )
    value_widget.pack(side="right")

    row.label_widget = label_widget
    row.value_widget = value_widget

    return row


def create_empty_state(parent, title, message):
    """Render a standard empty-state card for pages with no data yet."""

    card = create_card(parent, padding=32, style="SoftCard.TFrame")
    tb.Label(card, text=title, style="SectionTitleAlt.TLabel").pack(anchor="center")
    tb.Label(
        card,
        text=message,
        style="MutedAlt.TLabel",
        justify="center",
        wraplength=520,
    ).pack(anchor="center", pady=(10, 0))
    return card
