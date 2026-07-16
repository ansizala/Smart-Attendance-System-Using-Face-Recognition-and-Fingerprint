"""Desktop application entry point for the smart attendance dashboard."""

import ttkbootstrap as tb

from ui.charts_professional import show_charts
from ui.dashboard import show_dashboard
from ui.logs import view_logs
from ui.sidebar import create_sidebar
from ui.students import view_students
from ui.theme import COLORS, apply_app_theme


def main():
    """Create the main application window and wire page navigation."""

    app = tb.Window(themename="litera")
    apply_app_theme()

    app.title("AI Smart Attendance System")
    app.geometry("1440x820")
    app.minsize(1180, 720)
    app.configure(background=COLORS["bg"])

    container = tb.Frame(app, style="App.TFrame")
    container.pack(fill="both", expand=True)

    content = tb.Frame(container, style="App.TFrame")
    content.pack(side="right", fill="both", expand=True)

    pages = {
        "dashboard": lambda: show_dashboard(content),
        "students": lambda: view_students(content),
        "logs": lambda: view_logs(content),
        "charts": lambda: show_charts(content),
    }

    navigate = create_sidebar(container, pages)
    navigate("dashboard")

    app.mainloop()


if __name__ == "__main__":
    main()
