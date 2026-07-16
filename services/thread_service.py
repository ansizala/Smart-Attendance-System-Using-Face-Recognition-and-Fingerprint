"""Small helper for starting daemon threads without repeating boilerplate."""

import threading


def run_in_thread(target, *args, **kwargs):
    """Run a function in a daemon thread so the main flow stays responsive."""

    thread = threading.Thread(
        target=target,
        args=args,
        kwargs=kwargs,
        daemon=True
    )
    thread.start()
