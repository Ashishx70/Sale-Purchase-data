/* ═══════════════════════════════════════════════════════════════════════
   AJIO • MYNTRA • FLIPKART — Sale & Purchase Processor
   Frontend Logic — Slim Upload, Full Width, Universal Search
   ═══════════════════════════════════════════════════════════════════════ */

const DEFAULT_WEB_APP_URL_25_26 = 'https://script.google.com/macros/s/AKfycbwNUZf-kOwrze7bJOa89vHU1J2atjsyCTt3lQ7E15KJptTsBJ3g4tUH0MqnhSt-LHhoCw/exec';
const DEFAULT_WEB_APP_URL_26_27 = 'https://script.google.com/macros/s/AKfycbyWMb69Xfk-Gkkp5Ye5mYCE8DoFUG0ua804LBlLErACpGPBAh1yZc3UhaIcRWvaiMGA/exec';

const DEFAULT_SHEET_URL_25_26 = 'https://docs.google.com/spreadsheets/d/1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To/edit';
const DEFAULT_SHEET_URL_26_27 = 'https://docs.google.com/spreadsheets/d/1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w/edit';

function getSavedFyUrls() {
    try {
        const stored = localStorage.getItem('sale_purchase_fy_urls');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed && typeof parsed === 'object') {
                if (!parsed['2025-26']) parsed['2025-26'] = DEFAULT_WEB_APP_URL_25_26;
                if (!parsed['2026-27']) parsed['2026-27'] = DEFAULT_WEB_APP_URL_26_27;
                return parsed;
            }
        }
    } catch(e) {}
    return {
        '2025-26': DEFAULT_WEB_APP_URL_25_26,
        '2026-27': DEFAULT_WEB_APP_URL_26_27
    };
}

function saveFyUrls(urlsObj) {
    try {
        localStorage.setItem('sale_purchase_fy_urls', JSON.stringify(urlsObj));
    } catch(e) {}
}

function getSavedFySheetUrls() {
    try {
        const stored = localStorage.getItem('sale_purchase_fy_sheet_urls');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed && typeof parsed === 'object') {
                if (!parsed['2025-26']) parsed['2025-26'] = DEFAULT_SHEET_URL_25_26;
                if (!parsed['2026-27']) parsed['2026-27'] = DEFAULT_SHEET_URL_26_27;
                return parsed;
            }
        }
    } catch(e) {}
    return {
        '2025-26': DEFAULT_SHEET_URL_25_26,
        '2026-27': DEFAULT_SHEET_URL_26_27
    };
}

function saveFySheetUrls(sheetUrlsObj) {
    try {
        localStorage.setItem('sale_purchase_fy_sheet_urls', JSON.stringify(sheetUrlsObj));
    } catch(e) {}
}

function extractSpreadsheetId(urlOrId) {
    if (!urlOrId) return '';
    const str = String(urlOrId).trim();
    const match = str.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
    if (match) return match[1];
    if (/^[a-zA-Z0-9-_]{20,}$/.test(str)) return str;
    return '';
}

function getSheetUrlForFY(fy) {
    const urls = getSavedFySheetUrls();
    if (fy && urls[fy] && urls[fy].trim() !== '') {
        return urls[fy].trim();
    }
    if (fy === '2026-27') return DEFAULT_SHEET_URL_26_27;
    return DEFAULT_SHEET_URL_25_26;
}

function getSpreadsheetIdForFY(fy) {
    const sheetUrl = getSheetUrlForFY(fy);
    const extracted = extractSpreadsheetId(sheetUrl);
    if (extracted) return extracted;
    if (state.spreadsheetIds && state.spreadsheetIds[fy]) {
        return state.spreadsheetIds[fy];
    }
    return fy === '2026-27' ? '1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w' : '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To';
}

async function fetchFySettingsFromServer() {
    try {
        const res = await fetch('/api/get-fy-settings');
        const data = await res.json();
        if (data && data.status === 'Success') {
            if (data.urls) {
                const localUrls = getSavedFyUrls();
                const serverUrls = data.urls;
                const merged = { ...localUrls };
                Object.keys(serverUrls).forEach(fy => {
                    if (serverUrls[fy] && serverUrls[fy].trim() !== '') {
                        merged[fy] = serverUrls[fy].trim();
                    } else if (!(fy in merged)) {
                        merged[fy] = '';
                    }
                });
                saveFyUrls(merged);
            }
            if (data.sheet_urls) {
                const localSheets = getSavedFySheetUrls();
                const serverSheets = data.sheet_urls;
                const mergedSheets = { ...localSheets };
                Object.keys(serverSheets).forEach(fy => {
                    if (serverSheets[fy] && serverSheets[fy].trim() !== '') {
                        mergedSheets[fy] = serverSheets[fy].trim();
                    } else if (!(fy in mergedSheets)) {
                        mergedSheets[fy] = '';
                    }
                });
                saveFySheetUrls(mergedSheets);
            }
            populateFYSelector();
            // Refresh dropdown with verified server URLs
            refreshSheetDropdown();
        }
    } catch(e) {
        console.warn('[FY SETTINGS] Could not load server settings:', e);
    }
}
fetchFySettingsFromServer();

function getWebAppUrlForFY(fy) {
    const urls = getSavedFyUrls();
    if (fy && urls[fy] && urls[fy].trim() !== '') {
        return urls[fy].trim();
    }
    if (fy === '2026-27') return DEFAULT_WEB_APP_URL_26_27;
    return DEFAULT_WEB_APP_URL_25_26;
}

function getActiveWebAppUrl() {
    return getWebAppUrlForFY(state.currentFY || '2026-27');
}

// ─── State ──────────────────────────────────────────────────────────────
const state = {
    files: { sale_details:null, sale_summary:null, purchase_details:null, purchase_summary:null },
    saleData: [], purchaseData: [],
    currentTab: 'sale',
    currentFY: '2026-27',
    saleOffset: 0, purchaseOffset: 0,
    pageSize: 25,
    saleTotal: 0, purchaseTotal: 0,
    spreadsheetIds: {
        '2025-26': '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To',
        '2026-27': '1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w'
    },

    // Sheet Viewer
    selectedSheet: '',
    availableSheets: [],
    viewerHeaders: [], viewerRows: [], viewerAllRows: [],
    viewerStartRow: 3, viewerPageSize: 25, viewerTotalRows: 0,
    searchTimer: null, searchToken: 0,
};

// ─── DOM ────────────────────────────────────────────────────────────────
const processBtn = document.getElementById('process-btn');
const exportBtn = document.getElementById('export-btn');
const loaderSection = document.getElementById('loader-section');
const resultSection = document.getElementById('result-section');
const loaderText = document.getElementById('loader-text');
const progressFill = document.getElementById('progress-fill');

// ─── File Upload (Slim Strip) ───────────────────────────────────────────
const fileKeys = ['sale_details', 'sale_summary', 'purchase_details', 'purchase_summary'];

fileKeys.forEach(key => {
    const card = document.getElementById(`card-${key.replace('_', '-')}`);
    const input = document.getElementById(`file-${key.replace('_', '-')}`);
    const nameEl = document.getElementById(`name-${key.replace('_', '-')}`);

    card.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') input.click();
    });

    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            state.files[key] = file;
            nameEl.textContent = file.name;
            card.classList.add('file-added');
            checkAllFilesReady();
        }
    });

    card.addEventListener('dragover', (e) => { e.preventDefault(); card.style.borderColor = '#6366f1'; });
    card.addEventListener('dragleave', () => { card.style.borderColor = ''; });
    card.addEventListener('drop', (e) => {
        e.preventDefault();
        card.style.borderColor = '';
        const file = e.dataTransfer.files[0];
        if (file && (file.name.endsWith('.xls') || file.name.endsWith('.xlsx'))) {
            state.files[key] = file;
            nameEl.textContent = file.name;
            card.classList.add('file-added');
            input.files = e.dataTransfer.files;
            checkAllFilesReady();
        } else {
            showToast('❌', 'Please drop a .xls or .xlsx file');
        }
    });
});

function checkAllFilesReady() {
    processBtn.disabled = !fileKeys.every(k => state.files[k] !== null);
}

// ─── Rows Per Page ──────────────────────────────────────────────────────
document.getElementById('rows-per-page').addEventListener('change', (e) => {
    state.pageSize = parseInt(e.target.value);
    // Reload data with new page size
    reloadLocalData();
});

async function reloadLocalData() {
    try {
        const res = await fetch(`/preview-more?offset=0&limit=${state.pageSize}`);
        const data = await res.json();
        if (!data.error) {
            state.saleData = data.sale_data || [];
            state.purchaseData = data.purchase_data || [];
            state.saleOffset = state.saleData.length;
            state.purchaseOffset = state.purchaseData.length;
            renderTable(state.currentTab);
        }
    } catch(e) { console.error(e); }
}

// ─── Process Files ──────────────────────────────────────────────────────
processBtn.addEventListener('click', async () => {
    if (processBtn.disabled) return;
    loaderSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    processBtn.disabled = true;

    const steps = [
        {text:'Reading Sale Details...',pct:15}, {text:'Reading Sale Summary...',pct:30},
        {text:'Reading Purchase Details...',pct:45}, {text:'Reading Purchase Summary...',pct:60},
        {text:'Running VLOOKUP merge...',pct:75}, {text:'Calculating columns...',pct:88},
        {text:'Checking duplicates...',pct:95},
    ];
    let i = 0;
    const iv = setInterval(() => {
        if (i < steps.length) { loaderText.textContent = steps[i].text; progressFill.style.width = steps[i].pct+'%'; i++; }
    }, 600);

    const fd = new FormData();
    fileKeys.forEach(k => fd.append(k, state.files[k]));

    try {
        const res = await fetch('/upload', { method:'POST', body:fd });
        clearInterval(iv);
        const raw = await res.text();
        let data;
        try {
            data = JSON.parse(raw);
        } catch(parseErr) {
            throw new Error(raw ? `Server returned invalid response: ${raw.slice(0, 200)}` : 'Server returned an empty response');
        }
        if (!res.ok || data.error) throw new Error(data.error || 'Upload failed');

        progressFill.style.width = '100%';
        loaderText.textContent = 'Done! ✅';

        state.saleData = data.sale_preview || [];
        state.purchaseData = data.purchase_preview || [];
        state.saleOffset = state.saleData.length;
        state.purchaseOffset = state.purchaseData.length;
        state.saleTotal = data.sale_count;
        state.purchaseTotal = data.purchase_count;

        document.getElementById('sale-count').textContent = formatNumber(data.sale_count);
        document.getElementById('purchase-count').textContent = formatNumber(data.purchase_count);
        document.getElementById('total-count').textContent = formatNumber(data.sale_count + data.purchase_count);
        if (data.financial_year) {
            state.currentFY = data.financial_year;
            document.getElementById('fy-badge').textContent = `FY ${data.financial_year}`;
        }

        if (data.sale_duplicates > 0 || data.purchase_duplicates > 0)
            showToast('🔍', `Duplicates skipped: Sale=${data.sale_duplicates}, Purchase=${data.purchase_duplicates}`);

        setTimeout(() => {
            loaderSection.classList.add('hidden');
            resultSection.classList.remove('hidden');
            renderTable('sale');
            updateHeaderStatus(data.sale_count, data.purchase_count);
            showToast('✅', `Processed! Sale: ${data.sale_count}, Purchase: ${data.purchase_count}`);
        }, 400);
    } catch(err) {
        clearInterval(iv);
        loaderSection.classList.add('hidden');
        processBtn.disabled = false;
        showToast('❌', err.message);
    }
});

// ─── Tabs ───────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.currentTab = btn.dataset.tab;
        renderTable(btn.dataset.tab);
    });
});

// ─── Table Columns ──────────────────────────────────────────────────────
const SALE_COLUMNS = [
    {key:'no',label:'No.'},{key:'invoice_no',label:'Invoice No'},{key:'type',label:'TYPE'},
    {key:'invoice_date',label:'Invoice Date'},{key:'warehouse_name',label:'Warehouse'},
    {key:'warehouse_code',label:'WH Code'},{key:'gst_no',label:'GST No'},
    {key:'order_id',label:'Order ID'},{key:'item_asin',label:'Item Asin'},
    {key:'item_sku',label:'Item SKU'},{key:'item_name',label:'Item Name'},
    {key:'hsn_number',label:'HSN'},{key:'quantity',label:'Qty'},
    {key:'item_cost',label:'Item Cost'},{key:'gross',label:'Gross'},
    {key:'igst',label:'IGST%'},{key:'cgst',label:'CGST%'},{key:'sgst',label:'SGST%'},
    {key:'igst_amt',label:'IGST Amt'},{key:'cgst_amt',label:'CGST Amt'},
    {key:'sgst_amt',label:'SGST Amt'},{key:'invoice',label:'Invoice'},
    {key:'reason',label:'Reason'},{key:'zoho_status',label:'Zoho'},
    {key:'invoice_id',label:'Invoice ID'},{key:'state_code',label:'State Code'},
    {key:'sale_unique_id',label:'SALE UNIQUE ID'},
    {key:'calc_qty',label:'Qty*'},{key:'calc_cost',label:'Cost*'},
    {key:'calc_gross',label:'Gross*'},{key:'calc_igst',label:'IGST*'},
    {key:'calc_cgst',label:'CGST*'},{key:'calc_sgst',label:'SGST*'},
    {key:'calc_igst_amt',label:'IGST A*'},{key:'calc_cgst_amt',label:'CGST A*'},
    {key:'calc_sgst_amt',label:'SGST A*'},{key:'calc_invoice',label:'Invoice*'},
    {key:'state_code_short',label:'STATE'},
];

const PURCHASE_COLUMNS = [
    {key:'no',label:'No.'},{key:'invoice_no',label:'Invoice No'},
    {key:'warehouse_name',label:'Warehouse'},{key:'warehouse_code',label:'WH Code'},
    {key:'gst_no',label:'GST No'},{key:'order_id',label:'Order ID'},
    {key:'item_asin',label:'Item Asin'},{key:'item_sku',label:'Item SKU'},
    {key:'item_name',label:'Item Name'},{key:'hsn_number',label:'HSN'},
    {key:'quantity',label:'Qty'},{key:'item_cost',label:'Item Cost'},
    {key:'gross',label:'Gross'},{key:'igst',label:'IGST%'},
    {key:'cgst',label:'CGST%'},{key:'sgst',label:'SGST%'},
    {key:'igst_amt',label:'IGST Amt'},{key:'cgst_amt',label:'CGST Amt'},
    {key:'sgst_amt',label:'SGST Amt'},{key:'invoice',label:'Invoice'},
    {key:'purchase_unique_id',label:'PURCHASE UNIQUE ID'},
    {key:'calc_qty',label:'Qty*'},{key:'calc_cost',label:'Cost*'},
    {key:'calc_gross',label:'Gross*'},{key:'calc_igst',label:'IGST*'},
    {key:'calc_cgst',label:'CGST*'},{key:'calc_sgst',label:'SGST*'},
    {key:'calc_igst_amt',label:'IGST A*'},{key:'calc_cgst_amt',label:'CGST A*'},
    {key:'calc_sgst_amt',label:'SGST A*'},{key:'calc_total_amt',label:'Total Amt'},
];

function renderTable(tab) {
    const thead = document.getElementById('table-head');
    const tbody = document.getElementById('table-body');
    const cols = tab === 'sale' ? SALE_COLUMNS : PURCHASE_COLUMNS;
    const data = tab === 'sale' ? state.saleData : state.purchaseData;
    const thClass = tab === 'sale' ? 'sale-th' : 'purchase-th';
    const total = tab === 'sale' ? state.saleTotal : state.purchaseTotal;

    thead.innerHTML = '<tr>' + cols.map(c => `<th class="${thClass}">${c.label}</th>`).join('') + '</tr>';
    tbody.innerHTML = data.map(row =>
        '<tr>' + cols.map(c => {
            let v = row[c.key]; if (v==null) v='';
            if (typeof v==='number' && !Number.isInteger(v)) v=v.toFixed(2);
            return `<td title="${esc(String(v))}">${esc(String(v))}</td>`;
        }).join('') + '</tr>'
    ).join('');

    document.getElementById('showing-info').textContent = `Showing ${data.length} of ${formatNumber(total)} rows`;
    const btn = document.getElementById('load-more-btn');
    btn.classList.toggle('hidden', data.length >= total);
}

// ─── Load More ──────────────────────────────────────────────────────────
document.getElementById('load-more-btn').addEventListener('click', async () => {
    const btn = document.getElementById('load-more-btn');
    btn.textContent = 'Loading...'; btn.disabled = true;
    const offset = state.currentTab === 'sale' ? state.saleOffset : state.purchaseOffset;

    try {
        const res = await fetch(`/preview-more?offset=${offset}&limit=${state.pageSize}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const nd = state.currentTab === 'sale' ? data.sale_data : data.purchase_data;
        if (state.currentTab === 'sale') { state.saleData = state.saleData.concat(nd); state.saleOffset = state.saleData.length; }
        else { state.purchaseData = state.purchaseData.concat(nd); state.purchaseOffset = state.purchaseData.length; }
        renderTable(state.currentTab);
    } catch(e) { showToast('❌', e.message); }
    btn.textContent = 'Load More Rows'; btn.disabled = false;
});

// ─── Export ─────────────────────────────────────────────────────────────
exportBtn.addEventListener('click', async () => {
    exportBtn.disabled = true;
    exportBtn.querySelector('span').textContent = 'Generating...';
    try {
        const res = await fetch('/export');
        if (!res.ok) { const e = await res.json(); throw new Error(e.error||'Export failed'); }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'AJIO_MYNTRA_FLIPKART_Sale_Purchase.xlsx';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('✅', 'Excel downloaded!');
    } catch(e) { showToast('❌', e.message); }
    exportBtn.disabled = false;
    exportBtn.querySelector('span').textContent = 'Export .xlsx';
});

// ─── Clear Local Data ───────────────────────────────────────────────────
function clearAllData() { document.getElementById('modal-overlay').classList.remove('hidden'); }
function closeModal() { document.getElementById('modal-overlay').classList.add('hidden'); }

async function confirmClearData() {
    closeModal();
    showGlobalLoader('Clearing Data', 'Removing all processed records...');
    try {
        const res = await fetch('/clear', {method:'POST'});
        const data = await res.json();
        hideGlobalLoader();
        if (data.success) {
            state.saleData=[]; state.purchaseData=[];
            state.saleTotal=0; state.purchaseTotal=0;
            state.saleOffset=0; state.purchaseOffset=0;
            document.getElementById('sale-count').textContent = '0';
            document.getElementById('purchase-count').textContent = '0';
            document.getElementById('total-count').textContent = '0';
            document.getElementById('table-head').innerHTML = '';
            document.getElementById('table-body').innerHTML = '';
            document.getElementById('showing-info').textContent = 'Showing 0 rows';
            document.getElementById('load-more-btn').classList.add('hidden');
            resultSection.classList.add('hidden');
            document.getElementById('header-status').classList.add('hidden');
            showToast('✅', 'All data cleared!');
        } else { showToast('❌', data.error||'Clear failed'); }
    } catch(e) { hideGlobalLoader(); showToast('❌', e.message); }
}

// ─── Header Status ──────────────────────────────────────────────────────
function updateHeaderStatus(s, p) {
    const el = document.getElementById('header-status');
    const t = document.getElementById('header-status-text');
    if (s>0||p>0) { t.textContent=`${formatNumber(s)} sale • ${formatNumber(p)} purchase loaded`; el.classList.remove('hidden'); }
    else el.classList.add('hidden');
}

// ─── Auto Load ──────────────────────────────────────────────────────────
async function loadExistingData() {
    const overlay = document.getElementById('wakeup-overlay');
    const fill = document.getElementById('wakeup-progress-fill');
    const percentSpan = document.getElementById('wakeup-progress-percent');
    
    let progress = 0;
    let isAwake = false;
    
    // Smooth progress increment simulation
    const interval = setInterval(() => {
        if (isAwake) return;
        if (progress < 95) {
            progress += 1;
            if (fill) fill.style.width = progress + '%';
            if (percentSpan) percentSpan.textContent = progress;
        }
    }, 450); // Reaches 95% in about 42 seconds
    
    while (!isAwake) {
        try {
            console.log('[WAKEUP] Pinging server status...');
            const sRes = await fetch('/status');
            const st = await sRes.json();
            
            // Server responded successfully!
            isAwake = true;
            clearInterval(interval);
            
            // Fast forward progress bar to 100%
            progress = 100;
            if (fill) fill.style.width = '100%';
            if (percentSpan) percentSpan.textContent = '100';
            
            // Wait 500ms to show 100% state, then hide
            setTimeout(() => {
                if (overlay) overlay.classList.add('hidden');
            }, 500);
            
            // Process loaded data
            if (st.has_data) {
                state.saleTotal = st.sale_count; 
                state.purchaseTotal = st.purchase_count;
                document.getElementById('sale-count').textContent = formatNumber(st.sale_count);
                document.getElementById('purchase-count').textContent = formatNumber(st.purchase_count);
                document.getElementById('total-count').textContent = formatNumber(st.sale_count + st.purchase_count);
                if (st.financial_year) document.getElementById('fy-badge').textContent = `FY ${st.financial_year}`;

                const pRes = await fetch(`/preview-more?offset=0&limit=${state.pageSize}`);
                const pd = await pRes.json();
                if (!pd.error) {
                    state.saleData = pd.sale_data||[]; 
                    state.purchaseData = pd.purchase_data||[];
                    state.saleOffset = state.saleData.length; 
                    state.purchaseOffset = state.purchaseData.length;
                    resultSection.classList.remove('hidden');
                    renderTable('sale');
                    updateHeaderStatus(st.sale_count, st.purchase_count);
                }
            }
        } catch(e) {
            console.log('[WAKEUP] Backend still sleeping or offline. Retrying in 3 seconds...', e.message);
            // Wait 3 seconds before next ping attempt
            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }
}
loadExistingData();

// ═══════════════════════════════════════════════════════════════════════
// GOOGLE SHEETS — Hardcoded URL
// ═══════════════════════════════════════════════════════════════════════

function showGlobalLoader(t, s, percent = null) {
    const loader = document.getElementById('global-loader');
    const title = document.getElementById('global-loader-title');
    const status = document.getElementById('global-loader-status');
    const progressBar = document.getElementById('global-progress-bar');
    const progressFill = document.getElementById('global-progress-fill');

    title.textContent = t;
    status.textContent = s;
    loader.classList.remove('hidden');

    if (typeof percent === 'number' && percent >= 0) {
        progressBar.style.display = 'block';
        progressFill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    } else {
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
    }
}

function hideGlobalLoader() {
    const loader = document.getElementById('global-loader');
    const progressBar = document.getElementById('global-progress-bar');
    const progressFill = document.getElementById('global-progress-fill');

    loader.classList.add('hidden');
    progressBar.style.display = 'none';
    progressFill.style.width = '0%';
}

function updateGlobalLoaderProgress(percent, statusText = null) {
    const progressBar = document.getElementById('global-progress-bar');
    const progressFill = document.getElementById('global-progress-fill');
    const status = document.getElementById('global-loader-status');
    const displayPercent = Math.min(100, Math.max(0, percent));

    progressBar.style.display = 'block';
    progressFill.style.width = `${displayPercent}%`;
    status.textContent = statusText ? `${statusText} (${displayPercent}%)` : `${displayPercent}% complete`;
}
// ─── Financial Year Custom Dropdown ─────────────────────────────────────
function populateFYSelector() {
    const menu = document.getElementById('fy-dropdown-menu');
    const label = document.getElementById('fy-dropdown-label');
    if (!menu) return;
    const urls = getSavedFyUrls();
    const keys = Object.keys(urls).sort();
    menu.innerHTML = '';
    keys.forEach(fy => {
        const isActive = fy === state.currentFY;
        const item = document.createElement('div');
        item.className = 'fy-dropdown-item' + (isActive ? ' active' : '');
        item.innerHTML = `<span class="fy-check">${isActive ? '✓' : ''}</span> FY ${fy}`;
        item.onclick = () => {
            switchFinancialYear(fy);
            closeFYDropdown();
        };
        menu.appendChild(item);
    });
    if (label) label.textContent = `FY ${state.currentFY}`;
}

function toggleFYDropdown() {
    const dd = document.getElementById('fy-dropdown');
    const menu = document.getElementById('fy-dropdown-menu');
    if (!dd || !menu) return;
    const isOpen = dd.classList.contains('open');
    if (isOpen) {
        closeFYDropdown();
    } else {
        dd.classList.add('open');
        menu.classList.remove('hidden');
    }
}

function closeFYDropdown() {
    const dd = document.getElementById('fy-dropdown');
    const menu = document.getElementById('fy-dropdown-menu');
    if (dd) dd.classList.remove('open');
    if (menu) menu.classList.add('hidden');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dd = document.getElementById('fy-dropdown');
    if (dd && !dd.contains(e.target)) closeFYDropdown();
});

function switchFinancialYear(fy) {
    if (!fy || fy === state.currentFY) return;
    state.currentFY = fy;
    state.selectedSheet = '';
    const sel = document.getElementById('sheet-select');
    if (sel) sel.value = '';
    populateFYSelector();
    showToast('🔄', `Switched to FY ${fy}`);
    refreshSheetDropdown();
}

// Initialize FY selector on load
populateFYSelector();

// ─── Load Sheet Names ───────────────────────────────────────────────────
async function refreshSheetDropdown() {
    try {
        const res = await fetch(`${getActiveWebAppUrl()}?action=getSheetNames`);
        const r = await res.json();
        if (r.success) {
            const sel = document.getElementById('sheet-select');
            const syncSel = document.getElementById('sync-sheet-select');
            const curV = sel ? sel.value : '';
            const curSV = syncSel ? syncSel.value : '';

            if(sel) sel.innerHTML = '<option value="">-- Choose sheet --</option>';

            state.availableSheets = r.sheets || [];
            if (r.spreadsheetId) {
                state.spreadsheetIds[state.currentFY] = r.spreadsheetId;
            }
            r.sheets.forEach(sh => {
                const txt = `${sh.name} (${sh.rows} rows)`;
                if(sel) { const o=document.createElement('option'); o.value=sh.name; o.textContent=txt; sel.appendChild(o); }
            });

            // Render Google Sheets style tabs at the bottom
            const tabsBar = document.getElementById('sheet-tabs-bar');
            if (tabsBar) {
                tabsBar.innerHTML = '';
                r.sheets.forEach(sh => {
                    const tabEl = document.createElement('div');
                    tabEl.className = 'sheet-tab';
                    tabEl.dataset.name = sh.name;
                    tabEl.textContent = sh.name;
                    tabEl.addEventListener('click', () => {
                        setActiveSheetTab(sh.name);
                    });
                    tabsBar.appendChild(tabEl);
                });
            }

            // Find matching sheet for current FY
            const matchedFySheet = r.sheets.find(s => s.name.includes(state.currentFY || ''))?.name;
            const fallbackDef = (r.sheets.length > 0) ? r.sheets[0].name : '';
            const def = matchedFySheet || fallbackDef;

            if(sel) {
                if(curV && r.sheets.some(s=>s.name===curV)) {
                    setActiveSheetTab(curV);
                } else if(def) {
                    setActiveSheetTab(def);
                } else {
                    clearViewerTable();
                }
            }
            if(syncSel) {
                if(curSV && r.sheets.some(s=>s.name===curSV)) syncSel.value=curSV;
                else if(def) syncSel.value=def;
            }

        } else { showToast('⚠️', 'Sheets Error: ' + r.error); }
    } catch(e) {
        console.warn('[Sheet Connect Warning]', e);
        showToast('⚠️', 'Google Sheet URL not connected. Click ⚙️ Settings to configure URL.');
    }
}
refreshSheetDropdown();

function setActiveSheetTab(sheetName) {
    state.selectedSheet = sheetName;
    const sel = document.getElementById('sheet-select');
    if (sel) sel.value = sheetName;
    
    // Update active class on tab elements
    document.querySelectorAll('.sheet-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.name === sheetName);
    });
    
    document.getElementById('universal-search').value = ''; // Clear search on sheet change
    if (sheetName) loadSheetData(3);
    else clearViewerTable();
}

function onSheetSelectionChange() {
    const sel = document.getElementById('sheet-select');
    setActiveSheetTab(sel.value);
}

async function openDownloadSheetModal() {
    const modal = document.getElementById('download-sheet-modal');
    const list = document.getElementById('download-sheet-list');
    const selectAll = document.getElementById('download-sheet-select-all');

    if (!modal || !list) return;
    list.innerHTML = '<div style="color:var(--text-muted); padding:8px;">Loading sheets...</div>';
    if (selectAll) selectAll.checked = false;
    modal.classList.remove('hidden');

    try {
        const urls = getSavedFyUrls();
        const fyKeys = Object.keys(urls).sort();

        const promises = fyKeys.map(async (fy) => {
            const url = urls[fy];
            if (!url || !url.trim()) return null;
            try {
                const res = await fetch(`${url.trim()}?action=getSheetNames`);
                const r = await res.json();
                if (r.success && r.sheets) {
                    return { fy, url: url.trim(), sheets: r.sheets };
                }
            } catch (err) {
                console.warn(`Failed to load sheets for FY ${fy}:`, err);
            }
            return null;
        });

        const results = await Promise.all(promises);

        list.innerHTML = '';
        let count = 0;

        results.forEach(resObj => {
            if (resObj && resObj.sheets) {
                resObj.sheets.forEach(sheet => {
                    count++;
                    const wrapper = document.createElement('div');
                    wrapper.style.marginBottom = '10px';
                    wrapper.style.display = 'flex';
                    wrapper.style.alignItems = 'center';
                    wrapper.style.gap = '10px';

                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.id = `download-sheet-${count}`;
                    checkbox.value = sheet.name;
                    checkbox.dataset.url = resObj.url;
                    checkbox.dataset.fy = resObj.fy;
                    checkbox.style.cursor = 'pointer';

                    const label = document.createElement('label');
                    label.htmlFor = checkbox.id;
                    label.style.cursor = 'pointer';
                    label.style.display = 'flex';
                    label.style.justifyContent = 'space-between';
                    label.style.width = '100%';
                    label.style.fontSize = '0.9rem';
                    label.innerHTML = `<span><strong>FY ${resObj.fy}</strong> ── ${sheet.name}</span><span style="color:var(--text-muted); font-size:0.85rem;">${sheet.rows} rows</span>`;

                    wrapper.appendChild(checkbox);
                    wrapper.appendChild(label);
                    list.appendChild(wrapper);
                });
            }
        });

        if (count === 0) {
            list.innerHTML = '<div style="color:var(--text-muted);">No sheets available to download.</div>';
        }
    } catch(e) {
        console.error(e);
        list.innerHTML = '<div style="color:var(--text-muted);">Failed to load sheet list.</div>';
    }
}

function closeDownloadSheetModal() {
    document.getElementById('download-sheet-modal').classList.add('hidden');
}

function toggleDownloadSheetSelectAll(checked) {
    const list = document.getElementById('download-sheet-list');
    if (!list) return;
    list.querySelectorAll('input[type="checkbox"]').forEach(chk => {
        chk.checked = checked;
    });
}

function getSelectedDownloadSheets() {
    const list = document.getElementById('download-sheet-list');
    if (!list) return [];
    return Array.from(list.querySelectorAll('input[type="checkbox"]:checked'))
        .map(chk => ({
            name: chk.value,
            url: chk.dataset.url || getActiveWebAppUrl(),
            fy: chk.dataset.fy || ''
        }));
}

async function downloadSelectedSheets() {
    const selectedItems = getSelectedDownloadSheets();
    if (!selectedItems.length) {
        showToast('⚠️', 'Please select at least one sheet to download.');
        return;
    }

    closeDownloadSheetModal();
    showGlobalLoader('Preparing Excel', `Downloading ${selectedItems.length} sheet(s)...`, 0);

    try {
        if (typeof XLSX === 'undefined') {
            throw new Error('XLSX library is not loaded');
        }
        const wb = XLSX.utils.book_new();
        const usedTabNames = new Set();

        for (let i = 0; i < selectedItems.length; i++) {
            const item = selectedItems[i];
            const sheetName = item.name;
            const targetUrl = item.url;
            const fy = item.fy;
            
            let startRow = 3;
            const pageSize = 5000;
            const rows = [];
            let hasMore = true;
            let totalRows = 0;
            
            while (hasMore) {
                const res = await fetch(`${targetUrl}?action=getSheetData&sheetName=${encodeURIComponent(sheetName)}&startRow=${startRow}&numRows=${pageSize}`);
                const data = await res.json();
                if (!data.success) {
                    throw new Error(`Failed to load sheet: ${sheetName}`);
                }
                
                totalRows = data.totalRows || 0;
                
                if (startRow === 3 && Array.isArray(data.headers) && data.headers.length > 0) {
                    data.headers.forEach(headerRow => {
                        rows.push(headerRow.map(cell => cell == null ? '' : cell));
                    });
                }
                
                if (Array.isArray(data.data) && data.data.length > 0) {
                    data.data.forEach(row => {
                        rows.push(row.map(cell => cell == null ? '' : cell));
                    });
                    startRow += data.data.length;
                    
                    const currentProgress = totalRows > 0 ? Math.min(100, Math.round(((startRow - 3) / totalRows) * 100)) : 100;
                    const overallPercent = totalRows > 0 ? Math.round(((i + (startRow - 3) / totalRows) / selectedItems.length) * 100) : Math.round(((i + 1) / selectedItems.length) * 100);
                    updateGlobalLoaderProgress(
                        overallPercent,
                        `Downloading ${sheetName} (${fy}): ${currentProgress}% (${startRow - 3} of ${totalRows} rows)...`
                    );
                } else {
                    hasMore = false;
                }
                
                if (startRow - 3 >= totalRows || !data.data || data.data.length === 0) {
                    hasMore = false;
                }
            }

            const rawName = fy ? `${fy} - ${sheetName}` : sheetName;
            const safeName = rawName.substring(0, 31);
            let finalName = safeName;
            let idx = 1;
            while (usedTabNames.has(finalName)) {
                const suffix = `_${idx}`;
                finalName = safeName.substring(0, 31 - suffix.length) + suffix;
                idx += 1;
            }
            usedTabNames.add(finalName);

            const ws = XLSX.utils.aoa_to_sheet(rows.length ? rows : [[]]);
            XLSX.utils.book_append_sheet(wb, ws, finalName);
        }

        const dateStr = new Date().toISOString().split('T')[0];
        XLSX.writeFile(wb, `Google_Sheets_Export_${dateStr}.xlsx`);
        hideGlobalLoader();
        showToast('✅', 'Excel download complete!');
    } catch(err) {
        hideGlobalLoader();
        console.error('Download error:', err);
        showToast('❌', 'Download failed: ' + (err.message || err));
    }
}

function onSheetRowsChange() {
    const v = parseInt(document.getElementById('sheet-rows-per-page').value);
    state.viewerPageSize = v;
    if (document.getElementById('universal-search').value.trim()) runUniversalSearch();
    else if (state.selectedSheet) loadSheetData(3);
}

// ─── Load Sheet Data (Fast GViz with Apps Script Fallback) ───────────────────
async function loadSheetData(startRow) {
    if (!state.selectedSheet) return;
    state.searchToken++;
    state.viewerStartRow = startRow;
    showGlobalLoader('Loading Sheet', `Fetching from ${state.selectedSheet}...`);

    const offset = Math.max(0, (startRow || 3) - 3);
    const limit = state.viewerPageSize || 25;
    const spreadsheetId = getSpreadsheetIdForFY(state.currentFY);

    let gvizSuccess = false;
    if (spreadsheetId) {
        try {
            const gvizQuery = encodeURIComponent(`limit ${limit} offset ${offset}`);
            const gvizUrl = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/gviz/tq?tqx=out:json&sheet=${encodeURIComponent(state.selectedSheet)}&tq=${gvizQuery}`;
            const ctrl = new AbortController();
            const timeoutId = setTimeout(() => ctrl.abort(), 8000);
            const res = await fetch(gvizUrl, { signal: ctrl.signal });
            clearTimeout(timeoutId);

            if (res.ok) {
                const text = await res.text();
                const jsonStart = text.indexOf('{');
                const jsonEnd = text.lastIndexOf('}');
                if (jsonStart !== -1 && jsonEnd !== -1) {
                    const parsed = JSON.parse(text.substring(jsonStart, jsonEnd + 1));
                    if (parsed.status === 'ok' && parsed.table) {
                        const table = parsed.table;
                        const headers = (table.cols || []).map(c => c.label || c.id || '');
                        const rows = (table.rows || []).map(r => {
                            return (r.c || []).map(cell => {
                                if (!cell) return '';
                                return cell.f !== undefined ? cell.f : (cell.v !== null ? cell.v : '');
                            });
                        });

                        const curSheetObj = state.availableSheets.find(s => s.name === state.selectedSheet);
                        const totalRows = curSheetObj ? Math.max(0, curSheetObj.rows - 2) : (rows.length + offset);

                        hideGlobalLoader();
                        state.viewerHeaders = [headers];
                        state.viewerRows = rows;
                        state.viewerAllRows = rows;
                        state.viewerTotalRows = totalRows;
                        renderViewerTable();
                        gvizSuccess = true;
                    }
                }
            }
        } catch(gvizErr) {
            console.warn('[GViz Fast Load failed, falling back to Apps Script]', gvizErr);
        }
    }

    if (!gvizSuccess) {
        try {
            const res = await fetch(`${getActiveWebAppUrl()}?action=getSheetData&sheetName=${encodeURIComponent(state.selectedSheet)}&startRow=${startRow}&numRows=${state.viewerPageSize}`);
            const r = await res.json();
            hideGlobalLoader();

            if (r.success) {
                state.viewerHeaders = r.headers||[];
                state.viewerRows = r.data||[];
                state.viewerAllRows = r.data||[];
                state.viewerTotalRows = r.totalRows||0;
                renderViewerTable();
            } else {
                showToast('❌', 'Data Error: '+r.error);
                clearViewerTable();
            }
        } catch(e) {
            hideGlobalLoader();
            showToast('❌', 'Network error');
            clearViewerTable();
        }
    }
}

// ─── Render Viewer Table ────────────────────────────────────────────────
function renderViewerTable() {
    const thead = document.getElementById('viewer-thead');
    const tbody = document.getElementById('viewer-tbody');
    const pInfo = document.getElementById('page-info');
    const tInfo = document.getElementById('viewer-total-info');

    if (state.viewerHeaders.length === 0) {
        thead.innerHTML=''; tbody.innerHTML='<tr><td style="text-align:center;color:var(--text-muted);">Sheet is empty.</td></tr>';
        document.getElementById('prev-btn').disabled = true;
        document.getElementById('next-btn').disabled = true;
        return;
    }

    const hdr = state.viewerHeaders[1]||state.viewerHeaders[0]||[];
    thead.innerHTML = `<tr>${hdr.map(h=>`<th>${h}</th>`).join('')}</tr>`;

    if (state.viewerRows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${hdr.length}" style="text-align:center;color:var(--text-muted);">No records.</td></tr>`;
    } else {
        tbody.innerHTML = state.viewerRows.map(row =>
            `<tr>${row.map(v => {
                let d = (v==null)?'':v;
                if(typeof d==='number' && !Number.isInteger(d)) d=d.toFixed(2);
                return `<td title="${esc(String(d))}">${esc(String(d))}</td>`;
            }).join('')}</tr>`
        ).join('');
    }

    const endRow = Math.min(state.viewerStartRow + state.viewerPageSize - 1, state.viewerTotalRows + 2);
    pInfo.textContent = `${state.viewerStartRow} - ${endRow}`;
    tInfo.textContent = `Total: ${formatNumber(state.viewerTotalRows)} rows`;

    document.getElementById('prev-btn').disabled = (state.viewerStartRow <= 3);
    document.getElementById('next-btn').disabled = (endRow >= state.viewerTotalRows + 2);
}

function renderViewerSearchResults(totalMatches, returnedRows, limited) {
    renderViewerTable();
    document.getElementById('page-info').textContent = `Search`;
    document.getElementById('prev-btn').disabled = true;
    document.getElementById('next-btn').disabled = true;

    const shown = formatNumber(returnedRows || state.viewerRows.length);
    const total = formatNumber(totalMatches || 0);
    document.getElementById('viewer-total-info').textContent = limited
        ? `Search: showing ${shown} of ${total} matches`
        : `Search: ${total} match${totalMatches !== 1 ? 'es' : ''} found`;
}

function changePage(dir) {
    let next = state.viewerStartRow + (dir * state.viewerPageSize);
    if (next < 3) next = 3;
    document.getElementById('universal-search').value = ''; // Clear search on page change
    loadSheetData(next);
}

function clearViewerTable() {
    document.getElementById('viewer-thead').innerHTML='';
    document.getElementById('viewer-tbody').innerHTML='';
    document.getElementById('page-info').textContent='0 - 0';
    document.getElementById('viewer-total-info').textContent='Select a sheet.';
    document.getElementById('prev-btn').disabled=true;
    document.getElementById('next-btn').disabled=true;
}

// ─── Universal Search ───────────────────────────────────────────────────
function handleUniversalSearch() {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(runUniversalSearch, 350);
}

async function runUniversalSearch() {
    const input = document.getElementById('universal-search');
    const q = input.value.trim();

    if (!q) {
        if (state.selectedSheet) loadSheetData(state.viewerStartRow || 3);
        return;
    }
    if (!state.selectedSheet) {
        showToast('⚠️', 'Select a sheet first');
        return;
    }

    const token = ++state.searchToken;
    document.getElementById('viewer-total-info').textContent = 'Searching full sheet...';
    document.getElementById('prev-btn').disabled = true;
    document.getElementById('next-btn').disabled = true;

    try {
        const maxResults = 1000;
        const url = `${getActiveWebAppUrl()}?action=searchSheetData&sheetName=${encodeURIComponent(state.selectedSheet)}&query=${encodeURIComponent(q)}&maxResults=${maxResults}`;
        const res = await fetch(url);
        const r = await res.json();
        if (token !== state.searchToken) return;

        if (r.success) {
            state.viewerHeaders = r.headers || [];
            state.viewerRows = r.data || [];
            state.viewerAllRows = r.data || [];
            state.viewerTotalRows = r.totalRows || 0;
            renderViewerSearchResults(r.totalMatches || 0, r.returnedRows || state.viewerRows.length, !!r.limited);
        } else {
            showToast('❌', 'Search Error: ' + r.error);
        }
    } catch(e) {
        if (token === state.searchToken) showToast('❌', 'Search network error');
    }
}

// ─── Clear Sheet ────────────────────────────────────────────────────────
function triggerClearSheetWarning() {
    if (!state.selectedSheet) { showToast('⚠️', 'Select a sheet first!'); return; }
    document.getElementById('modal-sheet-name').textContent = state.selectedSheet;
    document.getElementById('clear-sheet-modal').classList.remove('hidden');
}
function closeClearSheetModal() { document.getElementById('clear-sheet-modal').classList.add('hidden'); }

async function confirmClearSheet() {
    closeClearSheetModal();
    showGlobalLoader('Clearing Sheet', `Wiping ${state.selectedSheet}...`);
    try {
        const res = await fetch(`${getActiveWebAppUrl()}?action=clearSheetData&sheetName=${encodeURIComponent(state.selectedSheet)}`);
        const r = await res.json();
        hideGlobalLoader();
        if (r.success) { showToast('✅', `Cleared: ${state.selectedSheet}`); refreshSheetDropdown(); }
        else showToast('❌', 'Error: '+r.error);
    } catch(e) { hideGlobalLoader(); showToast('❌', 'Network error'); }
}

// ─── Sync Modal ─────────────────────────────────────────────────────────
const syncBtn = document.getElementById('sync-sheet-btn');
if(syncBtn) syncBtn.addEventListener('click', openSyncModal);

function openSyncModal() { document.getElementById('sync-modal-overlay').classList.remove('hidden'); refreshSyncDropdown(); }
function closeSyncModal() { document.getElementById('sync-modal-overlay').classList.add('hidden'); }

async function refreshSyncDropdown() {
    try {
        const sel = document.getElementById('sync-sheet-select');
        if (!sel) return;
        const cur = sel.value;
        sel.innerHTML = '<option value="">-- Loading target sheets... --</option>';

        const urls = getSavedFyUrls();
        const fyKeys = Object.keys(urls).sort();

        let optionsHtml = '<option value="">-- Choose Target Sheet --</option>';

        const promises = fyKeys.map(async (fy) => {
            const url = urls[fy];
            if (!url || !url.trim()) return null;
            try {
                const res = await fetch(`${url.trim()}?action=getSheetNames`);
                const r = await res.json();
                if (r.success && r.sheets) {
                    return { fy, url: url.trim(), sheets: r.sheets };
                }
            } catch (err) {
                console.warn(`Failed to fetch sheets for FY ${fy}:`, err);
            }
            return null;
        });

        const results = await Promise.all(promises);

        results.forEach(resObj => {
            if (resObj && resObj.sheets) {
                resObj.sheets.forEach(sh => {
                    const label = `FY ${resObj.fy} ── ${sh.name} (${sh.rows} rows)`;
                    optionsHtml += `<option value="${esc(sh.name)}" data-url="${esc(resObj.url)}" data-fy="${esc(resObj.fy)}">${esc(label)}</option>`;
                });
            }
        });

        sel.innerHTML = optionsHtml;

        const allOpts = Array.from(sel.options);
        const curMatch = allOpts.find(o => o.value === cur);
        const fyMatch = allOpts.find(o => o.dataset?.fy === state.currentFY);
        if (curMatch) {
            sel.value = cur;
        } else if (fyMatch) {
            sel.value = fyMatch.value;
        } else if (allOpts.length > 1) {
            sel.value = allOpts[1].value;
        }
    } catch(e) { console.error(e); }
}

async function safeFetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const text = await response.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch (err) {
        if (text.includes('<!DOCTYPE') || text.includes('<html') || text.includes('<html>')) {
            if (response.status === 502 || response.status === 503 || response.status === 504) {
                throw new Error(`Server abhi restart / deploy ho raha hai (Render ${response.status}). Kripya 20-30 seconds wait karke page refresh karein aur dubara Sync karein.`);
            }
            throw new Error(`Server ne HTML page return kiya (HTTP ${response.status}). Kripya page refresh karke dubara try karein.`);
        }
        throw new Error(text.substring(0, 150) || `Server error (${response.status})`);
    }
    return { ok: response.ok, status: response.status, data };
}

async function startSyncToGoogleSheets() {
    const sel = document.getElementById('sync-sheet-select');
    const sheetName = sel?.value||'';
    const selectedOpt = sel?.options[sel?.selectedIndex];
    const activeUrl = selectedOpt?.dataset?.url || getActiveWebAppUrl();
    const mode = document.querySelector('input[name="sync-mode"]:checked')?.value||'append';
    if (!sheetName) { showToast('⚠️', 'Select a target sheet'); return; }

    closeSyncModal();
    
    // Set up progress bar
    const progBar = document.getElementById('global-progress-bar');
    const progFill = document.getElementById('global-progress-fill');
    if (progBar) progBar.style.display = 'block';
    if (progFill) progFill.style.width = '0%';
    
    showGlobalLoader('Preparing Sync', 'Fetching and deduplicating data...');
    
    try {
        // Fetch deduplicated counts from local backend (creates temp tables)
        const { ok: okPrep, data: syncData } = await safeFetchJson('/api/prepare-sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ webAppUrl: activeUrl, sheetName, mode })
        });
        if (!okPrep || syncData.error) throw new Error(syncData.error || 'Deduplication failed');
        
        const toSyncSale = syncData.toSyncSale || 0;
        const toSyncPurchase = syncData.toSyncPurchase || 0;
        
        const maxRows = Math.max(toSyncSale, toSyncPurchase);
        if (maxRows === 0) {
            hideGlobalLoader();
            if (progBar) progBar.style.display = 'none';
            // Show duplicate warning/info
            document.getElementById('success-sale-sent').textContent = '0';
            document.getElementById('success-purchase-sent').textContent = '0';
            document.getElementById('success-sale-skipped').textContent = formatNumber(syncData.skippedSale);
            document.getElementById('success-purchase-skipped').textContent = formatNumber(syncData.skippedPurchase);
            document.getElementById('success-skipped-container').style.display = 'block';
            document.getElementById('sync-success-modal').classList.remove('hidden');
            showToast('ℹ️', 'No new records to sync (all duplicates skipped)');
            refreshSheetDropdown();
            return;
        }
        
        // Chunk sizes and total calculations (1000 rows for safer large data transfer)
        const chunkSize = 1000;
        const totalBatches = Math.ceil(maxRows / chunkSize);
        
        for (let i = 1; i <= totalBatches; i++) {
            const startIdx = (i - 1) * chunkSize;
            
            const percent = Math.round((i / totalBatches) * 100);
            showGlobalLoader('Syncing to Google Sheets', `Uploading Batch ${i} of ${totalBatches}... (${percent}%)`);
            if (progFill) progFill.style.width = percent + '%';
            
            // Fetch chunk from SQLite
            const { ok: okChunk, data: chunkData } = await safeFetchJson(`/api/get-sync-chunk?offset=${startIdx}&limit=${chunkSize}`);
            if (!okChunk || chunkData.error) throw new Error(chunkData.error || `Failed to load batch ${i}`);
            
            const saleChunk = chunkData.saleRows || [];
            const purchaseChunk = chunkData.purchaseRows || [];
            
            // Check action type: Overwrite + First batch should clear sheet.
            const actionType = (mode === 'overwrite' && i === 1) ? 'writeData' : 'appendBatch';
            const payload = {
                action: actionType,
                sheetName: sheetName,
                saleRows: saleChunk,
                purchaseRows: purchaseChunk,
                isAppend: !(mode === 'overwrite' && i === 1),
                batchIndex: i,
                totalBatches: totalBatches
            };
            
            // Call Google Apps Script via backend proxy to bypass CORS / redirect errors
            console.log(`[SYNC] Uploading batch ${i}/${totalBatches} (Sales: ${saleChunk.length}, Purchases: ${purchaseChunk.length})...`);
            
            const remaining = Math.max(0, totalBatches - i);
            const liveTimer = setInterval(() => {
                const now = new Date().toLocaleTimeString();
                showGlobalLoader('Syncing Data', `[${now}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);
            }, 1000);
            
            let okSend = false, resJSON = null;
            try {
                const res = await safeFetchJson('/api/send-sync-chunk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        webAppUrl: activeUrl,
                        payload: payload
                    })
                });
                okSend = res.ok;
                resJSON = res.data;
            } finally {
                clearInterval(liveTimer);
            }
            
            if (!okSend || !resJSON.success) {
                console.error(`[SYNC ERROR] Batch ${i}/${totalBatches} failed:`, resJSON);
                throw new Error(resJSON.error || `Batch ${i} failed`);
            }
            const nowTime = new Date().toLocaleTimeString();
            console.log(`[${nowTime}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);
            showGlobalLoader('Syncing Data', `[${nowTime}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);
        }
        
        // Done! Hide loader and show success modal
        hideGlobalLoader();
        if (progBar) progBar.style.display = 'none';
        
        document.getElementById('success-sale-sent').textContent = formatNumber(syncData.toSyncSale);
        document.getElementById('success-purchase-sent').textContent = formatNumber(syncData.toSyncPurchase);
        document.getElementById('success-sale-skipped').textContent = formatNumber(syncData.skippedSale);
        document.getElementById('success-purchase-skipped').textContent = formatNumber(syncData.skippedPurchase);
        document.getElementById('success-skipped-container').style.display = (mode === 'append') ? 'block' : 'none';
        
        document.getElementById('sync-success-modal').classList.remove('hidden');
        showToast('✅', 'Sync completed successfully!');
        refreshSheetDropdown();
        
        // Silently clear local database and reset UI since data is successfully synced
        try {
            await fetch('/clear', { method: 'POST' });
            state.saleData=[]; state.purchaseData=[];
            state.saleTotal=0; state.purchaseTotal=0;
            state.saleOffset=0; state.purchaseOffset=0;
            document.getElementById('sale-count').textContent = '0';
            document.getElementById('purchase-count').textContent = '0';
            document.getElementById('total-count').textContent = '0';
            document.getElementById('table-head').innerHTML = '';
            document.getElementById('table-body').innerHTML = '';
            document.getElementById('showing-info').textContent = 'Showing 0 rows';
            document.getElementById('load-more-btn').classList.add('hidden');
            resultSection.classList.add('hidden');
            document.getElementById('header-status').classList.add('hidden');
        } catch (e) {
            console.error('Silent clear error:', e);
        }
        
    } catch(e) {
        console.error('[SYNC FAILED]:', e);
        hideGlobalLoader();
        if (progBar) progBar.style.display = 'none';
        showToast('❌', 'Sync Error: ' + e.message);
        document.getElementById('sync-modal-overlay').classList.remove('hidden');
    }
}

function closeSuccessModal() {
    document.getElementById('sync-success-modal').classList.add('hidden');
}

// ─── Helpers ────────────────────────────────────────────────────────────
function formatNumber(n) { return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

function showToast(icon, msg) {
    if (icon === '❌' || icon === '⚠️') {
        showErrorModal(msg);
        return;
    }
    const t = document.getElementById('toast');
    document.getElementById('toast-icon').textContent = icon;
    document.getElementById('toast-message').textContent = msg;
    t.classList.remove('hidden');
    t.classList.toggle('error', icon==='❌');
    clearTimeout(window._tt);
    window._tt = setTimeout(() => t.classList.add('hidden'), 5000);
}

function showErrorModal(msg, title) {
    const overlay = document.getElementById('error-modal-overlay');
    const msgEl = document.getElementById('error-modal-message');
    const titleEl = document.getElementById('error-modal-title');
    if (titleEl) {
        if (title) {
            titleEl.textContent = title;
        } else if (msg && (msg.toLowerCase().includes('sheet') || msg.toLowerCase().includes('data error'))) {
            titleEl.textContent = 'Google Sheets Error';
        } else {
            titleEl.textContent = 'Notice / Error';
        }
    }
    if (overlay && msgEl) {
        msgEl.textContent = msg;
        overlay.classList.remove('hidden');
        overlay.style.display = 'flex';
    } else {
        alert(msg);
    }
}

function closeErrorModal() {
    const overlay = document.getElementById('error-modal-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
        overlay.style.display = 'none';
    }
}

// ─── Multi-Year Settings UI & Password Security ──────────────────────────
const SETTINGS_PASS_CODE = 'Ajx7@938270';

function openSettingsModal() {
    // Open Security Password Prompt Modal
    const passInput = document.getElementById('settings-pass-input');
    if (passInput) passInput.value = '';
    const errDiv = document.getElementById('auth-error-msg');
    if (errDiv) errDiv.style.display = 'none';

    const authModal = document.getElementById('settings-auth-modal');
    if (authModal) {
        authModal.classList.remove('hidden');
        authModal.style.display = 'flex';
        setTimeout(() => passInput?.focus(), 150);
    } else {
        showActualSettingsModal();
    }
}

function closeSettingsAuthModal() {
    const authModal = document.getElementById('settings-auth-modal');
    if (authModal) {
        authModal.classList.add('hidden');
        authModal.style.display = 'none';
    }
}

function verifySettingsPassword(e) {
    if (e) e.preventDefault();
    const passInput = document.getElementById('settings-pass-input');
    const inputVal = passInput ? passInput.value.trim() : '';

    if (inputVal === SETTINGS_PASS_CODE) {
        closeSettingsAuthModal();
        showActualSettingsModal();
    } else {
        const errDiv = document.getElementById('auth-error-msg');
        if (errDiv) errDiv.style.display = 'block';
        showToast('❌', 'Incorrect Security Password Code!');
        if (passInput) {
            passInput.value = '';
            passInput.focus();
        }
    }
}

function showActualSettingsModal() {
    const modal = document.getElementById('settings-modal-overlay');
    const container = document.getElementById('fy-url-settings-list');
    if (!modal) {
        console.error('[Settings] Modal element #settings-modal-overlay not found');
        return;
    }

    if (container) {
        container.innerHTML = '';
        const urls = getSavedFyUrls();
        const sheetUrls = getSavedFySheetUrls();
        const allKeys = Array.from(new Set([...Object.keys(urls), ...Object.keys(sheetUrls)])).sort();
        if (allKeys.length === 0) {
            allKeys.push('2025-26', '2026-27');
        }

        allKeys.forEach(fy => {
            addFYSettingRowElement(fy, urls[fy] || '', sheetUrls[fy] || '');
        });
    }

    modal.classList.remove('hidden');
    modal.style.display = 'flex';
}

function closeSettingsModal() {
    const modal = document.getElementById('settings-modal-overlay');
    if (modal) {
        modal.classList.add('hidden');
        modal.style.display = 'none';
    }
}

function addFYSettingRowElement(fy = '', webAppUrl = '', sheetUrl = '') {
    const container = document.getElementById('fy-url-settings-list');
    if (!container) return;

    const div = document.createElement('div');
    div.className = 'fy-setting-item';
    div.style.cssText = 'background:var(--bg-secondary); padding:14px; border-radius:var(--radius-md); border:1px solid var(--border-glass); display:flex; flex-direction:column; gap:10px;';
    div.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:8px;">
                <label style="font-size:0.75rem; color:var(--text-muted); font-weight:700; text-transform:uppercase; letter-spacing:0.04em;">Financial Year:</label>
                <input type="text" class="fy-key-input compact-select" value="${esc(fy)}" placeholder="2026-27" style="font-weight:bold; width:110px; padding:4px 8px;">
            </div>
            <button type="button" class="btn btn-danger-outline btn-sm" onclick="this.closest('.fy-setting-item').remove()" style="padding:3px 8px; font-size:0.75rem;" title="Remove this FY">🗑️ Remove</button>
        </div>
        <div style="display:flex; flex-direction:column; gap:8px;">
            <div>
                <label style="font-size:0.72rem; color:var(--text-secondary); font-weight:600; display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span>📤 Google Web App URL <span style="font-weight:normal; color:var(--text-muted);">(Used for Data Adding / Syncing)</span></span>
                </label>
                <input type="text" class="fy-url-input search-input" value="${esc(webAppUrl)}" placeholder="https://script.google.com/macros/s/.../exec" style="width:100%; font-size:0.8rem; padding:6px 10px;">
            </div>
            <div>
                <label style="font-size:0.72rem; color:var(--accent-purchase); font-weight:600; display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span>⚡ Google Sheet Direct Link <span style="font-weight:normal; color:var(--text-muted);">(Superfast Viewer — Anyone with link: Viewer)</span></span>
                </label>
                <input type="text" class="fy-sheet-url-input search-input" value="${esc(sheetUrl)}" placeholder="https://docs.google.com/spreadsheets/d/.../edit" style="width:100%; font-size:0.8rem; padding:6px 10px; border-color:rgba(16, 185, 129, 0.4);">
            </div>
        </div>
    `;
    container.appendChild(div);
}

function addNewFYSettingRow() {
    addFYSettingRowElement('', '', '');
}

async function saveSettings() {
    const items = document.querySelectorAll('.fy-setting-item');
    const urls = {};
    const sheetUrls = {};
    items.forEach(item => {
        const fy = item.querySelector('.fy-key-input')?.value?.trim();
        const url = item.querySelector('.fy-url-input')?.value?.trim();
        const sheetUrl = item.querySelector('.fy-sheet-url-input')?.value?.trim();
        if (fy) {
            urls[fy] = url || '';
            sheetUrls[fy] = sheetUrl || '';
        }
    });
    saveFyUrls(urls);
    saveFySheetUrls(sheetUrls);
    try {
        await fetch('/api/save-fy-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls, sheet_urls: sheetUrls })
        });
    } catch(e) {
        console.error('[FY SETTINGS] Failed to sync settings to server:', e);
    }
    closeSettingsModal();
    showToast('✅', 'Settings Saved! Fast Viewer is active.');
    populateFYSelector();
    refreshSheetDropdown();
    refreshSyncDropdown();
}


Object.assign(window, {
    clearAllData,
    closeModal,
    confirmClearData,
    onSheetSelectionChange,
    onSheetRowsChange,
    loadSheetData,
    handleUniversalSearch,
    triggerClearSheetWarning,
    changePage,
    startSyncToGoogleSheets,
    closeSyncModal,
    confirmClearSheet,
    closeClearSheetModal,
    closeSuccessModal,
    openSettingsModal,
    closeSettingsModal,
    closeSettingsAuthModal,
    verifySettingsPassword,
    addNewFYSettingRow,
    saveSettings,
    switchFinancialYear,
    toggleFYDropdown
});
