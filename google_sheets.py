# ---------------------------------------------------------------------
# Google Sheets Writer Utility
# ---------------------------------------------------------------------

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import traceback
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SERVICE_ACCOUNT_FILE = "service_account.json"

# ---------------------------------------------------------------------
# Detect Platform
# ---------------------------------------------------------------------

def detect_platform(source_url):

    source_url = source_url.lower()

    if "instagram.com" in source_url:
        return "Instagram"

    if "youtube.com" in source_url:
        return "YouTube"

    if "youtu.be" in source_url:
        return "YouTube"

    return "Unknown"


# ---------------------------------------------------------------------
# Write Data Into Google Sheet
# ---------------------------------------------------------------------

def write_to_google_sheet(
    source_url,
    description=None,
    transcript=None,
    qa_summary=None
):

    try:

        # -------------------------------------------------------------
        # Detect Platform
        # -------------------------------------------------------------

        platform = detect_platform(source_url)

        # -------------------------------------------------------------
        # Success / Failure Logic
        # -------------------------------------------------------------

        if (
            description and description.strip()
            and qa_summary and qa_summary.strip()
        ):

            status = "Ready"

        else:

            description = "NA"
            transcript = "NA"
            qa_summary = "NA"

            status = "Failure"

        # -------------------------------------------------------------
        # Authenticate Google Sheets
        # -------------------------------------------------------------

        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )

        client = gspread.authorize(credentials)

        # -------------------------------------------------------------
        # Open Spreadsheet
        # -------------------------------------------------------------
        print("Spreadsheet ID:", SPREADSHEET_ID)
        print("Worksheet Name:", WORKSHEET_NAME)
        #spreadsheet = client.open(SPREADSHEET_NAME)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

        # Truncate data to fit within Google Sheets cell limits 
        MAX_CELL_LENGTH = 40000

        description = str(description)[:MAX_CELL_LENGTH]
        transcript = str(transcript)[:MAX_CELL_LENGTH]
        qa_summary = str(qa_summary)[:MAX_CELL_LENGTH] 

        # Prepare Row
        row = [
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            source_url,
            platform,
            description,
            transcript,
            qa_summary,
            status,
            "",                 # Score
            "",                 # Briefed Summary
            "Pending",          # Video Creation
            "Pending",          # Upload
            "Not Uploaded"      # Uploaded Status
        ]

        # -------------------------------------------------------------
        # Append Row
        # -------------------------------------------------------------

        worksheet.append_row(row, value_input_option="USER_ENTERED")

        print(
            f"{status} ✅ Data written successfully "
            f"to Google Sheet."
        )
        print(row)

    except Exception as e:

        print("❌ Google Sheets Write Error")
        traceback.print_exc()