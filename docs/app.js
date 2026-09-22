/* 复旦蹭课指南 —— 纯静态前端 */
'use strict';

const DATA_URL = 'data/latest.json';
const SYLLABUS_BASE = 'https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search/teachingSyllabusInfo/';

let DATA = null;
let state = {
  view: 'list',
  q: '',
  campuses: new Set(),
  bizTypes: new Set(),
  tableTypes: new Set(),
  depts: new Set(),
  days: new Set(),
  week: null,
  listLimit: 300,
};
let modalCtx = null; // {day, period, filters:{bizTypes,campuses,depts}}
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

/* ---------------- utils ---------------- */
const DAY_NAMES = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const BIZ_CLASS = { '本科': 'ug', '研究生': 'pg', '本研融通': 'br' };

function parseDate(s) { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function fmtMD(d) { return (d.getMonth() + 1) + '/' + d.getDate(); }
function sameDay(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
function today0() { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }

function week1Monday() { return parseDate(DATA.week1Monday); }
function dateOf(week, day) { return addDays(week1Monday(), (week - 1) * 7 + (day - 1)); }
function currentWeek() {
  const diff = Math.floor((today0() - week1Monday()) / 604800000);
  return Math.min(18, Math.max(1, diff + 1));
}
function clampWeek(w) { return Math.min(18, Math.max(1, w)); }

function campusName(id) { return DATA.campusNames[id - 1] || '其他'; }
function courseCampuses(c) { return (c.campuses || []).map(campusName).join(' / ') || '—'; }
function escapeHtml(s) { return String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])); }

function compressWeeks(weeks) {
  if (!weeks || !weeks.length) return '';
  const parts = [];
  let s = weeks[0], prev = weeks[0];
  for (let i = 1; i <= weeks.length; i++) {
    const w = weeks[i];
    if (w !== prev + 1) {
      parts.push(s === prev ? String(s) : s + '-' + prev);
      s = w;
    }
    prev = w;
  }
  return parts.join(',');
}

function schedLines(c) {
  if (!c.sessions.length) return [c.rawSchedule || '时间待定'];
  const groups = new Map();
  for (const s of c.sessions) {
    const key = `${s.day}|${s.p[0]}|${s.p[1]}|${s.room || ''}`;
    if (groups.has(key)) groups.get(key).weeks.push(...s.weeks);
    else groups.set(key, { s, weeks: [...s.weeks] });
  }
  return [...groups.values()].map(({ s, weeks }) => {
    weeks = [...new Set(weeks)].sort((a, b) => a - b);
    return `${DAY_NAMES[s.day]} ${s.p[0]}~${s.p[1]}节 ${s.room || ''} ${compressWeeks(weeks)}周`.trim();
  });
}

function syllabusLink(c) {
  if (!c.hasSyllabus) return '';
  return `<a class="syllabus-link" href="${SYLLABUS_BASE}${c.id}" target="_blank" rel="noopener">大纲 ↗</a>`;
}

function courseHtmlRow(c) {
  const sub = [c.tableType, c.credits != null ? c.credits + ' 学分' : '', c.lang && c.lang !== '中文' ? c.lang : '']
    .filter(Boolean).join(' · ');
  return `<tr>
    <td><div class="c-name">${escapeHtml(c.name)}</div>
        <div class="c-code">${escapeHtml(c.code)}${sub ? ' · ' + escapeHtml(sub) : ''}</div></td>
    <td>${escapeHtml(c.teachers.join('、')) || '—'}</td>
    <td class="td-sched">${schedLines(c).map(l => `<div class="sched-line">${escapeHtml(l)}</div>`).join('')}</td>
    <td>${escapeHtml(courseCampuses(c))}</td>
    <td>${escapeHtml(c.department)}</td>
    <td class="td-biz"><span class="badge ${BIZ_CLASS[c.bizType] || 'ug'}">${escapeHtml(c.bizType)}</span></td>
    <td>${syllabusLink(c)}</td>
  </tr>`;
}

/* ---------------- filtering ---------------- */
function matchesQuery(c, tokens) {
  if (!tokens.length) return true;
  const hay = [c.name, c.courseCode, c.code, c.teachers.join(' ')].join(' ').toLowerCase();
  return tokens.every(t => hay.includes(t));
}
function filteredCourses() {
  const tokens = state.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return DATA.courses.filter(c =>
    matchesQuery(c, tokens) &&
    (!state.campuses.size || c.campuses.some(id => state.campuses.has(campusName(id)))) &&
    (!state.bizTypes.size || state.bizTypes.has(c.bizType)) &&
    (!state.tableTypes.size || state.tableTypes.has(c.tableType)) &&
    (!state.depts.size || state.depts.has(c.department)) &&
    (!state.days.size || c.sessions.some(s => state.days.has(s.day)))
  );
}

/* ---------------- toolbar / dropdown ---------------- */
function makeDropdown(id, label, options, onChange, searchable) {
  const root = $('#' + id);
  root.innerHTML = `
    <button class="dd-btn" type="button"><span class="lbl">${label}</span><span class="cnt" hidden></span><span class="arr">▾</span></button>
    <div class="dd-panel">
      ${searchable ? '<input class="dd-search" type="text" placeholder="搜索…">' : ''}
      <div class="dd-opts"></div>
    </div>`;
  const optsEl = $('.dd-opts', root);
  const btn = $('.dd-btn', root);
  const cnt = $('.cnt', root);
  const render = (kw) => {
    optsEl.innerHTML = options
      .filter(o => !kw || o.toLowerCase().includes(kw))
      .map(o => `<label><input type="checkbox" value="${escapeHtml(o)}">${escapeHtml(o)}</label>`).join('');
  };
  render();
  if (searchable) {
    const si = $('.dd-search', root);
    si.addEventListener('input', () => render(si.value.trim().toLowerCase()));
    si.addEventListener('click', e => e.stopPropagation());
  }
  btn.addEventListener('click', e => {
    e.stopPropagation();
    const wasOpen = root.classList.contains('open');
    closeAllDropdowns();
    if (!wasOpen) { root.classList.add('open'); if (searchable) $('.dd-search', root).focus(); }
  });
  root.addEventListener('change', e => {
    if (e.target.type !== 'checkbox') return;
    const sel = new Set($$('input:checked', optsEl).map(i => i.value));
    cnt.hidden = !sel.size;
    cnt.textContent = sel.size;
    btn.classList.toggle('has-sel', sel.size > 0);
    onChange(sel);
  });
}
function closeAllDropdowns() { $$('.dd.open').forEach(d => d.classList.remove('open')); }
document.addEventListener('click', closeAllDropdowns);

/* ---------------- list view ---------------- */
function renderList() {
  const courses = filteredCourses();
  $('#result-line').textContent = `共 ${courses.length} 个教学班 · ${new Set(courses.map(c => c.courseCode)).size} 门课程 · 数据: ${DATA.semester}(${DATA.generatedAt} 更新)`;
  const shown = courses.slice(0, state.listLimit);
  $('#list-tbody').innerHTML = shown.length
    ? shown.map(courseHtmlRow).join('')
    : `<tr><td colspan="7"><div class="empty-tip">没有符合条件的课程,试试放宽筛选</div></td></tr>`;
  $('#more-wrap').style.display = courses.length > state.listLimit ? '' : 'none';
  const remain = courses.length - state.listLimit;
  $('#more-btn').textContent = `显示更多(还有 ${remain} 个)`;
}

/* ---------------- calendar ---------------- */
function heatClass(n) { return n >= 5 ? 'h5' : 'h' + n; }

function collectWeekCells() {
  // cells[day][p] = count ; hits[day][p] = [course,...]  (同一课程在同格只计一次)
  const cells = {}, hits = {}, seen = new Set();
  for (let d = 1; d <= 7; d++) { cells[d] = Array(15).fill(0); hits[d] = Array(15).fill(null); }
  for (const c of filteredCourses()) {
    for (const s of c.sessions) {
      if (!s.weeks.includes(state.week)) continue;
      for (let p = s.p[0]; p <= s.p[1]; p++) {
        const key = s.day + '-' + p + '-' + c.id;
        if (seen.has(key)) continue;
        seen.add(key);
        cells[s.day][p]++;
        (hits[s.day][p] ||= []).push(c);
      }
    }
  }
  return { cells, hits };
}

function renderCalendar() {
  const { cells, hits } = collectWeekCells();
  const week = state.week;
  const monday = dateOf(week, 1);
  const sunday = dateOf(week, 7);
  $('#wn-label').textContent = `第 ${week} 周`;
  $('#wn-range').textContent = `${monday.getFullYear()}年${fmtMD(monday)} - ${fmtMD(sunday)}`;
  $('#wn-prev').disabled = week <= 1;
  $('#wn-next').disabled = week >= 18;

  const today = today0();
  const now = new Date();
  const thead = $('#cal-thead'), tbody = $('#cal-tbody');
  let headHtml = '<th class="p-col">节次</th>';
  for (let d = 1; d <= 7; d++) {
    const dt = dateOf(week, d);
    const isToday = sameDay(dt, today);
    headHtml += `<th class="cal-day${isToday ? ' today-head' : ''}">${DAY_NAMES[d]} ${fmtMD(dt)}${isToday ? '<span class="today-mark">今</span>' : ''}</th>`;
  }
  thead.innerHTML = headHtml;

  let bodyHtml = '';
  for (let p = 1; p <= 14; p++) {
    bodyHtml += `<tr><td class="p-col">${p}<div class="ptime">${DATA.periodTimes[p - 1]}</div></td>`;
    for (let d = 1; d <= 7; d++) {
      const n = cells[d][p];
      const dt = dateOf(week, d);
      const pastDay = dt < today;
      const pastPeriod = sameDay(dt, today) && now >= parseHM(DATA.periodEndTimes[p - 1]);
      const cls = ['cell', 'p' + p];
      if (n) cls.push(heatClass(n));
      if (pastDay) cls.push('past-day');
      else if (pastPeriod) cls.push('past-period');
      const tip = n ? `${DAY_NAMES[d]} 第${p}节 · ${fmtMD(dt)}&#10;${n} 门课,点击查看` : '';
      bodyHtml += `<td class="${cls.join(' ')}" data-day="${d}" data-p="${p}" ${tip ? `title="${tip}"` : ''}>${n ? `<span class="n">${n}</span>` : ''}</td>`;
    }
    bodyHtml += '</tr>';
  }
  tbody.innerHTML = bodyHtml;
}

function parseHM(s) { const [h, m] = s.split(':').map(Number); const n = new Date(); n.setHours(h, m, 0, 0); return n; }

function gotoWeek(w) {
  state.week = clampWeek(w);
  syncUrl();
  renderCalendar();
}

/* ---------------- modal ---------------- */
function openModal(day, period) {
  modalCtx = { day, period, filters: { bizTypes: new Set(), campuses: new Set(), depts: new Set() } };
  renderModalFilters();
  renderModalBody();
  $('#modal-mask').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  modalCtx = null;
  $('#modal-mask').classList.remove('open');
  document.body.style.overflow = '';
}
function modalHits() {
  const { day, period } = modalCtx;
  const seen = new Set(), out = [];
  for (const c of filteredCourses()) {
    for (const s of c.sessions) {
      if (s.day === day && s.p[0] <= period && s.p[1] >= period && s.weeks.includes(state.week) && !seen.has(c.id)) {
        seen.add(c.id); out.push(c);
      }
    }
  }
  return out;
}
function renderModalFilters() {
  const wrap = $('#modal-filters');
  wrap.innerHTML = `
    <div class="dd" id="mf-biz"></div>
    <div class="dd" id="mf-campus"></div>
    <div class="dd" id="mf-dept"></div>`;
  makeDropdown('mf-biz', '学位类型', DATA.bizTypes, v => { modalCtx.filters.bizTypes = v; renderModalBody(); });
  makeDropdown('mf-campus', '校区', DATA.campusNames, v => { modalCtx.filters.campuses = v; renderModalBody(); });
  makeDropdown('mf-dept', '开课单位', DATA.departments, v => { modalCtx.filters.depts = v; renderModalBody(); }, true);
  $$('.dd', wrap).forEach(dd => dd.addEventListener('click', e => e.stopPropagation()));
}
function renderModalBody() {
  const { day, period } = modalCtx;
  const f = modalCtx.filters;
  let hits = modalHits().filter(c =>
    (!f.bizTypes.size || f.bizTypes.has(c.bizType)) &&
    (!f.campuses.size || c.campuses.some(id => f.campuses.has(campusName(id)))) &&
    (!f.depts.size || f.depts.has(c.department)));
  hits.sort((a, b) => {
    const pa = a.sessions.find(s => s.day === day && s.p[0] <= period && s.p[1] >= period);
    const pb = b.sessions.find(s => s.day === day && s.p[0] <= period && s.p[1] >= period);
    return (pa ? pa.p[0] : 99) - (pb ? pb.p[0] : 99) || a.code.localeCompare(b.code);
  });
  $('#modal-title').innerHTML = `${DAY_NAMES[day]} 第 ${period} 节 <span class="mh-sub">第 ${state.week} 周 · ${fmtMD(dateOf(state.week, day))} · ${hits.length} 门课(含跨节次)</span>`;
  $('#modal-body').innerHTML = hits.length ? hits.map(c => {
    const s = c.sessions.find(s => s.day === day && s.p[0] <= period && s.p[1] >= period);
    const extra = s && (s.p[0] !== period || s.p[1] !== period) ? ` <span class="t-sub">(本课 ${s.p[0]}~${s.p[1]}节)</span>` : '';
    return `<div class="m-course">
      <div class="mc-top">
        <span class="mc-name">${escapeHtml(c.name)}</span>
        <span class="t-sub">${escapeHtml(c.code)} · ${escapeHtml(c.teachers.join('、')) || '—'}</span>${extra}
        <span class="mc-right">${syllabusLink(c)}</span>
      </div>
      <div class="mc-meta">${escapeHtml(c.tableType || '')}${c.tableType ? ' · ' : ''}${escapeHtml(c.department)} · <span class="badge ${BIZ_CLASS[c.bizType] || 'ug'}">${escapeHtml(c.bizType)}</span> · ${escapeHtml(courseCampuses(c))}</div>
      <div class="mc-sched">${escapeHtml(s ? `${s.room || '教室待定'} · ${s.weeks[0]}-${s.weeks[s.weeks.length - 1]}周(${compressWeeks(s.weeks)}周)` : '')}</div>
    </div>`;
  }).join('') : '<div class="empty-tip">该时段没有符合条件的课程</div>';
}

/* ---------------- state / url ---------------- */
function syncUrl() {
  const p = new URLSearchParams();
  if (state.view === 'cal') p.set('view', 'cal');
  if (state.view === 'cal' && state.week != null) p.set('w', state.week);
  history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
}
function switchView(v) {
  state.view = v;
  $('#view-list').classList.toggle('on', v === 'list');
  $('#view-cal').classList.toggle('on', v === 'cal');
  $('#list-view').style.display = v === 'list' ? '' : 'none';
  $('#cal-view').style.display = v === 'cal' ? '' : 'none';
  $('#day-btns').style.visibility = v === 'list' ? '' : 'hidden';
  if (v === 'cal') state.week = currentWeek(); // 切回日历自动定位当前周
  syncUrl();
  if (v === 'cal') renderCalendar();
  else renderList();
}

function refresh() { state.view === 'cal' ? renderCalendar() : renderList(); }

function collectFiltersFromUI() {
  state.q = $('#search-box').value;
  state.listLimit = 300;
  refresh();
}

function resetFilters() {
  state.q = '';
  state.campuses.clear(); state.bizTypes.clear(); state.tableTypes.clear(); state.depts.clear(); state.days.clear();
  $('#search-box').value = '';
  $$('.dd[data-main] .dd-btn').forEach(b => { b.classList.remove('has-sel'); const c = $('.cnt', b); c.hidden = true; });
  $$('.dd[data-main] input[type=checkbox]').forEach(i => { i.checked = false; });
  $$('.day-btns button').forEach(b => b.classList.remove('on'));
  refresh();
}

/* ---------------- init ---------------- */
async function init() {
  DATA = await (await fetch(DATA_URL)).json();
  DATA.bizTypes = [...new Set(DATA.courses.map(c => c.bizType).filter(Boolean))].sort();
  $('#head-sub').textContent = `${DATA.semester} · 第 1 周始于 ${DATA.week1Monday} · 数据更新于 ${DATA.generatedAt}`;

  const params = new URLSearchParams(location.search);

  makeDropdown('dd-campus', '校区', DATA.campusNames, v => { state.campuses = v; refresh(); });
  makeDropdown('dd-biz', '学位类型', DATA.bizTypes, v => { state.bizTypes = v; refresh(); });
  makeDropdown('dd-table', '课程层级', [...new Set(DATA.courses.map(c => c.tableType).filter(Boolean))].sort(), v => { state.tableTypes = v; refresh(); });
  makeDropdown('dd-dept', '开课单位', DATA.departments, v => { state.depts = v; refresh(); }, true);
  $$('.toolbar .dd').forEach(d => d.setAttribute('data-main', '1'));

  $('#search-box').addEventListener('input', collectFiltersFromUI);
  $('#reset-btn').addEventListener('click', resetFilters);
  $$('.day-btns button').forEach(b => b.addEventListener('click', () => {
    b.classList.toggle('on');
    state.days = new Set($$('.day-btns button.on').map(x => +x.dataset.day));
    refresh();
  }));
  $('#more-btn').addEventListener('click', () => { state.listLimit += 500; renderList(); });
  $('#view-list').addEventListener('click', () => switchView('list'));
  $('#view-cal').addEventListener('click', () => switchView('cal'));
  $('#wn-prev').addEventListener('click', () => gotoWeek(state.week - 1));
  $('#wn-next').addEventListener('click', () => gotoWeek(state.week + 1));
  $('#wn-today').addEventListener('click', () => gotoWeek(currentWeek()));
  $('#modal-close').addEventListener('click', closeModal);
  $('#modal-mask').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
  $('#cal-tbody').addEventListener('click', e => {
    const td = e.target.closest('td.cell');
    if (td && td.querySelector('.n')) openModal(+td.dataset.day, +td.dataset.p);
  });

  const v = params.get('view');
  if (v === 'cal') {
    state.week = clampWeek(parseInt(params.get('w')) || currentWeek());
    switchView('cal');
    state.week = clampWeek(parseInt(params.get('w')) || currentWeek());
    renderCalendar();
  } else {
    renderList();
  }

  // 过去时段随时间推进:每分钟刷新
  setInterval(() => { if (state.view === 'cal' && !modalCtx) renderCalendar(); }, 60000);
}

init();
