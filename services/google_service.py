"""Google Sheets helpers with connection reuse, batching, and cached reads."""

import threading
import time

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SHEET_CACHE_TTL_SECONDS,
    SHEET_NAME,
)

sheet = None
sheet_lock = threading.RLock()
cache_lock = threading.RLock()

SHEET_HEADER = ["Date", "Enrollment", "Name", "Time"]

_cached_rows = None
_cache_expiry = 0.0
_refresh_in_progress = False


def connect_sheet():
    """Create the shared Google Sheets connection on first use."""

    global sheet
    with sheet_lock:
        if sheet is not None:
            return sheet

        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )

        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet


def _store_cache_rows(rows):
    global _cached_rows, _cache_expiry

    cached_rows = rows if rows else [SHEET_HEADER]
    with cache_lock:
        _cached_rows = cached_rows
        _cache_expiry = time.monotonic() + GOOGLE_SHEET_CACHE_TTL_SECONDS


def _extend_cached_rows(rows):
    global _cached_rows, _cache_expiry

    with cache_lock:
        if _cached_rows is None:
            _cached_rows = [SHEET_HEADER]

        for row in rows:
            _cached_rows.append(list(row))

        _cache_expiry = time.monotonic() + GOOGLE_SHEET_CACHE_TTL_SECONDS


def _fetch_sheet_rows():
    global sheet

    with sheet_lock:
        if sheet is None:
            connect_sheet()
        return sheet.get_all_values()


def _refresh_cache_in_background():
    global _refresh_in_progress

    try:
        _store_cache_rows(_fetch_sheet_rows())
    except Exception as exc:
        print("[WARNING] Google Sheet background refresh failed:", exc)
    finally:
        with cache_lock:
            _refresh_in_progress = False


def _schedule_background_refresh():
    global _refresh_in_progress

    with cache_lock:
        if _refresh_in_progress:
            return
        _refresh_in_progress = True

    threading.Thread(
        target=_refresh_cache_in_background,
        daemon=True,
        name="google-sheet-refresh",
    ).start()


def append_rows(rows):
    """Append multiple rows at once and keep the local cache coherent."""

    if not rows:
        return

    global sheet
    with sheet_lock:
        if sheet is None:
            connect_sheet()

        try:
            try:
                sheet.append_rows(rows, value_input_option="USER_ENTERED")
            except TypeError:
                sheet.append_rows(rows)
            except AttributeError:
                for row in rows:
                    sheet.append_row(row)
        except Exception:
            print("Retrying Google Sheets...")
            time.sleep(1)
            try:
                sheet.append_rows(rows, value_input_option="USER_ENTERED")
            except TypeError:
                sheet.append_rows(rows)
            except AttributeError:
                for row in rows:
                    sheet.append_row(row)

    _extend_cached_rows(rows)


def append_row(row):
    """Append a single row while sharing the batched append implementation."""

    append_rows([row])


def get_sheet_data(raise_on_error=False, force_refresh=False):
    """Return cached Google Sheets rows and refresh in the background when stale."""

    now = time.monotonic()
    with cache_lock:
        cached_rows = _cached_rows
        cache_is_fresh = cached_rows is not None and now < _cache_expiry

    if cached_rows is not None and cache_is_fresh and not force_refresh:
        return cached_rows

    if cached_rows is not None and not raise_on_error and not force_refresh:
        _schedule_background_refresh()
        return cached_rows

    try:
        fresh_rows = _fetch_sheet_rows()
        _store_cache_rows(fresh_rows)
        return fresh_rows if fresh_rows else [SHEET_HEADER]
    except Exception as exc:
        if raise_on_error:
            raise

        if cached_rows is not None:
            print("[WARNING] Google Sheet read failed, using cached data:", exc)
            return cached_rows

        print("[WARNING] Google Sheet read failed:", exc)
        return [SHEET_HEADER]
