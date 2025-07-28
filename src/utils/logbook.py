import csv
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover - optional dependency
    gspread = None
    Credentials = None

logger = logging.getLogger(__name__)


def _append_to_csv(entry: Dict[str, Any], csv_path: str) -> None:
    os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def _append_to_google_sheet(entry: Dict[str, Any], credentials_path: str,
                            sheet_id: str, worksheet: str = 'Sheet1') -> None:
    if not gspread or not Credentials:
        raise RuntimeError('gspread is not installed')
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(worksheet)
    sheet.append_row(list(entry.values()), value_input_option='USER_ENTERED')


def append_game_report(game_data: Dict[str, Any], analysis: Dict[str, Any],
                       csv_path: str = 'analysis_log.csv',
                       gs_credentials: Optional[str] = None,
                       gs_sheet_id: Optional[str] = None,
                       gs_worksheet: str = 'Sheet1') -> None:
    """Append a game analysis entry to CSV and optionally Google Sheets."""
    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'gameId': game_data.get('gameId'),
        'crashPoint': game_data.get('crashPoint'),
        'analysis': json.dumps(analysis)
    }
    try:
        _append_to_csv(entry, csv_path)
    except Exception as e:
        logger.error(f'Failed writing log CSV: {e}')
    if gs_credentials and gs_sheet_id:
        try:
            _append_to_google_sheet(entry, gs_credentials, gs_sheet_id, gs_worksheet)
        except Exception as e:
            logger.error(f'Failed logging to Google Sheets: {e}')
