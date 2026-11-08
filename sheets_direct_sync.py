import os
import re
import json
import sqlite3
import traceback
from threading import Thread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_KEY_PATH = os.path.join(WORKSPACE, 'flipkart-gmail-otp-reader-d7c1a22b35c6.json')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

_cached_service = None

def get_service_account_path():
    """Return path to service account JSON key if present on disk."""
    # 1. Standard workspace path
    if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        return SERVICE_ACCOUNT_KEY_PATH
    # 2. Render secret files path (/etc/secrets/...)
    render_secrets = [
        '/etc/secrets/flipkart-gmail-otp-reader-d7c1a22b35c6.json',
        '/etc/secrets/google_service_account.json',
        '/etc/secrets/credentials.json'
    ]
    for sp in render_secrets:
        if os.path.exists(sp):
            return sp
    # 3. Match any key in WORKSPACE
    import glob
    matches = glob.glob(os.path.join(WORKSPACE, '*gmail-otp-reader*.json')) + glob.glob(os.path.join(WORKSPACE, '*service_account*.json'))
    return matches[0] if matches else None

def get_service_account_credentials():
    """Return Google Credentials object from environment variable or local file."""
    # 1. Check Render / Cloud environment variable (GOOGLE_SERVICE_ACCOUNT_JSON)
    env_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if env_json and env_json.strip():
        try:
            info = json.loads(env_json.strip())
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            print(f"[DIRECT SYNC] Error parsing GOOGLE_SERVICE_ACCOUNT_JSON env: {e}", flush=True)

    # 2. Check local file or Render secret file
    p = get_service_account_path()
    if p and os.path.exists(p):
        try:
            return Credentials.from_service_account_file(p, scopes=SCOPES)
        except Exception as e:
            print(f"[DIRECT SYNC] Error loading credentials from {p}: {e}", flush=True)
            
    return None

def is_direct_sync_available():
    """Check if direct Google Sheets API sync is available."""
    if os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip():
        return True
    p = get_service_account_path()
    return bool(p and os.path.exists(p))

def get_sheets_service():
    """Create and cache googleapiclient sheets service."""
    global _cached_service
    if _cached_service is not None:
        return _cached_service
    creds = get_service_account_credentials()
    if not creds:
        raise ValueError("Service account JSON key not found in environment or workspace.")
    _cached_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    return _cached_service

def extract_spreadsheet_id(url):
    """Extract spreadsheet ID from any Google Sheet URL."""
    if not url:
        return None
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    return m.group(1) if m else None

def get_spreadsheet_id_for_target(sheet_name, web_app_url=None):
    """Resolve spreadsheet ID for target sheet or financial year."""
    # 1. Read fy_settings.json
    fy_settings_path = os.path.join(WORKSPACE, 'fy_settings.json')
    sheet_urls = {}
    if os.path.exists(fy_settings_path):
        try:
            with open(fy_settings_path, 'r', encoding='utf-8') as f:
                d = json.load(f)
                sheet_urls = d.get('sheet_urls', {})
        except Exception:
            pass

    # Detect FY from sheet_name or default to 2026-27
    target_fy = '2026-27'
    for fy in ['2025-26', '2026-27', '2027-28', '2024-25']:
        if fy in str(sheet_name):
            target_fy = fy
            break

    # Look up in sheet_urls
    if target_fy in sheet_urls and sheet_urls[target_fy]:
        sid = extract_spreadsheet_id(sheet_urls[target_fy])
        if sid:
            return sid

    # Hardcoded fallbacks if fy_settings is not configured
    hardcoded = {
        '2025-26': '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To',
        '2026-27': '1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w'
    }
    return hardcoded.get(target_fy, hardcoded['2026-27'])

def get_existing_unique_ids_fast(spreadsheet_id, tab_name):
    """Fetch existing Sale & Purchase unique IDs directly via Google Sheets API (Fast: < 1.5s)."""
    service = get_sheets_service()
    
    # Col AA (27) is SALE UNIQUE ID
    # Col AU (47 = 40 + 20) is PURCHASE UNIQUE ID
    res = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=[
            f"'{tab_name}'!AA:AA",
            f"'{tab_name}'!AU:AU",
            f"'{tab_name}'!A:A",
            f"'{tab_name}'!AN:AN"
        ]
    ).execute()
    
    val_ranges = res.get('valueRanges', [])
    sale_ids = set()
    purchase_ids = set()
    sale_count = 0
    purchase_count = 0
    
    if len(val_ranges) >= 1:
        vals = val_ranges[0].get('values', [])
        # Skip row 1 & 2 headers
        for r in vals[2:]:
            if r and str(r[0]).strip():
                sale_ids.add(str(r[0]).strip())
                
    if len(val_ranges) >= 2:
        vals = val_ranges[1].get('values', [])
        for r in vals[2:]:
            if r and str(r[0]).strip():
                purchase_ids.add(str(r[0]).strip())
                
    if len(val_ranges) >= 3:
        vals = val_ranges[2].get('values', [])
        # Count non-empty in col A
        for r in vals[2:]:
            if r and str(r[0]).strip():
                sale_count += 1
                
    if len(val_ranges) >= 4:
        vals = val_ranges[3].get('values', [])
        for r in vals[2:]:
            if r and str(r[0]).strip():
                purchase_count += 1
                
    return {
        'sale_ids': sale_ids,
        'purchase_ids': purchase_ids,
        'sale_count': max(sale_count, len(sale_ids)),
        'purchase_count': max(purchase_count, len(purchase_ids))
    }

def ensure_sheet_headers_and_capacity(spreadsheet_id, tab_name, mode, expected_sale_rows=0, expected_purchase_rows=0):
    """Ensure Row 1 & 2 headers, check grid capacity, and clear data if overwrite mode."""
    service = get_sheets_service()
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    
    target_sheet = None
    for s in meta.get('sheets', []):
        if s['properties']['title'] == tab_name:
            target_sheet = s
            break
            
    if not target_sheet:
        # If tab doesn't match exact title, pick first sheet
        target_sheet = meta['sheets'][0]
        tab_name = target_sheet['properties']['title']
        
    sheet_id = target_sheet['properties']['sheetId']
    grid_props = target_sheet['properties'].get('gridProperties', {})
    current_rows = grid_props.get('rowCount', 1000)
    current_cols = grid_props.get('columnCount', 70)
    
    sale_start_row = 3
    purchase_start_row = 3
    
    if mode == 'overwrite':
        # Clear data from row 3 downwards (A3:BR)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab_name}'!A3:BR"
        ).execute()
        sale_start_row = 3
        purchase_start_row = 3
    else:
        # Append mode: find last non-empty row in Col A and Col AN
        res = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[f"'{tab_name}'!A:A", f"'{tab_name}'!AN:AN"]
        ).execute()
        
        v_ranges = res.get('valueRanges', [])
        last_s = 2
        if len(v_ranges) >= 1:
            vals = v_ranges[0].get('values', [])
            for i in range(len(vals) - 1, -1, -1):
                if vals[i] and str(vals[i][0]).strip():
                    last_s = i + 1
                    break
        sale_start_row = max(3, last_s + 1)
        
        last_p = 2
        if len(v_ranges) >= 2:
            vals = v_ranges[1].get('values', [])
            for i in range(len(vals) - 1, -1, -1):
                if vals[i] and str(vals[i][0]).strip():
                    last_p = i + 1
                    break
        purchase_start_row = max(3, last_p + 1)

    # Check if we need to append row dimensions or column dimensions
    max_needed_rows = max(sale_start_row + expected_sale_rows + 10, purchase_start_row + expected_purchase_rows + 10)
    dim_requests = []
    
    if current_cols < 70:
        dim_requests.append({
            "appendDimension": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "length": 70 - current_cols
            }
        })
        
    if max_needed_rows > current_rows:
        dim_requests.append({
            "appendDimension": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "length": max_needed_rows - current_rows
            }
        })
        
    if dim_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": dim_requests}
        ).execute()
        
    return {
        'tab_name': tab_name,
        'sale_start_row': sale_start_row,
        'purchase_start_row': purchase_start_row
    }

def sync_batch_direct_api(spreadsheet_id, tab_name, sale_rows_2d, purchase_rows_2d, sale_start_row, purchase_start_row):
    """Write a large batch of Sale & Purchase rows directly in 1 API call (Fast: ~2s for 5,000 rows)."""
    service = get_sheets_service()
    
    data_updates = []
    if sale_rows_2d and len(sale_rows_2d) > 0:
        end_s = sale_start_row + len(sale_rows_2d) - 1
        data_updates.append({
            'range': f"'{tab_name}'!A{sale_start_row}:AL{end_s}",
            'values': sale_rows_2d
        })
        
    if purchase_rows_2d and len(purchase_rows_2d) > 0:
        end_p = purchase_start_row + len(purchase_rows_2d) - 1
        data_updates.append({
            'range': f"'{tab_name}'!AN{purchase_start_row}:BR{end_p}",
            'values': purchase_rows_2d
        })
        
    if data_updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                'valueInputOption': 'USER_ENTERED',
                'data': data_updates
            }
        ).execute()
        
    next_sale_start = sale_start_row + (len(sale_rows_2d) if sale_rows_2d else 0)
    next_purchase_start = purchase_start_row + (len(purchase_rows_2d) if purchase_rows_2d else 0)
    
    return {
        'success': True,
        'nextSaleStartRow': next_sale_start,
        'nextPurchaseStartRow': next_purchase_start
    }
