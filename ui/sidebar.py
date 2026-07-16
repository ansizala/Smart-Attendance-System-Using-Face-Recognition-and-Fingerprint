"""Sidebar navigation shared by the main desktop application pages."""

import ttkbootstrap as tb

from ui.theme import apply_app_theme


def create_sidebar(parent, commands):
    """Build the application sidebar and return a page navigation callback."""

    apply_app_theme()

    sidebar = tb.Frame(parent, width=300, style="Sidebar.TFrame", padding=(22, 24, 22, 24))
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    brand = tb.Frame(sidebar, style="Sidebar.TFrame")
    brand.pack(fill="x", pady=(2, 26))

    tb.Label(
        brand,
        text="SMART ATTENDANCE\nSYSTEM",
        style="SidebarBrand.TLabel",
        justify="left",
        wraplength=240,
    ).pack(anchor="w", fill="x")
    tb.Label(
        brand,
        text="Welcome to the SMART ATTENDANCE SYSTEM.",
        style="SidebarSubtitle.TLabel",
        justify="left",
        wraplength=240,
    ).pack(anchor="w", pady=(8, 0))

    nav_frame = tb.Frame(sidebar, style="Sidebar.TFrame")
    nav_frame.pack(fill="x", pady=(8, 0))

    buttons = {}

    def set_active(active_key):
        for key, button in buttons.items():
            button.configure(style="SidebarActive.TButton" if key == active_key else "SidebarNav.TButton")

    def navigate(page_key):
        set_active(page_key)
        commands[page_key]()

    nav_items = [
        ("dashboard", "Dashboard"),
        ("students", "Students"),
        ("logs", "Attendance Logs"),
        ("charts", "Analytics"),
    ]

    for key, label in nav_items:
        button = tb.Button(
            nav_frame,
            text=label,
            style="SidebarNav.TButton",
            command=lambda current_key=key: navigate(current_key),
        )
        button.pack(fill="x", pady=6)
        buttons[key] = button

    footer = tb.Frame(sidebar, style="SidebarPanel.TFrame", padding=16)
    footer.pack(side="bottom", fill="x")

    tb.Label(footer, text="Design System", style="SidebarFooterTitle.TLabel").pack(anchor="w")
    tb.Label(
        footer,
        text="Project Designed and Created by Riya Rathod.",
        style="SidebarFooterNote.TLabel",
        wraplength=230,
        justify="left",
    ).pack(anchor="w", pady=(8, 10))
    tb.Label(
        footer,
        text="Student of GPG,Ahemdabad.",
        style="SidebarFooterNote.TLabel",
        wraplength=230,
        justify="left",
    ).pack(anchor="w")

    set_active("dashboard")
    return navigate
