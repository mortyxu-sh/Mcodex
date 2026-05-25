const $ = (id) => document.getElementById(id);
const state = {
  customers: { page: 1, pageSize: 10, total: 0, rows: [] },
  numberList: { page: 1, pageSize: 10, total: 0, rows: [] },
  callerAuth: { page: 1, pageSize: 10, total: 0, rows: [] },
  batchFailures: [],
};

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (s) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
const toast = (msg, kind = 'info') => {
  const t = $('toast');
  t.className = kind;
  t.textContent = typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2);
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 5000);
};
const api = async (url, opt = {}) => {
  const r = await fetch(url, opt);
  const text = await r.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!r.ok) {
    const detail = data?.detail ?? data?.message ?? data;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
};
const rowsOf = (d) => d?.records || d?.list || d?.rows || d?.data?.records || d?.data?.list || d?.data?.rows || (Array.isArray(d?.data) ? d.data : []) || [];
const totalOf = (d, rows) => Number(d?.total ?? d?.data?.total ?? d?.count ?? d?.data?.count ?? rows.length);
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([_, v]) => v !== '' && v != null)).toString();
const asNumber = (v, fallback = 0) => Number.isFinite(Number(v)) ? Number(v) : fallback;
const asInt = (v, fallback = 0) => Number.isFinite(parseInt(v, 10)) ? parseInt(v, 10) : fallback;

document.querySelectorAll('.nav').forEach(btn => btn.onclick = () => {
  document.querySelectorAll('.nav,.panel').forEach(e => e.classList.remove('active'));
  btn.classList.add('active');
  $(btn.dataset.tab).classList.add('active');
});

function confirmAction(message, title = '请确认') {
  return new Promise((resolve) => {
    const dialog = $('confirmDialog');
    $('confirmTitle').textContent = title;
    $('confirmMessage').textContent = message;
    const done = (value) => {
      $('confirmOk').onclick = null;
      $('confirmCancel').onclick = null;
      dialog.close();
      resolve(value);
    };
    $('confirmOk').onclick = () => done(true);
    $('confirmCancel').onclick = () => done(false);
    dialog.showModal();
  });
}

function renderPager(id, pager, loader) {
  const totalPages = Math.max(1, Math.ceil(pager.total / pager.pageSize));
  $(id).innerHTML = `
    <span>共 ${pager.total} 条，第 ${pager.page} / ${totalPages} 页</span>
    <button class="secondary" ${pager.page <= 1 ? 'disabled' : ''}>上一页</button>
    <button class="secondary" ${pager.page >= totalPages ? 'disabled' : ''}>下一页</button>
    <select aria-label="每页条数">
      ${[10, 20, 50, 100].map(size => `<option value="${size}" ${size === pager.pageSize ? 'selected' : ''}>${size} 条/页</option>`).join('')}
    </select>
  `;
  const [prev, next] = $(id).querySelectorAll('button');
  const select = $(id).querySelector('select');
  prev.onclick = () => { pager.page -= 1; loader(); };
  next.onclick = () => { pager.page += 1; loader(); };
  select.onchange = () => { pager.pageSize = Number(select.value); pager.page = 1; loader(); };
}

async function loadCustomers(reset = false) {
  if (reset) state.customers.page = 1;
  try {
    const d = await api('/api/customers?' + qs({ account: $('custAccount').value, status: $('custStatus').value, page: state.customers.page, pageSize: state.customers.pageSize }));
    const rows = rowsOf(d);
    state.customers.rows = rows;
    state.customers.total = totalOf(d, rows);
    $('customersBody').innerHTML = rows.map(r => `<tr>
      <td>${escapeHtml(r.id)}</td><td>${escapeHtml(r.account)}</td><td>${escapeHtml(r.name)}</td>
      <td>${escapeHtml(r.balance)}</td><td>${escapeHtml(r.unitPrice ?? r.unit_price)}</td>
      <td>${(r.payType ?? r.pay_type) == 1 ? '后付费' : '预付费'}</td>
      <td>${escapeHtml(r.maxCallsPerHour ?? r.max_calls_per_hour)}</td><td>${badge(r.status)}</td>
      <td class="actions">
        <button onclick="openCustomerDialog(${r.id})">编辑</button>
        <button class="secondary" onclick="toggleCustomer(${r.id})">${Number(r.status) === 1 ? '禁用' : '启用'}</button>
        <button class="secondary" onclick="adjustBalance(${r.id})">余额</button>
        <button class="danger" onclick="delCustomer(${r.id})">删除</button>
      </td></tr>`).join('');
    renderPager('customersPager', state.customers, loadCustomers);
  } catch (e) { toast(e.message, 'error'); }
}

async function addCustomer(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  ['balance', 'unitPrice'].forEach(k => data[k] = asNumber(data[k]));
  ['payType', 'maxCallsPerHour'].forEach(k => data[k] = asInt(data[k]));
  data.status = 1;
  try {
    await api('/api/customers', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    toast('客户已添加');
    e.target.reset();
    loadCustomers(true);
  } catch (err) { toast(err.message, 'error'); }
}

function rowToCustomerPayload(r) {
  return {
    account: r.account,
    name: r.name,
    balance: asNumber(r.balance),
    unitPrice: asNumber(r.unitPrice ?? r.unit_price),
    payType: asInt(r.payType ?? r.pay_type),
    maxCallsPerHour: asInt(r.maxCallsPerHour ?? r.max_calls_per_hour),
    status: asInt(r.status, 1),
  };
}

function openCustomerDialog(id) {
  const row = state.customers.rows.find(r => Number(r.id) === Number(id));
  if (!row) return toast('未找到客户记录', 'error');
  const form = $('customerEditForm');
  const data = rowToCustomerPayload(row);
  form.elements.id.value = id;
  Object.entries(data).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value ?? ''; });
  $('customerDialog').showModal();
}

function closeCustomerDialog() { $('customerDialog').close(); }

$('customerEditForm').onsubmit = async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const id = data.id;
  delete data.id;
  ['balance', 'unitPrice'].forEach(k => data[k] = asNumber(data[k]));
  ['payType', 'maxCallsPerHour', 'status'].forEach(k => data[k] = asInt(data[k]));
  try {
    await api('/api/customers?' + qs({ id }), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    closeCustomerDialog();
    toast('客户已更新');
    loadCustomers();
  } catch (err) { toast(err.message, 'error'); }
};

async function toggleCustomer(id) {
  const row = state.customers.rows.find(r => Number(r.id) === Number(id));
  if (!row) return toast('未找到客户记录', 'error');
  const payload = rowToCustomerPayload(row);
  payload.status = Number(row.status) === 1 ? 0 : 1;
  if (!await confirmAction(`确认${payload.status === 1 ? '启用' : '禁用'}客户 ${payload.account}？`)) return;
  try {
    await api('/api/customers?' + qs({ id }), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    toast('客户状态已更新');
    loadCustomers();
  } catch (e) { toast(e.message, 'error'); }
}

async function adjustBalance(id) {
  const row = state.customers.rows.find(r => Number(r.id) === Number(id));
  if (!row) return toast('未找到客户记录', 'error');
  const current = asNumber(row.balance);
  const input = prompt(`当前余额 ${current}，请输入调整后的余额`);
  if (input === null) return;
  const next = Number(input);
  if (!Number.isFinite(next)) return toast('余额必须是数字', 'error');
  const payload = rowToCustomerPayload(row);
  payload.balance = next;
  try {
    await api('/api/customers?' + qs({ id }), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    toast('余额已调整');
    loadCustomers();
  } catch (e) { toast(e.message, 'error'); }
}

async function delCustomer(id) {
  if (!await confirmAction('确认删除客户？')) return;
  try {
    await api('/api/customers/' + id, { method: 'DELETE' });
    toast('客户已删除');
    loadCustomers();
  } catch (e) { toast(e.message, 'error'); }
}

async function loadNumberList(reset = false) {
  if (reset) state.numberList.page = 1;
  try {
    const d = await api('/api/number-list?' + qs({ customerAcc: $('nlCustomer').value, number: $('nlNumber').value, listType: $('nlListType').value, matchType: $('nlMatchType').value, page: state.numberList.page, pageSize: state.numberList.pageSize }));
    const rows = rowsOf(d);
    state.numberList.rows = rows;
    state.numberList.total = totalOf(d, rows);
    $('numberBody').innerHTML = rows.map(r => `<tr><td>${escapeHtml(r.id)}</td><td>${escapeHtml(r.customerAcc ?? r.customer_acc)}</td><td>${escapeHtml(r.number)}</td><td>${(r.listType ?? r.list_type) == 2 ? '白名单' : '黑名单'}</td><td>${(r.matchType ?? r.match_type) == 2 ? '前缀' : '精确'}</td><td>${badge(r.status)}</td><td>${escapeHtml(r.createTime ?? r.create_time)}</td><td><button class="danger" onclick="delNumber(${r.id})">删除</button></td></tr>`).join('');
    renderPager('numberPager', state.numberList, loadNumberList);
  } catch (e) { toast(e.message, 'error'); }
}

async function addNumber(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.listType = asInt(data.listType);
  data.matchType = asInt(data.matchType);
  data.status = 1;
  try {
    await api('/api/number-list', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    toast('号码已添加');
    e.target.reset();
    loadNumberList(true);
  } catch (err) { toast(err.message, 'error'); }
}

async function delNumber(id) {
  if (!await confirmAction('确认删除号码？')) return;
  try {
    await api('/api/number-list/' + id, { method: 'DELETE' });
    toast('号码已删除');
    loadNumberList();
  } catch (e) { toast(e.message, 'error'); }
}

async function batchAddNumber(e) {
  e.preventDefault();
  const f = new FormData(e.target);
  const params = qs({ customerAcc: f.get('customerAcc'), listType: f.get('listType'), matchType: f.get('matchType') });
  const body = new FormData();
  body.append('file', f.get('file'));
  try {
    const result = await api('/api/number-list/batch?' + params, { method: 'POST', body });
    renderBatchResult(result);
    toast(`批量完成：成功 ${result.success}，失败 ${result.failed}`);
    loadNumberList(true);
  } catch (err) { toast(err.message, 'error'); }
}

function renderBatchResult(result) {
  state.batchFailures = (result.items || []).filter(item => !item.success);
  const failedButton = state.batchFailures.length ? '<button class="secondary" onclick="downloadFailures()">下载失败列表</button>' : '';
  $('batchResult').innerHTML = `
    <div class="summary">导入 ${result.total} 条，成功 ${result.success} 条，失败 ${result.failed} 条 ${failedButton}</div>
    ${(result.items || []).length ? `<table><thead><tr><th>号码</th><th>结果</th><th>后端响应</th></tr></thead><tbody>${result.items.map(item => `<tr><td>${escapeHtml(item.number)}</td><td>${item.success ? '成功' : '失败'}</td><td>${escapeHtml(typeof item.response === 'string' ? item.response : JSON.stringify(item.response))}</td></tr>`).join('')}</tbody></table>` : ''}
  `;
}

function downloadFailures() {
  const csv = ['number,response'].concat(state.batchFailures.map(item => `"${String(item.number ?? '').replace(/"/g, '""')}","${String(typeof item.response === 'string' ? item.response : JSON.stringify(item.response)).replace(/"/g, '""')}"`)).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'number-list-failures.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function exportNumberList() { location.href = '/api/number-list/export?' + qs({ customerAcc: $('nlCustomer').value, listType: $('nlListType').value, matchType: $('nlMatchType').value }); }
async function syncNumberList() {
  if (!await confirmAction('确认同步被叫黑白名单到 Redis？')) return;
  try { toast(await api('/api/number-list/sync?' + qs({ customerAcc: $('nlCustomer').value }), { method: 'POST' })); } catch (e) { toast(e.message, 'error'); }
}

async function loadCallerAuth(reset = false) {
  if (reset) state.callerAuth.page = 1;
  try {
    const d = await api('/api/caller-auth?' + qs({ customerAcc: $('caCustomer').value, page: state.callerAuth.page, pageSize: state.callerAuth.pageSize }));
    const rows = rowsOf(d);
    state.callerAuth.rows = rows;
    state.callerAuth.total = totalOf(d, rows);
    $('callerBody').innerHTML = rows.map(r => `<tr><td>${escapeHtml(r.id)}</td><td>${escapeHtml(r.customerAcc ?? r.customer_acc)}</td><td>${escapeHtml(r.callerNumber ?? r.caller_number)}</td><td>${badge(r.status)}</td><td>${escapeHtml(r.createTime ?? r.create_time)}</td><td><button class="danger" onclick="delCallerAuth(${r.id})">删除</button></td></tr>`).join('');
    renderPager('callerPager', state.callerAuth, loadCallerAuth);
  } catch (e) { toast(e.message, 'error'); }
}

async function addCallerAuth(e) {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  data.status = 1;
  try {
    await api('/api/caller-auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    toast('主叫已添加');
    e.target.reset();
    loadCallerAuth(true);
  } catch (err) { toast(err.message, 'error'); }
}

async function delCallerAuth(id) {
  if (!await confirmAction('确认删除主叫白名单？')) return;
  try {
    await api('/api/caller-auth/' + id, { method: 'DELETE' });
    toast('主叫白名单已删除');
    loadCallerAuth();
  } catch (e) { toast(e.message, 'error'); }
}

async function syncCallerAuth() {
  if (!await confirmAction('确认同步主叫白名单到 Redis？')) return;
  try { toast(await api('/api/caller-auth/sync?' + qs({ customerAcc: $('caCustomer').value }), { method: 'POST' })); } catch (e) { toast(e.message, 'error'); }
}

function badge(v) { return Number(v) === 1 ? '<span class="badge ok">启用</span>' : '<span class="badge bad">禁用</span>'; }

loadCustomers();
