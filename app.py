import os
import sqlite3
import io
import time
import math
import json
import traceback
import pickle
import tempfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import xlrd
import openpyxl
import zipfile
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 250 * 1024 * 1024  # 250MB max upload

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ─── Persistent Data Storage ────────────────────────────────────────────────
# Store data in the workspace folder so it persists between restarts
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR')
if not DATA_DIR:
    if os.path.exists('/data') and os.access('/data', os.W_OK):
        DATA_DIR = '/data'
        print("[STORAGE] Using persistent storage at /data", flush=True)
    else:
        # Use WORKSPACE (disk-backed container directory) instead of RAM-backed /tmp on Render
        DATA_DIR = WORKSPACE



UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DATA_STORE_PATH = os.path.join(DATA_DIR, 'processed_data_store.pkl')


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({'error': 'Uploaded files are too large. Please reduce file size or upload smaller files.'}), 413


@app.errorhandler(500)
def internal_server_error(error):
    traceback.print_exc()
    return jsonify({'error': 'Server error while processing. Please try again; if it repeats, check Render logs.'}), 500



def get_financial_year():
    """Get current financial year string like '2026-27'."""
    now = datetime.now()
    if now.month >= 4:  # April onwards = new FY
        return f'{now.year}-{str(now.year + 1)[2:]}'
    else:
        return f'{now.year - 1}-{str(now.year)[2:]}'


LOCAL_DB_PATH = os.path.join(DATA_DIR, 'local_store.db')

def get_db_connection(db_path=LOCAL_DB_PATH):
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_local_db():
    conn = get_db_connection()
    # Create sales table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sale (
            no INTEGER,
            invoice_no TEXT,
            type TEXT,
            invoice_date TEXT,
            warehouse_name TEXT,
            warehouse_code TEXT,
            gst_no TEXT,
            order_id TEXT,
            item_asin TEXT,
            item_sku TEXT,
            item_name TEXT,
            hsn_number TEXT,
            quantity REAL,
            item_cost REAL,
            gross REAL,
            igst REAL,
            cgst REAL,
            sgst REAL,
            igst_amt REAL,
            cgst_amt REAL,
            sgst_amt REAL,
            invoice REAL,
            reason TEXT,
            zoho_status TEXT,
            invoice_id TEXT,
            state_code TEXT,
            sale_unique_id TEXT PRIMARY KEY,
            calc_qty REAL,
            calc_cost REAL,
            calc_gross REAL,
            calc_igst REAL,
            calc_cgst REAL,
            calc_sgst REAL,
            calc_igst_amt REAL,
            calc_cgst_amt REAL,
            calc_sgst_amt REAL,
            calc_invoice REAL,
            state_code_short TEXT,
            sheet_name TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sale_uid ON sale(sale_unique_id)")
    
    # Create purchase table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase (
            no INTEGER,
            invoice_no TEXT,
            warehouse_name TEXT,
            warehouse_code TEXT,
            gst_no TEXT,
            order_id TEXT,
            item_asin TEXT,
            item_sku TEXT,
            item_name TEXT,
            hsn_number TEXT,
            quantity REAL,
            item_cost REAL,
            gross REAL,
            igst REAL,
            cgst REAL,
            sgst REAL,
            igst_amt REAL,
            cgst_amt REAL,
            sgst_amt REAL,
            invoice REAL,
            purchase_unique_id TEXT PRIMARY KEY,
            calc_qty REAL,
            calc_cost REAL,
            calc_gross REAL,
            calc_igst REAL,
            calc_cgst REAL,
            calc_sgst REAL,
            calc_igst_amt REAL,
            calc_cgst_amt REAL,
            calc_sgst_amt REAL,
            calc_total_amt REAL,
            sheet_name TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_purchase_uid ON purchase(purchase_unique_id)")
    conn.commit()
    conn.close()

def migrate_pickle_to_sqlite():
    if os.path.exists(DATA_STORE_PATH):
        print("[MIGRATION] Found processed_data_store.pkl. Migrating to SQLite...", flush=True)
        try:
            with open(DATA_STORE_PATH, 'rb') as f:
                stored = pickle.load(f)
            stored = normalize_stored_data(stored)
            
            conn = get_db_connection()
            
            # Insert sales
            sales = stored.get('sale', [])
            if sales:
                keys = [
                    'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
                    'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
                    'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
                    'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
                    'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
                    'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
                    'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
                    'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short', 'sheet_name'
                ]
                placeholders = ','.join(['?' for _ in keys])
                insert_query = f"INSERT OR IGNORE INTO sale ({','.join(keys)}) VALUES ({placeholders})"
                
                batch = []
                for row in sales:
                    if 'sheet_name' not in row:
                        row['sheet_name'] = get_financial_year()
                    batch.append(tuple(row.get(k, '') for k in keys))
                conn.executemany(insert_query, batch)
                
            # Insert purchases
            purchases = stored.get('purchase', [])
            if purchases:
                keys = [
                    'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
                    'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
                    'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
                    'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
                    'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
                    'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
                    'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt', 'sheet_name'
                ]
                placeholders = ','.join(['?' for _ in keys])
                insert_query = f"INSERT OR IGNORE INTO purchase ({','.join(keys)}) VALUES ({placeholders})"
                
                batch = []
                for row in purchases:
                    if 'sheet_name' not in row:
                        row['sheet_name'] = get_financial_year()
                    batch.append(tuple(row.get(k, '') for k in keys))
                conn.executemany(insert_query, batch)
                
            conn.commit()
            conn.close()
            
            # Rename the pickle file so we don't migrate it again
            backup_path = DATA_STORE_PATH + '.bak'
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(DATA_STORE_PATH, backup_path)
            print("[MIGRATION] Migration successful! Backup created at processed_data_store.pkl.bak", flush=True)
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to migrate pickle to SQLite: {str(e)}", flush=True)
            traceback.print_exc()

# Initialize local database tables and migrate old data if needed
init_local_db()
migrate_pickle_to_sqlite()


def save_new_data_sqlite(new_sale_data, new_purchase_data):
    """Save new data directly into SQLite, skipping duplicates, and return counts of new/duplicate rows."""
    conn = get_db_connection()
    
    sale_keys = [
        'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
        'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
        'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
        'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
        'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
        'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short', 'sheet_name'
    ]
    
    purchase_keys = [
        'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
        'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
        'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
        'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
        'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt', 'sheet_name'
    ]
    
    # 1. Deduplicate new sales
    sale_new = 0
    sale_dups = 0
    
    cursor = conn.cursor()
    cursor.execute("SELECT sale_unique_id FROM sale")
    existing_sale_ids = {r[0] for r in cursor.fetchall()}
    
    cursor.execute("SELECT COALESCE(MAX(no), 0) FROM sale")
    current_sale_no = cursor.fetchone()[0]
    
    sale_insert_batch = []
    for row in new_sale_data:
        uid = row.get('sale_unique_id')
        if uid in existing_sale_ids:
            sale_dups += 1
        else:
            current_sale_no += 1
            row['no'] = current_sale_no
            row['sheet_name'] = get_financial_year()
            sale_insert_batch.append(tuple(row.get(k, '') for k in sale_keys))
            existing_sale_ids.add(uid)
            sale_new += 1
            
    if sale_insert_batch:
        placeholders = ','.join(['?' for _ in sale_keys])
        conn.executemany(f"INSERT INTO sale ({','.join(sale_keys)}) VALUES ({placeholders})", sale_insert_batch)
        
    # 2. Deduplicate new purchases
    purchase_new = 0
    purchase_dups = 0
    
    cursor.execute("SELECT purchase_unique_id FROM purchase")
    existing_purchase_ids = {r[0] for r in cursor.fetchall()}
    
    cursor.execute("SELECT COALESCE(MAX(no), 0) FROM purchase")
    current_purchase_no = cursor.fetchone()[0]
    
    purchase_insert_batch = []
    for row in new_purchase_data:
        uid = row.get('purchase_unique_id')
        if uid in existing_purchase_ids:
            purchase_dups += 1
        else:
            current_purchase_no += 1
            row['no'] = current_purchase_no
            row['sheet_name'] = get_financial_year()
            purchase_insert_batch.append(tuple(row.get(k, '') for k in purchase_keys))
            existing_purchase_ids.add(uid)
            purchase_new += 1
            
    if purchase_insert_batch:
        placeholders = ','.join(['?' for _ in purchase_keys])
        conn.executemany(f"INSERT INTO purchase ({','.join(purchase_keys)}) VALUES ({placeholders})", purchase_insert_batch)
        
    conn.commit()
    conn.close()
    
    return sale_new, sale_dups, purchase_new, purchase_dups

def get_rows_as_dicts(table_name, limit=100, offset=0):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY no ASC LIMIT ? OFFSET ?", (limit, offset))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def clean_json_value(value):
    """Return a value that can be safely serialized as strict JSON."""
    if isinstance(value, float):
        return value if math.isfinite(value) else 0
    if isinstance(value, dict):
        return {k: clean_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json_value(v) for v in value]
    return value


def clean_rows(rows):
    return [clean_json_value(dict(row)) for row in rows]


def normalize_stored_data(data):
    """Normalize old/new pickle data into the current strict JSON-safe shape."""
    if not isinstance(data, dict):
        return {'sale': [], 'purchase': [], 'sale_ids': set(), 'purchase_ids': set()}

    sale = clean_rows(data.get('sale', []))
    purchase = clean_rows(data.get('purchase', []))
    sale_ids = set(data.get('sale_ids') or [])
    purchase_ids = set(data.get('purchase_ids') or [])

    if not sale_ids:
        sale_ids = {row.get('sale_unique_id') for row in sale if row.get('sale_unique_id')}
    if not purchase_ids:
        purchase_ids = {row.get('purchase_unique_id') for row in purchase if row.get('purchase_unique_id')}

    return {
        'sale': sale,
        'purchase': purchase,
        'sale_ids': sale_ids,
        'purchase_ids': purchase_ids,
    }


def merge_with_dedup(existing_data, new_data, existing_ids, unique_id_key):
    """Merge new data into existing, skipping duplicates by UNIQUE ID.
    
    Returns: (merged_data, merged_ids, new_count, duplicate_count)
    """
    new_count = 0
    dup_count = 0
    merged = list(existing_data)
    merged_ids = set(existing_ids)
    
    for row in new_data:
        uid = row.get(unique_id_key, '')
        if uid and uid in merged_ids:
            dup_count += 1
        else:
            merged.append(row)
            if uid:
                merged_ids.add(uid)
            new_count += 1
    
    # Re-number all rows
    for i, row in enumerate(merged):
        row['no'] = i + 1
    
    return merged, merged_ids, new_count, dup_count

# ─── Helpers ──────────────────────────────────────────────────────────

def roundup2(value):
    """Round up to 2 decimal places (like Excel ROUNDUP)."""
    if value is None or value == '':
        return 0
    try:
        v = float(value)
        if not math.isfinite(v):
            return 0
        return math.ceil(v * 100) / 100
    except (ValueError, TypeError):
        return 0


def safe_float(value, default=0):
    """Safely convert to float."""
    if value is None or value == '':
        return default
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except (ValueError, TypeError):
        return default


def stream_xls_file(filepath):
    """Yield rows from .xls file one by one to save memory."""
    try:
        wb = xlrd.open_workbook(filepath, ignore_workbook_corruption=True)
        ws = wb.sheet_by_index(0)
    except Exception as e:
        raise Exception(f"Failed to open/parse .xls Excel file: {str(e)}")
    
    headers = []
    seen = {}
    for c in range(ws.ncols):
        h = str(ws.cell_value(1, c)).strip()
        if not h or h == '':
            h = f'Col_{c}'
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        headers.append(h)
        
    for r in range(2, ws.nrows):
        row_data = {}
        for c in range(ws.ncols):
            cell_value = ws.cell_value(r, c)
            if ws.cell_type(r, c) == xlrd.XL_CELL_DATE:
                try:
                    date_tuple = xlrd.xldate_as_tuple(cell_value, wb.datemode)
                    cell_value = f'{date_tuple[2]:02d}/{date_tuple[1]:02d}/{date_tuple[0]}'
                except Exception:
                    pass
            row_data[headers[c]] = cell_value
        yield row_data


def stream_xlsx_file(filepath):
    """Yield rows from .xlsx file one by one to save memory."""
    f = None
    wb = None
    try:
        f = open(filepath, 'rb')
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb.active if wb.active is not None else wb.worksheets[0]
    except Exception as e:
        if f:
            f.close()
        raise Exception(f"Failed to open/parse .xlsx Excel file: {str(e)}")
    
    try:
        headers = []
        seen = {}
        for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if r_idx == 2:
                for c_idx, cell_value in enumerate(row):
                    h = cell_value if cell_value is not None else f'Col_{c_idx + 1}'
                    h = str(h).strip()
                    if h in seen:
                        seen[h] += 1
                        h = f"{h}_{seen[h]}"
                    else:
                        seen[h] = 1
                    headers.append(h)
            elif r_idx >= 3:
                if not any(cell_value is not None and str(cell_value).strip() != '' for cell_value in row):
                    continue
                row_data = {}
                for c_idx, cell_value in enumerate(row):
                    if c_idx < len(headers):
                        row_data[headers[c_idx]] = cell_value
                    else:
                        row_data[f'Col_{c_idx + 1}'] = cell_value
                yield row_data
    finally:
        if wb:
            wb.close()
        if f:
            f.close()


def try_repair_excel_with_excel_app(filepath):
    """
    On Windows, if the file is corrupted (e.g. Ajio export),
    use Microsoft Excel COM interface to open, repair, and save it in background.
    """
    import os
    if os.name != 'nt':
        return None
        
    try:
        import win32com.client
        import pythoncom
        
        # Initialize COM thread if running in Flask request thread
        pythoncom.CoInitialize()
        
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        abs_path = os.path.abspath(filepath)
        repaired_path = os.path.splitext(abs_path)[0] + "_repaired.xlsx"
        
        # Open workbook (Excel automatically repairs on open)
        wb = excel.Workbooks.Open(abs_path)
        
        # Save as standard XLSX workbook (FileFormat 51 = xlOpenXMLWorkbook)
        wb.SaveAs(repaired_path, FileFormat=51)
        wb.Close(SaveChanges=True)
        excel.Quit()
        
        pythoncom.CoUninitialize()
        
        if os.path.exists(repaired_path):
            return repaired_path
    except Exception as e:
        print(f"Failed to auto-repair Excel file using COM: {str(e)}")
        try:
            excel.Quit()
        except:
            pass
            
    return None


def stream_file(filepath):
    """Robustly stream Excel file by auto-detecting the underlying format."""
    filename = os.path.basename(filepath)
    try:
        if zipfile.is_zipfile(filepath):
            return stream_xlsx_file(filepath)
        else:
            return stream_xls_file(filepath)
    except Exception as e:
        try:
            if zipfile.is_zipfile(filepath):
                return stream_xls_file(filepath)
            else:
                return stream_xlsx_file(filepath)
        except Exception:
            # Fallback 2: Try to repair using Windows Excel COM
            repaired_path = try_repair_excel_with_excel_app(filepath)
            if repaired_path:
                try:
                    def stream_repaired_generator():
                        try:
                            for row in stream_xlsx_file(repaired_path):
                                yield row
                        finally:
                            try:
                                if os.path.exists(repaired_path):
                                    os.remove(repaired_path)
                            except:
                                pass
                    return stream_repaired_generator()
                except Exception as stream_err:
                    try:
                        if os.path.exists(repaired_path):
                            os.remove(repaired_path)
                    except:
                        pass
                    raise stream_err
            else:
                raise Exception(
                    f"The uploaded Excel file '{filename}' appears to be corrupted or malformed. "
                    "Please open the file in Microsoft Excel on your computer, save it (Ctrl+S), and then try uploading it again."
                )


def build_sale_summary_lookup_streaming(filepath):
    lookup = {}
    for row in stream_file(filepath):
        key = None
        for possible_key in ['New Invoice No.', 'New Invoice No', 'New invoice No.']:
            if possible_key in row:
                key = safe_str(row[possible_key])
                break
        if key:
            lookup[key] = {
                'invoice_type': safe_str(row.get('Invoice Type', '')),
                'invoice_id': safe_str(row.get('Invoice No', row.get('Invoice No.', ''))),
                'state_code': safe_str(row.get('State Code', '')),
                'channel': safe_str(row.get('Channel', '')),
            }
    return lookup


def build_purchase_summary_lookup_streaming(filepath):
    lookup = {}
    for row in stream_file(filepath):
        key = None
        for possible_key in ['Invoice No.', 'Invoice No', 'Invoice Number']:
            if possible_key in row:
                key = safe_str(row[possible_key])
                break
        if key:
            lookup[key] = {
                'invoice_type': safe_str(row.get('Invoice Type', '')),
                'order_no': safe_str(row.get('Order No', '')),
            }
    return lookup


def process_and_save_streaming(file_paths):
    """Process Excel files in a streaming fashion, write directly to SQLite, and return stats."""
    import gc
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ─── 1. Get initial database counts ───
    cursor.execute("SELECT COUNT(*) FROM sale")
    init_sale_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM purchase")
    init_purchase_count = cursor.fetchone()[0]
    
    # ─── 2. Build lookups ───
    sale_lookup = build_sale_summary_lookup_streaming(file_paths['sale_summary'])
    purchase_lookup = build_purchase_summary_lookup_streaming(file_paths['purchase_summary'])
    
    # ─── 3. Stream & Process Sales details ───
    cursor.execute("SELECT COALESCE(MAX(no), 0) FROM sale")
    current_sale_no = cursor.fetchone()[0]
    
    sale_keys = [
        'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
        'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
        'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
        'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
        'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
        'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short', 'sheet_name'
    ]
    sale_placeholders = ','.join(['?' for _ in sale_keys])
    sale_insert_sql = f"INSERT OR IGNORE INTO sale ({','.join(sale_keys)}) VALUES ({sale_placeholders})"
    
    attempted_sales = 0
    sale_batch = []
    fy_str = get_financial_year()
    
    for row in stream_file(file_paths['sale_details']):
        invoice_no = safe_str(row.get('Invoice No', ''))
        summary = sale_lookup.get(invoice_no, {})
        
        quantity = safe_float(row.get('Quantity', 0))
        item_cost = safe_float(row.get('Item Cost', row.get('Item cost', 0)))
        gross = safe_float(row.get('Gross', 0))
        igst_rate = safe_float(row.get('IGST', 0))
        cgst_rate = safe_float(row.get('CGST', 0))
        sgst_rate = safe_float(row.get('SGST', 0))
        igst_amt = safe_float(row.get('IGST Amt', 0))
        cgst_amt = safe_float(row.get('CGST Amt', 0))
        sgst_amt = safe_float(row.get('SGST Amt', 0))
        invoice_val = safe_float(row.get('Invoice', 0))
        
        order_id = safe_str(row.get('Order ID', ''))
        item_asin = safe_str(row.get('Item Asin', ''))
        item_sku = safe_str(row.get('Item SKU', ''))
        
        sale_unique_id = f'{invoice_no}-{order_id}-{item_asin}-{item_sku}'
        state_code_full = summary.get('state_code', '')
        state_code_short = extract_state_short(state_code_full)
        
        calc_qty = quantity
        calc_cost = item_cost
        calc_gross = roundup2(calc_qty * calc_cost)
        calc_igst = igst_rate
        calc_cgst = cgst_rate
        calc_sgst = sgst_rate
        calc_igst_amt = roundup2(calc_gross * calc_igst / 100) if calc_igst else 0
        calc_cgst_amt = roundup2(calc_gross * calc_cgst / 100) if calc_cgst else 0
        calc_sgst_amt = roundup2(calc_gross * calc_sgst / 100) if calc_sgst else 0
        calc_invoice = calc_gross + calc_igst_amt + calc_cgst_amt + calc_sgst_amt
        
        current_sale_no += 1
        attempted_sales += 1
        
        sale_dict = {
            'no': current_sale_no,
            'invoice_no': invoice_no,
            'type': summary.get('invoice_type', ''),
            'invoice_date': safe_str(row.get('Invoice Date', '')),
            'warehouse_name': safe_str(row.get('Warehouse Name', '')),
            'warehouse_code': safe_str(row.get('Warehouse Code', '')),
            'gst_no': safe_str(row.get('GST No', '')),
            'order_id': order_id,
            'item_asin': item_asin,
            'item_sku': item_sku,
            'item_name': safe_str(row.get('Item Name', '')),
            'hsn_number': safe_str(row.get('HSN Number', '')),
            'quantity': quantity,
            'item_cost': item_cost,
            'gross': gross,
            'igst': igst_rate,
            'cgst': cgst_rate,
            'sgst': sgst_rate,
            'igst_amt': igst_amt,
            'cgst_amt': cgst_amt,
            'sgst_amt': sgst_amt,
            'invoice': invoice_val,
            'reason': safe_str(row.get('Reason', '')),
            'zoho_status': safe_str(row.get('Zoho Status', '')),
            'invoice_id': summary.get('invoice_id', ''),
            'state_code': state_code_full,
            'sale_unique_id': sale_unique_id,
            'calc_qty': calc_qty,
            'calc_cost': calc_cost,
            'calc_gross': calc_gross,
            'calc_igst': calc_igst,
            'calc_cgst': calc_cgst,
            'calc_sgst': calc_sgst,
            'calc_igst_amt': calc_igst_amt,
            'calc_cgst_amt': calc_cgst_amt,
            'calc_sgst_amt': calc_sgst_amt,
            'calc_invoice': roundup2(calc_invoice),
            'state_code_short': state_code_short,
            'sheet_name': fy_str
        }
        
        sale_batch.append(tuple(sale_dict.get(k, '') for k in sale_keys))
        if len(sale_batch) >= 1000:
            cursor.executemany(sale_insert_sql, sale_batch)
            sale_batch = []
            
    if sale_batch:
        cursor.executemany(sale_insert_sql, sale_batch)
        sale_batch = []
        
    conn.commit()
    
    # ─── 4. Reclaim Sales lookup RAM instantly ───
    sale_lookup = None
    gc.collect()
    
    # ─── 5. Stream & Process Purchase details ───
    cursor.execute("SELECT COALESCE(MAX(no), 0) FROM purchase")
    current_purchase_no = cursor.fetchone()[0]
    
    purchase_keys = [
        'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
        'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
        'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
        'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
        'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt', 'sheet_name'
    ]
    purchase_placeholders = ','.join(['?' for _ in purchase_keys])
    purchase_insert_sql = f"INSERT OR IGNORE INTO purchase ({','.join(purchase_keys)}) VALUES ({purchase_placeholders})"
    
    attempted_purchases = 0
    purchase_batch = []
    
    for row in stream_file(file_paths['purchase_details']):
        invoice_no = safe_str(row.get('Invoice No', ''))
        order_id = safe_str(row.get('Order ID', ''))
        item_asin = safe_str(row.get('Item Asin', ''))
        item_sku = safe_str(row.get('Item SKU', ''))
        quantity = safe_float(row.get('Quantity', 0))
        
        item_cost = 0
        if 'Quantity_2' in row:
            item_cost = safe_float(row.get('Quantity_2', 0))
        else:
            item_cost_key = 'Item cost'
            if item_cost_key not in row:
                item_cost_key = 'Item Cost'
            item_cost = safe_float(row.get(item_cost_key, 0))
            if item_cost == 0:
                for k, v in row.items():
                    if k not in [item_cost_key] and 'cost' in k.lower():
                        item_cost = safe_float(v)
                        break
                        
        gross = safe_float(row.get('Gross', 0))
        igst_rate = safe_float(row.get('IGST', 0))
        cgst_rate = safe_float(row.get('CGST', 0))
        sgst_rate = safe_float(row.get('SGST', 0))
        igst_amt = safe_float(row.get('IGST Amt', 0))
        cgst_amt = safe_float(row.get('CGST Amt', 0))
        sgst_amt = safe_float(row.get('SGST Amt', 0))
        invoice_val = safe_float(row.get('Invoice', 0))
        
        purchase_unique_id = f'{invoice_no}-{order_id}-{item_asin}-{item_sku}'
        
        calc_qty = quantity
        calc_cost = item_cost
        calc_gross = roundup2(calc_qty * calc_cost)
        calc_igst = igst_rate
        calc_cgst = cgst_rate
        calc_sgst = sgst_rate
        calc_igst_amt = roundup2(calc_gross * calc_igst / 100) if calc_igst else 0
        calc_cgst_amt = roundup2(calc_gross * calc_cgst / 100) if calc_cgst else 0
        calc_sgst_amt = roundup2(calc_gross * calc_sgst / 100) if calc_sgst else 0
        calc_total_amt = roundup2(calc_gross + calc_igst_amt + calc_cgst_amt + calc_sgst_amt)
        
        current_purchase_no += 1
        attempted_purchases += 1
        
        purchase_dict = {
            'no': current_purchase_no,
            'invoice_no': invoice_no,
            'warehouse_name': safe_str(row.get('Warehouse Name', '')),
            'warehouse_code': safe_str(row.get('Warehouse Code', '')),
            'gst_no': safe_str(row.get('GST No', '')),
            'order_id': order_id,
            'item_asin': item_asin,
            'item_sku': item_sku,
            'item_name': safe_str(row.get('Item Name', '')),
            'hsn_number': safe_str(row.get('HSN Number', '')),
            'quantity': quantity,
            'item_cost': item_cost,
            'gross': gross,
            'igst': igst_rate,
            'cgst': cgst_rate,
            'sgst': sgst_rate,
            'igst_amt': igst_amt,
            'cgst_amt': cgst_amt,
            'sgst_amt': sgst_amt,
            'invoice': invoice_val,
            'purchase_unique_id': purchase_unique_id,
            'calc_qty': calc_qty,
            'calc_cost': calc_cost,
            'calc_gross': calc_gross,
            'calc_igst': calc_igst,
            'calc_cgst': calc_cgst,
            'calc_sgst': calc_sgst,
            'calc_igst_amt': calc_igst_amt,
            'calc_cgst_amt': calc_cgst_amt,
            'calc_sgst_amt': calc_sgst_amt,
            'calc_total_amt': calc_total_amt,
            'sheet_name': fy_str
        }
        
        purchase_batch.append(tuple(purchase_dict.get(k, '') for k in purchase_keys))
        if len(purchase_batch) >= 1000:
            cursor.executemany(purchase_insert_sql, purchase_batch)
            purchase_batch = []
            
    if purchase_batch:
        cursor.executemany(purchase_insert_sql, purchase_batch)
        purchase_batch = []
        
    conn.commit()
    
    # ─── 6. Reclaim Purchase lookup RAM instantly ───
    purchase_lookup = None
    gc.collect()
    
    # ─── 7. Calculate final stats ───
    cursor.execute("SELECT COUNT(*) FROM sale")
    final_sale_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM purchase")
    final_purchase_count = cursor.fetchone()[0]
    
    conn.close()
    
    sale_new = final_sale_count - init_sale_count
    sale_dups = attempted_sales - sale_new
    
    purchase_new = final_purchase_count - init_purchase_count
    purchase_dups = attempted_purchases - purchase_new
    
    return {
        'sale_count': final_sale_count,
        'purchase_count': final_purchase_count,
        'sale_new': sale_new,
        'sale_duplicates': sale_dups,
        'purchase_new': purchase_new,
        'purchase_duplicates': purchase_dups
    }


def export_to_excel_streaming(output_path):
    """Export combined data to Excel directly streaming rows to disk using write-only workbook."""
    from openpyxl.cell import WriteOnlyCell
    wb = openpyxl.Workbook(write_only=True)
    fy = get_financial_year()
    ws = wb.create_sheet(title=f'AJIO & MYNTRA SALE-PURCHASE {fy}')
    
    # Define styles
    header_font = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
    sale_fill = PatternFill(start_color='1B5E20', end_color='1B5E20', fill_type='solid')
    purchase_fill = PatternFill(start_color='0D47A1', end_color='0D47A1', fill_type='solid')
    subheader_font = Font(name='Calibri', bold=True, size=10)
    sale_subheader_fill = PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid')
    purchase_subheader_fill = PatternFill(start_color='BBDEFB', end_color='BBDEFB', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal='center', vertical='center')
    
    # ─── Row 1: Merged Headers ──────────────────────────────────────────
    row1 = []
    for col_idx in range(1, 72):
        cell = WriteOnlyCell(ws, value=None)
        cell.border = thin_border
        
        if col_idx <= 38:
            cell.fill = sale_fill
            if col_idx == 1:
                cell.value = "SALE"
                cell.font = header_font
                cell.alignment = center_align
        elif col_idx == 39:
            pass
        else:
            cell.fill = purchase_fill
            if col_idx == 40:
                cell.value = "PURCHASE"
                cell.font = header_font
                cell.alignment = center_align
        row1.append(cell)
    ws.append(row1)
    ws.merge_cells('A1:AL1')
    ws.merge_cells('AN1:BR1')
    
    # ─── Row 2: Column Headers ──────────────────────────────────────────
    sale_headers = [
        'No.', 'Invoice No', 'TYPE', 'Invoice Date', 'Warehouse Name',
        'Warehouse Code', 'GST No', 'Order ID', 'Item Asin', 'Item SKU',
        'Item Name', 'HSN Number', 'Quantity', 'Item Cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Invoice', 'Reason', 'Zoho Status', 'invoice id', 'State Code',
        'SALE UNIQUE ID', 'Quantity', 'Item Cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Invoice', 'STATE CODE'
    ]
    
    purchase_headers = [
        'No.', 'Invoice No', 'Warehouse Name', 'Warehouse Code', 'GST No',
        'Order ID', 'Item Asin', 'Item SKU', 'Item Name', 'HSN Number',
        'Quantity', 'Item cost', 'Gross', 'IGST', 'CGST', 'SGST',
        'IGST Amt', 'CGST Amt', 'SGST Amt', 'Invoice',
        'PURCHASE UNIQUE ID', 'Quantity', 'Item cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Total Amt'
    ]
    
    row2 = []
    for col_idx in range(1, 72):
        cell = WriteOnlyCell(ws, value=None)
        cell.border = thin_border
        
        if col_idx <= 38:
            cell.fill = sale_subheader_fill
            cell.font = subheader_font
            cell.alignment = center_align
            if col_idx <= len(sale_headers):
                cell.value = sale_headers[col_idx - 1]
        elif col_idx == 39:
            pass
        else:
            cell.fill = purchase_subheader_fill
            cell.font = subheader_font
            cell.alignment = center_align
            p_idx = col_idx - 40
            if p_idx < len(purchase_headers):
                cell.value = purchase_headers[p_idx]
        row2.append(cell)
    ws.append(row2)
    
    # ─── Data Rows ──────────────────────────────────────────────────────
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor_sale = conn.cursor()
    cursor_sale.execute("SELECT * FROM sale ORDER BY no ASC")
    
    cursor_purchase = conn.cursor()
    cursor_purchase.execute("SELECT * FROM purchase ORDER BY no ASC")
    
    sale_keys = [
        'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
        'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
        'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
        'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
        'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
        'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short'
    ]
    
    purchase_keys = [
        'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
        'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
        'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
        'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
        'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt'
    ]
    
    while True:
        s_row = cursor_sale.fetchone()
        p_row = cursor_purchase.fetchone()
        
        if s_row is None and p_row is None:
            break
            
        row_cells = []
        for col_idx in range(1, 72):
            cell = WriteOnlyCell(ws, value=None)
            cell.border = thin_border
            
            if col_idx <= 38:
                if s_row is not None:
                    k = sale_keys[col_idx - 1]
                    cell.value = s_row[k]
            elif col_idx == 39:
                pass
            else:
                if p_row is not None:
                    k = purchase_keys[col_idx - 40]
                    cell.value = p_row[k]
            row_cells.append(cell)
        ws.append(row_cells)
        
    conn.close()
    
    for col in range(1, 72):
        ws.column_dimensions[get_column_letter(col)].width = 15
    ws.column_dimensions['K'].width = 40
    ws.column_dimensions['AW'].width = 40
    
    wb.save(output_path)


def safe_str(value, default=''):
    """Safely convert to string."""
    if value is None:
        return default
    s = str(value).strip()
    # Remove trailing .0 from numeric strings
    if s.endswith('.0'):
        try:
            int_val = int(float(s))
            if float(s) == int_val:
                return str(int_val)
        except (ValueError, TypeError):
            pass
    return s


def extract_state_short(state_code_full):
    """Extract short state code: 'Gujarat(GJ)' → '(GJ)'"""
    if not state_code_full:
        return ''
    s = str(state_code_full)
    # Find content in parentheses
    start = s.find('(')
    if start != -1:
        end = s.find(')', start)
        if end != -1:
            return s[start:end + 1]
    return s


def read_xls_file(filepath):
    """Read .xls file handling corruption."""
    try:
        wb = xlrd.open_workbook(filepath, ignore_workbook_corruption=True)
        ws = wb.sheet_by_index(0)
        
        # Read all data into list of dicts
        headers = []
        seen = {}
        for c in range(ws.ncols):
            h = str(ws.cell_value(1, c)).strip()  # Row 2 = headers (index 1)
            if not h or h == '':
                h = f'Col_{c}'
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 1
            headers.append(h)
        
        rows = []
        for r in range(2, ws.nrows):  # Skip title row and header row
            row_data = {}
            for c in range(ws.ncols):
                cell_value = ws.cell_value(r, c)
                # Handle dates
                if ws.cell_type(r, c) == xlrd.XL_CELL_DATE:
                    try:
                        date_tuple = xlrd.xldate_as_tuple(cell_value, wb.datemode)
                        cell_value = f'{date_tuple[2]:02d}/{date_tuple[1]:02d}/{date_tuple[0]}'
                    except Exception:
                        pass
                row_data[headers[c]] = cell_value
            rows.append(row_data)
        
        return headers, rows
    except Exception as e:
        raise Exception(f'Error reading {os.path.basename(filepath)}: {str(e)}')


def read_xlsx_file(filepath):
    """Read .xlsx file using read_only=True for extremely low memory usage."""
    f = None
    wb = None
    try:
        f = open(filepath, 'rb')
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        ws = wb.active if wb.active is not None else wb.worksheets[0]
        
        headers = []
        seen = {}
        rows = []
        
        for r_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if r_idx == 2:
                # Row 2 = headers
                for c_idx, cell_value in enumerate(row):
                    h = cell_value
                    if h is None:
                        h = f'Col_{c_idx + 1}'
                    h = str(h).strip()
                    if h in seen:
                        seen[h] += 1
                        h = f"{h}_{seen[h]}"
                    else:
                        seen[h] = 1
                    headers.append(h)
            elif r_idx >= 3:
                # Row 3 onwards = data
                # Skip row if it is completely empty
                if not any(cell_value is not None and str(cell_value).strip() != '' for cell_value in row):
                    continue
                
                row_data = {}
                for c_idx, cell_value in enumerate(row):
                    if c_idx < len(headers):
                        row_data[headers[c_idx]] = cell_value
                    else:
                        row_data[f'Col_{c_idx + 1}'] = cell_value
                rows.append(row_data)
                
        wb.close()
        return headers, rows
    except Exception as e:
        raise Exception(f'Error reading {os.path.basename(filepath)}: {str(e)}')
    finally:
        if f:
            f.close()


def read_file(filepath):
    """Read Excel file (auto-detect format)."""
    filename = os.path.basename(filepath)
    try:
        if zipfile.is_zipfile(filepath):
            return read_xlsx_file(filepath)
        else:
            return read_xls_file(filepath)
    except Exception as e:
        try:
            if zipfile.is_zipfile(filepath):
                return read_xls_file(filepath)
            else:
                return read_xlsx_file(filepath)
        except Exception:
            # Fallback 2: Try to repair using Windows Excel COM
            repaired_path = try_repair_excel_with_excel_app(filepath)
            if repaired_path:
                try:
                    headers, rows = read_xlsx_file(repaired_path)
                    return headers, rows
                finally:
                    try:
                        if os.path.exists(repaired_path):
                            os.remove(repaired_path)
                    except:
                        pass
            else:
                raise Exception(
                    f"The uploaded Excel file '{filename}' appears to be corrupted or malformed. "
                    "Please open the file in Microsoft Excel on your computer, save it (Ctrl+S), and then try uploading it again."
                )


# ─── LOOKUP Logic ────────────────────────────────────────────────────────

def build_sale_summary_lookup(sale_summary_rows, sale_summary_headers):
    """Build lookup dict from SALE SUMMARY keyed by New Invoice No."""
    lookup = {}
    for row in sale_summary_rows:
        # Try "New Invoice No." first, then "New Invoice No"
        key = None
        for possible_key in ['New Invoice No.', 'New Invoice No', 'New invoice No.']:
            if possible_key in row:
                key = safe_str(row[possible_key])
                break
        
        if key:
            lookup[key] = {
                'invoice_type': safe_str(row.get('Invoice Type', '')),
                'invoice_id': safe_str(row.get('Invoice No', row.get('Invoice No.', ''))),
                'state_code': safe_str(row.get('State Code', '')),
                'channel': safe_str(row.get('Channel', '')),
            }
    return lookup


def build_purchase_summary_lookup(purchase_summary_rows, purchase_summary_headers):
    """Build lookup dict from PURCHASE SUMMARY keyed by Invoice No."""
    lookup = {}
    for row in purchase_summary_rows:
        key = None
        for possible_key in ['Invoice No.', 'Invoice No', 'Invoice Number']:
            if possible_key in row:
                key = safe_str(row[possible_key])
                break
        
        if key:
            lookup[key] = {
                'invoice_type': safe_str(row.get('Invoice Type', '')),
                'order_no': safe_str(row.get('Order No', '')),
            }
    return lookup


# ─── Main Processing ───────────────────────────────────────────────────────

def process_files(sale_details_path, sale_summary_path, purchase_details_path, purchase_summary_path):
    """Process 4 files and generate combined data."""
    
    # Read all files
    sd_headers, sd_rows = read_file(sale_details_path)
    ss_headers, ss_rows = read_file(sale_summary_path)
    pd_headers, pd_rows = read_file(purchase_details_path)
    ps_headers, ps_rows = read_file(purchase_summary_path)
    
    # Build LOOKUP dicts
    sale_lookup = build_sale_summary_lookup(ss_rows, ss_headers)
    purchase_lookup = build_purchase_summary_lookup(ps_rows, ps_headers)
    
    # ─── Process SALE side ──────────────────────────────────────────────
    sale_processed = []
    for idx, row in enumerate(sd_rows):
        invoice_no = safe_str(row.get('Invoice No', ''))
        
        # VLOOKUP from SALE SUMMARY
        summary = sale_lookup.get(invoice_no, {})
        
        # Direct columns from SALE DETAILS
        quantity = safe_float(row.get('Quantity', 0))
        item_cost = safe_float(row.get('Item Cost', row.get('Item cost', 0)))
        gross = safe_float(row.get('Gross', 0))
        igst_rate = safe_float(row.get('IGST', 0))
        cgst_rate = safe_float(row.get('CGST', 0))
        sgst_rate = safe_float(row.get('SGST', 0))
        igst_amt = safe_float(row.get('IGST Amt', 0))
        cgst_amt = safe_float(row.get('CGST Amt', 0))
        sgst_amt = safe_float(row.get('SGST Amt', 0))
        invoice_val = safe_float(row.get('Invoice', 0))
        
        order_id = safe_str(row.get('Order ID', ''))
        item_asin = safe_str(row.get('Item Asin', ''))
        item_sku = safe_str(row.get('Item SKU', ''))
        
        # SALE UNIQUE ID = InvoiceNo - OrderID - ItemAsin - ItemSKU
        sale_unique_id = f'{invoice_no}-{order_id}-{item_asin}-{item_sku}'
        
        # State code
        state_code_full = summary.get('state_code', '')
        state_code_short = extract_state_short(state_code_full)
        
        # Duplicate calculated columns (Col 28-37)
        calc_qty = quantity  # Col 28 = Col 13
        calc_cost = item_cost  # Col 29 = Col 14
        calc_gross = roundup2(calc_qty * calc_cost)  # Col 30 = 28 * 29
        calc_igst = igst_rate  # Col 31 = Col 16
        calc_cgst = cgst_rate  # Col 32 = Col 17
        calc_sgst = sgst_rate  # Col 33 = Col 18
        calc_igst_amt = roundup2(calc_gross * calc_igst / 100) if calc_igst else 0  # Col 34
        calc_cgst_amt = roundup2(calc_gross * calc_cgst / 100) if calc_cgst else 0  # Col 35
        calc_sgst_amt = roundup2(calc_gross * calc_sgst / 100) if calc_sgst else 0  # Col 36
        calc_invoice = calc_gross + calc_igst_amt + calc_cgst_amt + calc_sgst_amt  # Col 37
        
        sale_row = {
            'no': idx + 1,
            'invoice_no': invoice_no,
            'type': summary.get('invoice_type', ''),
            'invoice_date': safe_str(row.get('Invoice Date', '')),
            'warehouse_name': safe_str(row.get('Warehouse Name', '')),
            'warehouse_code': safe_str(row.get('Warehouse Code', '')),
            'gst_no': safe_str(row.get('GST No', '')),
            'order_id': order_id,
            'item_asin': item_asin,
            'item_sku': item_sku,
            'item_name': safe_str(row.get('Item Name', '')),
            'hsn_number': safe_str(row.get('HSN Number', '')),
            'quantity': quantity,
            'item_cost': item_cost,
            'gross': gross,
            'igst': igst_rate,
            'cgst': cgst_rate,
            'sgst': sgst_rate,
            'igst_amt': igst_amt,
            'cgst_amt': cgst_amt,
            'sgst_amt': sgst_amt,
            'invoice': invoice_val,
            'reason': safe_str(row.get('Reason', '')),
            'zoho_status': safe_str(row.get('Zoho Status', '')),
            'invoice_id': summary.get('invoice_id', ''),
            'state_code': state_code_full,
            'sale_unique_id': sale_unique_id,
            # Duplicate calculated columns
            'calc_qty': calc_qty,
            'calc_cost': calc_cost,
            'calc_gross': calc_gross,
            'calc_igst': calc_igst,
            'calc_cgst': calc_cgst,
            'calc_sgst': calc_sgst,
            'calc_igst_amt': calc_igst_amt,
            'calc_cgst_amt': calc_cgst_amt,
            'calc_sgst_amt': calc_sgst_amt,
            'calc_invoice': roundup2(calc_invoice),
            'state_code_short': state_code_short,
        }
        sale_processed.append(sale_row)
    
    # ─── Process PURCHASE side ──────────────────────────────────────────
    purchase_processed = []
    for idx, row in enumerate(pd_rows):
        invoice_no = safe_str(row.get('Invoice No', ''))
        
        order_id = safe_str(row.get('Order ID', ''))
        item_asin = safe_str(row.get('Item Asin', ''))
        item_sku = safe_str(row.get('Item SKU', ''))
        
        quantity = safe_float(row.get('Quantity', 0))
        
        # Handle the duplicate "Quantity" column that's actually "Item cost"
        # In PURCHASE DETAILS, Col 12 header says "Quantity" but value is Item cost
        item_cost = 0
        if 'Quantity_2' in row:
            item_cost = safe_float(row.get('Quantity_2', 0))
        else:
            item_cost_key = 'Item cost'
            if item_cost_key not in row:
                item_cost_key = 'Item Cost'
            item_cost = safe_float(row.get(item_cost_key, 0))
            if item_cost == 0:
                # Fallback: the item cost might be mislabeled
                # Look at all values and find the one that looks like a cost
                for k, v in row.items():
                    if k not in [item_cost_key] and 'cost' in k.lower():
                        item_cost = safe_float(v)
                        break
        
        gross = safe_float(row.get('Gross', 0))
        igst_rate = safe_float(row.get('IGST', 0))
        cgst_rate = safe_float(row.get('CGST', 0))
        sgst_rate = safe_float(row.get('SGST', 0))
        igst_amt = safe_float(row.get('IGST Amt', 0))
        cgst_amt = safe_float(row.get('CGST Amt', 0))
        sgst_amt = safe_float(row.get('SGST Amt', 0))
        invoice_val = safe_float(row.get('Invoice', 0))
        
        # PURCHASE UNIQUE ID = InvoiceNo - OrderID - ItemAsin - ItemSKU (with "-" separator)
        purchase_unique_id = f'{invoice_no}-{order_id}-{item_asin}-{item_sku}'
        
        # Duplicate calculated columns (Col 61-69)
        calc_qty = quantity  # Col 61
        calc_cost = item_cost  # Col 62
        calc_gross = roundup2(calc_qty * calc_cost)  # Col 63
        calc_igst = igst_rate  # Col 64
        calc_cgst = cgst_rate  # Col 65
        calc_sgst = sgst_rate  # Col 66
        calc_igst_amt = roundup2(calc_gross * calc_igst / 100) if calc_igst else 0  # Col 67
        calc_cgst_amt = roundup2(calc_gross * calc_cgst / 100) if calc_cgst else 0  # Col 68
        calc_sgst_amt = roundup2(calc_gross * calc_sgst / 100) if calc_sgst else 0  # Col 69
        calc_total_amt = roundup2(calc_gross + calc_igst_amt + calc_cgst_amt + calc_sgst_amt)  # Col 70
        
        purchase_row = {
            'no': idx + 1,
            'invoice_no': invoice_no,
            'warehouse_name': safe_str(row.get('Warehouse Name', '')),
            'warehouse_code': safe_str(row.get('Warehouse Code', '')),
            'gst_no': safe_str(row.get('GST No', '')),
            'order_id': order_id,
            'item_asin': item_asin,
            'item_sku': item_sku,
            'item_name': safe_str(row.get('Item Name', '')),
            'hsn_number': safe_str(row.get('HSN Number', '')),
            'quantity': quantity,
            'item_cost': item_cost,
            'gross': gross,
            'igst': igst_rate,
            'cgst': cgst_rate,
            'sgst': sgst_rate,
            'igst_amt': igst_amt,
            'cgst_amt': cgst_amt,
            'sgst_amt': sgst_amt,
            'invoice': invoice_val,
            'purchase_unique_id': purchase_unique_id,
            # Duplicate calculated columns
            'calc_qty': calc_qty,
            'calc_cost': calc_cost,
            'calc_gross': calc_gross,
            'calc_igst': calc_igst,
            'calc_cgst': calc_cgst,
            'calc_sgst': calc_sgst,
            'calc_igst_amt': calc_igst_amt,
            'calc_cgst_amt': calc_cgst_amt,
            'calc_sgst_amt': calc_sgst_amt,
            'calc_total_amt': calc_total_amt,
        }
        purchase_processed.append(purchase_row)
    
    return sale_processed, purchase_processed


# ─── Excel Export ────────────────────────────────────────────────────────

def export_to_excel(sale_data, purchase_data, output_path):
    """Export combined data to Excel in the final format."""
    wb = openpyxl.Workbook()
    ws = wb.active
    fy = get_financial_year()
    ws.title = f'AJIO & MYNTRA SALE-PURCHASE {fy}'
    
    # ─── Styles ─────────────────────────────────────────────────────────
    header_font = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
    sale_fill = PatternFill(start_color='1B5E20', end_color='1B5E20', fill_type='solid')
    purchase_fill = PatternFill(start_color='0D47A1', end_color='0D47A1', fill_type='solid')
    subheader_font = Font(name='Calibri', bold=True, size=10)
    sale_subheader_fill = PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid')
    purchase_subheader_fill = PatternFill(start_color='BBDEFB', end_color='BBDEFB', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal='center', vertical='center')
    
    # ─── Row 1: Merged Headers ──────────────────────────────────────────
    ws.merge_cells('A1:AL1')  # SALE
    ws.merge_cells('AN1:BR1')  # PURCHASE
    
    sale_cell = ws.cell(row=1, column=1, value='SALE')
    sale_cell.font = header_font
    sale_cell.fill = sale_fill
    sale_cell.alignment = center_align
    
    purchase_cell = ws.cell(row=1, column=40, value='PURCHASE')
    purchase_cell.font = header_font
    purchase_cell.fill = purchase_fill
    purchase_cell.alignment = center_align
    
    # ─── Row 2: Column Headers ──────────────────────────────────────────
    sale_headers = [
        'No.', 'Invoice No', 'TYPE', 'Invoice Date', 'Warehouse Name',
        'Warehouse Code', 'GST No', 'Order ID', 'Item Asin', 'Item SKU',
        'Item Name', 'HSN Number', 'Quantity', 'Item Cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Invoice', 'Reason', 'Zoho Status', 'invoice id', 'State Code',
        'SALE UNIQUE ID', 'Quantity', 'Item Cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Invoice', 'STATE CODE'
    ]
    
    purchase_headers = [
        'No.', 'Invoice No', 'Warehouse Name', 'Warehouse Code', 'GST No',
        'Order ID', 'Item Asin', 'Item SKU', 'Item Name', 'HSN Number',
        'Quantity', 'Item cost', 'Gross', 'IGST', 'CGST', 'SGST',
        'IGST Amt', 'CGST Amt', 'SGST Amt', 'Invoice',
        'PURCHASE UNIQUE ID', 'Quantity', 'Item cost', 'Gross',
        'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
        'Total Amt'
    ]
    
    # Write SALE headers (Col 1-38)
    for i, h in enumerate(sale_headers):
        cell = ws.cell(row=2, column=i + 1, value=h)
        cell.font = subheader_font
        cell.fill = sale_subheader_fill
        cell.border = thin_border
        cell.alignment = center_align
    
    # Write PURCHASE headers (Col 40-70)
    for i, h in enumerate(purchase_headers):
        cell = ws.cell(row=2, column=40 + i, value=h)
        cell.font = subheader_font
        cell.fill = purchase_subheader_fill
        cell.border = thin_border
        cell.alignment = center_align
    
    # ─── Data Rows ──────────────────────────────────────────────────────
    max_rows = max(len(sale_data), len(purchase_data))
    
    sale_keys = [
        'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
        'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
        'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
        'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
        'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
        'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short'
    ]
    
    purchase_keys = [
        'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
        'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
        'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
        'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
        'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
        'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
        'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt'
    ]
    
    for r in range(max_rows):
        row_num = r + 3  # Data starts at row 3
        
        # SALE data
        if r < len(sale_data):
            for c, key in enumerate(sale_keys):
                cell = ws.cell(row=row_num, column=c + 1, value=sale_data[r].get(key, ''))
                cell.border = thin_border
        
        # PURCHASE data
        if r < len(purchase_data):
            for c, key in enumerate(purchase_keys):
                cell = ws.cell(row=row_num, column=40 + c, value=purchase_data[r].get(key, ''))
                cell.border = thin_border
    
    # ─── Column Widths ──────────────────────────────────────────────────
    for col in range(1, 72):
        ws.column_dimensions[get_column_letter(col)].width = 15
    # Wider columns for names
    ws.column_dimensions['K'].width = 40  # Item Name
    ws.column_dimensions['AW'].width = 40  # Purchase Item Name
    
    wb.save(output_path)
    return output_path


# ─── Routes ──────────────────────────────────────────────────────────

# Cache storage for Google Sheet Sale-Purchase Quantities (SQLite-based for low memory)
import threading
import re
import csv
import sqlite3
import gc

_CACHE_DB_PATH = os.path.join(DATA_DIR, 'sale_cache.db')
_cache_loaded_event = threading.Event()
_is_cache_loading = False

def _init_cache_db():
    """Initialize the SQLite cache database."""
    # Check if we need to migrate the database
    if os.path.exists(_CACHE_DB_PATH):
        try:
            conn = sqlite3.connect(_CACHE_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sale_cache)")
            columns = [col[1] for col in cursor.fetchall()]
            conn.close()
            # Migrate if any new column like 'invoice_no' or 'igst_amt' is missing
            if columns and ('invoice_no' not in columns or 'igst_amt' not in columns):
                print("[CACHE SYNC] Outdated SQLite schema detected. Deleting old DB to trigger fresh load.", flush=True)
                try:
                    os.remove(_CACHE_DB_PATH)
                except Exception as del_err:
                    print(f"[CACHE SYNC] Failed to delete old DB: {str(del_err)}", flush=True)
        except Exception as check_err:
            print(f"[CACHE SYNC] Error checking schema migration: {str(check_err)}", flush=True)

    conn = sqlite3.connect(_CACHE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sale_cache (
            key TEXT PRIMARY KEY, qty REAL, rate REAL, state TEXT, seller_name TEXT, sheet_name TEXT,
            invoice_no TEXT, invoice_date TEXT, warehouse_code TEXT, gst_no TEXT,
            order_id TEXT, item_asin TEXT, item_sku TEXT, item_name TEXT, hsn_number TEXT,
            invoice_val REAL, reason TEXT, zoho_status TEXT, invoice_id TEXT,
            gross REAL, igst REAL, cgst REAL, sgst REAL, igst_amt REAL, cgst_amt REAL, sgst_amt REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_key ON sale_cache(key)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchase_cache (
            key TEXT PRIMARY KEY, qty REAL, rate REAL, seller_name TEXT, sheet_name TEXT,
            invoice_no TEXT, warehouse_code TEXT, gst_no TEXT, order_id TEXT,
            item_asin TEXT, item_sku TEXT, item_name TEXT, hsn_number TEXT,
            invoice_val REAL,
            gross REAL, igst REAL, cgst REAL, sgst REAL, igst_amt REAL, cgst_amt REAL, sgst_amt REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_key_purchase ON purchase_cache(key)")
    conn.commit()
    conn.close()


# ─── Multi-Year FY Settings Storage ───────────────────────────────────────
FY_SETTINGS_FILE = os.path.join(DATA_DIR, 'fy_settings.json')

DEFAULT_FY_URLS = {
    '2025-26': 'https://script.google.com/macros/s/AKfycbwNUZf-kOwrze7bJOa89vHU1J2atjsyCTt3lQ7E15KJptTsBJ3g4tUH0MqnhSt-LHhoCw/exec',
    '2026-27': 'https://script.google.com/macros/s/AKfycbyWMb69Xfk-Gkkp5Ye5mYCE8DoFUG0ua804LBlLErACpGPBAh1yZc3UhaIcRWvaiMGA/exec'
}

DEFAULT_SHEET_URLS = {
    '2025-26': 'https://docs.google.com/spreadsheets/d/1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To/edit',
    '2026-27': 'https://docs.google.com/spreadsheets/d/1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w/edit'
}

def load_fy_all_settings():
    urls = dict(DEFAULT_FY_URLS)
    sheet_urls = dict(DEFAULT_SHEET_URLS)
    if os.path.exists(FY_SETTINGS_FILE):
        try:
            with open(FY_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if 'urls' in data and isinstance(data['urls'], dict):
                        urls.update(data['urls'])
                        if 'sheet_urls' in data and isinstance(data['sheet_urls'], dict):
                            sheet_urls.update(data['sheet_urls'])
                    else:
                        for k, v in data.items():
                            if isinstance(v, str):
                                urls[k] = v
        except Exception as err:
            print(f"[FY SETTINGS] Error reading fy_settings.json: {str(err)}", flush=True)
    return urls, sheet_urls

def load_fy_settings():
    urls, _ = load_fy_all_settings()
    return urls

def save_fy_settings_file(urls, sheet_urls=None):
    try:
        cur_urls, cur_sheet_urls = load_fy_all_settings()
        if isinstance(urls, dict):
            for k, v in urls.items():
                if v and str(v).strip():
                    cur_urls[k] = str(v).strip()
                elif k not in cur_urls:
                    cur_urls[k] = ''
        if isinstance(sheet_urls, dict):
            for k, v in sheet_urls.items():
                if v and str(v).strip():
                    cur_sheet_urls[k] = str(v).strip()
                elif k not in cur_sheet_urls:
                    cur_sheet_urls[k] = ''
        full_data = {
            'urls': cur_urls,
            'sheet_urls': cur_sheet_urls
        }
        with open(FY_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        print(f"[FY SETTINGS] Saved multi-year settings to fy_settings.json: {full_data}", flush=True)

    except Exception as err:
        print(f"[FY SETTINGS ERROR] Failed to save fy_settings.json: {str(err)}", flush=True)


@app.route('/api/get-fy-settings', methods=['GET', 'OPTIONS'])
def get_fy_settings():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
        return response
    urls, sheet_urls = load_fy_all_settings()
    response = jsonify({"status": "Success", "urls": urls, "sheet_urls": sheet_urls})
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route('/api/save-fy-settings', methods=['POST', 'OPTIONS'])
def save_fy_settings():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response
    try:
        data = request.get_json(force=True, silent=True) or {}
        urls = data.get('urls', {})
        sheet_urls = data.get('sheet_urls', {})
        if isinstance(urls, dict) or isinstance(sheet_urls, dict):
            save_fy_settings_file(urls, sheet_urls)
            threading.Thread(target=_load_cache_safely, daemon=True).start()
            response = jsonify({"status": "Success", "message": "Multi-Year FY settings saved successfully", "urls": urls, "sheet_urls": sheet_urls})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response
        else:
            response = jsonify({"status": "Error", "message": "Invalid urls format"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400
    except Exception as e:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

_sync_progress = {"status": "idle", "percent": 0, "message": ""}

def _fetch_and_store_google_sheet_to_sqlite():
    """Download Google Sheet CSV & Web App data for all Financial Years and store into SQLite (low memory)."""
    global _sync_progress
    _sync_progress = {"status": "running", "percent": 5, "message": "Fetching spreadsheet bootstrap data..."}
    def to_float(val):
        if val is None or val == "":
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        try:
            s = str(val).strip()
            return float(s) if s else 0.0
        except ValueError:
            return 0.0

    def to_str(val):
        if val is None:
            return ""
        return str(val).strip()

    spreadsheet_id = "1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To"
    edit_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    
    try:
        res = requests.get(edit_url, timeout=120)
        if res.status_code != 200:
            print(f"[CACHE SYNC ERROR] Failed to fetch edit page. Status: {res.status_code}", flush=True)
            return False
            
        html = res.text
        match = re.search(r'bootstrapData\s*=\s*({.+?});', html)
        if not match:
            match = re.search(r'var\s+bootstrapData\s*=\s*({.+?});', html)
            
        sheets = []
        if match:
            try:
                data = json.loads(match.group(1))
                topsnapshot = data.get("changes", {}).get("topsnapshot", [])
                for item in topsnapshot:
                    if not isinstance(item, list) or len(item) < 2:
                        continue
                    payload_str = item[1]
                    if isinstance(payload_str, str) and payload_str.startswith("["):
                        inner = json.loads(payload_str)
                        if isinstance(inner, list) and len(inner) >= 4:
                            gid = str(inner[2])
                            props_list = inner[3]
                            if isinstance(props_list, list) and len(props_list) > 0:
                                props_dict = props_list[0]
                                if isinstance(props_dict, dict) and "1" in props_dict:
                                    title_block = props_dict["1"]
                                    if isinstance(title_block, list) and len(title_block) > 0:
                                        title_info = title_block[0]
                                        if isinstance(title_info, list) and len(title_info) >= 3:
                                            title = title_info[2]
                                            sheets.append((gid, title))
            except Exception as e:
                print(f"[CACHE SYNC ERROR] Parsing bootstrapData failed: {str(e)}", flush=True)
        
        # Free the HTML string immediately
        del html, res
        gc.collect()
        
        print(f"[CACHE SYNC] Detected {len(sheets)} sheets from bootstrapData: {sheets}", flush=True)
        
        # Always ensure both known years are included
        known_sheets = {
            "0": "AJ&MY&FK SALE-PURCHASE 2025-26",
            "1563945167": "AJ&MY&FK SALE-PURCHASE 2025-26"
        }
        existing_gids = {s[0] for s in sheets}
        existing_titles = {s[1].upper().strip() for s in sheets}
        for gid, title in known_sheets.items():
            if gid not in existing_gids and title.upper().strip() not in existing_titles:
                sheets.append((gid, title))
                print(f"[CACHE SYNC] Added missing fallback sheet: {title} (GID {gid})", flush=True)
                existing_titles.add(title.upper().strip())
        
        if not sheets:
            sheets = list(known_sheets.items())
            sheets = list(known_sheets.items())
        
        # Use a temporary table in the main database
        conn = sqlite3.connect(_CACHE_DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS sale_cache_new")
        conn.execute("""
            CREATE TABLE sale_cache_new (
                key TEXT PRIMARY KEY, qty REAL, rate REAL, state TEXT, seller_name TEXT, sheet_name TEXT,
                invoice_no TEXT, invoice_date TEXT, warehouse_code TEXT, gst_no TEXT,
                order_id TEXT, item_asin TEXT, item_sku TEXT, item_name TEXT, hsn_number TEXT,
                invoice_val REAL, reason TEXT, zoho_status TEXT, invoice_id TEXT,
                gross REAL, igst REAL, cgst REAL, sgst REAL, igst_amt REAL, cgst_amt REAL, sgst_amt REAL
            )
        """)
        conn.execute("DROP TABLE IF EXISTS purchase_cache_new")
        conn.execute("""
            CREATE TABLE purchase_cache_new (
                key TEXT PRIMARY KEY, qty REAL, rate REAL, seller_name TEXT, sheet_name TEXT,
                invoice_no TEXT, warehouse_code TEXT, gst_no TEXT, order_id TEXT,
                item_asin TEXT, item_sku TEXT, item_name TEXT, hsn_number TEXT,
                invoice_val REAL,
                gross REAL, igst REAL, cgst REAL, sgst REAL, igst_amt REAL, cgst_amt REAL, sgst_amt REAL
            )
        """)
        conn.commit()
        
        total_keys = 0
        for gid, title in sheets:
            _sync_progress["message"] = f"Downloading CSV for '{title}'..."
            title_upper = title.upper()
            if any(x in title_upper for x in ["DASHBOARD", "SUMMARY", "CONFIG", "INSTRUCTION", "LIMIT", "USER", "PART", "REPORT", "WELCOME"]):
                continue
                
            csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
            print(f"[CACHE SYNC] Downloading CSV for tab '{title}' (GID {gid})...", flush=True)
            
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                res_csv = requests.get(csv_url, headers=headers, timeout=120)
                if res_csv.status_code != 200:
                    fallback_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
                    res_csv = requests.get(fallback_url, headers=headers, timeout=120)
                if res_csv.status_code == 200:
                    csv_text = res_csv.text
                    res_csv.close()
                    del res_csv
                    gc.collect()
                    _sync_progress["message"] = f"Parsing and storing '{title}' in SQLite..."
                    reader = csv.reader(io.StringIO(csv_text))
                    
                    sheet_count = 0
                    batch = []
                    pur_batch = []
                    for r_idx, row in enumerate(reader):
                        if r_idx < 2:  # Skip header rows
                            continue
                        if len(row) < 28:
                            continue
                            
                        key_val = row[26].strip()
                        qty_val = row[27].strip()
                        rate_val = row[28].strip() if len(row) > 28 else ""
                        state_val = ""
                        if len(row) > 37 and row[37].strip():
                            state_val = row[37].strip()
                        elif len(row) > 25 and row[25].strip():
                            state_val = row[25].strip()
                        seller_name_val = row[4].strip() if len(row) > 4 else ""
                        
                        inv_no_v = row[1].strip() if len(row) > 1 else ""
                        inv_date_v = row[3].strip() if len(row) > 3 else ""
                        wh_code_v = row[5].strip() if len(row) > 5 else ""
                        gst_no_v = row[6].strip() if len(row) > 6 else ""
                        ord_id_v = row[7].strip() if len(row) > 7 else ""
                        asin_v = row[8].strip() if len(row) > 8 else ""
                        sku_v = row[9].strip() if len(row) > 9 else ""
                        item_name_v = row[10].strip() if len(row) > 10 else ""
                        hsn_v = row[11].strip() if len(row) > 11 else ""
                        
                        try:
                            igst_v = float(row[15].strip()) if len(row) > 15 and row[15].strip() else 0.0
                        except ValueError:
                            igst_v = 0.0
                        try:
                            cgst_v = float(row[16].strip()) if len(row) > 16 and row[16].strip() else 0.0
                        except ValueError:
                            cgst_v = 0.0
                        try:
                            sgst_v = float(row[17].strip()) if len(row) > 17 and row[17].strip() else 0.0
                        except ValueError:
                            sgst_v = 0.0
                        try:
                            igst_amt_v = float(row[18].strip()) if len(row) > 18 and row[18].strip() else 0.0
                        except ValueError:
                            igst_amt_v = 0.0
                        try:
                            cgst_amt_v = float(row[19].strip()) if len(row) > 19 and row[19].strip() else 0.0
                        except ValueError:
                            cgst_amt_v = 0.0
                        try:
                            sgst_amt_v = float(row[20].strip()) if len(row) > 20 and row[20].strip() else 0.0
                        except ValueError:
                            sgst_amt_v = 0.0
                            
                        reason_v = row[22].strip() if len(row) > 22 else ""
                        zoho_stat_v = row[23].strip() if len(row) > 23 else ""
                        inv_id_v = row[24].strip() if len(row) > 24 else ""
                        
                        # Fallback key construction
                        if not key_val:
                            if inv_no_v and (ord_id_v or sku_v):
                                key_val = f"{inv_no_v}-{ord_id_v}-{asin_v}-{sku_v}"
                                
                        if key_val:
                            norm_key = key_val.strip().upper()
                            try:
                                qty = float(qty_val) if qty_val else 0.0
                            except ValueError:
                                qty = 0.0
                            try:
                                rate = float(rate_val) if rate_val else 0.0
                            except ValueError:
                                rate = 0.0
                            state = state_val.strip()
                            try:
                                gross_v = float(row[14].strip()) if len(row) > 14 and row[14].strip() else round(qty * rate, 2)
                            except ValueError:
                                gross_v = round(qty * rate, 2)
                            try:
                                inv_val_v = float(row[21].strip()) if len(row) > 21 and row[21].strip() else round(qty * rate + igst_amt_v + cgst_amt_v + sgst_amt_v, 2)
                            except ValueError:
                                inv_val_v = round(qty * rate + igst_amt_v + cgst_amt_v + sgst_amt_v, 2)
                            
                            batch.append((
                                norm_key, qty, rate, state, seller_name_val, "AJ&MY&FK SALE-PURCHASE 2025-26",
                                inv_no_v, inv_date_v, wh_code_v, gst_no_v, ord_id_v, asin_v, sku_v, item_name_v, hsn_v,
                                inv_val_v, reason_v, zoho_stat_v, inv_id_v, gross_v, igst_v, cgst_v, sgst_v, igst_amt_v, cgst_amt_v, sgst_amt_v
                            ))
                            sheet_count += 1
                            
                            if len(batch) >= 5000:
                                conn.executemany("""
                                    INSERT OR REPLACE INTO sale_cache_new (
                                        key, qty, rate, state, seller_name, sheet_name,
                                        invoice_no, invoice_date, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                        invoice_val, reason, zoho_status, invoice_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, batch)
                                conn.commit()
                                batch = []
                                
                        pur_key_val = row[59].strip() if len(row) > 59 else ""
                        if pur_key_val:
                            pur_norm_key = pur_key_val.strip().upper()
                            pur_inv_no = row[39].strip() if len(row) > 39 else ""
                            pur_wh_code = row[41].strip() if len(row) > 41 else ""
                            pur_gst_no = row[42].strip() if len(row) > 42 else ""
                            pur_ord_id = row[43].strip() if len(row) > 43 else ""
                            pur_asin = row[44].strip() if len(row) > 44 else ""
                            pur_sku = row[45].strip() if len(row) > 45 else ""
                            pur_item_name = row[46].strip() if len(row) > 46 else ""
                            pur_hsn = row[47].strip() if len(row) > 47 else ""
                            try:
                                pur_qty = float(row[60].strip()) if len(row) > 60 and row[60].strip() else 0.0
                            except ValueError:
                                pur_qty = 0.0
                            try:
                                pur_rate = float(row[61].strip()) if len(row) > 61 and row[61].strip() else 0.0
                            except ValueError:
                                pur_rate = 0.0
                                
                            try:
                                pur_igst = float(row[51].strip()) if len(row) > 51 and row[51].strip() else (float(row[63].strip()) if len(row) > 63 and row[63].strip() else 0.0)
                            except ValueError:
                                pur_igst = 0.0
                            try:
                                pur_cgst = float(row[52].strip()) if len(row) > 52 and row[52].strip() else (float(row[64].strip()) if len(row) > 64 and row[64].strip() else 0.0)
                            except ValueError:
                                pur_cgst = 0.0
                            try:
                                pur_sgst = float(row[53].strip()) if len(row) > 53 and row[53].strip() else (float(row[65].strip()) if len(row) > 65 and row[65].strip() else 0.0)
                            except ValueError:
                                pur_sgst = 0.0
                            try:
                                pur_igst_amt = float(row[54].strip()) if len(row) > 54 and row[54].strip() else (float(row[66].strip()) if len(row) > 66 and row[66].strip() else 0.0)
                            except ValueError:
                                pur_igst_amt = 0.0
                            try:
                                pur_cgst_amt = float(row[55].strip()) if len(row) > 55 and row[55].strip() else (float(row[67].strip()) if len(row) > 67 and row[67].strip() else 0.0)
                            except ValueError:
                                pur_cgst_amt = 0.0
                            try:
                                pur_sgst_amt = float(row[56].strip()) if len(row) > 56 and row[56].strip() else (float(row[68].strip()) if len(row) > 68 and row[68].strip() else 0.0)
                            except ValueError:
                                pur_sgst_amt = 0.0

                            pur_seller_name_val = row[40].strip() if len(row) > 40 else ""
                            pur_gross = round(pur_qty * pur_rate, 2)
                            pur_inv_val = round(pur_qty * pur_rate + pur_igst_amt + pur_cgst_amt + pur_sgst_amt, 2)
                            
                            pur_batch.append((
                                pur_norm_key, pur_qty, pur_rate, pur_seller_name_val, "AJ&MY&FK SALE-PURCHASE 2025-26",
                                pur_inv_no, pur_wh_code, pur_gst_no, pur_ord_id, pur_asin, pur_sku, pur_item_name, pur_hsn,
                                pur_inv_val, pur_gross, pur_igst, pur_cgst, pur_sgst, pur_igst_amt, pur_cgst_amt, pur_sgst_amt
                            ))

                            
                            if len(pur_batch) >= 5000:
                                conn.executemany("""
                                    INSERT OR REPLACE INTO purchase_cache_new (
                                        key, qty, rate, seller_name, sheet_name,
                                        invoice_no, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                        invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, pur_batch)
                                conn.commit()
                                pur_batch = []
                    
                    # Insert remaining batch
                    if batch:
                        conn.executemany("""
                            INSERT OR REPLACE INTO sale_cache_new (
                                key, qty, rate, state, seller_name, sheet_name,
                                invoice_no, invoice_date, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                invoice_val, reason, zoho_status, invoice_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        conn.commit()
                        batch = []
                    if pur_batch:
                        conn.executemany("""
                            INSERT OR REPLACE INTO purchase_cache_new (
                                key, qty, rate, seller_name, sheet_name,
                                invoice_no, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, pur_batch)
                        conn.commit()
                        pur_batch = []

                        
                    total_keys += sheet_count
                    _sync_progress["percent"] = min(30, _sync_progress.get("percent", 5) + 12)
                    print(f"[CACHE SYNC] Loaded {sheet_count} keys for FY 2025-26", flush=True)
                    
                    res_csv.close()
                    del res_csv
                    gc.collect()
                else:
                    print(f"[CACHE SYNC ERROR] Failed to fetch tab '{title}'. Status: {res_csv.status_code}", flush=True)
            except Exception as ex:
                print(f"[CACHE SYNC ERROR] Error loading tab '{title}': {str(ex)}", flush=True)

        # Fetch FY 2026-27 full data from configured FY Web App URL via parallel workers
        _sync_progress["message"] = "Querying Web App config for FY 2026-27..."
        fy_urls = load_fy_settings()
        web_app_2026_27 = fy_urls.get("2026-27")
        if web_app_2026_27 and str(web_app_2026_27).strip():
            target_url = str(web_app_2026_27).strip()
            print("[CACHE SYNC] Syncing FY 2026-27 full records from Web App...", flush=True)
            try:
                sheet_title_26_27 = "AJ&MY&FK SALE-PURCHASE 2026-27"
                sheet_name_param = "AJ%26MY%26FK%20SALE-PURCHASE%202026-27"
                sn_url = f"{target_url}?action=getSheetNames"
                r_sn = requests.get(sn_url, timeout=30)
                csv_success = False
                loaded_26_27_count = 0
                if r_sn.status_code == 200 and r_sn.json().get("success"):
                    r_json = r_sn.json()
                    spreadsheet_id_26_27 = r_json.get("spreadsheetId")
                    sheets_info = r_json.get("sheets", [])
                    total_rows_26_27 = sheets_info[0].get("rows", 65000) if sheets_info else 65000
                    if spreadsheet_id_26_27 and sheets_info and "gid" in sheets_info[0]:
                        gid_26_27 = sheets_info[0].get("gid")
                        csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id_26_27}/gviz/tq?tqx=out:csv&gid={gid_26_27}"
                        print(f"[CACHE SYNC] Attempting fast CSV sync for FY 2026-27 via {csv_url}...", flush=True)
                        _sync_progress["message"] = "Downloading CSV for FY 2026-27..."
                        try:
                            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                            res_csv = requests.get(csv_url, headers=headers, timeout=120)
                            if res_csv.status_code != 200:
                                fallback_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id_26_27}/export?format=csv&gid={gid_26_27}"
                                res_csv = requests.get(fallback_url, headers=headers, timeout=120)
                            
                            if res_csv.status_code == 200:
                                csv_text = res_csv.text
                                res_csv.close()
                                del res_csv
                                gc.collect()
                                _sync_progress["message"] = "Parsing and storing FY 2026-27 CSV in SQLite..."
                                reader = csv.reader(io.StringIO(csv_text))
                                
                                batch = []
                                pur_batch = []
                                
                                for r_idx, row in enumerate(reader):
                                    if r_idx % 2000 == 0:
                                        pct = min(98, 30 + int((r_idx / max(1, total_rows_26_27)) * 68))
                                        _sync_progress["percent"] = pct
                                        _sync_progress["message"] = f"Parsing and storing FY 2026-27 CSV... ({r_idx:,}/{total_rows_26_27:,} rows)"
                                    if r_idx < 2:  # Skip header rows
                                        continue
                                    if len(row) < 28:
                                        continue
                                        
                                    key_val = row[26].strip()
                                    qty_val = row[27].strip()
                                    rate_val = row[28].strip() if len(row) > 28 else ""
                                    state_val = ""
                                    if len(row) > 37 and row[37].strip():
                                        state_val = row[37].strip()
                                    elif len(row) > 25 and row[25].strip():
                                        state_val = row[25].strip()
                                    seller_name_val = row[4].strip() if len(row) > 4 else ""
                                    
                                    inv_no_v = row[1].strip() if len(row) > 1 else ""
                                    inv_date_v = row[3].strip() if len(row) > 3 else ""
                                    wh_code_v = row[5].strip() if len(row) > 5 else ""
                                    gst_no_v = row[6].strip() if len(row) > 6 else ""
                                    ord_id_v = row[7].strip() if len(row) > 7 else ""
                                    asin_v = row[8].strip() if len(row) > 8 else ""
                                    sku_v = row[9].strip() if len(row) > 9 else ""
                                    item_name_v = row[10].strip() if len(row) > 10 else ""
                                    hsn_v = row[11].strip() if len(row) > 11 else ""
                                    
                                    try:
                                        igst_v = float(row[15].strip()) if len(row) > 15 and row[15].strip() else 0.0
                                    except ValueError:
                                        igst_v = 0.0
                                    try:
                                        cgst_v = float(row[16].strip()) if len(row) > 16 and row[16].strip() else 0.0
                                    except ValueError:
                                        cgst_v = 0.0
                                    try:
                                        sgst_v = float(row[17].strip()) if len(row) > 17 and row[17].strip() else 0.0
                                    except ValueError:
                                        sgst_v = 0.0
                                    try:
                                        igst_amt_v = float(row[18].strip()) if len(row) > 18 and row[18].strip() else 0.0
                                    except ValueError:
                                        igst_amt_v = 0.0
                                    try:
                                        cgst_amt_v = float(row[19].strip()) if len(row) > 19 and row[19].strip() else 0.0
                                    except ValueError:
                                        cgst_amt_v = 0.0
                                    try:
                                        sgst_amt_v = float(row[20].strip()) if len(row) > 20 and row[20].strip() else 0.0
                                    except ValueError:
                                        sgst_amt_v = 0.0
                                        
                                    reason_v = row[22].strip() if len(row) > 22 else ""
                                    zoho_stat_v = row[23].strip() if len(row) > 23 else ""
                                    inv_id_v = row[24].strip() if len(row) > 24 else ""
                                    
                                    # Fallback key construction
                                    key_val_to_use = key_val
                                    if not key_val_to_use:
                                        if inv_no_v and (ord_id_v or sku_v):
                                            key_val_to_use = f"{inv_no_v}-{ord_id_v}-{asin_v}-{sku_v}"
                                            
                                    if key_val_to_use:
                                        norm_key = key_val_to_use.strip().upper()
                                        try:
                                            qty = float(qty_val) if qty_val else 0.0
                                        except ValueError:
                                            qty = 0.0
                                        try:
                                            rate = float(rate_val) if rate_val else 0.0
                                        except ValueError:
                                            rate = 0.0
                                        state = state_val.strip()
                                        try:
                                            gross_v = float(row[14].strip()) if len(row) > 14 and row[14].strip() else round(qty * rate, 2)
                                        except ValueError:
                                            gross_v = round(qty * rate, 2)
                                        try:
                                            inv_val_v = float(row[21].strip()) if len(row) > 21 and row[21].strip() else round(qty * rate + igst_amt_v + cgst_amt_v + sgst_amt_v, 2)
                                        except ValueError:
                                            inv_val_v = round(qty * rate + igst_amt_v + cgst_amt_v + sgst_amt_v, 2)
                                        
                                        batch.append((
                                            norm_key, qty, rate, state, seller_name_val, sheet_title_26_27,
                                            inv_no_v, inv_date_v, wh_code_v, gst_no_v, ord_id_v, asin_v, sku_v, item_name_v, hsn_v,
                                            inv_val_v, reason_v, zoho_stat_v, inv_id_v, gross_v, igst_v, cgst_v, sgst_v, igst_amt_v, cgst_amt_v, sgst_amt_v
                                        ))
                                        
                                        if len(batch) >= 5000:
                                            conn.executemany("""
                                                INSERT OR REPLACE INTO sale_cache_new (
                                                    key, qty, rate, state, seller_name, sheet_name,
                                                    invoice_no, invoice_date, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                                    invoice_val, reason, zoho_status, invoice_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """, batch)
                                            conn.commit()
                                            loaded_26_27_count += len(batch)
                                            batch = []
                                            
                                    pur_key_val = row[59].strip() if len(row) > 59 else ""
                                    if pur_key_val:
                                        pur_norm_key = pur_key_val.strip().upper()
                                        pur_inv_no = row[39].strip() if len(row) > 39 else ""
                                        pur_wh_code = row[41].strip() if len(row) > 41 else ""
                                        pur_gst_no = row[42].strip() if len(row) > 42 else ""
                                        pur_ord_id = row[43].strip() if len(row) > 43 else ""
                                        pur_asin = row[44].strip() if len(row) > 44 else ""
                                        pur_sku = row[45].strip() if len(row) > 45 else ""
                                        pur_item_name = row[46].strip() if len(row) > 46 else ""
                                        pur_hsn = row[47].strip() if len(row) > 47 else ""
                                        try:
                                            pur_qty = float(row[60].strip()) if len(row) > 60 and row[60].strip() else 0.0
                                        except ValueError:
                                            pur_qty = 0.0
                                        try:
                                            pur_rate = float(row[61].strip()) if len(row) > 61 and row[61].strip() else 0.0
                                        except ValueError:
                                            pur_rate = 0.0
                                            
                                        try:
                                            pur_igst = float(row[51].strip()) if len(row) > 51 and row[51].strip() else (float(row[63].strip()) if len(row) > 63 and row[63].strip() else 0.0)
                                        except ValueError:
                                            pur_igst = 0.0
                                        try:
                                            pur_cgst = float(row[52].strip()) if len(row) > 52 and row[52].strip() else (float(row[64].strip()) if len(row) > 64 and row[64].strip() else 0.0)
                                        except ValueError:
                                            pur_cgst = 0.0
                                        try:
                                            pur_sgst = float(row[53].strip()) if len(row) > 53 and row[53].strip() else (float(row[65].strip()) if len(row) > 65 and row[65].strip() else 0.0)
                                        except ValueError:
                                            pur_sgst = 0.0
                                        try:
                                            pur_igst_amt = float(row[54].strip()) if len(row) > 54 and row[54].strip() else (float(row[66].strip()) if len(row) > 66 and row[66].strip() else 0.0)
                                        except ValueError:
                                            pur_igst_amt = 0.0
                                        try:
                                            pur_cgst_amt = float(row[55].strip()) if len(row) > 55 and row[55].strip() else (float(row[67].strip()) if len(row) > 67 and row[67].strip() else 0.0)
                                        except ValueError:
                                            pur_cgst_amt = 0.0
                                        try:
                                            pur_sgst_amt = float(row[56].strip()) if len(row) > 56 and row[56].strip() else (float(row[68].strip()) if len(row) > 68 and row[68].strip() else 0.0)
                                        except ValueError:
                                            pur_sgst_amt = 0.0
                                            
                                        pur_seller_name_val = row[40].strip() if len(row) > 40 else ""
                                        pur_gross = round(pur_qty * pur_rate, 2)
                                        pur_inv_val = round(pur_qty * pur_rate + pur_igst_amt + pur_cgst_amt + pur_sgst_amt, 2)
                                        
                                        pur_batch.append((
                                            pur_norm_key, pur_qty, pur_rate, pur_seller_name_val, sheet_title_26_27,
                                            pur_inv_no, pur_wh_code, pur_gst_no, pur_ord_id, pur_asin, pur_sku, pur_item_name, pur_hsn,
                                            pur_inv_val, pur_gross, pur_igst, pur_cgst, pur_sgst, pur_igst_amt, pur_cgst_amt, pur_sgst_amt
                                        ))
                                        
                                        if len(pur_batch) >= 5000:
                                            conn.executemany("""
                                                INSERT OR REPLACE INTO purchase_cache_new (
                                                    key, qty, rate, seller_name, sheet_name,
                                                    invoice_no, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                                    invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """, pur_batch)
                                            conn.commit()
                                            pur_batch = []
                                
                                if batch:
                                    conn.executemany("""
                                        INSERT OR REPLACE INTO sale_cache_new (
                                            key, qty, rate, state, seller_name, sheet_name,
                                            invoice_no, invoice_date, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                            invoice_val, reason, zoho_status, invoice_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, batch)
                                    conn.commit()
                                    loaded_26_27_count += len(batch)
                                if pur_batch:
                                    conn.executemany("""
                                        INSERT OR REPLACE INTO purchase_cache_new (
                                            key, qty, rate, seller_name, sheet_name,
                                            invoice_no, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                            invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, pur_batch)
                                    conn.commit()
                                
                                total_keys += loaded_26_27_count
                                _sync_progress["percent"] = 98
                                print(f"[CACHE SYNC SUCCESS] Fast CSV sync loaded {loaded_26_27_count} full records for FY 2026-27.", flush=True)
                                csv_success = True
                        except Exception as csv_err:
                            print(f"[CACHE SYNC WARNING] Fast CSV sync failed: {str(csv_err)}, falling back to paginated sync.", flush=True)

                if not csv_success:
                    print("[CACHE SYNC] Starting paginated chunk fetch fallback for FY 2026-27...", flush=True)
                    _sync_progress["message"] = "Initializing 2026-27 paginated chunk sync (Fallback)..."
                    total_26_27_rows = 65000
                    if r_sn.status_code == 200 and r_sn.json().get("success"):
                        sheets_info = r_sn.json().get("sheets", [])
                        if sheets_info:
                            total_26_27_rows = sheets_info[0].get("rows", 65000)

                    batch_size = 500
                    start_rows = list(range(3, total_26_27_rows + 3, batch_size))
                    
                    completed_batches = 0
                    total_b = max(1, len(start_rows))

                    def _fetch_26_27_batch(start_row):
                        u = f"{target_url}?action=getSheetData&sheetName={sheet_name_param}&startRow={start_row}&numRows={batch_size}"
                        for attempt in range(3):
                            try:
                                res = requests.get(u, timeout=60)
                                if res.status_code == 200 and res.json().get("success"):
                                    return res.json().get("data", [])
                            except Exception as b_err:
                                time.sleep(1)
                        return []

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {executor.submit(_fetch_26_27_batch, sr): sr for sr in start_rows}
                        for future in as_completed(futures):
                            rows = future.result()
                            completed_batches += 1
                            _sync_progress["percent"] = min(98, 30 + int((completed_batches / total_b) * 65))
                            _sync_progress["message"] = f"Loading 2026-27 data... ({completed_batches}/{total_b} batches loaded)"
                            if rows:
                                to_sale = []
                                to_purchase = []
                                for row in rows:
                                    if len(row) > 26:
                                        k = to_str(row[26]).upper()
                                        if k:
                                            q = to_float(row[27])
                                            rt = to_float(row[28])
                                            st = to_str(row[37]) if len(row) > 37 and row[37] else to_str(row[25])
                                            sel = to_str(row[4])
                                            
                                            inv_no_v = to_str(row[1])
                                            inv_date_v = to_str(row[3])
                                            wh_code_v = to_str(row[5])
                                            gst_no_v = to_str(row[6])
                                            ord_id_v = to_str(row[7])
                                            asin_v = to_str(row[8])
                                            sku_v = to_str(row[9])
                                            item_name_v = to_str(row[10])
                                            hsn_v = to_str(row[11])
                                            
                                            igst_v = to_float(row[15]) if len(row) > 15 else 0.0
                                            cgst_v = to_float(row[16]) if len(row) > 16 else 0.0
                                            sgst_v = to_float(row[17]) if len(row) > 17 else 0.0
                                            igst_amt_v = to_float(row[18]) if len(row) > 18 else 0.0
                                            cgst_amt_v = to_float(row[19]) if len(row) > 19 else 0.0
                                            sgst_amt_v = to_float(row[20]) if len(row) > 20 else 0.0
                                                
                                            reason_v = to_str(row[22]) if len(row) > 22 else ""
                                            zoho_stat_v = to_str(row[23]) if len(row) > 23 else ""
                                            inv_id_v = to_str(row[24]) if len(row) > 24 else ""
                                            gross_v = to_float(row[14]) if len(row) > 14 and row[14] is not None else round(q * rt, 2)
                                            inv_val_v = to_float(row[21]) if len(row) > 21 and row[21] is not None else round(q * rt + igst_amt_v + cgst_amt_v + sgst_amt_v, 2)

                                            to_sale.append((
                                                k, q, rt, st, sel, sheet_title_26_27,
                                                inv_no_v, inv_date_v, wh_code_v, gst_no_v, ord_id_v, asin_v, sku_v, item_name_v, hsn_v,
                                                inv_val_v, reason_v, zoho_stat_v, inv_id_v, gross_v, igst_v, cgst_v, sgst_v, igst_amt_v, cgst_amt_v, sgst_amt_v
                                            ))
                                    if len(row) > 59:
                                        pk = to_str(row[59]).upper()
                                        if pk:
                                            pq = to_float(row[60])
                                            prt = to_float(row[61])
                                            psel = to_str(row[40]) if len(row) > 40 and row[40] else to_str(row[4])
                                            
                                            pur_inv_no = to_str(row[39])
                                            pur_wh_code = to_str(row[41])
                                            pur_gst_no = to_str(row[42])
                                            pur_ord_id = to_str(row[43])
                                            pur_asin = to_str(row[44])
                                            pur_sku = to_str(row[45])
                                            pur_item_name = to_str(row[46])
                                            pur_hsn = to_str(row[47])
                                            
                                            pur_igst = to_float(row[51]) if len(row) > 51 and row[51] is not None else (to_float(row[63]) if len(row) > 63 else 0.0)
                                            pur_cgst = to_float(row[52]) if len(row) > 52 and row[52] is not None else (to_float(row[64]) if len(row) > 64 else 0.0)
                                            pur_sgst = to_float(row[53]) if len(row) > 53 and row[53] is not None else (to_float(row[65]) if len(row) > 65 else 0.0)
                                            pur_igst_amt = to_float(row[54]) if len(row) > 54 and row[54] is not None else (to_float(row[66]) if len(row) > 66 else 0.0)
                                            pur_cgst_amt = to_float(row[55]) if len(row) > 55 and row[55] is not None else (to_float(row[67]) if len(row) > 67 else 0.0)
                                            pur_sgst_amt = to_float(row[56]) if len(row) > 56 and row[56] is not None else (to_float(row[68]) if len(row) > 68 else 0.0)

                                            pur_gross = round(pq * prt, 2)
                                            pur_inv_val = round(pq * prt + pur_igst_amt + pur_cgst_amt + pur_sgst_amt, 2)
                                            
                                            to_purchase.append((
                                                pk, pq, prt, psel, sheet_title_26_27,
                                                pur_inv_no, pur_wh_code, pur_gst_no, pur_ord_id, pur_asin, pur_sku, pur_item_name, pur_hsn,
                                                pur_inv_val, pur_gross, pur_igst, pur_cgst, pur_sgst, pur_igst_amt, pur_cgst_amt, pur_sgst_amt
                                            ))

                                if to_sale:
                                    conn.executemany("""
                                        INSERT OR REPLACE INTO sale_cache_new (
                                            key, qty, rate, state, seller_name, sheet_name,
                                            invoice_no, invoice_date, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                            invoice_val, reason, zoho_status, invoice_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, to_sale)
                                if to_purchase:
                                    conn.executemany("""
                                        INSERT OR REPLACE INTO purchase_cache_new (
                                            key, qty, rate, seller_name, sheet_name,
                                            invoice_no, warehouse_code, gst_no, order_id, item_asin, item_sku, item_name, hsn_number,
                                            invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, to_purchase)
                                conn.commit()

                                loaded_26_27_count += len(to_sale)

                print(f"[CACHE SYNC SUCCESS] Loaded {loaded_26_27_count} full records for FY 2026-27.", flush=True)

            except Exception as e_26_27:
                print(f"[CACHE SYNC ERROR] Failed to fetch 2026-27 Web App full records: {str(e_26_27)}", flush=True)
        
        # Create index on the temporary table
        conn.execute("CREATE INDEX IF NOT EXISTS idx_key_new ON sale_cache_new(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_key_purchase_new ON purchase_cache_new(key)")
        conn.commit()
        
        # Preserve dynamically fetched Web App keys before dropping old cache
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_cache'")
            if cursor.fetchone():
                conn.execute("""
                    INSERT OR IGNORE INTO sale_cache_new (key, qty, rate, state, seller_name, sheet_name)
                    SELECT key, qty, rate, state, seller_name, sheet_name FROM sale_cache
                """)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_cache'")
            if cursor.fetchone():
                conn.execute("""
                    INSERT OR IGNORE INTO purchase_cache_new (key, qty, rate, seller_name, sheet_name)
                    SELECT key, qty, rate, seller_name, sheet_name FROM purchase_cache
                """)
            conn.commit()
        except Exception as preserve_err:
            print(f"[CACHE SYNC] Note on preserving dynamic keys: {str(preserve_err)}", flush=True)

        # Atomically swap table names
        _sync_progress["message"] = "Atomic swap: Renaming cache tables in SQLite..."
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DROP TABLE IF EXISTS sale_cache_old")
            conn.execute("DROP TABLE IF EXISTS purchase_cache_old")
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_cache'")
            if cursor.fetchone():
                conn.execute("ALTER TABLE sale_cache RENAME TO sale_cache_old")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_cache'")
            if cursor.fetchone():
                conn.execute("ALTER TABLE purchase_cache RENAME TO purchase_cache_old")
            
            conn.execute("ALTER TABLE sale_cache_new RENAME TO sale_cache")
            conn.execute("ALTER TABLE purchase_cache_new RENAME TO purchase_cache")
            conn.execute("DROP TABLE IF EXISTS sale_cache_old")
            conn.execute("DROP TABLE IF EXISTS purchase_cache_old")
            conn.commit()
            try:
                conn.execute("VACUUM")
            except:
                pass
        except Exception as swap_ex:
            conn.rollback()
            raise swap_ex
        finally:
            conn.close()
        
        _sync_progress = {"status": "idle", "percent": 100, "message": "Sync complete!"}
        gc.collect()
        return total_keys > 0
    except Exception as e:
        _sync_progress = {"status": "idle", "percent": 0, "message": f"Sync failed: {str(e)}"}
        print(f"[CACHE SYNC ERROR] Global sheet load failed: {str(e)}", flush=True)
        traceback.print_exc()
        try:
            conn.close()
        except:
            pass
        return False

def get_cache_db_connection():
    conn = sqlite3.connect(_CACHE_DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except:
        pass
    return conn

def _load_cache_safely(force_sync=False):
    global _is_cache_loading
    if _is_cache_loading:
        return
    try:
        _is_cache_loading = True
        
        # Check if database already exists on disk and has records
        has_existing_cache = False
        if os.path.exists(_CACHE_DB_PATH):
            try:
                conn = get_cache_db_connection()
                count = conn.execute("SELECT COUNT(*) FROM sale_cache").fetchone()[0]
                conn.close()
                if count > 0:
                    print(f"[CACHE SYNC] Found existing SQLite cache on disk with {count} keys. Marking loaded immediately.", flush=True)
                    _cache_loaded_event.set()
                    has_existing_cache = True
            except Exception as check_err:
                print(f"[CACHE SYNC] Error checking existing cache: {str(check_err)}", flush=True)
                
        # Only download from Google Sheets if cache does not exist or if force_sync is True
        if not has_existing_cache or force_sync:
            print("[CACHE SYNC] Starting background sync from Google Sheets...", flush=True)
            success = _fetch_and_store_google_sheet_to_sqlite()
            if success:
                _cache_loaded_event.set()
                # Count keys in DB
                try:
                    conn = sqlite3.connect(_CACHE_DB_PATH)
                    count = conn.execute("SELECT COUNT(*) FROM sale_cache").fetchone()[0]
                    conn.close()
                    print(f"[CACHE SYNC SUCCESS] SQLite cache updated with {count} keys.", flush=True)
                except:
                    print("[CACHE SYNC SUCCESS] SQLite cache updated.", flush=True)
            else:
                print("[CACHE SYNC WARNING] Failed to load data, keeping previous cache.", flush=True)
                if has_existing_cache:
                    _cache_loaded_event.set()
        else:
            print("[CACHE SYNC] Using existing cache on disk. Skipping Google Sheets download.", flush=True)
    except Exception as e:
        print(f"[CACHE SYNC ERROR] {str(e)}", flush=True)
        traceback.print_exc()
        if has_existing_cache:
            _cache_loaded_event.set()
    finally:
        _is_cache_loading = False

def _background_cache_loader_loop():
    _load_cache_safely()
    while True:
        time.sleep(43200)  # Refresh every 12 hours (43200 seconds) to save CPU/RAM on Render
        _load_cache_safely(force_sync=True)

_last_user_activity = time.time()

def _auto_cleanup_idle_loop():
    global _last_user_activity
    while True:
        time.sleep(300)  # Check every 5 minutes
        idle_seconds = time.time() - _last_user_activity
        if idle_seconds >= 10800:  # 3 hours of inactivity (180 minutes)
            try:
                conn = get_cache_db_connection()
                conn.execute("DELETE FROM sale_cache WHERE sheet_name IN ('NOT_FOUND', 'unmapped')")
                conn.execute("DELETE FROM purchase_cache WHERE sheet_name IN ('NOT_FOUND', 'unmapped')")
                conn.commit()
                conn.close()
                print("[AUTO CLEANUP] Cleared dummy/unmapped cache after 3 hours of inactivity.", flush=True)
            except Exception as ex:
                pass

_cache_loader_started = False
_cache_loader_lock = threading.Lock()

def start_background_cache_loader():
    global _cache_loader_started
    # Disabled background loader to run stateless lookups directly from Google Sheets Web App.
    _cache_loader_started = True
    _cache_loaded_event.set()
    return

_gviz_metadata = {
    '2025-26': {
        'spreadsheet_id': '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To',
        'gid': '0'
    }
}
_gviz_metadata_lock = threading.Lock()

def get_gviz_metadata(fy):
    global _gviz_metadata
    if fy in _gviz_metadata:
        return _gviz_metadata[fy]
    
    with _gviz_metadata_lock:
        if fy in _gviz_metadata:
            return _gviz_metadata[fy]
            
        fy_urls = load_fy_settings()
        web_app_url = fy_urls.get(fy)
        if web_app_url and str(web_app_url).strip():
            try:
                sn_url = f"{str(web_app_url).strip()}?action=getSheetNames"
                r = requests.get(sn_url, timeout=30)
                if r.status_code == 200 and r.json().get("success"):
                    r_json = r.json()
                    sheets_info = r_json.get("sheets", [])
                    if sheets_info:
                        meta = {
                            'spreadsheet_id': r_json.get("spreadsheetId"),
                            'gid': str(sheets_info[0].get("gid", "0"))
                        }
                        _gviz_metadata[fy] = meta
                        return meta
            except Exception as e:
                print(f"[GVIZ METADATA ERROR] Failed to fetch metadata for {fy}: {e}", flush=True)
    return None

def query_gviz_lookup(fy, keys, is_sale=True):
    import urllib.parse
    import csv
    import io
    
    meta = get_gviz_metadata(fy)
    if not meta:
        return {}
        
    spreadsheet_id = meta.get('spreadsheet_id')
    gid = meta.get('gid')
    if not spreadsheet_id or not gid:
        return {}
        
    mapping = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # E is Seller Name, AA is SALE UNIQUE ID, AB is Quantity, AC is Rate, AL is State
    # AP is Seller Name, BH is PURCHASE UNIQUE ID, BI is Quantity, BJ is Rate
    select_cols = "E, AA, AB, AC, AL" if is_sale else "AP, BH, BI, BJ"
    
    query = f"SELECT {select_cols}"
    encoded_query = urllib.parse.quote(query)
    
    gviz_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&gid={gid}&tq={encoded_query}"
    try:
        print(f"[GVIZ LOOKUP] Downloading columns for {fy}...", flush=True)
        res = requests.get(gviz_url, headers=headers, timeout=90)
        if res.status_code == 200:
            csv_data = res.text
            reader = csv.reader(io.StringIO(csv_data))
            rows = list(reader)
            
            norm_search_keys = {str(k).strip().upper(): k for k in keys if k}
            
            if len(rows) > 1:
                for row_idx, row in enumerate(rows):
                    if row_idx == 0:
                        continue # skip header
                    if is_sale:
                        if len(row) >= 5:
                            seller, key_val, qty, rate, state = row[0], row[1], row[2], row[3], row[4]
                            norm_key = key_val.strip().upper()
                            if norm_key in norm_search_keys:
                                orig_key = norm_search_keys[norm_key]
                                mapping[orig_key] = {
                                    "qty": float(qty) if qty else 0.0,
                                    "rate": float(rate) if rate else 0.0,
                                    "state": state,
                                    "sellerName": seller
                                }
                    else:
                        if len(row) >= 4:
                            seller, key_val, qty, rate = row[0], row[1], row[2], row[3]
                            norm_key = key_val.strip().upper()
                            if norm_key in norm_search_keys:
                                orig_key = norm_search_keys[norm_key]
                                mapping[orig_key] = {
                                    "qty": float(qty) if qty else 0.0,
                                    "rate": float(rate) if rate else 0.0,
                                    "state": "",
                                    "sellerName": seller
                                }
    except Exception as e:
        print(f"[GVIZ LOOKUP ERROR] Failed querying {fy}: {e}", flush=True)
        
    return mapping

@app.route('/api/lookup-sale-quantities', methods=['POST', 'OPTIONS'])
def lookup_sale_quantities():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    global _last_user_activity
    try:
        _last_user_activity = time.time()
        
        print("[LOOKUP] Received lookup request!", flush=True)
        req_data = request.get_json(force=True, silent=True) or {}
        keys = req_data.get('keys', [])
        print(f"[LOOKUP] Keys count: {len(keys)}", flush=True)
        if not keys or not isinstance(keys, list):
            response = jsonify({"status": "Error", "message": "Invalid keys format"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400

        mapping = {}

        # 1. Search in local 'sale' table (active session uploaded data)
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in keys])
            query = f"SELECT sale_unique_id, calc_qty, quantity, calc_cost, item_cost, state_code_short, warehouse_name FROM sale WHERE UPPER(sale_unique_id) IN ({placeholders})"
            cursor.execute(query, [str(k).strip().upper() for k in keys])
            sale_rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            for row in sale_rows:
                uid = row.get('sale_unique_id')
                if uid:
                    uid_str = str(uid).strip().upper()
                    for orig_key in keys:
                        if str(orig_key).strip().upper() == uid_str:
                            mapping[orig_key] = {
                                "qty": row.get('calc_qty', row.get('quantity', 0)),
                                "rate": row.get('calc_cost', row.get('item_cost', 0)),
                                "state": row.get('state_code_short', ''),
                                "sellerName": row.get('warehouse_name', '')
                            }
                            break
        except Exception as e:
            print(f"[LOOKUP] Local query error: {str(e)}", flush=True)

        # 2. Query remaining unmapped keys directly from Google Sheets Web App
        unmapped_keys = [k for k in keys if k not in mapping or not (mapping[k].get('qty') or mapping[k].get('rate'))]
        if unmapped_keys:
            fy_urls = load_fy_settings()
            
            # Group keys by targeted FY based on prefix
            keys_by_fy = {}
            for k in unmapped_keys:
                k_upper = str(k).strip().upper()
                target_fy = None
                if "27" in k_upper[:10]:
                    target_fy = "2026-27"
                elif "26" in k_upper[:10]:
                    target_fy = "2025-26"
                
                if target_fy and target_fy in fy_urls and fy_urls[target_fy]:
                    keys_by_fy.setdefault(target_fy, []).append(k)
                else:
                    for fy in fy_urls:
                        keys_by_fy.setdefault(fy, []).append(k)

            for fy, fy_keys in keys_by_fy.items():
                if fy_keys:
                    try:
                        res_mapping = query_gviz_lookup(fy, fy_keys, is_sale=True)
                        for k, v in res_mapping.items():
                            norm_k = str(k).strip().upper()
                            for orig_key in keys:
                                if str(orig_key).strip().upper() == norm_k:
                                    mapping[orig_key] = v
                                    break
                    except Exception as fallback_err:
                        print(f"[LOOKUP DIRECT ERROR] Failed querying Web App for FY {fy}: {str(fallback_err)}", flush=True)

        print(f"[LOOKUP] Found {len(mapping)} matches out of {len(keys)} keys.", flush=True)
        response = jsonify({"status": "Success", "mapping": mapping})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    except Exception as e:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500
@app.route('/api/force-refresh-cache', methods=['POST', 'GET', 'OPTIONS'])
def force_refresh_cache():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        return response

    global _is_cache_loading
    if _is_cache_loading:
        response = jsonify({
            "status": "Success",
            "message": "Cache refresh is already in progress. Please wait."
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response

    try:
        print("[FORCE REFRESH] Clearing old negative cache and re-fetching fresh data from Google Sheets...", flush=True)
        try:
            conn = sqlite3.connect(_CACHE_DB_PATH)
            conn.execute("DELETE FROM sale_cache WHERE sheet_name IN ('NOT_FOUND', 'unmapped')")
            conn.execute("DELETE FROM purchase_cache WHERE sheet_name IN ('NOT_FOUND', 'unmapped')")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FORCE REFRESH] Error clearing old cache: {str(e)}", flush=True)

        # Run synchronously since it has been optimized to complete in a few seconds
        _load_cache_safely(force_sync=True)
        
        count = 0
        try:
            conn = sqlite3.connect(_CACHE_DB_PATH)
            count = conn.execute("SELECT COUNT(*) FROM sale_cache WHERE sheet_name NOT IN ('NOT_FOUND', 'unmapped')").fetchone()[0]
            conn.close()
        except Exception as c_err:
            pass

        _last_user_activity = time.time()
        response = jsonify({
            "status": "Success",
            "message": f"Fresh Sale & Purchase data synced successfully ({count:,} records loaded).",
            "count": count
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    except Exception as err:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(err)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@app.route('/api/sync-progress', methods=['GET', 'OPTIONS'])
def sync_progress():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    response = jsonify(_sync_progress)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route('/api/view-cache', methods=['GET', 'OPTIONS'])
def view_cache():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response

    sale_count = 0
    purchase_count = 0
    sample_sales = []

    try:
        conn = get_cache_db_connection()
        sale_count = conn.execute("SELECT COUNT(*) FROM sale_cache WHERE sheet_name NOT IN ('NOT_FOUND', 'unmapped')").fetchone()[0]
        purchase_count = conn.execute("SELECT COUNT(*) FROM purchase_cache WHERE sheet_name NOT IN ('NOT_FOUND', 'unmapped')").fetchone()[0]
        
        sample_rows = conn.execute("SELECT key, qty, rate, state, seller_name FROM sale_cache WHERE sheet_name NOT IN ('NOT_FOUND', 'unmapped') LIMIT 5").fetchall()
        for r in sample_rows:
            sample_sales.append({"key": r[0], "qty": r[1], "rate": r[2], "state": r[3], "sellerName": r[4]})
        conn.close()
    except Exception as e:
        print("[VIEW CACHE ERROR]", str(e))

    idle_mins = round((time.time() - _last_user_activity) / 60, 1)

    response = jsonify({
        "status": "Success",
        "saleRecords": sale_count,
        "purchaseRecords": purchase_count,
        "totalRecords": sale_count + purchase_count,
        "idleMinutes": idle_mins,
        "autoCleanupPolicy": "Removes temporary unmapped data after 3 hours inactivity",
        "sampleSales": sample_sales
    })
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@app.route('/api/lookup-purchase-quantities', methods=['POST', 'OPTIONS'])
def lookup_purchase_quantities():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    try:
        print("[LOOKUP PURCHASE] Received lookup request!", flush=True)
        req_data = request.get_json(force=True, silent=True) or {}
        keys = req_data.get('keys', [])
        print(f"[LOOKUP PURCHASE] Keys count: {len(keys)}", flush=True)
        if not keys or not isinstance(keys, list):
            response = jsonify({"status": "Error", "message": "Invalid keys format"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400

        mapping = {}

        # 1. Search in local 'purchase' table (active session uploaded data)
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in keys])
            query = f"SELECT purchase_unique_id, calc_qty, quantity, calc_cost, item_cost, warehouse_name FROM purchase WHERE UPPER(purchase_unique_id) IN ({placeholders})"
            cursor.execute(query, [str(k).strip().upper() for k in keys])
            purchase_rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            for row in purchase_rows:
                uid = row.get('purchase_unique_id')
                if uid:
                    uid_str = str(uid).strip().upper()
                    for orig_key in keys:
                        if str(orig_key).strip().upper() == uid_str:
                            mapping[orig_key] = {
                                "qty": row.get('calc_qty', row.get('quantity', 0)),
                                "rate": row.get('calc_cost', row.get('item_cost', 0)),
                                "state": "",
                                "sellerName": row.get('warehouse_name', '')
                            }
                            break
        except Exception as e:
            print(f"[LOOKUP PURCHASE] Local query error: {str(e)}", flush=True)

        # 2. Query remaining unmapped keys directly from Google Sheets Web App
        unmapped_keys = [k for k in keys if k not in mapping or not (mapping[k].get('qty') or mapping[k].get('rate'))]
        if unmapped_keys:
            fy_urls = load_fy_settings()
            
            # Group keys by targeted FY based on prefix
            keys_by_fy = {}
            for k in unmapped_keys:
                k_upper = str(k).strip().upper()
                target_fy = None
                if "27" in k_upper[:10]:
                    target_fy = "2026-27"
                elif "26" in k_upper[:10]:
                    target_fy = "2025-26"
                
                if target_fy and target_fy in fy_urls and fy_urls[target_fy]:
                    keys_by_fy.setdefault(target_fy, []).append(k)
                else:
                    for fy in fy_urls:
                        keys_by_fy.setdefault(fy, []).append(k)

            for fy, fy_keys in keys_by_fy.items():
                if fy_keys:
                    try:
                        res_mapping = query_gviz_lookup(fy, fy_keys, is_sale=False)
                        for k, v in res_mapping.items():
                            norm_k = str(k).strip().upper()
                            for orig_key in keys:
                                if str(orig_key).strip().upper() == norm_k:
                                    mapping[orig_key] = v
                                    break
                    except Exception as fallback_err:
                        print(f"[LOOKUP PURCHASE DIRECT ERROR] Failed querying Web App for FY {fy}: {str(fallback_err)}", flush=True)

        print(f"[LOOKUP PURCHASE] Found {len(mapping)} matches out of {len(keys)} keys.", flush=True)
        response = jsonify({"status": "Success", "mapping": mapping})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    except Exception as e:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500

@app.route('/api/get-available-sheets', methods=['GET', 'OPTIONS'])
def get_available_sheets():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
        return response

    try:
        # Lazy start of background loader
        _init_cache_db()
        start_background_cache_loader()
        
        # Wait up to 10s if cache is loading
        if not _cache_loaded_event.is_set():
            _cache_loaded_event.wait(timeout=10)

        conn = sqlite3.connect(_CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sheet_name FROM sale_cache WHERE sheet_name IS NOT NULL AND sheet_name != ''")
        sales_sheets = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT sheet_name FROM purchase_cache WHERE sheet_name IS NOT NULL AND sheet_name != ''")
        purchases_sheets = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        all_sheets = list(set(sales_sheets + purchases_sheets))
        
        import re
        years = []
        for s in all_sheets:
            m = re.search(r'\d{4}-\d{2}', s)
            if m:
                years.append(m.group(0))
                
        fy_urls = load_fy_settings()
        configured_years = list(fy_urls.keys())
        years = sorted(list(set(years + configured_years)))
        if not years:
            years = ["2025-26", "2026-27"] # Fallbacks if empty

            
        response = jsonify({
            "status": "Success",
            "sheets": all_sheets,
            "years": years
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response

    except Exception as e:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@app.route('/api/export-returns', methods=['POST', 'OPTIONS'])
def export_returns():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    try:
        start_background_cache_loader()
        
        req_data = request.get_json(force=True, silent=True) or {}
        platform = req_data.get('platform', '').strip().upper()
        year = req_data.get('year', 'ALL').strip() # 'ALL' or '2025-26', '2026-27', etc.
        data_type = req_data.get('dataType', 'ALL').strip().upper() # 'ALL', 'SALE', 'PURCHASE'
        
        def matches_platform(plat, key, seller_name, row_type=""):
            if not plat or plat == 'ALL':
                return True
            plat = plat.upper()
            key = (key or '').upper()
            seller_name = (seller_name or '').upper()
            row_type = (row_type or '').upper()
            
            if plat == 'AJIO':
                # Exclude Myntra and Flipkart specific prefixes
                if key.startswith('MY') or key.startswith('FK'):
                    return False
                if key.startswith('AJ') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'AJIO' in key or 'AJIO' in seller_name or 'AJ' in seller_name:
                    return True
            elif plat == 'MYNTRA':
                # Exclude Ajio and Flipkart specific prefixes
                if key.startswith('AJ') or key.startswith('FK'):
                    return False
                if key.startswith('MY') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'MYNTRA' in key or 'MYNTRA' in seller_name or 'MY' in seller_name:
                    return True
            elif plat == 'FLIPKART':
                # Exclude Ajio and Myntra specific prefixes
                if key.startswith('AJ') or key.startswith('MY'):
                    return False
                if key.startswith('FK') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'FLIPKART' in key or 'FLIPKART' in seller_name or 'FK' in seller_name:
                    return True
            return False

        if not _cache_loaded_event.is_set():
            _cache_loaded_event.wait(timeout=120)

        conn = sqlite3.connect(_CACHE_DB_PATH)
        
        # Build query for sales
        sale_query = """
            SELECT 
                key, qty, rate, state, seller_name, sheet_name,
                invoice_no, invoice_date, warehouse_code, gst_no,
                order_id, item_asin, item_sku, item_name, hsn_number,
                invoice_val, reason, zoho_status, invoice_id,
                gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
            FROM sale_cache
        """
        params = []
        conditions = []
        if year != 'ALL':
            conditions.append("sheet_name LIKE ?")
            params.append(f"%{year}%")
        if conditions:
            sale_query += " WHERE " + " AND ".join(conditions)
        
        sale_results = conn.execute(sale_query, params).fetchall()
        
        # Build query for purchases
        purchase_query = """
            SELECT 
                key, qty, rate, seller_name, sheet_name,
                invoice_no, warehouse_code, gst_no, order_id,
                item_asin, item_sku, item_name, hsn_number,
                invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
            FROM purchase_cache
        """
        pur_params = []
        pur_conditions = []
        if year != 'ALL':
            pur_conditions.append("sheet_name LIKE ?")
            pur_params.append(f"%{year}%")
        if pur_conditions:
            purchase_query += " WHERE " + " AND ".join(pur_conditions)
            
        purchase_results = conn.execute(purchase_query, pur_params).fetchall()
        conn.close()
        
        # Format database records to match the expected Excel schema
        sale_rows = []
        for row in sale_results:
            db_key, db_qty, db_rate, db_state, db_seller_name, db_sheet = row[0:6]
            (
                invoice_no, invoice_date, warehouse_code, gst_no,
                order_id, item_asin, item_sku, item_name, hsn_number,
                invoice_val, reason, zoho_status, invoice_id,
                gross_val, igst_val, cgst_val, sgst_val, igst_amt_val, cgst_amt_val, sgst_amt_val
            ) = row[6:]
            
            if not matches_platform(platform, db_key, db_seller_name):
                continue
            
            sale_rows.append({
                'no': len(sale_rows) + 1,
                'invoice_no': invoice_no,
                'type': platform,
                'invoice_date': invoice_date,
                'warehouse_name': db_seller_name,
                'warehouse_code': warehouse_code,
                'gst_no': gst_no,
                'order_id': order_id,
                'item_asin': item_asin,
                'item_sku': item_sku,
                'item_name': item_name,
                'hsn_number': hsn_number,
                'quantity': db_qty,
                'item_cost': db_rate,
                'gross': gross_val,
                'igst': igst_val, 'cgst': cgst_val, 'sgst': sgst_val,
                'igst_amt': igst_amt_val, 'cgst_amt': cgst_amt_val, 'sgst_amt': sgst_amt_val,
                'invoice': invoice_val,
                'reason': reason,
                'zoho_status': zoho_status,
                'invoice_id': invoice_id,
                'state_code': db_state,
                'sale_unique_id': db_key,
                'calc_qty': db_qty,
                'calc_cost': db_rate,
                'calc_gross': gross_val if gross_val is not None else round(db_qty * db_rate, 2),
                'calc_igst': igst_val or 0, 
                'calc_cgst': cgst_val or 0, 
                'calc_sgst': sgst_val or 0,
                'calc_igst_amt': igst_amt_val or 0, 
                'calc_cgst_amt': cgst_amt_val or 0, 
                'calc_sgst_amt': sgst_amt_val or 0,
                'calc_invoice': round((gross_val or 0) + (igst_amt_val or 0) + (cgst_amt_val or 0) + (sgst_amt_val or 0), 2) if gross_val is not None else round(db_qty * db_rate, 2),
                'state_code_short': f"({db_state})" if db_state else "",
                'sheet_name': db_sheet
            })
            
        purchase_rows = []
        for row in purchase_results:
            db_key, db_qty, db_rate, db_seller_name, db_sheet = row[0:5]
            (
                invoice_no, warehouse_code, gst_no, order_id,
                item_asin, item_sku, item_name, hsn_number,
                invoice_val,
                gross_val, igst_val, cgst_val, sgst_val, igst_amt_val, cgst_amt_val, sgst_amt_val
            ) = row[5:]
            
            if not matches_platform(platform, db_key, db_seller_name):
                continue
                    
            purchase_rows.append({
                'no': len(purchase_rows) + 1,
                'invoice_no': invoice_no,
                'warehouse_name': db_seller_name,
                'warehouse_code': warehouse_code,
                'gst_no': gst_no,
                'order_id': order_id,
                'item_asin': item_asin,
                'item_sku': item_sku,
                'item_name': item_name,
                'hsn_number': hsn_number,
                'quantity': db_qty,
                'item_cost': db_rate,
                'gross': gross_val,
                'igst': igst_val, 'cgst': cgst_val, 'sgst': sgst_val,
                'igst_amt': igst_amt_val, 'cgst_amt': cgst_amt_val, 'sgst_amt': sgst_amt_val,
                'invoice': invoice_val,
                'purchase_unique_id': db_key,
                'calc_qty': db_qty,
                'calc_cost': db_rate,
                'calc_gross': round(db_qty * db_rate, 2),
                'calc_igst': 0, 'calc_cgst': 0, 'calc_sgst': 0,
                'calc_igst_amt': 0, 'calc_cgst_amt': 0, 'calc_sgst_amt': 0,
                'calc_total_amt': round(db_qty * db_rate, 2),
                'sheet_name': db_sheet
            })

        # Merge with locally uploaded data from SQLite
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sale")
            local_sales = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT * FROM purchase")
            local_purchases = [dict(r) for r in cursor.fetchall()]
            conn.close()
            
            for row in local_sales:
                db_sheet = row.get('sheet_name', get_financial_year())
                if year != 'ALL' and year not in db_sheet:
                    continue
                if not matches_platform(platform, row.get('sale_unique_id', ''), row.get('warehouse_name', ''), row.get('type', '')):
                    continue
                row['sheet_name'] = db_sheet
                row['no'] = len(sale_rows) + 1
                sale_rows.append(row)
                
            for row in local_purchases:
                db_sheet = row.get('sheet_name', get_financial_year())
                if year != 'ALL' and year not in db_sheet:
                    continue
                if not matches_platform(platform, row.get('purchase_unique_id', ''), row.get('warehouse_name', '')):
                    continue
                row['sheet_name'] = db_sheet
                row['no'] = len(purchase_rows) + 1
                purchase_rows.append(row)
        except Exception:
            pass

        # Organize by sheet/year dynamically based on matched sheets
        sheets_data = {}
        
        # Helper to extract year suffix
        import re
        def get_year_key(sh):
            m = re.search(r'\d{4}-\d{2}', sh)
            return m.group(0) if m else sh

        # Find all distinct years in results to construct keys
        found_years = set()
        for r in sale_rows:
            found_years.add(get_year_key(r.get('sheet_name', '')))
        for r in purchase_rows:
            found_years.add(get_year_key(r.get('sheet_name', '')))
            
        for y_key in found_years:
            if y_key:
                sheets_data[y_key] = { 'sale': [], 'purchase': [] }
                
        # If no years found, make sure we have current year as default
        if not sheets_data:
            sheets_data[get_financial_year()] = { 'sale': [], 'purchase': [] }
            
        for row in sale_rows:
            y_key = get_year_key(row.get('sheet_name', ''))
            if y_key in sheets_data:
                sheets_data[y_key]['sale'].append(row)
            else:
                # Default fallback
                first_key = list(sheets_data.keys())[0]
                sheets_data[first_key]['sale'].append(row)
                
        for row in purchase_rows:
            y_key = get_year_key(row.get('sheet_name', ''))
            if y_key in sheets_data:
                sheets_data[y_key]['purchase'].append(row)
            else:
                first_key = list(sheets_data.keys())[0]
                sheets_data[first_key]['purchase'].append(row)
                
        # Re-index row 'no' within each sheet
        for yr in sheets_data:
            for i, row in enumerate(sheets_data[yr]['sale']):
                row['no'] = i + 1
            for i, row in enumerate(sheets_data[yr]['purchase']):
                row['no'] = i + 1

        response = jsonify({
            "status": "Success",
            "data": sheets_data
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    except Exception as e:
        traceback.print_exc()
        response = jsonify({"status": "Error", "message": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500


@app.route('/api/export-returns-file', methods=['POST', 'OPTIONS'])
def export_returns_file():
    if request.method == 'OPTIONS':
        response = jsonify({"status": "Success"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    try:
        start_background_cache_loader()
        if not _cache_loaded_event.is_set():
            _cache_loaded_event.wait(timeout=120)
        req_data = request.get_json(force=True, silent=True) or {}
        platform = req_data.get('platform', '').strip().upper()
        year = req_data.get('year', 'ALL').strip()
        data_type = req_data.get('dataType', 'ALL').strip().upper()
        
        _init_cache_db()
        conn = sqlite3.connect(_CACHE_DB_PATH)
        fy_urls = load_fy_settings()
        configured_years = list(fy_urls.keys())
        
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT sheet_name FROM sale_cache UNION SELECT DISTINCT sheet_name FROM purchase_cache")

        cached_sheets = [r[0] for r in cursor.fetchall() if r[0]]
        
        import re
        import csv
        import zipfile
        db_years = []
        for s in cached_sheets:
            m = re.search(r'\d{4}-\d{2}', s)
            if m:
                db_years.append(m.group(0))
        
        all_avail_years = sorted(list(set(configured_years + db_years)))
        if not all_avail_years:
            all_avail_years = ["2025-26", "2026-27"]
            
        years_to_process = all_avail_years if year == 'ALL' else [year]
        
        sale_headers = [
            'No.', 'Invoice No', 'TYPE', 'Invoice Date', 'Warehouse Name',
            'Warehouse Code', 'GST No', 'Order ID', 'Item Asin', 'Item SKU',
            'Item Name', 'HSN Number', 'Quantity', 'Item Cost', 'Gross',
            'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
            'Invoice', 'Reason', 'Zoho Status', 'invoice id', 'State Code',
            'SALE UNIQUE ID', 'Quantity', 'Item Cost', 'Gross',
            'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
            'Invoice', 'STATE CODE'
        ]
        
        purchase_headers = [
            'No.', 'Invoice No', 'Warehouse Name', 'Warehouse Code', 'GST No',
            'Order ID', 'Item Asin', 'Item SKU', 'Item Name', 'HSN Number',
            'Quantity', 'Item cost', 'Gross', 'IGST', 'CGST', 'SGST',
            'IGST Amt', 'CGST Amt', 'SGST Amt', 'Invoice',
            'PURCHASE UNIQUE ID', 'Quantity', 'Item cost', 'Gross',
            'IGST', 'CGST', 'SGST', 'IGST Amt', 'CGST Amt', 'SGST Amt',
            'Total Amt'
        ]

        def matches_platform(plat, key, seller_name):
            if not plat or plat == 'ALL':
                return True
            plat = plat.upper()
            key = (key or '').upper()
            seller_name = (seller_name or '').upper()
            if plat == 'AJIO':
                if key.startswith('MY') or key.startswith('FK'):
                    return False
                if key.startswith('AJ') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'AJIO' in key or 'AJIO' in seller_name or 'AJ' in seller_name:
                    return True
            elif plat == 'MYNTRA':
                if key.startswith('AJ') or key.startswith('FK'):
                    return False
                if key.startswith('MY') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'MYNTRA' in key or 'MYNTRA' in seller_name or 'MY' in seller_name:
                    return True
            elif plat == 'FLIPKART':
                if key.startswith('AJ') or key.startswith('MY'):
                    return False
                if key.startswith('FK') or key.startswith('CG') or key.startswith('PG'):
                    return True
                if 'FLIPKART' in key or 'FLIPKART' in seller_name or 'FK' in seller_name:
                    return True
            return False

        def parse_key_components(k):
            inv_no, ord_id, asin, sku = "", "", "", ""
            if k:
                parts = str(k).strip().split('-')
                if len(parts) >= 4:
                    if len(parts[0]) <= 10 and len(parts[1]) <= 10 and parts[1].isdigit():
                        inv_no = f"{parts[0]}-{parts[1]}"
                        ord_id = parts[2]
                        asin = parts[3]
                        sku = "-".join(parts[4:]) if len(parts) > 4 else ""
                    else:
                        inv_no = parts[0]
                        ord_id = parts[1]
                        asin = parts[2]
                        sku = "-".join(parts[3:])
                elif len(parts) == 3:
                    inv_no = parts[0]
                    ord_id = parts[1]
                    asin = parts[2]
                else:
                    inv_no = str(k)
            return inv_no, ord_id, asin, sku

        generated_files = [] # List of tuples: (filename, csv_bytes)

        for yr in years_to_process:
            # Determine active sale and purchase tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_cache'")
            has_sale_cache = bool(cursor.fetchone())
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_cache_new'")
            has_sale_cache_new = bool(cursor.fetchone())
            
            sale_tbl = 'sale_cache'
            if not has_sale_cache and has_sale_cache_new:
                sale_tbl = 'sale_cache_new'
            elif has_sale_cache and has_sale_cache_new:
                cursor.execute("SELECT COUNT(*) FROM sale_cache")
                if cursor.fetchone()[0] == 0:
                    sale_tbl = 'sale_cache_new'

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_cache'")
            has_pur_cache = bool(cursor.fetchone())
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchase_cache_new'")
            has_pur_cache_new = bool(cursor.fetchone())

            purchase_tbl = 'purchase_cache'
            if not has_pur_cache and has_pur_cache_new:
                purchase_tbl = 'purchase_cache_new'
            elif has_pur_cache and has_pur_cache_new:
                cursor.execute("SELECT COUNT(*) FROM purchase_cache")
                if cursor.fetchone()[0] == 0:
                    purchase_tbl = 'purchase_cache_new'

            # Inspect available columns in active tables
            cursor.execute(f"PRAGMA table_info({sale_tbl})")
            has_detailed_sale = any(col[1] == 'invoice_no' for col in cursor.fetchall())

            cursor.execute(f"PRAGMA table_info({purchase_tbl})")
            has_detailed_pur = any(col[1] == 'invoice_no' for col in cursor.fetchall())

            # Fetch sales
            sale_rows = []
            if data_type in ('ALL', 'SALE'):
                if has_detailed_sale:
                    cursor.execute(f"""
                        SELECT key, qty, rate, state, seller_name, sheet_name,
                               invoice_no, invoice_date, warehouse_code, gst_no,
                               order_id, item_asin, item_sku, item_name, hsn_number,
                               invoice_val, reason, zoho_status, invoice_id,
                               gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                        FROM {sale_tbl} WHERE sheet_name LIKE ?
                    """, (f"%{yr}%",))
                    for s_row in cursor.fetchall():
                        k, qty, rate, state, seller_name = s_row[0:5]
                        sheet_n = s_row[5]
                        (
                            inv_no, inv_date, wh_code, gst_no, ord_id, asin, sku, item_name, hsn,
                            inv_val, reason, zoho_stat, inv_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                        ) = s_row[6:]
                        if matches_platform(platform, k, seller_name):
                            sale_rows.append((
                                k, qty, rate, state, seller_name, sheet_n,
                                inv_no, inv_date, wh_code, gst_no, ord_id, asin, sku, item_name, hsn,
                                inv_val, reason, zoho_stat, inv_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                            ))
                else:
                    cursor.execute(f"""
                        SELECT key, qty, rate, state, seller_name, sheet_name
                        FROM {sale_tbl} WHERE sheet_name LIKE ?
                    """, (f"%{yr}%",))
                    for s_row in cursor.fetchall():
                        k, qty, rate, state, seller_name, sheet_n = s_row
                        if matches_platform(platform, k, seller_name):
                            sale_rows.append((
                                k, qty, rate, state, seller_name, sheet_n,
                                "", "", "", "", "", "", "", "", "",
                                None, "", "", "", None, 0, 0, 0, 0, 0, 0
                            ))
                        
            # Fetch purchases
            purchase_rows = []
            if data_type in ('ALL', 'PURCHASE'):
                if has_detailed_pur:
                    cursor.execute(f"""
                        SELECT key, qty, rate, seller_name, sheet_name,
                               invoice_no, warehouse_code, gst_no, order_id,
                               item_asin, item_sku, item_name, hsn_number,
                               invoice_val, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                        FROM {purchase_tbl} WHERE sheet_name LIKE ?
                    """, (f"%{yr}%",))
                    for p_row in cursor.fetchall():
                        pk, pqty, prate, pseller_name, psheet_n = p_row[0:5]
                        (
                            pinv_no, pwh_code, pgst_no, pord_id, pasin, psku, pitem_name, phsn,
                            pinv_val, pgross, pigst, pcgst, psgst, pigst_amt, pcgst_amt, psgst_amt
                        ) = p_row[5:]
                        if matches_platform(platform, pk, pseller_name):
                            purchase_rows.append((
                                pk, pqty, prate, pseller_name, psheet_n,
                                pinv_no, pwh_code, pgst_no, pord_id, pasin, psku, pitem_name, phsn,
                                pinv_val, pgross, pigst, pcgst, psgst, pigst_amt, pcgst_amt, psgst_amt
                            ))
                else:
                    cursor.execute(f"""
                        SELECT key, qty, rate, seller_name, sheet_name
                        FROM {purchase_tbl} WHERE sheet_name LIKE ?
                    """, (f"%{yr}%",))
                    for p_row in cursor.fetchall():
                        pk, pqty, prate, pseller_name, psheet_n = p_row
                        if matches_platform(platform, pk, pseller_name):
                            purchase_rows.append((
                                pk, pqty, prate, pseller_name, psheet_n,
                                "", "", "", "", "", "", "", "",
                                None, None, 0, 0, 0, 0, 0, 0
                            ))

            # Generate CSV content for this year
            csv_io = io.StringIO()
            writer = csv.writer(csv_io)
            
            header_row = []
            if data_type == 'ALL':
                header_row = sale_headers + purchase_headers
            elif data_type == 'SALE':
                header_row = sale_headers
            else:
                header_row = purchase_headers
            writer.writerow(header_row)
            
            max_len = max(len(sale_rows), len(purchase_rows)) if data_type == 'ALL' else (len(sale_rows) if data_type == 'SALE' else len(purchase_rows))
            
            for idx in range(max_len):
                row_vals = []
                if data_type in ('ALL', 'SALE'):
                    if idx < len(sale_rows):
                        sr = sale_rows[idx]
                        (
                            k, qty, rate, state, seller_name, sheet_n,
                            inv_no, inv_date, wh_code, gst_no, ord_id, asin, sku, item_name, hsn,
                            inv_val, reason, zoho_stat, inv_id, gross, igst, cgst, sgst, igst_amt, cgst_amt, sgst_amt
                        ) = sr
                        p_inv_no, p_ord_id, p_asin, p_sku = parse_key_components(k)
                        final_inv_no = inv_no if inv_no else p_inv_no
                        final_ord_id = ord_id if ord_id else p_ord_id
                        final_asin = asin if asin else p_asin
                        final_sku = sku if sku else p_sku
                        gross_calc = gross if (gross is not None and gross != 0) else round((qty or 0) * (rate or 0), 2)
                        inv_calc = inv_val if (inv_val is not None and inv_val != 0) else round(gross_calc + (igst_amt or 0) + (cgst_amt or 0) + (sgst_amt or 0), 2)
                        st_short = f"({state})" if state else ""

                        row_vals.extend([
                            idx + 1, final_inv_no, platform, inv_date or '', seller_name or '', wh_code or '', gst_no or '', final_ord_id, final_asin, final_sku,
                            item_name or final_sku, hsn or '', qty or 0, rate or 0, gross_calc, igst or 0, cgst or 0, sgst or 0, igst_amt or 0, cgst_amt or 0, sgst_amt or 0,
                            inv_calc, reason or '', zoho_stat or '', inv_id or '', state or '',
                            k, qty or 0, rate or 0, gross_calc, igst or 0, cgst or 0, sgst or 0, igst_amt or 0, cgst_amt or 0, sgst_amt or 0, inv_calc, st_short
                        ])
                    else:
                        row_vals.extend([''] * len(sale_headers))
                        
                if data_type in ('ALL', 'PURCHASE'):
                    if idx < len(purchase_rows):
                        pr = purchase_rows[idx]
                        (
                            pk, pqty, prate, pseller_name, psheet_n,
                            pinv_no, pwh_code, pgst_no, pord_id, pasin, psku, pitem_name, phsn,
                            pinv_val, pgross, pigst, pcgst, psgst, pigst_amt, pcgst_amt, psgst_amt
                        ) = pr
                        p_inv_no, p_ord_id, p_asin, p_sku = parse_key_components(pk)
                        final_pinv_no = pinv_no if pinv_no else p_inv_no
                        final_pord_id = pord_id if pord_id else p_ord_id
                        final_pasin = pasin if pasin else p_asin
                        final_psku = psku if psku else p_sku
                        pgross_calc = pgross if (pgross is not None and pgross != 0) else round((pqty or 0) * (prate or 0), 2)
                        pinv_calc = pinv_val if (pinv_val is not None and pinv_val != 0) else round(pgross_calc + (pigst_amt or 0) + (pcgst_amt or 0) + (psgst_amt or 0), 2)

                        row_vals.extend([
                            idx + 1, final_pinv_no, pseller_name or '', pwh_code or '', pgst_no or '', final_pord_id, final_pasin, final_psku, pitem_name or final_psku, phsn or '',
                            pqty or 0, prate or 0, pgross_calc, pigst or 0, pcgst or 0, psgst or 0, pigst_amt or 0, pcgst_amt or 0, psgst_amt or 0, pinv_calc,
                            pk, pqty or 0, prate or 0, pgross_calc, pigst or 0, pcgst or 0, psgst or 0, pigst_amt or 0, pcgst_amt or 0, psgst_amt or 0, pinv_calc
                        ])
                    else:
                        row_vals.extend([''] * len(purchase_headers))
                        
                writer.writerow(row_vals)
            
            csv_data = csv_io.getvalue().encode('utf-8')
            scope_str = 'both' if data_type == 'ALL' else (data_type.lower() + 's')
            filename = f"{platform or 'ALL'}_export_{yr}_{scope_str}_{datetime.now().strftime('%Y-%m-%d')}.csv"
            generated_files.append((filename, csv_data))

        conn.close()

        if len(generated_files) == 1:
            fn, data = generated_files[0]
            io_buf = io.BytesIO(data)
            res = send_file(
                io_buf,
                mimetype='text/csv',
                as_attachment=True,
                download_name=fn
            )
            res.headers.add("Access-Control-Allow-Origin", "*")
            res.headers.add("Access-Control-Expose-Headers", "Content-Disposition")
            return res
        else:
            zip_buf = io.BytesIO()
            scope_str = 'both' if data_type == 'ALL' else (data_type.lower() + 's')
            zip_filename = f"{platform or 'ALL'}_export_all_years_{scope_str}_{datetime.now().strftime('%Y-%m-%d')}.zip"
            
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for fn, data in generated_files:
                    zip_file.writestr(fn, data)
            
            zip_buf.seek(0)
            res = send_file(
                zip_buf,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            res.headers.add("Access-Control-Allow-Origin", "*")
            res.headers.add("Access-Control-Expose-Headers", "Content-Disposition")
            return res
    except Exception as e:
        traceback.print_exc()
        res = jsonify({"status": "Error", "message": str(e)})
        res.headers.add("Access-Control-Allow-Origin", "*")
        return res, 500


@app.route('/')
def index():

    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads, process data, merge with existing, deduplicate."""
    file_paths = {}
    try:
        print("\n[UPLOAD] 📥 4 Excel files received. Processing & Deduplicating...", flush=True)
        required_files = ['sale_details', 'sale_summary', 'purchase_details', 'purchase_summary']
        
        for file_key in required_files:
            if file_key not in request.files:
                print(f"[UPLOAD ERROR] ❌ Missing file: {file_key}", flush=True)
                return jsonify({'error': f'Missing file: {file_key}'}), 400
            
            file = request.files[file_key]
            if file.filename == '':
                print(f"[UPLOAD ERROR] ❌ No file selected for: {file_key}", flush=True)
                return jsonify({'error': f'No file selected for: {file_key}'}), 400
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'{file_key}_{file.filename}')
            file.save(filepath)
            file_paths[file_key] = filepath
            print(f"  -> Received {file_key}: {file.filename}", flush=True)
        
        # Process and save new uploaded files directly using streaming
        stats = process_and_save_streaming(file_paths)
        print(f"[UPLOAD SUCCESS] ✅ Sales: +{stats['sale_new']} new ({stats['sale_duplicates']} dups skipped) | Purchases: +{stats['purchase_new']} new ({stats['purchase_duplicates']} dups skipped)", flush=True)
        
        # Clean up uploaded files to save disk space
        for path in file_paths.values():
            try:
                os.remove(path)
            except Exception:
                pass
                
        # Force garbage collection to reclaim memory instantly
        gc.collect()
        
        # Return previews (first 100 rows)
        preview_sale = get_rows_as_dicts('sale', limit=100)
        preview_purchase = get_rows_as_dicts('purchase', limit=100)
        
        return jsonify({
            'success': True,
            'sale_count': stats['sale_count'],
            'purchase_count': stats['purchase_count'],
            'sale_new': stats['sale_new'],
            'sale_duplicates': stats['sale_duplicates'],
            'purchase_new': stats['purchase_new'],
            'purchase_duplicates': stats['purchase_duplicates'],
            'financial_year': get_financial_year(),
            'sale_preview': preview_sale,
            'purchase_preview': preview_purchase,
        })
    except Exception as e:
        print(f"[UPLOAD ERROR] ❌ Exception during upload: {str(e)}", flush=True)
        # Clean up files in case of error as well!
        for path in file_paths.values():
            try:
                os.remove(path)
            except Exception:
                pass
        gc.collect()
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/export', methods=['GET'])
def export_file():
    """Export processed data as Excel."""
    try:
        # Verify if we have any data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sale")
        s_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM purchase")
        p_count = cursor.fetchone()[0]
        conn.close()
        
        if s_count == 0 and p_count == 0:
            return jsonify({'error': 'No processed data. Please upload files first.'}), 400
        
        fy = get_financial_year()
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'AJIO_MYNTRA_FLIPKART_{fy}_Output.xlsx')
        export_to_excel_streaming(output_path)
        
        # Force garbage collection to reclaim memory instantly
        gc.collect()
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f'AJIO_MYNTRA_FLIPKART_Sale_Purchase_{fy}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        gc.collect()
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/preview-more', methods=['GET'])
def preview_more():
    """Get more rows for preview."""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 100))
        
        sale_data = get_rows_as_dicts('sale', limit=limit, offset=offset)
        purchase_data = get_rows_as_dicts('purchase', limit=limit, offset=offset)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sale")
        sale_total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM purchase")
        purchase_total = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'sale_data': sale_data,
            'purchase_data': purchase_data,
            'sale_total': sale_total,
            'purchase_total': purchase_total,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """Get current data status."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sale")
        sale_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM purchase")
        purchase_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'sale_count': sale_count,
            'purchase_count': purchase_count,
            'financial_year': get_financial_year(),
            'has_data': bool(sale_count or purchase_count),
        })
    except Exception:
        return jsonify({
            'sale_count': 0,
            'purchase_count': 0,
            'financial_year': get_financial_year(),
            'has_data': False,
        })


@app.route('/clear', methods=['POST'])
def clear_data():
    """Clear all stored data (fresh start)."""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM sale")
        conn.execute("DELETE FROM purchase")
        conn.execute("DROP TABLE IF EXISTS sync_sale_temp")
        conn.execute("DROP TABLE IF EXISTS sync_purchase_temp")
        conn.commit()
        try:
            conn.execute("VACUUM")
        except Exception as vac_err:
            print(f"[VACUUM ERROR] Failed to vacuum DB: {str(vac_err)}", flush=True)
        conn.close()
        
        # Also clean up output excels
        try:
            for f in os.listdir(app.config['UPLOAD_FOLDER']):
                if f.endswith('.xlsx') or f.endswith('.pkl'):
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
        except Exception:
            pass
            
        return jsonify({'success': True, 'message': 'All data cleared!'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/prepare-sync', methods=['POST'])
def prepare_sync():
    """Prepare sync by filtering local data against sheets unique IDs and storing in temp tables."""
    try:
        req_data = request.json or {}
        web_app_url = req_data.get('webAppUrl')
        sheet_name = req_data.get('sheetName')
        mode = req_data.get('mode', 'append')
        
        print(f"\n[SYNC PREPARE] 🔄 Target Sheet: '{sheet_name}', Mode: '{mode}'...", flush=True)
        if not web_app_url:
            print("[SYNC PREPARE ERROR] ❌ Google Web App URL is required", flush=True)
            return jsonify({'error': 'Google Web App URL is required'}), 400
        if not sheet_name:
            print("[SYNC PREPARE ERROR] ❌ Target Sheet Name is required", flush=True)
            return jsonify({'error': 'Target Sheet Name is required'}), 400
            
        existing_sale_ids = set()
        existing_purchase_ids = set()
        
        sheet_sale_count = 0
        sheet_purchase_count = 0
        
        if mode == 'append':
            try:
                # Call getExistingUniqueIds from Google Sheets Web App once
                from urllib.parse import quote
                url = f"{web_app_url}?action=getExistingUniqueIds&sheetName={quote(sheet_name)}"
                res = requests.get(url, allow_redirects=False, timeout=120)
                if res.status_code in [302, 307, 308]:
                    redirect_url = res.headers.get('Location')
                    res = requests.get(redirect_url, timeout=120)
                
                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get('success'):
                        existing_sale_ids = set(str(uid) for uid in res_data.get('saleIds', []))
                        existing_purchase_ids = set(str(uid) for uid in res_data.get('purchaseIds', []))
                        sheet_sale_count = int(res_data.get('saleCount', len(existing_sale_ids)))
                        sheet_purchase_count = int(res_data.get('purchaseCount', len(existing_purchase_ids)))
            except Exception as e:
                print(f"Error fetching unique IDs from sheet: {str(e)}", flush=True)
                # Fallback: check SQLite cache
                try:
                    cache_conn = sqlite3.connect(_CACHE_DB_PATH)
                    cache_cursor = cache_conn.cursor()
                    cache_cursor.execute("SELECT key FROM sale_cache WHERE sheet_name = ?", (sheet_name,))
                    existing_sale_ids = {str(r[0]) for r in cache_cursor.fetchall()}
                    cache_cursor.execute("SELECT key FROM purchase_cache WHERE sheet_name = ?", (sheet_name,))
                    existing_purchase_ids = {str(r[0]) for r in cache_cursor.fetchall()}
                    cache_conn.close()
                except Exception as cache_err:
                    print(f"Fallback cache query failed: {str(cache_err)}", flush=True)
                    
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get count of original records
        cursor.execute("SELECT COUNT(*) FROM sale")
        original_sale_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM purchase")
        original_purchase_count = cursor.fetchone()[0]
        
        # Write to temporary tables in local_store.db
        conn.execute("DROP TABLE IF EXISTS sync_sale_temp")
        conn.execute("DROP TABLE IF EXISTS sync_purchase_temp")
        conn.execute("CREATE TABLE sync_sale_temp AS SELECT * FROM sale WHERE 1=0")
        conn.execute("CREATE TABLE sync_purchase_temp AS SELECT * FROM purchase WHERE 1=0")
        
        sale_keys = [
            'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
            'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
            'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
            'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
            'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
            'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short', 'sheet_name'
        ]
        
        purchase_keys = [
            'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
            'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
            'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
            'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
            'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt', 'sheet_name'
        ]
        
        # Filter and insert sales row by row using a cursor to keep memory flat
        cursor.execute("SELECT * FROM sale ORDER BY no ASC")
        skipped_sale = 0
        inserted_sale = 0
        existing_sale_count = max(sheet_sale_count, len(existing_sale_ids)) if mode == 'append' else 0
        
        sale_batch = []
        for r in cursor:
            row = dict(r)
            uid = str(row.get('sale_unique_id', ''))
            if mode == 'append' and uid in existing_sale_ids:
                skipped_sale += 1
            else:
                row['no'] = existing_sale_count + inserted_sale + 1
                sale_batch.append(tuple(row.get(k, '') for k in sale_keys))
                inserted_sale += 1
                
            if len(sale_batch) >= 1000:
                placeholders = ','.join(['?' for _ in sale_keys])
                conn.execute("BEGIN TRANSACTION")
                conn.executemany(f"INSERT INTO sync_sale_temp ({','.join(sale_keys)}) VALUES ({placeholders})", sale_batch)
                conn.commit()
                sale_batch = []
                
        if sale_batch:
            placeholders = ','.join(['?' for _ in sale_keys])
            conn.execute("BEGIN TRANSACTION")
            conn.executemany(f"INSERT INTO sync_sale_temp ({','.join(sale_keys)}) VALUES ({placeholders})", sale_batch)
            conn.commit()
            
        # Filter and insert purchases row by row using a cursor to keep memory flat
        cursor.execute("SELECT * FROM purchase ORDER BY no ASC")
        skipped_purchase = 0
        inserted_purchase = 0
        existing_purchase_count = max(sheet_purchase_count, len(existing_purchase_ids)) if mode == 'append' else 0
        
        purchase_batch = []
        for r in cursor:
            row = dict(r)
            uid = str(row.get('purchase_unique_id', ''))
            if mode == 'append' and uid in existing_purchase_ids:
                skipped_purchase += 1
            else:
                row['no'] = existing_purchase_count + inserted_purchase + 1
                purchase_batch.append(tuple(row.get(k, '') for k in purchase_keys))
                inserted_purchase += 1
                
            if len(purchase_batch) >= 1000:
                placeholders = ','.join(['?' for _ in purchase_keys])
                conn.execute("BEGIN TRANSACTION")
                conn.executemany(f"INSERT INTO sync_purchase_temp ({','.join(purchase_keys)}) VALUES ({placeholders})", purchase_batch)
                conn.commit()
                purchase_batch = []
                
        if purchase_batch:
            placeholders = ','.join(['?' for _ in purchase_keys])
            conn.execute("BEGIN TRANSACTION")
            conn.executemany(f"INSERT INTO sync_purchase_temp ({','.join(purchase_keys)}) VALUES ({placeholders})", purchase_batch)
            conn.commit()
            
        conn.close()
        
        # Free memory
        del existing_sale_ids, existing_purchase_ids
        import gc
        gc.collect()
        
        print(f"[SYNC PREPARE SUCCESS] ✅ Ready to sync: {inserted_sale} sales, {inserted_purchase} purchases. (Skipped: {skipped_sale} sales, {skipped_purchase} purchases)", flush=True)
        return jsonify({
            'success': True,
            'originalSale': original_sale_count,
            'originalPurchase': original_purchase_count,
            'skippedSale': skipped_sale,
            'skippedPurchase': skipped_purchase,
            'toSyncSale': inserted_sale,
            'toSyncPurchase': inserted_purchase,
        })
    except Exception as e:
        print(f"[SYNC PREPARE ERROR] ❌ Exception in prepare_sync: {str(e)}", flush=True)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-sync-chunk', methods=['GET'])
def get_sync_chunk():
    """Retrieve a paginated chunk of sync data from temp tables as 2D lists."""
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 2000))
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verify if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_sale_temp'")
        has_sale = cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_purchase_temp'")
        has_purchase = cursor.fetchone() is not None
        
        sale_rows = []
        if has_sale:
            cursor.execute("SELECT * FROM sync_sale_temp ORDER BY no ASC LIMIT ? OFFSET ?", (limit, offset))
            sale_rows = [dict(r) for r in cursor.fetchall()]
            
        purchase_rows = []
        if has_purchase:
            cursor.execute("SELECT * FROM sync_purchase_temp ORDER BY no ASC LIMIT ? OFFSET ?", (limit, offset))
            purchase_rows = [dict(r) for r in cursor.fetchall()]
            
        conn.close()
        
        # Map to 2D list format matching Google Sheets Columns
        sale_keys = [
            'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
            'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
            'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
            'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
            'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
            'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short'
        ]
        
        purchase_keys = [
            'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
            'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
            'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
            'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
            'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt'
        ]
        
        sale_rows_2d = [[row.get(k, '') for k in sale_keys] for row in sale_rows]
        purchase_rows_2d = [[row.get(k, '') for k in purchase_keys] for row in purchase_rows]
        
        # Free memory
        del sale_rows, purchase_rows
        import gc
        gc.collect()
        
        return jsonify({
            'success': True,
            'saleRows': sale_rows_2d,
            'purchaseRows': purchase_rows_2d
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/send-sync-chunk', methods=['POST'])
def send_sync_chunk():
    """Proxy endpoint to send a batch chunk to Google Apps Script safely without browser CORS issues."""
    try:
        data = request.get_json(force=True, silent=True) or {}
        web_app_url = data.get('webAppUrl')
        payload = data.get('payload')
        
        if not web_app_url or not payload:
            print("[SYNC CHUNK ERROR] ❌ Missing webAppUrl or payload in request", flush=True)
            return jsonify({'success': False, 'error': 'Missing webAppUrl or payload'}), 400
            
        b_idx = payload.get('batchIndex', '?')
        b_tot = payload.get('totalBatches', '?')
        s_cnt = len(payload.get('saleRows', []))
        p_cnt = len(payload.get('purchaseRows', []))
        print(f"[SYNC CHUNK] 📤 Uploading Batch {b_idx}/{b_tot} to Google Sheets (Sales: {s_cnt}, Purchases: {p_cnt})...", flush=True)
        
        response = requests.post(web_app_url, json=payload, timeout=180)
        if response.status_code != 200:
            print(f"[SYNC CHUNK ERROR] ❌ Google Apps Script HTTP status {response.status_code}: {response.text[:200]}", flush=True)
            return jsonify({'success': False, 'error': f'Google Apps Script returned status {response.status_code}'}), 500
            
        try:
            result = response.json()
        except Exception:
            print(f"[SYNC CHUNK ERROR] ❌ Google Apps Script returned non-JSON: {response.text[:200]}", flush=True)
            return jsonify({'success': False, 'error': f'Google Apps Script returned invalid response (HTML/Text): {response.text[:150]}'}), 500

        if result.get('success'):
            print(f"[SYNC CHUNK SUCCESS] ✅ Batch {b_idx}/{b_tot} written successfully to Google Sheet!", flush=True)
            print(f"[DATABASE] 💾 Updated to Database: Batch {b_idx}/{b_tot} ({s_cnt} Sales, {p_cnt} Purchases) saved successfully!\n", flush=True)
        else:
            print(f"[SYNC CHUNK ERROR] ⚠️ Google Apps Script error: {result.get('error')}", flush=True)
        return jsonify(result)
    except Exception as e:
        print(f"[SYNC CHUNK EXCEPTION] ❌ {str(e)}", flush=True)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-sync-data', methods=['POST'])
def get_sync_data():
    """Fallback get-sync-data using SQLite (returns all sync rows)."""
    try:
        req_data = request.json or {}
        web_app_url = req_data.get('webAppUrl')
        sheet_name = req_data.get('sheetName')
        mode = req_data.get('mode', 'append')
        
        # Call prepare_sync logic and fetch all rows from temp tables
        # This keeps compatibility with anything expecting this endpoint
        # but loads from SQLite.
        prepare_res = prepare_sync()
        if prepare_res.status_code != 200:
            return prepare_res
            
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sync_sale_temp ORDER BY no ASC")
        sale_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM sync_purchase_temp ORDER BY no ASC")
        purchase_rows = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM sale")
        original_sale = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM purchase")
        original_purchase = cursor.fetchone()[0]
        conn.close()
        
        sale_keys = [
            'no', 'invoice_no', 'type', 'invoice_date', 'warehouse_name',
            'warehouse_code', 'gst_no', 'order_id', 'item_asin', 'item_sku',
            'item_name', 'hsn_number', 'quantity', 'item_cost', 'gross',
            'igst', 'cgst', 'sgst', 'igst_amt', 'cgst_amt', 'sgst_amt',
            'invoice', 'reason', 'zoho_status', 'invoice_id', 'state_code',
            'sale_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_invoice', 'state_code_short'
        ]
        
        purchase_keys = [
            'no', 'invoice_no', 'warehouse_name', 'warehouse_code', 'gst_no',
            'order_id', 'item_asin', 'item_sku', 'item_name', 'hsn_number',
            'quantity', 'item_cost', 'gross', 'igst', 'cgst', 'sgst',
            'igst_amt', 'cgst_amt', 'sgst_amt', 'invoice',
            'purchase_unique_id', 'calc_qty', 'calc_cost', 'calc_gross',
            'calc_igst', 'calc_cgst', 'calc_sgst', 'calc_igst_amt',
            'calc_cgst_amt', 'calc_sgst_amt', 'calc_total_amt'
        ]
        
        sale_rows_2d = [[row.get(k, '') for k in sale_keys] for row in sale_rows]
        purchase_rows_2d = [[row.get(k, '') for k in purchase_keys] for row in purchase_rows]
        
        skipped_sale = original_sale - len(sale_rows)
        skipped_purchase = original_purchase - len(purchase_rows)
        
        return jsonify({
            'success': True,
            'saleRows': sale_rows_2d,
            'purchaseRows': purchase_rows_2d,
            'originalSale': original_sale,
            'originalPurchase': original_purchase,
            'skippedSale': skipped_sale,
            'skippedPurchase': skipped_purchase,
            'toSyncSale': len(sale_rows_2d),
            'toSyncPurchase': len(purchase_rows_2d),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/sync-sheet', methods=['POST'])
def sync_sheet():
    """Fallback sync-sheet using SQLite."""
    try:
        req_data = request.json or {}
        web_app_url = req_data.get('webAppUrl')
        sheet_name = req_data.get('sheetName')
        mode = req_data.get('mode', 'append')
        
        sync_data_res = get_sync_data()
        if sync_data_res.status_code != 200:
            return sync_data_res
            
        sync_data = sync_data_res.json
        sale_rows_2d = sync_data.get('saleRows', [])
        purchase_rows_2d = sync_data.get('purchaseRows', [])
        
        payload = {
            'action': 'writeData',
            'sheetName': sheet_name,
            'saleRows': sale_rows_2d,
            'purchaseRows': purchase_rows_2d,
            'isAppend': (mode == 'append')
        }
        
        response = requests.post(web_app_url, json=payload, allow_redirects=False)
        if response.status_code in [302, 307, 308]:
            redirect_url = response.headers.get('Location')
            response = requests.post(redirect_url, json=payload)
            
        if response.status_code != 200:
            return jsonify({'error': f'Failed to write to Google Sheets. Status code: {response.status_code}'}), 500
            
        result = response.json()
        if not result.get('success'):
            return jsonify({'error': result.get('error', 'Unknown error writing to Google Sheets')}), 500
            
        return jsonify({
            'success': True,
            'message': result.get('message', 'Data synced successfully!'),
            'saleRows': result.get('saleRows', 0),
            'purchaseRows': result.get('purchaseRows', 0)
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, use_reloader=False, threaded=True, port=port)
