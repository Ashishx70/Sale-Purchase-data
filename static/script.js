/* ═══════════════════════════════════════════════════════════════════════

   AJIO • MYNTRA • FLIPKART — Sale & Purchase Processor

   Frontend Logic — Slim Upload, Full Width, Universal Search

   ═══════════════════════════════════════════════════════════════════════ */



const DEFAULT_WEB_APP_URL_25_26 = 'https://script.google.com/macros/s/AKfycbwNUZf-kOwrze7bJOa89vHU1J2atjsyCTt3lQ7E15KJptTsBJ3g4tUH0MqnhSt-LHhoCw/exec';

const DEFAULT_WEB_APP_URL_26_27 = 'https://script.google.com/macros/s/AKfycbyWMb69Xfk-Gkkp5Ye5mYCE8DoFUG0ua804LBlLErACpGPBAh1yZc3UhaIcRWvaiMGA/exec';



const DEFAULT_SHEET_URL_25_26 = 'https://docs.google.com/spreadsheets/d/1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To/edit';

const DEFAULT_SHEET_URL_26_27 = 'https://docs.google.com/spreadsheets/d/1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w/edit';

const DEFAULT_SHEET_URL_26_27_1 = 'https://docs.google.com/spreadsheets/d/1wcnhQnTZruaVNDMJbg3ssCskDV-7WmKLDXX8Q6YgvU4/edit?usp=sharing';



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

                if (!parsed['2026-27-1']) parsed['2026-27-1'] = DEFAULT_SHEET_URL_26_27_1;

                return parsed;

            }

        }

    } catch(e) {}

    return {

        '2025-26': DEFAULT_SHEET_URL_25_26,

        '2026-27': DEFAULT_SHEET_URL_26_27,

        '2026-27-1': DEFAULT_SHEET_URL_26_27_1

    };

}



function saveFySheetUrls(sheetUrlsObj) {

    try {

        localStorage.setItem('sale_purchase_fy_sheet_urls', JSON.stringify(sheetUrlsObj));

    } catch(e) {}

}

const DEFAULT_FY_ROW_COUNTS = {
    '2026-27': 157945,
    '2025-26': 44809,
    '2026-27-1': 3944
};

function getSavedFyRowCounts() {
    try {
        const stored = localStorage.getItem('sale_purchase_fy_row_counts');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed && typeof parsed === 'object') {
                if (!parsed['2026-27'] || parseInt(parsed['2026-27'], 10) <= 0) {
                    parsed['2026-27'] = 157945;
                }
                return Object.assign({}, DEFAULT_FY_ROW_COUNTS, parsed);
            }
        }
    } catch(e) {}
    return Object.assign({}, DEFAULT_FY_ROW_COUNTS);
}

function saveFyRowCounts(countsObj) {
    try {
        const safe = Object.assign({}, DEFAULT_FY_ROW_COUNTS, countsObj || {});
        if (!safe['2026-27'] || parseInt(safe['2026-27'], 10) <= 0) {
            safe['2026-27'] = 157945;
        }
        localStorage.setItem('sale_purchase_fy_row_counts', JSON.stringify(safe));
    } catch(e) {}
}



function parseFYKey(k) {

    if (!k) return [0, 0, 0];

    const str = String(k).trim();

    const m = str.match(/^(\d{4})-(\d{2,4})(?:-(\d+))?$/);

    if (m) {

        const startY = parseInt(m[1], 10);

        const rawEnd = m[2];

        const endY = rawEnd.length === 4 ? parseInt(rawEnd, 10) : parseInt(String(startY).slice(0, 2) + rawEnd, 10);

        const part = m[3] ? parseInt(m[3], 10) : 0;

        return [startY, endY, part];

    }

    const nums = (str.match(/\d+/g) || []).map(n => parseInt(n, 10));

    return nums.length ? [...nums, 0] : [0, 0, 0];

}



function compareFYKeys(a, b) {

    const pa = parseFYKey(a);

    const pb = parseFYKey(b);

    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {

        const va = pa[i] !== undefined ? pa[i] : 0;

        const vb = pb[i] !== undefined ? pb[i] : 0;

        if (va !== vb) return va - vb;

    }

    return String(a).localeCompare(String(b));

}



function getAvailableFYKeys() {

    const urls = getSavedFyUrls();

    const sheetUrls = getSavedFySheetUrls();

    const keys = Array.from(new Set([...Object.keys(urls), ...Object.keys(sheetUrls)]));

    if (keys.length === 0) keys.push('2025-26', '2026-27', '2026-27-1');

    keys.sort(compareFYKeys);

    return keys;

}



function getLatestConfiguredFY() {

    const keys = getAvailableFYKeys();

    return keys[keys.length - 1] || '2026-27-1';

}



function getSheetCapacityStatus(rowCount) {

    const count = parseInt(rowCount, 10) || 0;

    if (count > 150000) {

        return {

            level: 'critical',

            tier: 4,

            isWarning: true,

            isCritical: true,

            badgeClass: 'capacity-badge-critical',

            label: 'Red Alert (≥1.5L)',

            shortText: '1.5L+ Full',

            color: '#dc2626',

            warningTitle: 'CRITICAL RED ALERT: Sheet Overload Limit Reached (≥ 1,50,000 Rows)',

            warningDesc: 'This sheet has reached its maximum recommended capacity. Adding more data will cause Google Sheets to crash or fail. Please switch to a new FY sheet or create a new partition.'

        };

    }

    if (count > 100000) {

        return {

            level: 'orange',

            tier: 3,

            isWarning: true,

            isCritical: false,

            badgeClass: 'capacity-badge-orange',

            label: 'Orange Alert (1L - 1.5L)',

            shortText: '1L+ Heavy',

            color: '#ea580c',

            warningTitle: 'HIGH CAPACITY WARNING: Approaching Limit (1,00,001 – 1,50,000 Rows)',

            warningDesc: 'This sheet is nearing its maximum recommended capacity. Operations may experience lag. We strongly recommend creating a new partition sheet in Settings to maintain fast loading.'

        };

    }

    if (count > 50000) {

        return {

            level: 'yellow',

            tier: 2,

            isWarning: false,

            isCritical: false,

            badgeClass: 'capacity-badge-yellow',

            label: 'Yellow Alert (50K - 1L)',

            shortText: '50K+ Active',

            color: '#ca8a04',

            warningTitle: 'MODERATE LOAD: Normal Sheet Capacity (50,001 – 1,00,000 Rows)',

            warningDesc: 'Sheet capacity is within normal working limits. Operations remain stable, but monitor row volume as it continues to grow.'

        };

    }

    return {

        level: 'healthy',

        tier: 1,

        isWarning: false,

        isCritical: false,

        badgeClass: 'capacity-badge-healthy',

        label: 'Green Alert (1 - 50K)',

        shortText: 'Optimal',

        color: '#059669',

        warningTitle: 'OPTIMAL STATUS: Sheet Health is Healthy & Fast (1 – 50,000 Rows)',

        warningDesc: 'This sheet is operating at peak speed and optimal capacity. Safe to add more Sale & Purchase data without any performance delay.'

    };

}



function formatRowCount(num) {

    const n = parseInt(num, 10) || 0;

    if (n >= 100000) {

        const lakh = (n / 100000).toFixed(n % 100000 === 0 ? 0 : 2);

        return `${n.toLocaleString('en-IN')} (${lakh}L)`;

    }

    return n.toLocaleString('en-IN');

}



function extractSpreadsheetId(urlOrId) {

    if (!urlOrId) return '';

    const str = String(urlOrId).trim();

    const match = str.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);

    if (match) return match[1];

    if (/^[a-zA-Z0-9-_]{20,}$/.test(str)) return str;

    return '';

}



function extractGid(urlOrGid) {

    if (!urlOrGid) return '0';

    const str = String(urlOrGid).trim();

    const match = str.match(/[#?&]gid=([0-9]+)/);

    if (match) return match[1];

    if (/^[0-9]+$/.test(str)) return str;

    return '0';

}



function getSheetUrlForFY(fy) {

    const urls = getSavedFySheetUrls();

    if (fy && urls[fy] && urls[fy].trim() !== '') {

        return urls[fy].trim();

    }

    if (fy === '2026-27-1') return DEFAULT_SHEET_URL_26_27_1;

    if (fy === '2026-27') return DEFAULT_SHEET_URL_26_27;

    if (fy === '2025-26') return DEFAULT_SHEET_URL_25_26;

    const latest = getLatestConfiguredFY();

    if (urls[latest] && urls[latest].trim() !== '') return urls[latest].trim();

    return DEFAULT_SHEET_URL_26_27_1;

}



function getSpreadsheetIdForFY(fy) {

    const sheetUrl = getSheetUrlForFY(fy);

    const extracted = extractSpreadsheetId(sheetUrl);

    if (extracted) return extracted;

    if (state && state.spreadsheetIds && state.spreadsheetIds[fy]) {

        return state.spreadsheetIds[fy];

    }

    if (fy === '2026-27-1') return '1wcnhQnTZruaVNDMJbg3ssCskDV-7WmKLDXX8Q6YgvU4';

    if (fy === '2026-27') return '1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w';

    return '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To';

}



async function fetchFySettingsFromServer() {

    try {

        const res = await fetch('/api/get-fy-settings');

        const data = await res.json();

        if (data && data.status === 'Success') {

            const localUrls = getSavedFyUrls();

            const localSheetUrls = getSavedFySheetUrls();

            const mergedUrls = Object.assign({}, localUrls, data.urls || {});

            const mergedSheetUrls = Object.assign({}, localSheetUrls, data.sheet_urls || {});

            saveFyUrls(mergedUrls);

            saveFySheetUrls(mergedSheetUrls);

            // Dynamically set default to latest sheet on app launch / login
            const serverLatest = data.latest_fy || getLatestConfiguredFY();
            if (serverLatest) {
                state.currentFY = serverLatest;
                try { sessionStorage.setItem('user_switched_fy', serverLatest); } catch(e) {}
                const label = document.getElementById('fy-dropdown-label');
                if (label) label.textContent = `FY ${state.currentFY}`;
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

    currentFY: (function() {
        try {
            return getLatestConfiguredFY();
        } catch(e) {
            return '2026-27-1';
        }
    })(),

    saleOffset: 0, purchaseOffset: 0,

    pageSize: 25,

    saleTotal: 0, purchaseTotal: 0,

    spreadsheetIds: {

        '2025-26': '1xXR4gfDPN-0A1B8gaY7kcW52gr4uRjfJ-TmafuJr6To',

        '2026-27': '1AvlkDSR_zA3Vov2PGNLnZC6NDqM_-3On52ncpLf6d6w',

        '2026-27-1': '1wcnhQnTZruaVNDMJbg3ssCskDV-7WmKLDXX8Q6YgvU4'

    },



    // Sheet Viewer

    selectedSheet: '',

    availableSheets: [],

    viewerHeaders: [], viewerRows: [], viewerAllRows: [],

    viewerStartRow: 3, viewerPageSize: 50, viewerTotalRows: 0,

    fyRowCounts: getSavedFyRowCounts(),

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

        loaderText.textContent = 'Done!';



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

    const dot = document.getElementById('active-fy-indicator-dot');

    const btn = document.getElementById('fy-dropdown-btn');

    if (!menu) return;



    const keys = getAvailableFYKeys();

    if (!state.currentFY || !keys.includes(state.currentFY)) {
        state.currentFY = getLatestConfiguredFY();
    }

    menu.innerHTML = '';



    const headerEl = document.createElement('div');

    headerEl.className = 'fy-dropdown-header';

    headerEl.innerHTML = `<span>Select FY Sheet</span><span>Capacity / Rows</span>`;

    menu.appendChild(headerEl);



    keys.forEach(fy => {

        const isActive = fy === state.currentFY;

        const rowCount = state.fyRowCounts[fy] || 0;

        const cap = getSheetCapacityStatus(rowCount);

        const percent = Math.min(100, Math.round((rowCount / 150000) * 100));



        const item = document.createElement('div');

        item.className = 'fy-dropdown-item' + (isActive ? ' active' : '');

        

        const countBadge = rowCount > 0 ? `<span class="fy-row-count-badge">${formatRowCount(rowCount)}</span>` : '';



        item.innerHTML = `

            <div class="fy-dropdown-row">

                <div class="fy-dropdown-title-group">

                    <span class="fy-check">${isActive ? '✓' : ''}</span>

                    <span class="fy-dropdown-name">FY ${esc(fy)}</span>

                </div>

                <div class="fy-meta-group">

                    ${countBadge}

                    <span class="fy-status-pill ${cap.level}">${esc(cap.shortText)}</span>

                </div>

            </div>

            ${rowCount > 0 ? `

            <div class="fy-progress-track" title="${formatNumber(rowCount)} / 1,50,000 rows (${percent}%)">

                <div class="fy-progress-fill ${cap.level}" style="width: ${Math.max(3, percent)}%;"></div>

            </div>` : ''}

        `;



        item.onclick = () => {

            switchFinancialYear(fy);

            closeFYDropdown();

        };

        menu.appendChild(item);

    });



    if (label) label.textContent = `FY ${state.currentFY}`;



    const activeCount = state.fyRowCounts[state.currentFY] || state.viewerTotalRows || 0;

    const activeCap = getSheetCapacityStatus(activeCount);

    if (dot) {

        dot.className = `fy-indicator-dot ${activeCap.level}`;

    }

    if (btn) {

        btn.classList.toggle('yellow-load', activeCap.level === 'yellow');

        btn.classList.toggle('orange-load', activeCap.level === 'orange');

        btn.classList.toggle('warning-load', activeCap.level === 'orange');

        btn.classList.toggle('critical-load', activeCap.level === 'critical');

    }

}



function updateCapacityIndicators(rowCount) {

    const count = parseInt(rowCount, 10) || 0;

    const cap = getSheetCapacityStatus(count);

    const percent = Math.min(100, Math.round((count / 150000) * 100));



    // 1. Update toolbar widget

    const widget = document.getElementById('sheet-capacity-widget');

    const widgetDot = document.getElementById('widget-capacity-dot');

    const widgetText = document.getElementById('widget-capacity-text');

    const widgetFill = document.getElementById('widget-capacity-fill');



    if (widget) {

        widget.classList.remove('hidden');

        widget.className = `sheet-capacity-widget ${cap.level}`;

        if (widgetDot) widgetDot.className = `fy-indicator-dot ${cap.level}`;

        if (widgetText) {

            widgetText.innerHTML = `<strong>${formatNumber(count)}</strong> / 1.5L (${percent}%)`;

        }

        if (widgetFill) {

            widgetFill.className = `widget-meter-fill ${cap.level}`;

            widgetFill.style.width = `${Math.max(4, percent)}%`;

        }

    }



    // 2. Update Alert Banner above table (Always active for all 4 tiers: Green, Yellow, Orange, Red)

    const banner = document.getElementById('sheet-capacity-alert');

    const bannerIcon = document.getElementById('capacity-banner-icon');

    const bannerTitle = document.getElementById('capacity-banner-title');

    const bannerDesc = document.getElementById('capacity-banner-desc');



    if (banner) {

        banner.classList.remove('hidden');

        banner.className = `sheet-capacity-banner ${cap.level}`;

        if (bannerTitle) bannerTitle.textContent = cap.warningTitle;

        if (bannerDesc) bannerDesc.innerHTML = `${cap.warningDesc} (Current Load: <strong>${formatRowCount(count)}</strong>)`;

        if (bannerIcon) {

            if (cap.level === 'critical') {

                bannerIcon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;

            } else if (cap.level === 'orange') {

                bannerIcon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;

            } else if (cap.level === 'yellow') {

                bannerIcon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;

            } else {

                bannerIcon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;

            }

        }

    }

}



async function fetchAllFYRowCounts() {

    try {

        const urls = getSavedFyUrls();

        const sheetUrls = getSavedFySheetUrls();

        const fyKeys = Array.from(new Set([...Object.keys(urls), ...Object.keys(sheetUrls)]));

        if (fyKeys.length === 0) return;



        const promises = fyKeys.map(async (fy) => {

            const sheetUrl = sheetUrls[fy] || '';

            const appUrl = urls[fy] || '';

            try {

                // 1. Check directly via server proxy
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 8000);
                const res = await fetch(`/api/view-sheet-data?action=getMetadata&fy=${encodeURIComponent(fy)}&sheetUrl=${encodeURIComponent(sheetUrl)}`, { signal: controller.signal });
                clearTimeout(timeoutId);
                if (res.ok) {
                    const r = await res.json();
                    let maxRows = 0;
                    if (r && r.success) {
                        if (r.totalRows !== undefined && parseInt(r.totalRows, 10) > 0) {
                            maxRows = parseInt(r.totalRows, 10);
                        } else if (Array.isArray(r.sheets) && r.sheets.length > 0) {
                            r.sheets.forEach(sh => {
                                const count = parseInt(sh.rows, 10) || 0;
                                if (count > maxRows) maxRows = count;
                            });
                        }
                    }
                    if (maxRows <= 0 && fy === '2026-27') maxRows = 157945;
                    if (maxRows > 0) {
                        return { fy, maxRows };
                    }
                }
            } catch (err) {}

            // 2. Fallback to Apps Script if available
            if (appUrl && appUrl.trim()) {
                try {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 7000);
                    const res = await fetch(`${appUrl.trim()}?action=getSheetNames`, { signal: controller.signal });
                    clearTimeout(timeoutId);
                    const r = await res.json();
                    if (r && r.success && Array.isArray(r.sheets)) {
                        let maxRows = 0;
                        r.sheets.forEach(sh => {
                            const count = parseInt(sh.rows, 10) || 0;
                            if (count > maxRows) maxRows = count;
                        });
                        if (maxRows <= 0 && fy === '2026-27') maxRows = 157945;
                        if (maxRows > 0) return { fy, maxRows };
                    }
                } catch (asErr) {}
            }

            // 3. Fallback to baseline default count
            const defaultBaseline = DEFAULT_FY_ROW_COUNTS[fy] || 0;
            if (defaultBaseline > 0) {
                return { fy, maxRows: defaultBaseline };
            }

            return null;
        });



        const results = await Promise.all(promises);

        let updated = false;

        results.forEach(res => {

            if (res && res.fy) {

                state.fyRowCounts[res.fy] = res.maxRows;

                updated = true;

            }

        });



        if (updated) {

            saveFyRowCounts(state.fyRowCounts);

            populateFYSelector();

            const activeCount = state.fyRowCounts[state.currentFY] || state.viewerTotalRows || 0;

            updateCapacityIndicators(activeCount);

        }

    } catch (e) {

        console.warn('[Capacity Row Count Check Error]', e);

    }

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

    if (!fy) return;

    try { sessionStorage.setItem('user_switched_fy', fy); } catch(e) {}

    if (fy === state.currentFY) return;

    state.currentFY = fy;

    state.selectedSheet = '';

    state.viewerHeaders = [];

    state.viewerRows = [];

    state.viewerAllRows = [];

    state.viewerTotalRows = 0;

    clearViewerTable();

    const sel = document.getElementById('sheet-select');

    if (sel) sel.value = '';

    populateFYSelector();

    const knownCount = state.fyRowCounts[fy] || 0;

    updateCapacityIndicators(knownCount);

    showToast('🔄', `Switched to FY ${fy}`);

    refreshSheetDropdown();

}



// Initialize FY selector and background row counts check on load

populateFYSelector();

fetchAllFYRowCounts();



// ─── Load Sheet Names ───────────────────────────────────────────────────

async function refreshSheetDropdown() {

    try {

        const fy = state.currentFY || '2026-27';

        const sheetUrl = getSheetUrlForFY(fy);

        let r = null;



        // 1. Direct Google Sheet Proxy via local server (no Apps Script required)

        try {

            const metaRes = await fetch(`/api/view-sheet-data?action=getMetadata&fy=${encodeURIComponent(fy)}&sheetUrl=${encodeURIComponent(sheetUrl)}`);

            if (metaRes.ok) {

                const metaData = await metaRes.json();

                if (metaData && metaData.success) {

                    r = metaData;

                }

            }

        } catch (localErr) {

            console.warn('[Direct Sheet Meta Error]', localErr);

        }



        // 2. Fallback to Apps Script if available and local direct proxy didn't return

        if (!r && getActiveWebAppUrl()) {

            try {

                const res = await fetch(`${getActiveWebAppUrl()}?action=getSheetNames`);

                if (res.ok) r = await res.json();

            } catch (asErr) {

                console.warn('[Apps Script Meta Error]', asErr);

            }

        }



        if (r && r.success) {

            const sel = document.getElementById('sheet-select');

            const syncSel = document.getElementById('sync-sheet-select');

            const curV = sel ? sel.value : '';

            const curSV = syncSel ? syncSel.value : '';



            if(sel) sel.innerHTML = '<option value="">-- Choose sheet --</option>';



            state.availableSheets = r.sheets || [];

            if (r.spreadsheetId) {

                state.spreadsheetIds[state.currentFY] = r.spreadsheetId;

            }

            let fyMaxRows = 0;

            r.sheets.forEach(sh => {

                const rCount = parseInt(sh.rows, 10) || 0;

                if (rCount > fyMaxRows) fyMaxRows = rCount;

                const cap = getSheetCapacityStatus(rCount);

                let capTag = '';

                if (cap.isCritical) capTag = ' [RED ALERT]';

                else if (cap.level === 'orange') capTag = ' [Orange Alert]';

                else if (cap.level === 'yellow') capTag = ' [Yellow Alert]';

                else capTag = ' [Optimal]';

                const txt = `${sh.name} (${formatRowCount(rCount)})${capTag}`;

                if(sel) { const o=document.createElement('option'); o.value=sh.name; o.textContent=txt; sel.appendChild(o); }

            });



            if (fyMaxRows > 0) {

                state.fyRowCounts[state.currentFY] = fyMaxRows;

                saveFyRowCounts(state.fyRowCounts);

                populateFYSelector();

                updateCapacityIndicators(fyMaxRows);

            }



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
                const latestFy = getLatestConfiguredFY();
                const latestSh = r.sheets.find(s => s.name.includes(latestFy));
                if (latestSh) {
                    syncSel.value = latestSh.name;
                } else if(curSV && r.sheets.some(s=>s.name===curSV)) {
                    syncSel.value=curSV;
                } else if(def) {
                    syncSel.value=def;
                }
            }



        } else { showToast('⚠️', 'Sheets Error: ' + r.error); }

    } catch(e) {

        console.warn('[Sheet Connect Warning]', e);

        showToast('⚠️', 'Google Sheet URL not connected. Click Settings to configure URL.');

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

    const v = parseInt(document.getElementById('sheet-rows-per-page')?.value || '50', 10) || 50;

    state.viewerPageSize = v;

    const footerSelect = document.getElementById('footer-rows-per-page');

    if (footerSelect) footerSelect.value = String(v);

    if (document.getElementById('universal-search').value.trim()) runUniversalSearch();

    else if (state.selectedSheet) loadSheetData(3);

}



// ─── Fast RFC-4180 Compliant CSV Parser (Preserves All Data & Column Alignment) ───
function parseCSVRows(csvText) {
    if (!csvText) return [];
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;
    const n = csvText.length;
    for (let i = 0; i < n; i++) {
        const c = csvText[i];
        const next = (i + 1 < n) ? csvText[i + 1] : '';
        if (c === '"') {
            if (inQuotes && next === '"') {
                field += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (c === ',' && !inQuotes) {
            row.push(field);
            field = '';
        } else if ((c === '\r' || c === '\n') && !inQuotes) {
            if (c === '\r' && next === '\n') i++;
            row.push(field);
            field = '';
            if (row.length > 1 || (row.length === 1 && row[0] !== '')) {
                rows.push(row);
            }
            row = [];
        } else {
            field += c;
        }
    }
    if (field.length > 0 || row.length > 0) {
        row.push(field);
        if (row.length > 1 || (row.length === 1 && row[0] !== '')) {
            rows.push(row);
        }
    }
    return rows;
}

// ─── Load Sheet Data (Fast Range with Apps Script Fallback) ───
async function loadSheetData(startRow, isRefresh = false) {

    if (!state.selectedSheet && state.availableSheets && state.availableSheets.length > 0) {

        state.selectedSheet = state.availableSheets[0].name;

    }

    if (!state.selectedSheet) return;



    // Defensive check: Ensure selectedSheet belongs to current FY's available sheets

    if (state.availableSheets && state.availableSheets.length > 0) {

        const found = state.availableSheets.some(s => s.name === state.selectedSheet);

        if (!found) {

            console.warn(`[SHEET MISMATCH] ${state.selectedSheet} not in FY ${state.currentFY}. Resetting.`);

            const matched = state.availableSheets.find(s => s.name.includes(state.currentFY)) || state.availableSheets[0];

            state.selectedSheet = matched.name;

            const sel = document.getElementById('sheet-select');

            if (sel) sel.value = state.selectedSheet;

        }

    }



    state.searchToken++;

    state.viewerStartRow = startRow || 3;

    showGlobalLoader('Loading Sheet', `Fetching page from ${state.selectedSheet}...`);



    const limit = state.viewerPageSize || 25;

    const fy = state.currentFY || '2026-27';

    const sheetUrl = getSheetUrlForFY(fy);

    const curSheetObj = (state.availableSheets || []).find(s => s.name === state.selectedSheet);

    const curGid = (curSheetObj && curSheetObj.gid !== undefined) ? curSheetObj.gid : (extractGid(sheetUrl) || 0);

    const spreadsheetId = getSpreadsheetIdForFY(fy);



    // Calculate exact cell range:

    // Sheet Row 1 is Headers.

    // Sheet Row 2 onwards are data rows (Row 2 = Item 1, Row 3 = Item 2, etc.)

    const p = Math.floor(Math.max(0, (state.viewerStartRow - 3)) / limit);

    let fromRow, toRow;

    if (p === 0) {

        fromRow = 1; // Include Row 1 (header row)

        toRow = 1 + limit; // 50 data items (Rows 2..51)

    } else {

        fromRow = 2 + (p * limit); // e.g. Row 52 for Page 2 (51..100)

        toRow = fromRow + limit - 1;

    }



    let loadSuccess = false;



    // 1. Direct High-Precision Server Proxy (Uses Google Sheets CSV without Apps Script & preserves all text/IDs)

    try {

        const refreshParam = isRefresh ? '&refresh=1' : '';

        const apiUrl = `/api/view-sheet-data?action=getData&fy=${encodeURIComponent(fy)}&sheetUrl=${encodeURIComponent(sheetUrl)}&gid=${curGid}&fromRow=${fromRow}&toRow=${toRow}&totalRows=${state.viewerTotalRows || 0}${refreshParam}`;

        const ctrl = new AbortController();

        const timeoutId = setTimeout(() => ctrl.abort(), 25000);

        const res = await fetch(apiUrl, { signal: ctrl.signal });

        clearTimeout(timeoutId);



        if (res.ok) {

            const r = await res.json();

            if (r && r.success && r.data) {

                hideGlobalLoader();

                state.viewerHeaders = r.headers || [];

                state.viewerRows = r.data || [];

                state.viewerAllRows = r.data || [];

                if (r.totalRows > 0) state.viewerTotalRows = r.totalRows;

                renderViewerTable();

                loadSuccess = true;

            }

        }

    } catch(directErr) {

        if (directErr && directErr.name !== 'AbortError') {

            console.log('[Direct Sheet Proxy notice, using Apps Script fallback]:', directErr.message || directErr);

        }

    }



    // 2. Fallback to Apps Script only if Direct Proxy did not succeed and Web App URL exists

    if (!loadSuccess && getActiveWebAppUrl()) {

        try {

            const res = await fetch(`${getActiveWebAppUrl()}?action=getSheetData&sheetName=${encodeURIComponent(state.selectedSheet)}&startRow=${state.viewerStartRow}&numRows=${state.viewerPageSize}`);

            const r = await res.json();

            hideGlobalLoader();



            if (r.success) {

                state.viewerHeaders = r.headers || [];

                state.viewerRows = r.data || [];

                state.viewerAllRows = r.data || [];

                state.viewerTotalRows = r.totalRows || 0;

                renderViewerTable();

            } else {

                showToast('❌', 'Data Error: ' + r.error);

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

        thead.innerHTML = '';

        tbody.innerHTML = '<tr><td style="text-align:center;color:var(--text-muted);">Sheet is empty.</td></tr>';

        document.getElementById('prev-btn').disabled = true;

        document.getElementById('next-btn').disabled = true;

        return;

    }



    const hdr = state.viewerHeaders[1] || state.viewerHeaders[0] || [];

    thead.innerHTML = `<tr>${hdr.map(h => `<th>${h}</th>`).join('')}</tr>`;



    if (state.viewerRows.length === 0) {

        tbody.innerHTML = `<tr><td colspan="${hdr.length}" style="text-align:center;color:var(--text-muted);">No records.</td></tr>`;

    } else {

        tbody.innerHTML = state.viewerRows.map(row =>

            `<tr>${row.map(v => {

                let d = (v == null) ? '' : v;

                if (typeof d === 'number' && !Number.isInteger(d)) d = d.toFixed(2);

                return `<td title="${esc(String(d))}">${esc(String(d))}</td>`;

            }).join('')}</tr>`

        ).join('');

    }



    const limit = state.viewerPageSize || 50;

    const p = Math.floor(Math.max(0, (state.viewerStartRow || 3) - 3) / limit);

    const startItem = p * limit + 1;

    const endItem = Math.min(startItem + state.viewerRows.length - 1, state.viewerTotalRows);



    pInfo.textContent = `${formatNumber(startItem)} - ${formatNumber(endItem)}`;

    tInfo.textContent = `Total: ${formatNumber(state.viewerTotalRows)} rows`;

    if (state.viewerTotalRows > 0) {

        updateCapacityIndicators(state.viewerTotalRows);

        state.fyRowCounts[state.currentFY] = Math.max(state.fyRowCounts[state.currentFY] || 0, state.viewerTotalRows);

        saveFyRowCounts(state.fyRowCounts);

    }



    document.getElementById('prev-btn').disabled = (p === 0);

    document.getElementById('next-btn').disabled = (endItem >= state.viewerTotalRows || state.viewerRows.length === 0);



    // Render bottom pagination controls

    renderFooterPagination();

}



function renderViewerSearchResults(totalMatches, returnedRows, limited) {

    renderViewerTable();

    document.getElementById('page-info').textContent = `Search`;

    document.getElementById('prev-btn').disabled = true;

    document.getElementById('next-btn').disabled = true;



    const shown = formatNumber(returnedRows || state.viewerRows.length);

    const total = formatNumber(totalMatches || 0);

    const searchMsg = limited

        ? `Search: showing <strong>${shown}</strong> of <strong>${total}</strong> matches`

        : `Search: <strong>${total}</strong> match${totalMatches !== 1 ? 'es' : ''} found`;

    

    const infoEl = document.getElementById('footer-entries-info');

    if (infoEl) infoEl.innerHTML = searchMsg;

    document.getElementById('viewer-total-info').innerHTML = searchMsg;

}



function goToPage(pageNum) {

    const limit = state.viewerPageSize || 50;

    const totalRows = state.viewerTotalRows || 0;

    const totalPages = Math.max(1, Math.ceil(totalRows / limit));

    let targetPage = parseInt(pageNum, 10);

    if (isNaN(targetPage) || targetPage < 1) targetPage = 1;

    if (targetPage > totalPages) targetPage = totalPages;



    const nextStartRow = 3 + ((targetPage - 1) * limit);

    const searchInput = document.getElementById('universal-search');

    if (searchInput) searchInput.value = '';

    loadSheetData(nextStartRow);

}



function getPageNumbersList(current, total) {

    if (total <= 7) {

        const pages = [];

        for (let i = 1; i <= total; i++) pages.push(i);

        return pages;

    }

    if (current <= 4) {

        return [1, 2, 3, 4, 5, '...', total];

    }

    if (current >= total - 3) {

        return [1, '...', total - 4, total - 3, total - 2, total - 1, total];

    }

    return [1, '...', current - 1, current, current + 1, '...', total];

}



function renderFooterPagination() {

    const totalRows = state.viewerTotalRows || 0;

    const limit = state.viewerPageSize || 50;

    const totalPages = Math.max(1, Math.ceil(totalRows / limit));

    const currentPage = Math.min(totalPages, Math.floor(Math.max(0, (state.viewerStartRow || 3) - 3) / limit) + 1);



    // 1. Update entries info on left (e.g. "Showing 1 to 50 of 3,021 entries")

    const infoEl = document.getElementById('footer-entries-info');

    if (infoEl) {

        if (totalRows === 0) {

            infoEl.textContent = 'Showing 0 to 0 of 0 entries';

        } else {

            const startItem = (currentPage - 1) * limit + 1;

            const endItem = Math.min(startItem + (state.viewerRows ? state.viewerRows.length : 0) - 1, totalRows);

            infoEl.innerHTML = `Showing <strong>${formatNumber(startItem)}</strong> to <strong>${formatNumber(endItem)}</strong> of <strong>${formatNumber(totalRows)}</strong> entries`;

        }

    }



    // 2. Sync entries select dropdowns

    const footerSelect = document.getElementById('footer-rows-per-page');

    if (footerSelect && footerSelect.value !== String(limit)) {

        footerSelect.value = String(limit);

    }

    const topSelect = document.getElementById('sheet-rows-per-page');

    if (topSelect && topSelect.value !== String(limit)) {

        topSelect.value = String(limit);

    }



    // 3. Render page buttons: « ‹ 1 2 3 4 5 ... 61 › »

    const container = document.getElementById('footer-pagination-pages');

    if (!container) return;

    container.innerHTML = '';



    // First page button «

    const firstBtn = document.createElement('button');

    firstBtn.type = 'button';

    firstBtn.className = 'footer-page-btn nav-btn';

    firstBtn.title = 'First Page';

    firstBtn.textContent = '«';

    firstBtn.disabled = (currentPage === 1 || totalRows === 0);

    firstBtn.onclick = () => goToPage(1);

    container.appendChild(firstBtn);



    // Prev page button ‹

    const prevBtn = document.createElement('button');

    prevBtn.type = 'button';

    prevBtn.className = 'footer-page-btn nav-btn';

    prevBtn.title = 'Previous Page';

    prevBtn.textContent = '‹';

    prevBtn.disabled = (currentPage === 1 || totalRows === 0);

    prevBtn.onclick = () => goToPage(currentPage - 1);

    container.appendChild(prevBtn);



    // Numbered pages algorithm

    const pageNumbers = getPageNumbersList(currentPage, totalPages);

    pageNumbers.forEach(p => {

        if (p === '...') {

            const dots = document.createElement('span');

            dots.className = 'footer-page-ellipsis';

            dots.textContent = '...';

            container.appendChild(dots);

        } else {

            const pageBtn = document.createElement('button');

            pageBtn.type = 'button';

            pageBtn.className = 'footer-page-btn' + (p === currentPage ? ' active' : '');

            pageBtn.textContent = String(p);

            pageBtn.title = `Page ${p}`;

            if (p === currentPage) {

                pageBtn.setAttribute('aria-current', 'page');

            } else {

                pageBtn.onclick = () => goToPage(p);

            }

            container.appendChild(pageBtn);

        }

    });



    // Next page button ›

    const nextBtn = document.createElement('button');

    nextBtn.type = 'button';

    nextBtn.className = 'footer-page-btn nav-btn';

    nextBtn.title = 'Next Page';

    nextBtn.textContent = '›';

    nextBtn.disabled = (currentPage === totalPages || totalRows === 0);

    nextBtn.onclick = () => goToPage(currentPage + 1);

    container.appendChild(nextBtn);



    // Last page button »

    const lastBtn = document.createElement('button');

    lastBtn.type = 'button';

    lastBtn.className = 'footer-page-btn nav-btn';

    lastBtn.title = 'Last Page';

    lastBtn.textContent = '»';

    lastBtn.disabled = (currentPage === totalPages || totalRows === 0);

    lastBtn.onclick = () => goToPage(totalPages);

    container.appendChild(lastBtn);



    // 4. Update Go to input placeholder / max

    const gotoInput = document.getElementById('footer-goto-input');

    if (gotoInput) {

        gotoInput.max = totalPages;

        gotoInput.value = currentPage;

    }

}



function executeFooterGoTo() {

    const input = document.getElementById('footer-goto-input');

    if (!input) return;

    const page = parseInt(input.value, 10);

    if (!isNaN(page)) {

        goToPage(page);

    }

}



function onFooterRowsPerPageChange(val) {

    const newLimit = parseInt(val, 10) || 50;

    state.viewerPageSize = newLimit;

    const topSelect = document.getElementById('sheet-rows-per-page');

    if (topSelect) topSelect.value = String(newLimit);

    state.viewerStartRow = 3;

    loadSheetData(3);

}







function changePage(dir) {

    const limit = state.viewerPageSize || 50;

    let p = Math.floor(Math.max(0, (state.viewerStartRow || 3) - 3) / limit);

    let nextP = p + dir;

    if (nextP < 0) nextP = 0;

    const nextStartRow = 3 + (nextP * limit);

    document.getElementById('universal-search').value = ''; // Clear search on page change

    loadSheetData(nextStartRow);

}



function clearViewerTable() {

    document.getElementById('viewer-thead').innerHTML='';

    document.getElementById('viewer-tbody').innerHTML='';

    document.getElementById('page-info').textContent='0 - 0';

    document.getElementById('viewer-total-info').textContent='Select a sheet.';

    document.getElementById('prev-btn').disabled=true;

    document.getElementById('next-btn').disabled=true;

    renderFooterPagination();

}



// ─── Universal Search ───────────────────────────────────────────────────

function showSearchSpinner() {
    const staticIcon = document.getElementById('search-static-icon');
    const spinner = document.getElementById('search-loading-spinner');
    if (staticIcon) staticIcon.style.display = 'none';
    if (spinner) spinner.style.display = 'block';
}

function hideSearchSpinner() {
    const staticIcon = document.getElementById('search-static-icon');
    const spinner = document.getElementById('search-loading-spinner');
    if (staticIcon) staticIcon.style.display = 'block';
    if (spinner) spinner.style.display = 'none';
}

function handleUniversalSearchKey(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        runUniversalSearch();
    }
}

function handleUniversalSearchInput(input) {
    if (!input) return;
    const q = input.value.trim();
    // Only reset when user completely clears the search field
    if (q === '' && state.isSearchActive) {
        state.isSearchActive = false;
        hideSearchSpinner();
        if (state.selectedSheet) {
            loadSheetData(state.viewerStartRow || 3);
        }
    }
}

function handleUniversalSearch() {
    runUniversalSearch();
}

async function runUniversalSearch() {
    const input = document.getElementById('universal-search');
    if (!input) return;
    const q = input.value.trim();

    if (!q) {
        state.isSearchActive = false;
        hideSearchSpinner();
        if (state.selectedSheet) loadSheetData(state.viewerStartRow || 3);
        return;
    }

    if (!state.selectedSheet) {
        showToast('Notice', 'Select a sheet first');
        return;
    }

    state.isSearchActive = true;
    showSearchSpinner();

    const token = ++state.searchToken;
    const infoEl = document.getElementById('viewer-total-info');
    if (infoEl) infoEl.textContent = 'Searching full sheet...';
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;

    try {
        const fy = state.currentFY || '2026-27';
        const sheetUrl = getSheetUrlForFY(fy);
        const curSheetObj = (state.availableSheets || []).find(s => s.name === state.selectedSheet);
        const curGid = (curSheetObj && curSheetObj.gid !== undefined) ? curSheetObj.gid : (extractGid(sheetUrl) || 0);

        let r = null;
        try {
            const searchApiUrl = `/api/view-sheet-data?action=search&fy=${encodeURIComponent(fy)}&sheetUrl=${encodeURIComponent(sheetUrl)}&gid=${curGid}&query=${encodeURIComponent(q)}`;
            const res = await fetch(searchApiUrl);
            if (res.ok) {
                const searchData = await res.json();
                if (searchData && searchData.success) r = searchData;
            }
        } catch (searchErr) {
            console.warn('[Direct Search Proxy failed, trying fallback]', searchErr);
        }

        if (!r && getActiveWebAppUrl()) {
            const maxResults = 1000;
            const url = `${getActiveWebAppUrl()}?action=searchSheetData&sheetName=${encodeURIComponent(state.selectedSheet)}&query=${encodeURIComponent(q)}&maxResults=${maxResults}`;
            const res = await fetch(url);
            r = await res.json();
        }

        if (token !== state.searchToken) return;

        if (r && r.success) {
            state.viewerHeaders = r.headers || [];
            state.viewerRows = r.data || [];
            state.viewerAllRows = r.data || [];
            state.viewerTotalRows = r.totalRows || 0;
            renderViewerSearchResults(r.totalMatches || 0, r.returnedRows || state.viewerRows.length, !!r.limited);
        } else {
            showToast('Error', 'Search Error: ' + (r ? r.error : 'Unknown error'));
        }
    } catch(e) {
        if (token === state.searchToken) showToast('Error', 'Search network error');
    } finally {
        if (token === state.searchToken) {
            hideSearchSpinner();
        }
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



function openSyncModal() {
    const overlay = document.getElementById('sync-modal-overlay');
    if (overlay) overlay.classList.remove('hidden');

    // 1. Immediately render known / cached sheets with latest partition selected (e.g. 2026-27-1)
    const knownSheets = getKnownSyncSheets();
    const latestFy = getLatestConfiguredFY();
    const latestMatch = knownSheets.find(s => s.fy === latestFy);
    const targetVal = latestMatch ? latestMatch.name : (knownSheets[knownSheets.length - 1]?.name || null);
    renderCustomSyncDropdown(knownSheets, targetVal);

    // 2. Silently update from network in background without freezing UI
    refreshSyncDropdown(true);
}

function closeSyncModal() {
    const overlay = document.getElementById('sync-modal-overlay');
    if (overlay) overlay.classList.add('hidden');
    const menu = document.getElementById('custom-sync-menu');
    if (menu) menu.classList.add('hidden');
    const dropdown = document.getElementById('custom-sync-dropdown');
    if (dropdown) dropdown.classList.remove('open');
}

function getKnownSyncSheets() {
    const defaultCounts = {
        '2026-27': 157945,
        '2025-26': 44809,
        '2026-27-1': 3944
    };
    try {
        const stored = localStorage.getItem('sale_purchase_cached_sync_sheets');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed) && parsed.length > 0) {
                parsed.forEach(sh => {
                    let rCount = parseInt(sh.rows, 10) || 0;
                    if (rCount <= 0 || (sh.fy === '2026-27' && rCount < 100000)) {
                        sh.rows = state.fyRowCounts[sh.fy] || defaultCounts[sh.fy] || 157945;
                    }
                });
                return parsed;
            }
        }
    } catch (e) {}

    const urls = getSavedFyUrls();
    const sheetUrls = getSavedFySheetUrls();
    const rowCounts = getSavedFyRowCounts();
    const list = [];
    const keys = getAvailableFYKeys();
    keys.forEach(fy => {
        const url = (urls[fy] || '').trim();
        const sUrl = (sheetUrls[fy] || '').trim();
        const targetUrl = url || sUrl;
        if (!targetUrl) return;
        let rows = parseInt(rowCounts[fy] || defaultCounts[fy] || '0', 10);
        if (fy === '2026-27' && (rows <= 0 || rows < 100000)) rows = 157945;
        list.push({
            fy: fy,
            name: `AJ&MY&FK SALE-PURCHASE ${fy}`,
            url: targetUrl,
            rows: rows
        });
    });
    return list;
}

let _customSyncSheets = [];

function renderCustomSyncDropdown(sheets, keepSelectedVal = null) {
    const defaultCounts = {
        '2026-27': 157945,
        '2025-26': 44809,
        '2026-27-1': 3944
    };
    _customSyncSheets = (sheets || []).map(sh => {
        let rows = parseInt(sh.rows, 10) || 0;
        if (rows <= 0 || (sh.fy === '2026-27' && rows < 100000)) {
            rows = state.fyRowCounts[sh.fy] || defaultCounts[sh.fy] || 157945;
        }
        return Object.assign({}, sh, { rows: rows });
    });
    const sel = document.getElementById('sync-sheet-select');
    const listContainer = document.getElementById('custom-sync-options-list');
    const badge = document.getElementById('sync-sheets-count-badge');
    if (!sel || !listContainer) return;

    if (badge) {
        badge.textContent = `${_customSyncSheets.length} Target${_customSyncSheets.length === 1 ? '' : 's'} Ready`;
    }

    // Determine current value to maintain: ALWAYS default to the latest added partition (e.g. 2026-27-1)
    const latestFy = getLatestConfiguredFY();
    const latestSheetObj = _customSyncSheets.find(s => s.fy === latestFy) || _customSyncSheets[_customSyncSheets.length - 1];
    let selectedVal = keepSelectedVal;
    if (!selectedVal || !_customSyncSheets.some(s => s.name === selectedVal)) {
        selectedVal = latestSheetObj ? latestSheetObj.name : (_customSyncSheets[0]?.name || '');
    }

    // Populate hidden native select
    let optionsHtml = '<option value="">-- Choose Target Sheet --</option>';
    _customSyncSheets.forEach(sh => {
        const rows = parseInt(sh.rows, 10) || 0;
        optionsHtml += `<option value="${esc(sh.name)}" data-url="${esc(sh.url)}" data-fy="${esc(sh.fy)}" data-rows="${rows}">${esc(sh.name)}</option>`;
    });
    sel.innerHTML = optionsHtml;
    sel.value = selectedVal;

    // Render custom option cards
    renderCustomOptionRows(_customSyncSheets, selectedVal);

    // Update custom trigger UI
    const chosen = _customSyncSheets.find(s => s.name === selectedVal) || _customSyncSheets[0];
    if (chosen) {
        updateCustomTriggerUI(chosen);
        sel.value = chosen.name;
    }

    // Update the live capacity alert card
    onSyncSheetSelected();
}

function renderCustomOptionRows(sheets, selectedVal) {
    const listContainer = document.getElementById('custom-sync-options-list');
    if (!listContainer) return;

    if (!sheets || sheets.length === 0) {
        listContainer.innerHTML = '<div style="padding:16px; text-align:center; color:#94a3b8; font-size:0.84rem;">No target sheets available</div>';
        return;
    }

    listContainer.innerHTML = sheets.map(sh => {
        const rows = parseInt(sh.rows, 10) || 0;
        const cap = getSheetCapacityStatus(rows);
        const isSelected = sh.name === selectedVal;
        return `
            <div class="custom-sync-option-row ${isSelected ? 'selected' : ''}" onclick="selectCustomSyncOption('${esc(sh.name)}', '${esc(sh.fy)}', '${esc(sh.url)}', ${rows})">
                <div class="custom-sync-option-left">
                    <span class="custom-sync-fy-tag">FY ${esc(sh.fy)}</span>
                    <span class="custom-sync-option-name" title="${esc(sh.name)}">${esc(sh.name)}</span>
                </div>
                <div class="custom-sync-option-right">
                    <span class="custom-sync-cap-pill ${cap.level}">
                        <span class="fy-indicator-dot ${cap.level}"></span>
                        ${formatRowCount(rows)}
                    </span>
                    ${isSelected ? '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>' : ''}
                </div>
            </div>
        `;
    }).join('');
}

function updateCustomTriggerUI(sh) {
    const triggerContent = document.getElementById('custom-sync-trigger-content');
    if (!triggerContent || !sh) return;
    const rows = parseInt(sh.rows, 10) || 0;
    const cap = getSheetCapacityStatus(rows);
    triggerContent.innerHTML = `
        <div class="custom-sync-trigger-selected">
            <span class="custom-sync-fy-tag">FY ${esc(sh.fy)}</span>
            <span class="custom-sync-sheet-name">${esc(sh.name)}</span>
            <span class="custom-sync-cap-pill ${cap.level}">
                <span class="fy-indicator-dot ${cap.level}"></span>
                ${formatRowCount(rows)} • ${cap.label.split(' ')[0]}
            </span>
        </div>
    `;
}

function toggleCustomSyncDropdown() {
    const dropdown = document.getElementById('custom-sync-dropdown');
    const menu = document.getElementById('custom-sync-menu');
    if (!dropdown || !menu) return;
    const isOpen = dropdown.classList.contains('open');
    if (isOpen) {
        dropdown.classList.remove('open');
        menu.classList.add('hidden');
    } else {
        dropdown.classList.add('open');
        menu.classList.remove('hidden');
        const searchInput = document.getElementById('custom-sync-search-input');
        if (searchInput) {
            searchInput.value = '';
            searchInput.focus();
            renderCustomOptionRows(_customSyncSheets, document.getElementById('sync-sheet-select')?.value);
        }
    }
}

function selectCustomSyncOption(sheetName, fy, url, rows) {
    const sel = document.getElementById('sync-sheet-select');
    if (sel) {
        sel.value = sheetName;
        const opt = Array.from(sel.options).find(o => o.value === sheetName);
        if (opt) {
            opt.selected = true;
            opt.dataset.rows = rows;
            opt.dataset.url = url;
            opt.dataset.fy = fy;
        }
    }
    const chosen = _customSyncSheets.find(s => s.name === sheetName) || { name: sheetName, fy, url, rows };
    updateCustomTriggerUI(chosen);

    const dropdown = document.getElementById('custom-sync-dropdown');
    const menu = document.getElementById('custom-sync-menu');
    if (dropdown) dropdown.classList.remove('open');
    if (menu) menu.classList.add('hidden');

    onSyncSheetSelected();
}

function filterCustomSyncSheets(query) {
    const q = (query || '').toLowerCase().trim();
    const selVal = document.getElementById('sync-sheet-select')?.value || '';
    if (!q) {
        renderCustomOptionRows(_customSyncSheets, selVal);
        return;
    }
    const filtered = _customSyncSheets.filter(s =>
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.fy && s.fy.toLowerCase().includes(q))
    );
    renderCustomOptionRows(filtered, selVal);
}

function selectSyncMode(mode) {
    const radios = document.querySelectorAll('input[name="sync-mode"]');
    radios.forEach(r => {
        r.checked = (r.value === mode);
    });
    updateSyncModeUI();
}

function updateSyncModeUI() {
    const appendCard = document.getElementById('sync-mode-append-label');
    const overwriteCard = document.getElementById('sync-mode-overwrite-label');
    const mode = document.querySelector('input[name="sync-mode"]:checked')?.value || 'append';
    if (appendCard) appendCard.classList.toggle('active', mode === 'append');
    if (overwriteCard) overwriteCard.classList.toggle('active', mode === 'overwrite');
}

async function refreshSyncDropdown(silent = false) {
    try {
        const badge = document.getElementById('sync-sheets-count-badge');
        if (!silent && badge) badge.textContent = 'Updating...';

        const urls = getSavedFyUrls();
        const sheetUrls = getSavedFySheetUrls();
        const fyKeys = getAvailableFYKeys();
        if (fyKeys.length === 0) return;

        const promises = fyKeys.map(async (fy) => {
            const asUrl = (urls[fy] || '').trim();
            const sUrl = (sheetUrls[fy] || '').trim();
            if (!asUrl && !sUrl) return null;

            // 1. Local fast proxy (100ms cached)
            try {
                const res = await fetch(`/api/view-sheet-data?action=getMetadata&fy=${encodeURIComponent(fy)}`);
                if (res.ok) {
                    const r = await res.json();
                    if (r.success && r.sheets && r.sheets.length > 0) {
                        return { fy, url: asUrl || sUrl, sheets: r.sheets };
                    }
                }
            } catch (err) {
                console.warn(`Local meta fetch failed for FY ${fy}:`, err);
            }

            // 2. Fallback to direct Apps Script call
            if (asUrl) {
                try {
                    const res = await fetch(`${asUrl}?action=getSheetNames`);
                    if (res.ok) {
                        const r = await res.json();
                        if (r.success && r.sheets) {
                            return { fy, url: asUrl, sheets: r.sheets };
                        }
                    }
                } catch (err) {
                    console.warn(`Apps script fetch failed for FY ${fy}:`, err);
                }
            }

            // 3. Fallback to known default entry
            const defFallback = DEFAULT_FY_ROW_COUNTS[fy] || 0;
            return {
                fy,
                url: asUrl || sUrl,
                sheets: [{ name: `AJ&MY&FK SALE-PURCHASE ${fy}`, rows: state.fyRowCounts[fy] || defFallback }]
            };
        });

        const results = await Promise.all(promises);
        const compiledSheets = [];

        results.forEach(resObj => {
            if (resObj && resObj.sheets) {
                resObj.sheets.forEach(sh => {
                    let rowCount = parseInt(sh.rows, 10) || 0;
                    if (rowCount <= 0 || (resObj.fy === '2026-27' && rowCount < 100000)) {
                        rowCount = state.fyRowCounts[resObj.fy] || DEFAULT_FY_ROW_COUNTS[resObj.fy] || 157945;
                    }
                    compiledSheets.push({
                        fy: resObj.fy,
                        url: resObj.url,
                        name: sh.name,
                        rows: rowCount
                    });
                });
            }
        });

        if (compiledSheets.length > 0) {
            localStorage.setItem('sale_purchase_cached_sync_sheets', JSON.stringify(compiledSheets));
            const curVal = document.getElementById('sync-sheet-select')?.value;
            const latestFy = getLatestConfiguredFY();
            const latestMatch = compiledSheets.find(s => s.fy === latestFy);
            let chosenVal = curVal;
            // If current selected value is empty or points to the overloaded 2026-27, default to latest 2026-27-1
            if (!chosenVal || chosenVal.endsWith('2026-27') || !compiledSheets.some(s => s.name === chosenVal)) {
                chosenVal = latestMatch ? latestMatch.name : (compiledSheets[compiledSheets.length - 1]?.name || '');
            }
            renderCustomSyncDropdown(compiledSheets, chosenVal);
        } else {
            if (badge) badge.textContent = 'Ready';
        }
    } catch (e) {
        console.error('Error refreshing sync dropdown:', e);
    }
}

function onSyncSheetSelected() {
    const sel = document.getElementById('sync-sheet-select');
    const alertBox = document.getElementById('sync-sheet-capacity-alert');
    if (!sel || !alertBox) return;

    const opt = sel.options[sel.selectedIndex];
    if (!opt || !opt.value) {
        alertBox.className = 'sync-capacity-card hidden';
        alertBox.innerHTML = '';
        return;
    }

    const rows = parseInt(opt.dataset?.rows || '0', 10);
    const cap = getSheetCapacityStatus(rows);
    const percent = Math.min(100, Math.round((rows / 150000) * 100));

    alertBox.className = `sync-capacity-card ${cap.level}`;

    let iconSvg = '';
    if (cap.level === 'critical') {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 7.86 7.86 2"></polygon><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else if (cap.level === 'orange') {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
    } else if (cap.level === 'yellow') {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;
    }

    alertBox.innerHTML = `
        <div class="sync-capacity-card-icon">
            ${iconSvg}
        </div>
        <div class="sync-capacity-card-body">
            <div class="sync-capacity-card-title">
                <span>${esc(cap.warningTitle.split(':')[0])}</span>
                <span style="font-size:0.75rem; font-weight:700;">${percent}%</span>
            </div>
            <div class="sync-capacity-card-sub">
                Target Sheet Load: <strong>${formatRowCount(rows)}</strong> / 1.5 Lakh max recommended rows
            </div>
            <div class="sync-capacity-progress-track">
                <div class="sync-capacity-progress-fill ${cap.level}" style="width: ${Math.max(4, percent)}%;"></div>
            </div>
            <p class="sync-capacity-card-advisory">${esc(cap.warningDesc)}</p>
        </div>
    `;
}

// Close custom sync dropdown on outside click
document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('custom-sync-dropdown');
    if (!dropdown) return;
    if (!dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
        const menu = document.getElementById('custom-sync-menu');
        if (menu) menu.classList.add('hidden');
    }
});

function closeCapacityConfirmModal() {

    const modal = document.getElementById('capacity-confirm-modal-overlay');

    if (modal) modal.classList.add('hidden');

}



function proceedSyncAnyway() {

    closeCapacityConfirmModal();

    window._overrideCapacitySync = true;

    startSyncToGoogleSheets();

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



    const sheetRows = parseInt(selectedOpt?.dataset?.rows || '0', 10);

    if (sheetRows >= 150000 && mode === 'append' && !window._overrideCapacitySync) {

        const modal = document.getElementById('capacity-confirm-modal-overlay');

        const msg = document.getElementById('capacity-confirm-msg');

        if (modal && msg) {

            msg.innerHTML = `Target sheet <strong>"${esc(sheetName)}"</strong> already contains <strong>${formatRowCount(sheetRows)}</strong> (≥ 1.5 Lakh limit).<br><br>Appending more records to this sheet may cause Google Sheets to freeze, slow down, or fail due to Google cell capacity limits.<br><br><strong>Recommendation:</strong> Click below to create a new partition sheet (e.g. FY 2026-27-1) instead.`;

            modal.classList.remove('hidden');

            return;

        }

    }

    window._overrideCapacitySync = false;



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

        

        // Ultra-Fast Direct Google Sheets API v4 Sync (5,000 rows/batch)
        const isDirect = !!syncData.directSync;
        const chunkSize = 5000;
        const totalBatches = Math.ceil(maxRows / chunkSize);
        
        let currentSaleStartRow = 3;
        let currentPurchaseStartRow = 3;

        if (isDirect) {
            showGlobalLoader('Direct Google Sheets API', 'Initializing high-speed connection...');
            const initRes = await safeFetchJson('/api/direct-sync-init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sheetName,
                    mode,
                    toSyncSale,
                    toSyncPurchase
                })
            });
            if (!initRes.ok || !initRes.data || !initRes.data.success) {
                throw new Error(initRes.data?.error || 'Direct sync initialization failed');
            }
            currentSaleStartRow = initRes.data.saleStartRow || 3;
            currentPurchaseStartRow = initRes.data.purchaseStartRow || 3;
        }

        for (let i = 1; i <= totalBatches; i++) {
            const startIdx = (i - 1) * chunkSize;
            const percent = Math.round((i / totalBatches) * 100);
            const remaining = Math.max(0, totalBatches - i);
            const batchTitle = isDirect ? 'Direct Google Sheets API v4' : 'Syncing to Google Sheets';
            const batchMsg = isDirect 
                ? `Direct API Batch ${i} of ${totalBatches} (${Math.min(chunkSize, maxRows - startIdx)} rows)... [${percent}%]`
                : `Uploading Batch ${i} of ${totalBatches}... (${percent}%)`;

            showGlobalLoader(batchTitle, batchMsg);
            if (progFill) progFill.style.width = percent + '%';

            // Print live ticker in browser console every second with exact timestamp
            const initialTime = new Date().toLocaleTimeString();
            console.log(`[${initialTime}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);

            const liveTimer = setInterval(() => {
                const now = new Date().toLocaleTimeString();
                console.log(`[${now}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);
                showGlobalLoader(batchTitle, `[${now}] Updating data to database... (Batch ${i}/${totalBatches} | Remaining: ${remaining})`);
            }, 1000);

            try {
                if (isDirect) {
                    const res = await safeFetchJson('/api/direct-sync-chunk', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            sheetName,
                            mode,
                            offset: startIdx,
                            limit: chunkSize,
                            saleStartRow: currentSaleStartRow,
                            purchaseStartRow: currentPurchaseStartRow,
                            batchIndex: i,
                            totalBatches: totalBatches
                        })
                    });
                    if (!res.ok || !res.data || !res.data.success) {
                        throw new Error(res.data?.error || `Direct API Batch ${i} failed`);
                    }
                    currentSaleStartRow = res.data.nextSaleStartRow;
                    currentPurchaseStartRow = res.data.nextPurchaseStartRow;
                } else {
                    // Fallback to Google Apps Script Web App
                    const { ok: okChunk, data: chunkData } = await safeFetchJson(`/api/get-sync-chunk?offset=${startIdx}&limit=${chunkSize}`);
                    if (!okChunk || chunkData.error) throw new Error(chunkData.error || `Failed to load batch ${i}`);

                    const saleChunk = chunkData.saleRows || [];
                    const purchaseChunk = chunkData.purchaseRows || [];

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

                    const res = await safeFetchJson('/api/send-sync-chunk', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            webAppUrl: activeUrl,
                            payload: payload
                        })
                    });

                    if (!res.ok || !res.data || !res.data.success) {
                        throw new Error(res.data?.error || `Batch ${i} failed`);
                    }
                }
            } finally {
                clearInterval(liveTimer);
            }

            const doneTime = new Date().toLocaleTimeString();
            console.log(`[${doneTime}] Updating data to database... (Batch ${i}/${totalBatches} done | Remaining: ${remaining})`);
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
    const isErr = icon === '❌' || icon === 'Error' || (typeof icon === 'string' && (icon.includes('❌') || icon.includes('Error')));
    const isWarn = icon === '⚠️' || icon === 'Warning';
    const t = document.getElementById('toast');
    const iconEl = document.getElementById('toast-icon');
    if (iconEl) {
        if (isErr) {
            iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
        } else if (isWarn) {
            iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
        } else {
            iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
        }
    }
    document.getElementById('toast-message').textContent = msg;
    t.classList.remove('hidden');
    t.classList.toggle('error', isErr);
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

        const allKeys = getAvailableFYKeys();



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



    const rowCount = state.fyRowCounts[fy] || 0;

    const cap = getSheetCapacityStatus(rowCount);

    let badgeHtml = '';

    if (rowCount > 0) {

        badgeHtml = `<span class="fy-status-pill ${cap.level}">${formatRowCount(rowCount)} • ${cap.label}</span>`;

    }



    const div = document.createElement('div');

    div.className = 'fy-setting-item';

    div.style.cssText = 'background:var(--bg-secondary); padding:14px; border-radius:var(--radius-md); border:1px solid var(--border-glass); display:flex; flex-direction:column; gap:10px;';

    div.innerHTML = `

        <div style="display:flex; justify-content:space-between; align-items:center;">

            <div style="display:flex; align-items:center; gap:8px;">

                <label style="font-size:0.75rem; color:var(--text-muted); font-weight:700; text-transform:uppercase; letter-spacing:0.04em;">Financial Year:</label>

                <input type="text" class="fy-key-input compact-select" value="${esc(fy)}" placeholder="2026-27" style="font-weight:bold; width:110px; padding:4px 8px;">

                ${badgeHtml}

            </div>

            <button type="button" class="btn btn-sm" onclick="this.closest('.fy-setting-item').remove()" style="display:inline-flex; align-items:center; gap:6px; background:rgba(239, 68, 68, 0.08); border:1px solid rgba(239, 68, 68, 0.28); color:#dc2626; padding:5px 12px; border-radius:8px; font-weight:700; font-size:0.75rem; cursor:pointer; backdrop-filter:blur(8px); transition:all 0.2s;" title="Remove this FY"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg><span>Remove</span></button>

        </div>

        <div style="display:flex; flex-direction:column; gap:8px;">

            <div>

                <label style="font-size:0.72rem; color:var(--text-secondary); font-weight:600; display:flex; justify-content:space-between; margin-bottom:3px;">

                    <span>Google Web App URL <span style="font-weight:normal; color:var(--text-muted);">(Optional / Legacy Fallback)</span></span>

                </label>

                <input type="text" class="fy-url-input search-input" value="${esc(webAppUrl)}" placeholder="https://script.google.com/macros/s/.../exec" style="width:100%; font-size:0.8rem; padding:6px 10px;">

            </div>

            <div>

                <label style="font-size:0.72rem; color:var(--accent-purchase); font-weight:600; display:flex; justify-content:space-between; margin-bottom:3px;">

                    <span>Google Sheet Direct Link <span style="font-weight:normal; color:var(--text-muted);">(Superfast Viewer — Anyone with link: Viewer)</span></span>

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



function addNewPartitionRow() {

    const keys = getAvailableFYKeys();

    let baseFY = state.currentFY || getLatestConfiguredFY();

    let nextFY = '';

    const match = baseFY.match(/^(.*?)_?(\d{4}-\d{2})(?:-(\d+))?$/);

    if (match) {

        const coreYears = match[2];

        const currentPart = match[3] ? parseInt(match[3], 10) : 0;

        let maxPart = currentPart;

        keys.forEach(k => {

            const km = k.match(new RegExp(`^${coreYears}(?:-(\\d+))?$`));

            if (km) {

                const p = km[1] ? parseInt(km[1], 10) : 0;

                if (p > maxPart) maxPart = p;

            }

        });

        nextFY = `${coreYears}-${maxPart + 1}`;

    } else {

        nextFY = `${baseFY}-1`;

    }



    addFYSettingRowElement(nextFY, '', '');

    showToast('✨', `Added partition row: FY ${nextFY}`);



    const container = document.getElementById('fy-url-settings-list');

    if (container) {

        container.scrollTop = container.scrollHeight;

        const lastInput = container.querySelector('.fy-setting-item:last-child .fy-sheet-url-input');

        if (lastInput) lastInput.focus();

    }

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

        const res = await fetch('/api/save-fy-settings', {

            method: 'POST',

            headers: { 'Content-Type': 'application/json' },

            body: JSON.stringify({ urls, sheet_urls: sheetUrls })

        });

        const data = await res.json();

        if (data && data.status === 'Success') {

            if (data.urls) saveFyUrls(data.urls);

            if (data.sheet_urls) saveFySheetUrls(data.sheet_urls);

            try { sessionStorage.removeItem('user_switched_fy'); } catch(e) {}

            state.currentFY = (data && data.latest_fy) ? data.latest_fy : getLatestConfiguredFY();

            const label = document.getElementById('fy-dropdown-label');

            if (label) label.textContent = `FY ${state.currentFY}`;

        }

    } catch(e) {

        console.error('[FY SETTINGS] Failed to sync settings to server:', e);

    }

    closeSettingsModal();

    showToast('Settings Saved! Switched to latest FY sheet.', 'success');

    populateFYSelector();

    refreshSheetDropdown();

    refreshSyncDropdown();

    fetchAllFYRowCounts();

}





Object.assign(window, {

    clearAllData,

    closeModal,

    confirmClearData,

    onSheetSelectionChange,

    onSheetRowsChange,

    loadSheetData,

    handleUniversalSearch,
    handleUniversalSearchKey,
    handleUniversalSearchInput,

    triggerClearSheetWarning,

    changePage,

    startSyncToGoogleSheets,

    openSyncModal,

    closeSyncModal,

    toggleCustomSyncDropdown,

    selectCustomSyncOption,

    filterCustomSyncSheets,

    selectSyncMode,

    updateSyncModeUI,

    refreshSyncDropdown,

    confirmClearSheet,

    closeClearSheetModal,

    closeSuccessModal,

    openSettingsModal,

    closeSettingsModal,

    closeSettingsAuthModal,

    verifySettingsPassword,

    addNewFYSettingRow,

    addNewPartitionRow,

    saveSettings,

    switchFinancialYear,

    toggleFYDropdown,

    closeCapacityConfirmModal,

    proceedSyncAnyway,

    onSyncSheetSelected,

    updateCapacityIndicators,

    fetchAllFYRowCounts,

    goToPage,

    renderFooterPagination,

    executeFooterGoTo,

    onFooterRowsPerPageChange

});

