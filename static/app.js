// ===================================================== tiện ích
const $ = (s) => document.querySelector(s);
const vnd = (v) => v == null ? '—' : new Intl.NumberFormat('vi-VN').format(Math.round(v)) + ' đ';
const mil = (v) => v == null ? '—' : (v / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + ' tr';
const num = (v, d = 0) => v == null ? '—' : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v, d = 1) => v == null ? '—' : (v * 100).toLocaleString('vi-VN', { maximumFractionDigits: d, minimumFractionDigits: d }) + '%';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const TX_LABEL = { NHAP: ['Nhập', 'success'], BAN: ['Bán', 'primary'], TRA: ['Trả', 'warning'], HUY: ['Hủy', 'danger'] };
const STATUS = { CHO_DUYET: ['Chờ duyệt', 'secondary'], AP_DUNG: ['Đã áp dụng', 'success'], TU_CHOI: ['Từ chối', 'danger'] };
const STRATEGY = { LOI_NHUAN: 'Tối đa lợi nhuận', DOANH_THU: 'Tối đa doanh thu', XA_KHO: 'Giải phóng tồn kho' };

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {},
    ...opts,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : res.statusText);
  return data;
}

function toast(msg, ok = true) {
  const el = $('#toast');
  el.className = 'toast text-bg-' + (ok ? 'success' : 'danger');
  $('#toastBody').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3500 }).show();
}

const charts = {};
function drawChart(id, config) {
  charts[id]?.destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

// ===================================================== điều hướng tab
const loaders = {};
let phones = [], brands = [], cpus = [];

document.querySelectorAll('#tabs .nav-link').forEach((a) => a.addEventListener('click', (e) => {
  e.preventDefault();
  showTab(a.dataset.tab);
}));

function showTab(name) {
  document.querySelectorAll('#tabs .nav-link').forEach((x) => x.classList.toggle('active', x.dataset.tab === name));
  document.querySelectorAll('.tab').forEach((s) => s.classList.toggle('d-none', s.id !== 'tab-' + name));
  loaders[name]?.().catch((e) => toast(e.message, false));
}

async function refreshPhones() {
  phones = await api('/api/phones');
  const opts = phones.map((p) => `<option value="${p.id}">${esc(p.sku)} — ${esc(p.name)}</option>`).join('');
  $('#txPhone').innerHTML = opts;
  $('#prPhone').innerHTML = opts;
  $('#txFilterPhone').innerHTML = '<option value="">Tất cả mặt hàng</option>' + opts;
  updateTxInfo();
}

// ===================================================== TỔNG QUAN
loaders.dashboard = async () => {
  const d = await api('/api/dashboard');
  const kpi = (label, value, icon, cls = '') => `
    <div class="col-6 col-lg-2"><div class="card kpi h-100"><div class="card-body">
      <div class="label"><i class="bi ${icon}"></i> ${label}</div><div class="value ${cls}">${value}</div></div></div></div>`;
  $('#kpis').innerHTML =
    kpi('Mặt hàng', num(d.n_phones), 'bi-phone') +
    kpi('Tổng tồn kho', num(d.total_stock) + ' máy', 'bi-box-seam') +
    kpi('Giá trị tồn (giá nhập)', mil(d.stock_value), 'bi-cash-stack') +
    kpi('Doanh thu 30 ngày', mil(d.revenue_30d), 'bi-graph-up') +
    kpi('Lợi nhuận gộp 30 ngày', mil(d.profit_30d), 'bi-piggy-bank', 'text-success') +
    kpi('Gợi ý giá chờ duyệt', num(d.pending_suggestions), 'bi-magic', d.pending_suggestions ? 'text-primary' : '');

  drawChart('chartWeekly', {
    type: 'bar',
    data: {
      labels: d.weekly.map((w) => w.week.slice(5).split('-').reverse().join('/')),
      datasets: [
        { label: 'Doanh thu (triệu đ)', data: d.weekly.map((w) => w.revenue / 1e6), backgroundColor: '#4c7bf3', yAxisID: 'y' },
        { label: 'Số máy bán', data: d.weekly.map((w) => w.qty), type: 'line', borderColor: '#f29d38', backgroundColor: '#f29d38', yAxisID: 'y1', tension: .3, pointRadius: 2 },
      ],
    },
    options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: { y: { title: { display: true, text: 'triệu đ' } }, y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'máy' } } } },
  });

  $('#topList').innerHTML = d.top.map((t) => `<li class="list-group-item d-flex justify-content-between small">
    <span class="ms-2 me-auto">${esc(t.name)}</span><span class="badge text-bg-primary">${t.qty} máy</span></li>`).join('') || '<li class="list-group-item small">Chưa có dữ liệu</li>';
  $('#lowList').innerHTML = d.low_stock.length ? `<table class="table table-sm mb-0"><thead><tr><th>Mặt hàng</th><th class="num">Tồn</th><th class="num">Tối thiểu</th><th></th></tr></thead><tbody>${
    d.low_stock.map((p) => `<tr><td>${esc(p.name)}</td><td class="num text-danger fw-semibold">${p.stock}</td><td class="num">${p.min_stock}</td>
      <td class="text-end"><button class="btn btn-sm btn-outline-success" onclick="quickImport(${p.id})">Nhập hàng</button></td></tr>`).join('')}</tbody></table>`
    : '<span class="text-body-secondary">Không có mặt hàng nào dưới ngưỡng tồn tối thiểu.</span>';
  $('#slowList').innerHTML = d.slow_moving.length ? `<table class="table table-sm mb-0"><thead><tr><th>Mặt hàng</th><th class="num">Tồn</th><th class="num">Bán/tuần</th><th class="num">Đủ bán</th><th></th></tr></thead><tbody>${
    d.slow_moving.map((p) => `<tr><td>${esc(p.name)}</td><td class="num">${p.stock}</td><td class="num">${num(p.weekly_rate, 1)}</td>
      <td class="num">${p.weeks_cover ? num(p.weeks_cover, 1) + ' tuần' : '∞'}</td>
      <td class="text-end"><button class="btn btn-sm btn-outline-primary" onclick="openPricing(${p.id}, 'XA_KHO')">Tính giá xả kho</button></td></tr>`).join('')}</tbody></table>`
    : '<span class="text-body-secondary">Không có mặt hàng tồn lâu.</span>';
};

// ===================================================== KHO HÀNG
loaders.phones = async () => {
  await refreshPhones();
  renderPhones();
};

function renderPhones() {
  const q = $('#phoneSearch').value.trim().toLowerCase();
  const list = phones.filter((p) => !q || [p.sku, p.name, p.brand].some((s) => s.toLowerCase().includes(q)));
  $('#phoneRows').innerHTML = list.map((p) => {
    const margin = (p.price - p.cost_price) / p.price;
    return `<tr>
      <td class="text-nowrap">${esc(p.sku)}</td><td>${esc(p.name)}</td><td>${esc(p.brand)}</td><td class="text-nowrap">${esc(p.cpu)}</td>
      <td class="text-nowrap">${p.ram}/${p.rom >= 1024 ? p.rom / 1024 + 'TB' : p.rom + 'GB'}</td>
      <td class="num">${vnd(p.cost_price)}</td><td class="num fw-semibold">${vnd(p.price)}</td>
      <td class="num ${margin < 0.05 ? 'text-danger' : ''}">${pct(margin)}</td>
      <td class="num">${p.low_stock ? `<span class="badge text-bg-danger">${p.stock}</span>` : p.stock}</td>
      <td class="num">${p.sold_30d}</td>
      <td class="text-end text-nowrap">
        <button class="btn btn-sm btn-outline-primary" title="Tối ưu giá" onclick="openPricing(${p.id})"><i class="bi bi-graph-up-arrow"></i></button>
        <button class="btn btn-sm btn-outline-secondary" title="Sửa" onclick="editPhone(${p.id})"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger" title="Xóa" onclick="deletePhone(${p.id})"><i class="bi bi-trash"></i></button>
      </td></tr>`;
  }).join('');
}
$('#phoneSearch').addEventListener('input', renderPhones);

const phoneModal = () => bootstrap.Modal.getOrCreateInstance($('#phoneModal'));
let editingId = null;

async function ensureCatalog() {
  if (!brands.length) brands = await api('/api/brands');
  if (!cpus.length) cpus = await api('/api/cpus');
  const f = $('#phoneForm');
  f.id_brand.innerHTML = brands.map((b) => `<option value="${b.id}">${esc(b.name)} (điểm ${b.point})</option>`).join('');
  f.id_cpu.innerHTML = cpus.map((c) => `<option value="${c.id}">${esc(c.name_cpu)} (điểm ${c.point})</option>`).join('');
}

$('#btnNewPhone').addEventListener('click', async () => {
  await ensureCatalog();
  editingId = null;
  const f = $('#phoneForm');
  f.reset();
  f.release_year.value = new Date().getFullYear();
  $('#phoneModalTitle').textContent = 'Thêm mặt hàng';
  $('#predictConfigMsg').innerHTML = '';
  phoneModal().show();
});

window.editPhone = async (id) => {
  await ensureCatalog();
  const p = phones.find((x) => x.id === id);
  editingId = id;
  const f = $('#phoneForm');
  for (const k of ['sku', 'name', 'id_brand', 'id_cpu', 'ram', 'rom', 'widescreen', 'ppi', 'battery', 'camera', 'release_year', 'cost_price', 'price', 'min_stock']) f[k].value = p[k];
  $('#phoneModalTitle').textContent = 'Sửa mặt hàng ' + p.sku;
  $('#predictConfigMsg').innerHTML = '';
  phoneModal().show();
};

window.deletePhone = async (id) => {
  const p = phones.find((x) => x.id === id);
  if (!confirm(`Xóa mặt hàng "${p.name}" cùng toàn bộ lịch sử nhập/xuất?`)) return;
  await api('/api/phones/' + id, { method: 'DELETE' });
  toast('Đã xóa ' + p.name);
  loaders.phones();
};

function formData(f) {
  const d = Object.fromEntries(new FormData(f).entries());
  for (const k of Object.keys(d)) if (k !== 'sku' && k !== 'name') d[k] = Number(d[k]);
  return d;
}

$('#btnPredictConfig').addEventListener('click', async () => {
  const d = formData($('#phoneForm'));
  try {
    const r = await api('/api/ml/predict-config', { method: 'POST', body: d });
    $('#predictConfigMsg').innerHTML = `<div class="alert alert-info py-2 mb-0">Giá tham chiếu theo cấu hình (hồi quy bội): <b>${vnd(r.rounded)}</b>
      <span class="text-body-secondary">— khoảng ±RMSE: ${mil(r.low)} – ${mil(r.high)}</span>
      <button type="button" class="btn btn-sm btn-primary ms-2" id="btnUseRef">Dùng giá này</button></div>`;
    $('#btnUseRef').onclick = () => { $('#phoneForm').price.value = r.rounded; };
  } catch (e) { toast('Cần nhập đủ cấu hình: ' + e.message, false); }
});

$('#phoneForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const d = formData(e.target);
  try {
    if (editingId) await api('/api/phones/' + editingId, { method: 'PUT', body: d });
    else await api('/api/phones', { method: 'POST', body: d });
    phoneModal().hide();
    toast('Đã lưu ' + d.name);
    loaders.phones();
  } catch (err) { toast(err.message, false); }
});

// ===================================================== NHẬP / XUẤT
loaders.stock = async () => {
  await refreshPhones();
  await loadTx();
};

function updateTxInfo() {
  const p = phones.find((x) => x.id === Number($('#txPhone').value));
  $('#txInfo').innerHTML = p ? `Tồn: <b>${p.stock}</b> · Giá nhập BQ: ${vnd(p.cost_price)} · Giá bán: ${vnd(p.price)}` : '';
}
$('#txPhone').addEventListener('change', updateTxInfo);

async function loadTx() {
  const params = new URLSearchParams({ limit: 300 });
  if ($('#txFilterType').value) params.set('type', $('#txFilterType').value);
  if ($('#txFilterPhone').value) params.set('phone_id', $('#txFilterPhone').value);
  const rows = await api('/api/stock/tx?' + params);
  $('#txRows').innerHTML = rows.map((t) => `<tr><td class="text-nowrap">${t.created_at}</td>
    <td><span class="badge text-bg-${TX_LABEL[t.type][1]}">${TX_LABEL[t.type][0]}</span></td>
    <td>${esc(t.name)}</td><td class="num">${t.quantity}</td><td class="num">${vnd(t.unit_price)}</td><td>${esc(t.note)}</td></tr>`).join('');
}
$('#txFilterType').addEventListener('change', loadTx);
$('#txFilterPhone').addEventListener('change', loadTx);

window.quickImport = async (id) => {
  showTab('stock');
  await loaders.stock();
  $('#txNhap').checked = true;
  $('#txPhone').value = id;
  updateTxInfo();
  $('#txQty').focus();
};

$('#stockForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const kind = document.querySelector('input[name=txType]:checked').value;
  const body = { phone_id: Number($('#txPhone').value), quantity: Number($('#txQty').value), note: $('#txNote').value || null };
  if ($('#txPrice').value) body.unit_price = Number($('#txPrice').value);
  try {
    const r = await api('/api/stock/' + kind, { method: 'POST', body });
    toast(`Đã lưu phiếu ${kind === 'import' ? 'nhập' : 'xuất bán'}. Tồn mới: ${r.stock}`);
    $('#txNote').value = ''; $('#txPrice').value = '';
    await loaders.stock();
  } catch (err) { toast(err.message, false); }
});

// ===================================================== TỐI ƯU GIÁ
loaders.pricing = async () => {
  if (!phones.length) await refreshPhones();
};

window.openPricing = async (id, strategy) => {
  showTab('pricing');
  if (!phones.length) await refreshPhones();
  $('#prPhone').value = id;
  if (strategy) $('#prStrategy').value = strategy;
  runPricing();
};

function pricingBody() {
  return { strategy: $('#prStrategy').value, weeks_to_clear: Number($('#prWeeks').value), min_margin: Number($('#prMargin').value) / 100 };
}

$('#pricingForm').addEventListener('submit', (e) => { e.preventDefault(); runPricing(); });

async function runPricing() {
  $('#pricingAll').innerHTML = '';
  $('#pricingResult').innerHTML = '<div class="text-center p-4"><div class="spinner-border"></div></div>';
  try {
    const r = await api('/api/pricing/suggest', { method: 'POST', body: { phone_id: Number($('#prPhone').value), ...pricingBody() } });
    renderPricing(r);
  } catch (e) { $('#pricingResult').innerHTML = ''; toast(e.message, false); }
}

function changeBadge(v) {
  if (Math.abs(v) < 0.005) return '<span class="badge text-bg-light">giữ giá</span>';
  return `<span class="badge ${v > 0 ? 'badge-up' : 'badge-down'}">${v > 0 ? '▲ tăng' : '▼ giảm'} ${pct(Math.abs(v))}</span>`;
}

function renderPricing(r) {
  const cmp = (label, cur, sug, fmt) => `<tr><td>${label}</td><td class="num">${fmt(cur)}</td><td class="num fw-semibold">${fmt(sug)}</td></tr>`;
  const formula = r.demand_valid ? `
    <div class="small mt-2"><b>Đường cầu:</b> Q = ${num(r.a * 1e6, 3)}·P<sub>(triệu)</sub> + ${num(r.b, 2)}
      &nbsp;·&nbsp; R² = ${num(r.r2, 3)} &nbsp;·&nbsp; RMSE = ${num(r.rmse, 2)} máy/tuần<br>
      <b>Nghiệm giải tích</b> (${r.strategy === 'LOI_NHUAN' ? 'P* = c/2 − b/(2a)' : r.strategy === 'DOANH_THU' ? 'P* = −b/(2a)' : 'P ≤ (S/W − b)/a'}): ${vnd(r.closed_form_price)}
      &nbsp;·&nbsp; vùng giá an toàn: ${mil(r.price_range[0])} – ${mil(r.price_range[1])}</div>` : '';
  $('#pricingResult').innerHTML = `
  <div class="row g-3">
    <div class="col-lg-5"><div class="card h-100"><div class="card-body">
      <h6 class="card-title">${esc(r.name)} <span class="text-body-secondary small">(${esc(r.sku)})</span></h6>
      <div class="small text-body-secondary mb-2">${esc(r.strategy_label)} · ${esc(r.method)}</div>
      <div class="d-flex align-items-baseline gap-3 flex-wrap">
        <div><div class="small text-body-secondary">Giá hiện hành</div><div class="price-big">${vnd(r.current_price)}</div></div>
        <i class="bi bi-arrow-right fs-4"></i>
        <div><div class="small text-body-secondary">Giá đề xuất</div><div class="price-big text-primary">${vnd(r.suggested_price)}</div></div>
        ${changeBadge(r.change_pct)}
      </div>
      <table class="table table-sm small mt-3"><thead><tr><th></th><th class="num">Giá hiện hành</th><th class="num">Giá đề xuất</th></tr></thead><tbody>
        ${r.demand_valid ? cmp('Số máy bán dự kiến/tuần', r.current_qty, r.expected_qty, (v) => num(v, 1)) +
          cmp('Doanh thu dự kiến/tuần', r.current_revenue, r.expected_revenue, mil) +
          cmp('Lợi nhuận gộp dự kiến/tuần', r.current_profit, r.expected_profit, mil) +
          cmp('Tồn kho đủ bán', r.weeks_of_stock_current, r.weeks_of_stock_suggested, (v) => v == null ? '∞' : num(v, 1) + ' tuần') : ''}
        <tr><td>Giá nhập bình quân</td><td class="num" colspan="2">${vnd(r.cost_price)}</td></tr>
        <tr><td>Giá tham chiếu theo cấu hình</td><td class="num" colspan="2">${vnd(r.reference_price)}</td></tr>
        <tr><td>Tồn kho hiện tại</td><td class="num" colspan="2">${r.stock} máy</td></tr>
      </tbody></table>
      ${formula}
      ${r.notes.length ? `<ul class="small text-warning-emphasis note-list mt-2 mb-0">${r.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>` : ''}
      <div class="d-flex gap-2 mt-3">
        <button class="btn btn-success" onclick="decide(${r.suggestion_id}, 'apply')"><i class="bi bi-check2"></i> Áp dụng giá đề xuất</button>
        <button class="btn btn-outline-danger" onclick="decide(${r.suggestion_id}, 'reject')"><i class="bi bi-x"></i> Từ chối</button>
      </div>
    </div></div></div>
    <div class="col-lg-7"><div class="card h-100"><div class="card-body">
      ${r.demand_valid ? `<h6 class="card-title">Dữ liệu bán theo tuần và đường hồi quy Q = a·P + b</h6>
      <div class="chart-box"><canvas id="chartDemand"></canvas></div>
      <h6 class="card-title mt-3">Doanh thu / lợi nhuận dự kiến theo giá</h6>
      <div class="chart-box"><canvas id="chartProfit"></canvas></div>`
      : '<div class="alert alert-warning">Chưa đủ dữ liệu bán để xây dựng đường cầu, hệ thống dùng giá tham chiếu theo cấu hình.</div>'}
    </div></div></div>
  </div>`;
  if (!r.demand_valid) return;

  const line = [r.price_range[0], r.price_range[1]].map((p) => ({ x: p / 1e6, y: Math.max(0, r.a * p + r.b) }));
  drawChart('chartDemand', {
    type: 'scatter',
    data: { datasets: [
      { label: 'Tuần thực tế (giá, số bán)', data: r.points.map((p) => ({ x: p.price / 1e6, y: p.qty })), backgroundColor: 'rgba(76,123,243,.55)' },
      { label: 'Hồi quy tuyến tính', data: line, type: 'line', borderColor: '#e2483d', pointRadius: 0, borderWidth: 2 },
      { label: 'Giá hiện hành', data: [{ x: r.current_price / 1e6, y: r.current_qty }], backgroundColor: '#555', pointRadius: 7, pointStyle: 'triangle' },
      { label: 'Giá đề xuất', data: [{ x: r.suggested_price / 1e6, y: r.expected_qty }], backgroundColor: '#1a9e5a', pointRadius: 8, pointStyle: 'rectRot' },
    ] },
    options: { maintainAspectRatio: false, scales: { x: { title: { display: true, text: 'Giá bán (triệu đ)' } }, y: { title: { display: true, text: 'Số máy bán / tuần' }, beginAtZero: true } } },
  });
  drawChart('chartProfit', {
    type: 'line',
    data: { labels: r.curve.map((c) => (c.price / 1e6).toFixed(2)), datasets: [
      { label: 'Doanh thu/tuần (triệu đ)', data: r.curve.map((c) => c.revenue / 1e6), borderColor: '#4c7bf3', pointRadius: 0, yAxisID: 'y' },
      { label: 'Lợi nhuận gộp/tuần (triệu đ)', data: r.curve.map((c) => c.profit / 1e6), borderColor: '#1a9e5a', pointRadius: 0, yAxisID: 'y1' },
    ] },
    options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: { x: { title: { display: true, text: 'Giá bán (triệu đ)' }, ticks: { maxTicksLimit: 10 } },
        y: { title: { display: true, text: 'Doanh thu' } }, y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Lợi nhuận' } } } },
  });
}

window.decide = async (sid, action) => {
  try {
    await api(`/api/pricing/suggestions/${sid}/${action}`, { method: 'POST' });
    toast(action === 'apply' ? 'Đã áp dụng giá mới' : 'Đã từ chối gợi ý');
    await refreshPhones();
    if ($('#pricingAll').innerHTML) suggestAll(false);
  } catch (e) { toast(e.message, false); }
};

$('#btnSuggestAll').addEventListener('click', () => suggestAll(true));

async function suggestAll(recompute) {
  $('#pricingResult').innerHTML = '';
  $('#pricingAll').innerHTML = '<div class="text-center p-4"><div class="spinner-border"></div></div>';
  let rows;
  if (recompute) rows = await api('/api/pricing/suggest-all', { method: 'POST', body: pricingBody() });
  else rows = (await api('/api/pricing/suggestions?status=CHO_DUYET')).map((s) => ({ ...s, suggestion_id: s.id, current_price: s.current_price, change_pct: (s.suggested_price - s.current_price) / s.current_price, strategy_label: STRATEGY[s.strategy] }));
  const totalCur = rows.reduce((a, r) => a + (r.current_profit || 0), 0);
  const totalNew = rows.reduce((a, r) => a + (r.expected_profit || 0), 0);
  $('#pricingAll').innerHTML = `<div class="card"><div class="card-body">
    <div class="d-flex align-items-center mb-2"><h6 class="card-title mb-0 me-auto">Gợi ý giá cho toàn bộ kho</h6>
      ${recompute ? `<span class="small me-3">Lợi nhuận gộp dự kiến/tuần: ${mil(totalCur)} → <b class="text-success">${mil(totalNew)}</b></span>` : ''}
      <button class="btn btn-sm btn-success" onclick="applyAll()">Áp dụng tất cả</button></div>
    <div class="table-responsive"><table class="table table-sm small align-middle mb-0"><thead class="table-light"><tr>
      <th>Mặt hàng</th><th class="num">Tồn</th><th class="num">Giá hiện hành</th><th class="num">Giá đề xuất</th><th>Thay đổi</th>
      <th class="num">SL/tuần dự kiến</th><th class="num">LN/tuần dự kiến</th><th class="num">R²</th><th></th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${esc(r.name)}</td><td class="num">${r.stock ?? ''}</td><td class="num">${vnd(r.current_price)}</td>
        <td class="num fw-semibold">${vnd(r.suggested_price)}</td><td>${changeBadge(r.change_pct)}</td>
        <td class="num">${num(r.expected_qty, 1)}</td><td class="num">${mil(r.expected_profit)}</td><td class="num">${r.r2 != null ? num(r.r2, 2) : '—'}</td>
        <td class="text-end text-nowrap"><button class="btn btn-sm btn-outline-secondary" title="Chi tiết" onclick="openPricing(${r.phone_id})"><i class="bi bi-eye"></i></button>
          <button class="btn btn-sm btn-outline-success" onclick="decide(${r.suggestion_id}, 'apply')"><i class="bi bi-check2"></i></button>
          <button class="btn btn-sm btn-outline-danger" onclick="decide(${r.suggestion_id}, 'reject')"><i class="bi bi-x"></i></button></td></tr>`).join('')}
    </tbody></table></div></div></div>`;
  window._pendingIds = rows.map((r) => r.suggestion_id);
}

window.applyAll = async () => {
  if (!confirm('Áp dụng toàn bộ giá đề xuất đang chờ duyệt?')) return;
  for (const id of window._pendingIds || []) await api(`/api/pricing/suggestions/${id}/apply`, { method: 'POST' }).catch(() => {});
  toast('Đã áp dụng toàn bộ giá đề xuất');
  await refreshPhones();
  $('#pricingAll').innerHTML = '';
};

// ===================================================== MÔ HÌNH & DỮ LIỆU
loaders.model = async () => {
  const [m, market] = await Promise.all([api('/api/ml/config-model'), api('/api/market')]);
  const h = m.metrics.hold_out, k = m.metrics.k_fold;
  const row = (name, s) => `<tr><td>${name}</td><td class="num">${num(s.R2, 3)}</td><td class="num">${mil(s.RMSE)}</td><td class="num">${mil(s.MAE)}</td></tr>`;
  $('#configMetrics').innerHTML = `<div class="small text-body-secondary mb-1">Huấn luyện lúc ${m.trained_at.replace('T', ' ').slice(0, 19)} · ${m.n_samples} mẫu</div>
    <table class="table table-sm small mb-0"><thead><tr><th>Đánh giá</th><th class="num">R²</th><th class="num">RMSE</th><th class="num">MAE</th></tr></thead><tbody>
    ${row(`Hold-out – tập huấn luyện (${h.n_train})`, h.train)}${row(`Hold-out – tập kiểm tra (${h.n_test})`, h.test)}${row(`k-fold (k = ${k.k}), trung bình`, k)}</tbody></table>`;
  $('#coefRows').innerHTML = m.coefficients.map((c) => `<tr><td>${c.label}</td><td class="num">${num(c.weight_01, 3)}</td>
    <td class="num ${c.pct_per_unit >= 0 ? 'text-success' : 'text-danger'}">${c.pct_per_unit >= 0 ? '+' : ''}${pct(c.pct_per_unit, 2)}</td></tr>`).join('');
  const maxV = Math.max(...m.test_points.flatMap((p) => [p.actual, p.predicted])) / 1e6;
  drawChart('chartConfig', {
    type: 'scatter',
    data: { datasets: [
      { label: 'Mẫu kiểm tra', data: m.test_points.map((p) => ({ x: p.actual / 1e6, y: p.predicted / 1e6, name: p.name })), backgroundColor: 'rgba(76,123,243,.65)' },
      { label: 'Dự đoán đúng (y = x)', data: [{ x: 0, y: 0 }, { x: maxV, y: maxV }], type: 'line', borderColor: '#999', borderDash: [5, 5], pointRadius: 0 },
    ] },
    options: { maintainAspectRatio: false,
      plugins: { tooltip: { callbacks: { label: (c) => c.raw.name ? `${c.raw.name}: thực tế ${c.raw.x.toFixed(2)} tr, dự đoán ${c.raw.y.toFixed(2)} tr` : '' } } },
      scales: { x: { title: { display: true, text: 'Giá thực tế (triệu đ)' } }, y: { title: { display: true, text: 'Giá dự đoán (triệu đ)' } } } },
  });
  $('#marketCount').textContent = market.length;
  $('#marketRows').innerHTML = market.map((r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.brand)}</td><td>${esc(r.cpu)}</td><td>${r.ram}</td><td>${r.rom}</td>
    <td>${r.widescreen}</td><td>${r.ppi}</td><td>${r.battery}</td><td>${r.camera}</td><td>${r.release_year}</td><td class="num">${vnd(r.price)}</td></tr>`).join('');
};

$('#btnTrainConfig').addEventListener('click', async () => {
  $('#modelMsg').textContent = 'Đang huấn luyện…';
  try { await api('/api/ml/config-model/train', { method: 'POST' }); $('#modelMsg').textContent = ''; toast('Đã huấn luyện lại mô hình cấu hình'); loaders.model(); }
  catch (e) { $('#modelMsg').textContent = ''; toast(e.message, false); }
});

$('#btnRetrainAll').addEventListener('click', async () => {
  $('#modelMsg').textContent = 'Đang huấn luyện lại toàn bộ…';
  try {
    const r = await api('/api/ml/retrain-all', { method: 'POST' });
    $('#modelMsg').textContent = `Xong: R² kiểm tra mô hình cấu hình = ${num(r.config_r2_test, 3)}; ${r.demand_valid}/${r.demand_models} mô hình nhu cầu hợp lệ.`;
    loaders.model();
  } catch (e) { $('#modelMsg').textContent = ''; toast(e.message, false); }
});

$('#csvFile').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append('file', f);
  try {
    const r = await api('/api/market/import-csv', { method: 'POST', body: fd });
    toast(`Đã nhập ${r.added} mẫu${r.errors.length ? `, ${r.errors.length} dòng lỗi` : ''}`, !r.errors.length);
    if (r.errors.length) console.warn(r.errors);
    loaders.model();
  } catch (err) { toast(err.message, false); }
  e.target.value = '';
});

// ===================================================== NHẬT KÝ
loaders.logs = async () => {
  const [sugs, runs] = await Promise.all([api('/api/pricing/suggestions'), api('/api/ml/runs')]);
  $('#sugRows').innerHTML = sugs.map((s) => `<tr><td>${s.id}</td><td>${esc(s.name)}</td><td>${STRATEGY[s.strategy]}</td>
    <td class="num text-nowrap">${mil(s.current_price)} → <b>${mil(s.suggested_price)}</b></td>
    <td class="num">${num(s.expected_qty, 1)}</td><td class="num">${s.actual_weekly_qty != null ? num(s.actual_weekly_qty, 1) : (s.status === 'AP_DUNG' ? `<span class="text-body-secondary" title="Cần ≥ 7 ngày sau khi áp dụng">${s.days_since}/7 ngày</span>` : '')}</td>
    <td><span class="badge text-bg-${STATUS[s.status][1]}">${STATUS[s.status][0]}</span></td></tr>`).join('') || '<tr><td colspan="7" class="text-body-secondary">Chưa có gợi ý nào</td></tr>';
  $('#runRows').innerHTML = runs.map((r) => {
    const m = r.metrics.hold_out?.test || r.metrics.fit || {};
    return `<tr><td>${r.id}</td><td class="text-nowrap">${r.created_at}</td><td>${r.model_type === 'CAU_HINH' ? 'Cấu hình (bội)' : 'Nhu cầu (đơn)'}</td>
      <td>${esc(r.phone_name || '—')}</td><td class="num">${r.n_samples}</td><td class="num">${num(m.R2, 3)}</td>
      <td class="num">${r.model_type === 'CAU_HINH' ? mil(m.RMSE) : num(m.RMSE, 2)}</td></tr>`;
  }).join('');
};

// ===================================================== khởi động
showTab('dashboard');
refreshPhones().catch((e) => toast(e.message, false));
