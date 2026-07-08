import gspread
import json
import os
import base64
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_google_creds():
    """
    Load Google credentials from:
    1. GOOGLE_CREDENTIALS env var (base64 encoded JSON) — used in cloud/Railway
    2. Local credentials file — used locally
    """
    # Cloud mode: credentials stored as base64 env variable
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_b64:
        creds_json = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
        return Credentials.from_service_account_info(creds_json, scopes=SCOPES)

    # Local mode: read from file specified in config
    config_file = os.environ.get("CONFIG_FILE", "config.json")
    if os.path.exists(config_file):
        with open(config_file) as f:
            cfg = json.load(f)
        creds_file = cfg.get("credentials_file", "credentials.json")
        if os.path.exists(creds_file):
            return Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    raise FileNotFoundError("No Google credentials found. Set GOOGLE_CREDENTIALS env var or credentials file.")


def get_sheet_id():
    """Get Google Sheet ID from env var or config file."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if sheet_id:
        return sheet_id
    config_file = os.environ.get("CONFIG_FILE", "config.json")
    if os.path.exists(config_file):
        with open(config_file) as f:
            cfg = json.load(f)
        return cfg.get("google_sheet_id")
    return None


def get_sheet(credentials_file=None, sheet_id=None, tab_name="Sheet1"):
    """Connect to Google Sheet and return the worksheet."""
    creds  = get_google_creds()
    sid    = sheet_id or get_sheet_id()
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sid)
    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=50)
    return worksheet


def get_or_create_date_column(worksheet, date_str):
    header_row = worksheet.row_values(1)
    if date_str in header_row:
        return header_row.index(date_str) + 1

    for i, val in enumerate(header_row):
        if val.strip() == "":
            worksheet.update_cell(1, i + 1, date_str)
            return i + 1

    new_col_index  = len(header_row) + 1
    current_cols   = worksheet.col_count
    if new_col_index > current_cols:
        worksheet.resize(rows=worksheet.row_count, cols=current_cols + 20)
    worksheet.update_cell(1, new_col_index, date_str)
    return new_col_index


def find_or_create_profile_row(worksheet, username, profile_link):
    all_values = worksheet.get_all_values()
    header     = all_values[0] if all_values else []

    try:
        link_col = header.index("Profile link")
    except ValueError:
        link_col = 3

    try:
        srno_col = header.index("Sr.No")
    except ValueError:
        srno_col = 0

    for i, row in enumerate(all_values[1:], start=2):
        cell_val = row[link_col] if len(row) > link_col else ""
        if username.lower() in cell_val.lower() or profile_link.lower() in cell_val.lower():
            return i

    for i, row in enumerate(all_values[1:], start=2):
        name_val = row[1] if len(row) > 1 else ""
        if name_val.strip() == "":
            worksheet.update_cell(i, srno_col + 1, i - 1)
            worksheet.update_cell(i, 2, username)
            worksheet.update_cell(i, 3, "Social Blade")
            worksheet.update_cell(i, link_col + 1, profile_link)
            return i

    new_row = len(all_values) + 1
    worksheet.update_cell(new_row, srno_col + 1, new_row - 1)
    worksheet.update_cell(new_row, 2, username)
    worksheet.update_cell(new_row, 3, "Social Blade")
    worksheet.update_cell(new_row, link_col + 1, profile_link)
    return new_row


def update_follower_count(worksheet, row_index, col_index, followers):
    worksheet.update_cell(row_index, col_index, followers)


def get_previous_follower_count(worksheet, row_index, date_col_index):
    if date_col_index <= 5:
        return None
    val = worksheet.cell(row_index, date_col_index - 1).value
    try:
        return int(str(val).replace(",", "")) if val else None
    except:
        return None


# ─── Config Tab in Sheet (for cloud storage of profiles) ──────

def get_config_sheet(tab_name="BotConfig"):
    """Get or create a config tab to store tracked profiles in the sheet."""
    ws = get_sheet(tab_name=tab_name)
    # Ensure headers exist
    first_row = ws.row_values(1)
    if first_row != ["username", "added_date", "track_days"]:
        ws.update("A1:C1", [["username", "added_date", "track_days"]])
    return ws


def load_profiles_from_sheet():
    """Load tracked profiles from the BotConfig sheet tab."""
    try:
        ws   = get_config_sheet()
        rows = ws.get_all_records()
        return rows  # list of dicts: {username, added_date, track_days}
    except Exception as e:
        print(f"[config] Error loading profiles: {e}")
        return []


def save_profile_to_sheet(username, added_date, track_days=4):
    """Append a new profile row to BotConfig tab."""
    ws = get_config_sheet()
    ws.append_row([username, added_date, str(track_days)])


def remove_profile_from_sheet(username):
    """Remove a profile row from BotConfig tab."""
    ws   = get_config_sheet()
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0].lower() == username.lower():
            ws.delete_rows(i)
            return True
    return False
