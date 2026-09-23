const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const {buildPrompt, parseFilters, makeQueryUrl} = require('../docs/ai-query.js');
const root = path.resolve(__dirname, '..');
const schema = JSON.parse(fs.readFileSync(path.join(root, 'docs/query-schema.json'), 'utf8'));
const tick = () => new Promise(resolve => setImmediate(resolve));

async function setup(t, {failSchema = false, clipboardFails = false} = {}) {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'docs/index.html'), 'utf8'), {
    url: 'https://dirtycomputer.github.io/fdu_courses/?view=ai', runScripts: 'outside-only',
  });
  t.after(() => dom.window.close());
  let copied = '';
  let failing = failSchema;
  dom.window.fetch = async () => ({ok: !failing, status: failing ? 503 : 200, json: async () => schema});
  Object.defineProperty(dom.window.navigator, 'clipboard', {value: {writeText: async text => {
    if (clipboardFails) throw new Error('clipboard denied');
    copied = text;
  }}});
  dom.window.document.execCommand = () => false;
  for (const file of ['docs/ai-query.js', 'docs/ai-tools.js']) {
    dom.window.eval(fs.readFileSync(path.join(root, file), 'utf8'));
  }
  await tick();
  return {window: dom.window, $: s => dom.window.document.querySelector(s),
    copied: () => copied, recover: () => { failing = false; }};
}

test('LLM prompt supplies the exact schema, semantic requirements and execution protocol', () => {
  const prompt = buildPrompt('查询黄萱菁老师的所有课程', schema);
  assert.ok(prompt.includes(JSON.stringify(schema, null, 2)));
  assert.ok(prompt.includes('{"teacher":"黄萱菁","limit":50}'));
  assert.ok(prompt.includes('POST https://fducourses.vercel.app/api/courses'));
  assert.ok(prompt.includes('has_more=false'));
  assert.ok(prompt.includes('enrollment_source'));
  assert.ok(prompt.endsWith(JSON.stringify('查询黄萱菁老师的所有课程')));
});

test('JSON URL round-trips Unicode, ampersands and literal percent signs', () => {
  const filters = {teacher: '王 & Li', keyword: 'A+B 100% #？', day: 3, limit: 50};
  const url = new URL(makeQueryUrl(filters));
  assert.equal(url.pathname, '/api/courses');
  assert.deepEqual(JSON.parse(url.searchParams.get('filters')), filters);
  assert.equal(url.searchParams.size, 1);
  const duplicate = '{"day":1,"day":2}';
  assert.equal(new URL(makeQueryUrl(duplicate)).searchParams.get('filters'), duplicate);
  for (const raw of ['null', '[]', '"hello"', '{', '查询课程']) {
    assert.throws(() => parseFilters(raw));
  }
});

test('all five platforms use LLM JSON instructions and switching restores platform notes', async t => {
  const ui = await setup(t);
  assert.equal(ui.$('#ai-view').style.display, '');
  assert.equal(ui.$('#ai-copy-prompt').disabled, false);
  assert.equal(ui.$('#ai-json-actions').hidden, true);
  for (const platform of ['doubao', 'deepseek', 'gemini', 'claude', 'chatgpt']) {
    ui.$(`[data-platform="${platform}"]`).click();
    assert.equal(ui.$(`[data-platform="${platform}"]`).getAttribute('aria-pressed'), 'true');
    assert.ok(ui.$('#ai-platform-prompt').textContent.includes('JSON Schema'));
  }
  assert.match(ui.$('#ai-platform-note').textContent, /ChatGPT/);
  assert.doesNotMatch(ui.$('#ai-platform-note').textContent, /豆包|DeepSeek/);
  ui.$('#ai-copy-prompt').click();
  await tick();
  assert.equal(ui.copied(), ui.$('#ai-platform-prompt').textContent);
  assert.equal(ui.$('#ai-copy-prompt').textContent, '已复制');
});

test('paste LLM JSON, generate and copy URL, then invalidate stale links when intent changes', async t => {
  const ui = await setup(t);
  const input = ui.$('#ai-json-input');
  input.value = '{"teacher":"黄萱菁","limit":50}';
  input.dispatchEvent(new ui.window.Event('input'));
  assert.equal(ui.$('#ai-json-actions').hidden, false);
  const url = ui.$('#ai-open-api').href;
  assert.deepEqual(JSON.parse(new URL(url).searchParams.get('filters')), {teacher: '黄萱菁', limit: 50});
  ui.$('#ai-copy-url').click();
  await tick();
  assert.equal(ui.copied(), url);
  ui.$('#ai-query-input').value = '周三下午的课程';
  ui.$('#ai-query-input').dispatchEvent(new ui.window.Event('input'));
  assert.equal(input.value, '');
  assert.equal(ui.$('#ai-json-actions').hidden, true);
  assert.equal(ui.$('#ai-open-api').getAttribute('href'), null);
  assert.ok(ui.$('#ai-platform-prompt').textContent.endsWith(JSON.stringify('周三下午的课程')));
  ui.$('#ai-query-input').value = ' ';
  ui.$('#ai-query-input').dispatchEvent(new ui.window.Event('input'));
  assert.equal(ui.$('#ai-copy-prompt').disabled, true);
});

test('invalid JSON is not converted to a query and copy failure is not reported as success', async t => {
  const ui = await setup(t, {clipboardFails: true});
  ui.$('#ai-json-input').value = '黄萱菁老师的所有课程';
  ui.$('#ai-json-input').dispatchEvent(new ui.window.Event('input'));
  assert.equal(ui.$('#ai-json-actions').hidden, true);
  assert.match(ui.$('#ai-json-status').textContent, /格式错误/);
  ui.$('#ai-copy-prompt').click();
  await tick();
  assert.match(ui.$('#ai-copy-prompt').textContent, /复制失败/);
});

test('schema load failure disables copying, and retry recovers', async t => {
  const ui = await setup(t, {failSchema: true});
  assert.equal(ui.$('#ai-copy-prompt').disabled, true);
  assert.equal(ui.$('#ai-retry-schema').hidden, false);
  assert.match(ui.$('#ai-schema-status').textContent, /加载失败/);
  ui.recover();
  ui.$('#ai-retry-schema').click();
  await tick();
  assert.equal(ui.$('#ai-copy-prompt').disabled, false);
  assert.equal(ui.$('#ai-retry-schema').hidden, true);
});

test('JSON executor posts generated filters and advances to the next page', async t => {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'web/index.html'), 'utf8'), {
    url: 'https://fducourses.vercel.app/', runScripts: 'outside-only',
  });
  t.after(() => dom.window.close());
  const calls = [];
  dom.window.fetch = async (url, options) => {
    const filters = JSON.parse(options.body);
    calls.push({url, filters});
    return {ok: true, json: async () => ({filters, total: 2, returned: 1,
      offset: filters.offset || 0, has_more: !filters.offset, courses: [],
      enrollment_source: 'stale-cache', enrollment_updated_at: '2026-09-20'})};
  };
  for (const script of dom.window.document.querySelectorAll('script')) dom.window.eval(script.textContent);
  const $ = s => dom.window.document.querySelector(s);
  $('#query').value = '{"teacher":"黄萱菁","limit":1}';
  $('#submit').click();
  await tick();
  assert.deepEqual(calls[0], {url: '/api/courses', filters: {teacher: '黄萱菁', limit: 1}});
  assert.equal($('#next-page').hidden, false);
  assert.match($('#status').textContent, /过期缓存/);
  $('#next-page').click();
  await tick();
  assert.equal(calls[1].filters.offset, 1);
  assert.equal($('#next-page').hidden, true);
  $('#query').value = '查询黄萱菁老师的课程';
  $('#submit').click();
  await tick();
  assert.equal(calls.length, 2);
  assert.match($('#status').textContent, /JSON/);
});
