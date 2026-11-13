// ============================================================================
// TURSO MONTH-END AUTO RESET - MASTER APPS SCRIPT
// Runs automatically on the LAST DAY of every month at 11:00 PM (IST)
// One-Shot Fast Drop & Recreate (Preserves Sheet Settings, Zero Row Write Waste!)
// ============================================================================

const TURSO_DB_URL = "https://sale-purchase-db-ashishx70.aws-ap-south-1.turso.io";
const TURSO_AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQ1ODEyOTMsImlkIjoiMDFhMWQ1NjAtMmIwMS03ZmZhLWJlNDktYTlmMDBiNzNmY2MyIiwia2lkIjoianBTUEJoNkJBcHcwVXN2Mmx5eWZPRUpBZWpiaF9VVlp4d2x6MGZwT1lBRSIsInJpZCI6IjFlMzFmZTc4LTU4MTItNDkxNi1hYmI1LWUzZDgzZDAxNTA2YyJ9.qOHHq62dlCuJ527kuawkcaaOHKTR5IdStrWRG5gUcHz3xFPI-td6RaYTOdInv-ZriJNhx3dTjUntuU0R-O2gCw";

/**
 * Checks if today is the last day of the current calendar month.
 */
function isLastDayOfMonth() {
  const today = new Date();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  // If tomorrow's date is 1, then today is the last day of the month!
  return tomorrow.getDate() === 1;
}

/**
 * Main Trigger Function: Set this on a Daily Time Trigger between 10:00 PM - 11:00 PM.
 * Automatically checks if today is the LAST DAY of the month.
 * If yes -> Executes Turso One-Shot Reset.
 * If no  -> Skips quietly with zero writes.
 */
function monthEndTursoResetTrigger() {
  if (!isLastDayOfMonth()) {
    Logger.log("[SKIP] Today is not the last day of the month. No action needed.");
    return;
  }
  Logger.log("[MATCH] Today is the LAST DAY of the month! Executing One-Shot Turso Reset...");
  executeTursoOneShotReset();
}

/**
 * Executes One-Shot Table Drop & Recreate on Turso.
 * Takes ~50ms, 0 row-by-row write waste, leaves sheet_details_cache safe!
 */
function executeTursoOneShotReset() {
  const url = TURSO_DB_URL + "/v2/pipeline";

  const stmts = [
    // 1. One-shot wipe of sale_cache without row-by-row penalty
    { type: "execute", stmt: { sql: "DROP TABLE IF EXISTS sale_cache" } },
    { type: "execute", stmt: { sql: "CREATE TABLE IF NOT EXISTS sale_cache (key TEXT PRIMARY KEY, qty REAL DEFAULT 0, rate REAL DEFAULT 0, state TEXT DEFAULT '', seller_name TEXT DEFAULT '', sheet_name TEXT DEFAULT '')" } },
    { type: "execute", stmt: { sql: "CREATE INDEX IF NOT EXISTS idx_sale_sheet ON sale_cache(sheet_name)" } },

    // 2. One-shot wipe of purchase_cache without row-by-row penalty
    { type: "execute", stmt: { sql: "DROP TABLE IF EXISTS purchase_cache" } },
    { type: "execute", stmt: { sql: "CREATE TABLE IF NOT EXISTS purchase_cache (key TEXT PRIMARY KEY, qty REAL DEFAULT 0, rate REAL DEFAULT 0, state TEXT DEFAULT '', seller_name TEXT DEFAULT '', sheet_name TEXT DEFAULT '')" } },
    { type: "execute", stmt: { sql: "CREATE INDEX IF NOT EXISTS idx_purch_sheet ON purchase_cache(sheet_name)" } },

    // 3. Reset session state in system_cache
    { 
      type: "execute", 
      stmt: { 
        sql: "INSERT OR REPLACE INTO system_cache (key, value, updated_at) VALUES (?, ?, ?)",
        args: [
          { type: "text", value: "__CACHE_SESSION__" },
          { type: "text", value: JSON.stringify({ synced_at: 0, active_sheets: [] }) },
          { type: "float", value: Date.now() / 1000 }
        ]
      }
    },
    { type: "close" }
  ];

  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "Authorization": "Bearer " + TURSO_AUTH_TOKEN
    },
    payload: JSON.stringify({ requests: stmts }),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    if (code === 200) {
      Logger.log("[SUCCESS] Turso database successfully reset to 0 rows for new month! Sheet settings preserved.");
    } else {
      Logger.log("[ERROR] Turso returned HTTP " + code + ": " + response.getContentText());
    }
  } catch (err) {
    Logger.log("[EXCEPTION] Failed to reset Turso: " + err.message);
  }
}

/**
 * Diagnostic Function: Run this manually in Apps Script to verify connection!
 * Does NOT delete any data. Simply logs current table counts.
 */
function testTursoConnection() {
  const url = TURSO_DB_URL + "/v2/pipeline";
  const stmts = [
    { type: "execute", stmt: { sql: "SELECT count(*) AS cnt FROM sheet_details_cache" } },
    { type: "execute", stmt: { sql: "SELECT count(*) AS cnt FROM sale_cache" } },
    { type: "execute", stmt: { sql: "SELECT count(*) AS cnt FROM purchase_cache" } },
    { type: "close" }
  ];

  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "Authorization": "Bearer " + TURSO_AUTH_TOKEN
    },
    payload: JSON.stringify({ requests: stmts }),
    muteHttpExceptions: true
  };

  try {
    const res = UrlFetchApp.fetch(url, options);
    Logger.log("[TEST STATUS]: " + res.getResponseCode());
    Logger.log("[RESPONSE]: " + res.getContentText());
  } catch (e) {
    Logger.log("[TEST ERROR]: " + e.message);
  }
}
