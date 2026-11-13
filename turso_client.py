import os
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TURSO_DB_URL = os.environ.get(
    "TURSO_DB_URL"
) or os.environ.get(
    "TURSO_DATABASE_URL"
) or "https://sale-purchase-db-ashishx70.aws-ap-south-1.turso.io"
if TURSO_DB_URL.startswith("libsql://"):
    TURSO_DB_URL = TURSO_DB_URL.replace("libsql://", "https://")

TURSO_AUTH_TOKEN = os.environ.get(
    "TURSO_AUTH_TOKEN",
    "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQ1ODEyOTMsImlkIjoiMDFhMWQ1NjAtMmIwMS03ZmZhLWJlNDktYTlmMDBiNzNmY2MyIiwia2lkIjoianBTUEJoNkJBcHcwVXN2Mmx5eWZPRUpBZWpiaF9VVlp4d2x6MGZwT1lBRSIsInJpZCI6IjFlMzFmZTc4LTU4MTItNDkxNi1hYmI1LWUzZDgzZDAxNTA2YyJ9.qOHHq62dlCuJ527kuawkcaaOHKTR5IdStrWRG5gUcHz3xFPI-td6RaYTOdInv-ZriJNhx3dTjUntuU0R-O2gCw"
)

# Persistent HTTP Session with connection pooling
_session = requests.Session()
_adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=0.3, status_forcelist=[502, 503, 504])
)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)


def _get_headers():
    return {
        "Authorization": f"Bearer {TURSO_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }


def to_turso_val(v):
    if v is None:
        return {"type": "null"}
    elif isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    elif isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    elif isinstance(v, float):
        return {"type": "float", "value": float(v)}
    else:
        return {"type": "text", "value": str(v)}


def parse_turso_rows(execute_result):
    cols = [c.get("name") for c in execute_result.get("cols", [])]
    rows = []
    for r in execute_result.get("rows", []):
        row_dict = {}
        for idx, col_val in enumerate(r):
            v_type = col_val.get("type")
            val = col_val.get("value")
            if v_type == "integer":
                val = int(val) if val is not None else 0
            elif v_type == "float":
                val = float(val) if val is not None else 0.0
            elif v_type == "null":
                val = None
            row_dict[cols[idx]] = val
        rows.append(row_dict)
    return rows


def execute_pipeline(stmts, timeout=20):
    """
    Executes a list of statement dicts against Turso HTTP Pipeline API.
    stmts: [{'sql': '...', 'args': [...]}, ...]
    Returns list of parsed execute result dicts.
    """
    url = f"{TURSO_DB_URL}/v2/pipeline"
    requests_payload = []
    for s in stmts:
        requests_payload.append({
            "type": "execute",
            "stmt": {
                "sql": s["sql"],
                "args": s.get("args", [])
            }
        })
    requests_payload.append({"type": "close"})

    resp = _session.post(
        url,
        headers=_get_headers(),
        json={"requests": requests_payload},
        timeout=timeout
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Turso pipeline error HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    results = []
    for res_item in data.get("results", []):
        if res_item.get("type") == "ok":
            response_obj = res_item.get("response", {})
            if response_obj.get("type") == "execute":
                results.append(response_obj.get("result", {}))
        elif res_item.get("type") == "error":
            err_msg = res_item.get("error", {}).get("message", "Unknown Turso Error")
            raise RuntimeError(f"Turso Query Error: {err_msg}")
    return results


def ensure_tables():
    """Ensure required tables exist in Turso with dedicated separation for sheet details and system cache."""
    ddl_stmts = [
        # Dedicated cache for Sheet details (name, web_app_url, sheet_url)
        {
            "sql": """CREATE TABLE IF NOT EXISTS sheet_details_cache (
                sheet_name TEXT PRIMARY KEY,
                web_app_url TEXT DEFAULT '',
                sheet_url TEXT DEFAULT '',
                updated_at REAL DEFAULT 0
            )"""
        },
        # Dedicated cache for session and system state
        {
            "sql": """CREATE TABLE IF NOT EXISTS system_cache (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT '',
                updated_at REAL DEFAULT 0
            )"""
        },
        # Pure Sales Cache table (NO system rows allowed)
        {
            "sql": """CREATE TABLE IF NOT EXISTS sale_cache (
                key TEXT PRIMARY KEY,
                qty REAL DEFAULT 0,
                rate REAL DEFAULT 0,
                state TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                sheet_name TEXT DEFAULT ''
            )"""
        },
        # Pure Purchase Cache table (NO system rows allowed)
        {
            "sql": """CREATE TABLE IF NOT EXISTS purchase_cache (
                key TEXT PRIMARY KEY,
                qty REAL DEFAULT 0,
                rate REAL DEFAULT 0,
                state TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                sheet_name TEXT DEFAULT ''
            )"""
        },
        {"sql": "CREATE INDEX IF NOT EXISTS idx_sale_sheet ON sale_cache(sheet_name)"},
        {"sql": "CREATE INDEX IF NOT EXISTS idx_purch_sheet ON purchase_cache(sheet_name)"}
    ]
    try:
        execute_pipeline(ddl_stmts, timeout=15)
        return True
    except Exception as e:
        print(f"[TURSO INIT ERROR]: {e}", flush=True)
        return False


def get_turso_session(cache_session_file=None):
    """Retrieve the cached session metadata from dedicated system_cache table."""
    data = {"synced_at": 0, "active_sheets": []}
    try:
        results = execute_pipeline([{
            "sql": "SELECT value FROM system_cache WHERE key = ?",
            "args": [to_turso_val("__CACHE_SESSION__")]
        }], timeout=5)
        if results:
            rows = parse_turso_rows(results[0])
            if rows and rows[0].get("value"):
                return json.loads(rows[0]["value"])
    except Exception as e:
        print(f"[SESSION TURSO READ ERR]: {e}", flush=True)

    if cache_session_file and os.path.exists(cache_session_file):
        try:
            with open(cache_session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    return data


def save_turso_session(data, cache_session_file=None):
    """Save session metadata to dedicated system_cache table."""
    try:
        sql = "INSERT OR REPLACE INTO system_cache (key, value, updated_at) VALUES (?, ?, ?)"
        args = [to_turso_val("__CACHE_SESSION__"), to_turso_val(json.dumps(data)), to_turso_val(time.time())]
        execute_pipeline([{"sql": sql, "args": args}], timeout=10)
    except Exception as e:
        print(f"[SESSION TURSO WRITE ERR]: {e}", flush=True)

    if cache_session_file:
        try:
            with open(cache_session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CACHE SESSION ERROR]: {e}", flush=True)


def load_fy_settings_turso():
    """Load Sheet details (names and URLs) from dedicated sheet_details_cache table."""
    try:
        results = execute_pipeline([{
            "sql": "SELECT sheet_name, web_app_url, sheet_url FROM sheet_details_cache",
            "args": []
        }], timeout=5)
        if results:
            rows = parse_turso_rows(results[0])
            if rows:
                urls = {}
                sheet_urls = {}
                for r in rows:
                    s_name = r.get("sheet_name")
                    if s_name:
                        if r.get("web_app_url"):
                            urls[s_name] = r.get("web_app_url")
                        if r.get("sheet_url"):
                            sheet_urls[s_name] = r.get("sheet_url")
                if urls or sheet_urls:
                    return urls, sheet_urls
    except Exception as e:
        print(f"[FY SETTINGS TURSO LOAD ERR]: {e}", flush=True)
    return None, None


def save_fy_settings_turso(full_data):
    """Save Sheet details (names, web app URLs, and sheet URLs) into dedicated sheet_details_cache table."""
    try:
        urls = full_data.get("urls", {}) if isinstance(full_data, dict) else {}
        sheet_urls = full_data.get("sheet_urls", {}) if isinstance(full_data, dict) else {}
        all_sheet_names = set(list(urls.keys()) + list(sheet_urls.keys()))

        if not all_sheet_names:
            return False

        stmts = []
        now = time.time()
        for s_name in all_sheet_names:
            w_url = urls.get(s_name, "")
            sh_url = sheet_urls.get(s_name, "")
            stmts.append({
                "sql": "INSERT OR REPLACE INTO sheet_details_cache (sheet_name, web_app_url, sheet_url, updated_at) VALUES (?, ?, ?, ?)",
                "args": [to_turso_val(s_name), to_turso_val(w_url), to_turso_val(sh_url), to_turso_val(now)]
            })

        execute_pipeline(stmts, timeout=10)
        print(f"[SHEET DETAILS] Successfully cached {len(stmts)} sheets into sheet_details_cache table in Turso!", flush=True)
        return True
    except Exception as e:
        print(f"[SHEET DETAILS TURSO WRITE ERR]: {e}", flush=True)
        return False


def nill_turso_tables(cache_session_file=None):
    """
    Wipes sale_cache and purchase_cache tables to 0 rows using one-shot DROP & RECREATE.
    Leaves sheet_details_cache completely untouched!
    Takes ~50ms, zero row-by-row write waste in Turso.
    """
    try:
        stmts = [
            {"sql": "DROP TABLE IF EXISTS sale_cache"},
            {"sql": "CREATE TABLE IF NOT EXISTS sale_cache (key TEXT PRIMARY KEY, qty REAL DEFAULT 0, rate REAL DEFAULT 0, state TEXT DEFAULT '', seller_name TEXT DEFAULT '', sheet_name TEXT DEFAULT '')"},
            {"sql": "CREATE INDEX IF NOT EXISTS idx_sale_sheet ON sale_cache(sheet_name)"},
            {"sql": "DROP TABLE IF EXISTS purchase_cache"},
            {"sql": "CREATE TABLE IF NOT EXISTS purchase_cache (key TEXT PRIMARY KEY, qty REAL DEFAULT 0, rate REAL DEFAULT 0, state TEXT DEFAULT '', seller_name TEXT DEFAULT '', sheet_name TEXT DEFAULT '')"},
            {"sql": "CREATE INDEX IF NOT EXISTS idx_purch_sheet ON purchase_cache(sheet_name)"}
        ]
        execute_pipeline(stmts, timeout=30)
        save_turso_session({"synced_at": 0, "active_sheets": []}, cache_session_file)
        print("[TURSO NILL] Successfully one-shot reset cache tables to 0 rows while preserving sheet details.", flush=True)
        return True
    except Exception as e:
        print(f"[NILL TURSO ERROR]: {e}", flush=True)
        return False


def get_turso_live_counts():
    """Retrieve row counts of sale_cache and purchase_cache (pure counts)."""
    try:
        stmts = [
            {"sql": "SELECT COUNT(*) as cnt FROM sale_cache"},
            {"sql": "SELECT COUNT(*) as cnt FROM purchase_cache"}
        ]
        results = execute_pipeline(stmts, timeout=10)
        if len(results) >= 2:
            s_rows = parse_turso_rows(results[0])
            p_rows = parse_turso_rows(results[1])
            s_cnt = int(s_rows[0].get("cnt", 0)) if s_rows else 0
            p_cnt = int(p_rows[0].get("cnt", 0)) if p_rows else 0
            return s_cnt, p_cnt
    except Exception as e:
        print(f"[TURSO LIVE COUNT ERR]: {e}", flush=True)
    return 0, 0


def batch_insert_turso(table_name, rows, chunk_size=500):
    """
    Inserts a list of dicts into table_name using multi-row INSERT OR REPLACE.
    Each dict should have: key, qty, rate, state, seller_name, sheet_name
    """
    if not rows:
        return 0

    total_inserted = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        vals = []
        args = []
        for r in chunk:
            vals.append("(?, ?, ?, ?, ?, ?)")
            args.extend([
                to_turso_val(r.get("key", "")),
                to_turso_val(r.get("qty", 0)),
                to_turso_val(r.get("rate", 0)),
                to_turso_val(r.get("state", "")),
                to_turso_val(r.get("seller_name", "")),
                to_turso_val(r.get("sheet_name", ""))
            ])
        sql = f"INSERT OR REPLACE INTO {table_name} (key, qty, rate, state, seller_name, sheet_name) VALUES " + ",".join(vals)
        execute_pipeline([{"sql": sql, "args": args}], timeout=30)
        total_inserted += len(chunk)
    return total_inserted


def query_turso_lookup(keys, is_sale=True, chunk_size=300):
    """
    Ultra-fast batch lookup for sales or purchase keys from Turso.
    Returns: mapping[clean_key] = {"qty": ..., "rate": ..., "state": ..., "sellerName": ...}
    """
    if not keys:
        return {}

    mapping = {}
    table = "sale_cache" if is_sale else "purchase_cache"
    clean_keys = list(set(str(k).strip().upper() for k in keys if k))

    for i in range(0, len(clean_keys), chunk_size):
        chunk = clean_keys[i:i + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        sql = f"SELECT key, qty, rate, state, seller_name FROM {table} WHERE key IN ({placeholders})"
        args = [to_turso_val(k) for k in chunk]
        try:
            results = execute_pipeline([{"sql": sql, "args": args}], timeout=15)
            if results:
                rows = parse_turso_rows(results[0])
                for row in rows:
                    k = str(row.get("key", "")).strip().upper()
                    if k:
                        mapping[k] = {
                            "qty": row.get("qty", 0),
                            "rate": row.get("rate", 0),
                            "state": row.get("state", "") if is_sale else "",
                            "sellerName": row.get("seller_name", "")
                        }
        except Exception as e:
            print(f"[TURSO LOOKUP EXCEPTION]: {e}", flush=True)

    return mapping
