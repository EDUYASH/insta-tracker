import csv
import json
import os
from datetime import datetime
from scraper import scrape_socialblade
from sheets import (
    get_sheet,
    get_or_create_date_column,
    find_or_create_profile_row,
    update_follower_count,
    get_previous_follower_count,
)

# ─── Load Config ─────────────────────────────────────────────
with open("config.json", "r") as f:
    config = json.load(f)

PROFILES         = config.get("profiles", [])
OUTPUT_FILE      = config.get("output_file", "follower_tracker.csv")
SHEET_ID         = config.get("google_sheet_id")
CREDENTIALS_FILE = config.get("credentials_file", "credentials.json")
SHEET_TAB        = config.get("sheet_tab_name", "Sheet1")

# ─── CSV Backup ───────────────────────────────────────────────
CSV_HEADERS = ["Date", "Username", "Followers", "Daily Change", "Following", "Posts"]

def append_csv(record):
    file_exists = os.path.exists(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

# ─── Main Tracker ─────────────────────────────────────────────
def run():
    now      = datetime.now()
    date_str = now.strftime("%d/%m/%y")   # Format matching Sheet1 dates: 07/07/26
    full_dt  = now.strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 52)
    print("   Instagram Follower Tracker - Social Blade")
    print(f"   {full_dt}")
    print("=" * 52)

    # Connect to Google Sheets
    worksheet = None
    if SHEET_ID and os.path.exists(CREDENTIALS_FILE):
        try:
            print(f"\n  Connecting to Google Sheets (tab: {SHEET_TAB})...")
            worksheet = get_sheet(CREDENTIALS_FILE, SHEET_ID, SHEET_TAB)
            print("  Connected!")

            # Get or create today's date column
            date_col = get_or_create_date_column(worksheet, date_str)

        except Exception as e:
            print(f"  [!] Google Sheets error: {e}")
            worksheet = None
    else:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"\n  [!] {CREDENTIALS_FILE} not found — CSV only mode.")

    for username in PROFILES:
        print(f"\n  Fetching @{username} ...")
        data = scrape_socialblade(username)

        if not data or data["followers"] is None:
            print(f"  [!] Skipping @{username} — could not fetch data.")
            continue

        followers = data["followers"]
        following = data["following"] if data["following"] is not None else "N/A"
        posts     = data["posts"]     if data["posts"]     is not None else "N/A"
        profile_link = f"https://www.instagram.com/{username}/"

        # Update Google Sheet
        daily_change = "N/A"
        if worksheet:
            try:
                row_idx = find_or_create_profile_row(worksheet, username, profile_link)
                prev    = get_previous_follower_count(worksheet, row_idx, date_col)
                if prev is not None:
                    diff = followers - prev
                    daily_change = f"+{diff}" if diff >= 0 else str(diff)
                update_follower_count(worksheet, row_idx, date_col, followers)
                print(f"  Google Sheets updated!")
            except Exception as e:
                print(f"  [!] Sheet write error: {e}")

        # CSV Backup
        append_csv({
            "Date":         date_str,
            "Username":     username,
            "Followers":    followers,
            "Daily Change": daily_change,
            "Following":    following,
            "Posts":        posts,
        })

        print(f"\n  ----------------------------------------")
        print(f"  Profile   : @{username}")
        print(f"  Followers : {followers:,}")
        print(f"  Change    : {daily_change}")
        print(f"  Following : {following}")
        print(f"  ----------------------------------------")

    print("\n" + "=" * 52)
    print("  Done! Har roz 9 AM pe auto-run hoga.")
    print("=" * 52)

if __name__ == "__main__":
    run()
