'use strict';

(() => {
  const aiBtn = document.getElementById('view-ai');
  const listBtn = document.getElementById('view-list');
  const calBtn = document.getElementById('view-cal');
  const aiView = document.getElementById('ai-view');
  const listView = document.getElementById('list-view');
  const calView = document.getElementById('cal-view');
  const toolbar = document.querySelector('.toolbar');
  if (!aiBtn || !aiView) return;

  const {buildPrompt, parseFilters, makeQueryUrl} = window.FduAiQuery;
  const platforms = {
    chatgpt: {label: 'ChatGPT', note: '把指令交给 ChatGPT，让它生成查询 JSON；具备网页或 HTTP 工具时，再实际访问接口。'},
    claude: {label: 'Claude', note: '把指令交给 Claude。已连接 MCP 时可直接生成对应工具参数，否则使用 JSON 查询接口。'},
    gemini: {label: 'Gemini', note: '让 Gemini 先生成符合约束的 JSON；当前模式无法访问接口时，可将 JSON 粘贴到下方生成链接。'},
    doubao: {label: '豆包', note: '让豆包使用自身模型理解需求并生成 JSON。接口访问取决于当前联网能力；无法访问时可将 JSON 粘贴到下方。'},
    deepseek: {label: 'DeepSeek', note: '让 DeepSeek 先生成查询 JSON。若当前联网能力无法访问接口，可将 JSON 粘贴到下方生成链接。'},
  };
  let activePlatform = 'chatgpt';
  let schema = null;
  let generatedUrl = '';

  function injectStyles() {
    if (document.getElementById('ai-platform-style-v2')) return;
    const style = document.createElement('style');
    style.id = 'ai-platform-style-v2';
    style.textContent = `
      .ai-query-box{margin-top:14px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px}
      .ai-query-label{display:block;font-size:13px;font-weight:700;margin-bottom:7px}
      .ai-query-input{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:9px;padding:10px 12px;background:var(--page);color:var(--ink);font-size:16px;line-height:1.5}
      .ai-platform-tabs{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 8px}
      .ai-platform-tab{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:999px;padding:7px 12px;font-weight:650;cursor:pointer}
      .ai-platform-tab.on{border-color:var(--accent);background:var(--accent-wash);color:var(--accent-deep)}
      .ai-platform-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
      .ai-platform-name{font-size:17px;font-weight:750;color:var(--ink)}
      .ai-platform-badge{font-size:12px;padding:3px 8px;border-radius:999px;background:var(--accent-wash);color:var(--accent-deep);border:1px solid var(--border)}
      .ai-platform-note{margin:0 0 12px;color:var(--ink-2);line-height:1.7}
      .ai-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
      .ai-action-link,.ai-action-btn{display:inline-flex;align-items:center;justify-content:center;min-height:36px;box-sizing:border-box;padding:6px 11px;border-radius:8px;font-size:13px;font-weight:650;text-decoration:none;cursor:pointer}
      .ai-action-link{background:var(--accent);color:white;border:1px solid var(--accent)}
      .ai-action-btn{background:var(--surface);color:var(--accent-deep);border:1px solid var(--accent)}
      .ai-fallback{margin-top:14px;padding:12px 13px;border:1px dashed var(--border);border-radius:10px;color:var(--ink-2);line-height:1.7;background:var(--page)}
      .ai-fallback strong{color:var(--ink)}
      .ai-url{display:block;margin-top:7px;padding:9px 10px;background:var(--surface);border:1px solid var(--border);border-radius:8px;font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;overflow-wrap:anywhere;color:var(--ink)}
      @media(max-width:720px){.ai-platform-tabs{flex-wrap:nowrap;overflow-x:auto;padding-bottom:3px}.ai-platform-tab{flex:0 0 auto;min-height:40px}.ai-actions>*{flex:1 1 auto}.ai-query-box{padding:12px}}
    `;
    document.head.appendChild(style);
  }


  function buildAiView() {
    aiView.innerHTML = `
      <div class="ai-wrap">
        <div class="ai-hero">
          <h2>AI工具查询指令</h2>
          <p>输入需求并复制指令，让 AI 理解需求、生成查询 JSON，再获取课程结果。</p>
        </div>
        <div class="ai-query-box">
          <label class="ai-query-label" for="ai-query-input">你的课程需求</label>
          <input class="ai-query-input" id="ai-query-input" type="text" value="查询黄萱菁老师的所有课程" autocomplete="off">
          <div class="ai-platform-tabs" role="group" aria-label="选择 AI 平台">
            ${Object.entries(platforms).map(([key, item]) => `<button class="ai-platform-tab" type="button" data-platform="${key}">${item.label}</button>`).join('')}
          </div>
        </div>
        <div class="ai-card">
          <div class="ai-platform-meta"><span class="ai-platform-name" id="ai-platform-name"></span></div>
          <p class="ai-platform-note" id="ai-platform-note"></p>
          <div class="ai-card-head"><h3>1. 将指令发送给 AI</h3><button class="ai-copy" id="ai-copy-prompt" type="button" disabled>复制 Prompt</button></div>
          <pre class="ai-prompt" id="ai-platform-prompt">正在加载查询格式…</pre>
          <p id="ai-schema-status" role="status"></p>
          <button class="ai-action-btn" id="ai-retry-schema" type="button" hidden>重新加载查询格式</button>
        </div>
        <div class="ai-card">
          <h3>2. AI 无法访问接口时，粘贴它生成的 JSON</h3>
          <p class="ai-platform-note">AI 能访问接口时可直接完成查询；也可将生成的 JSON 粘贴到这里，在浏览器中打开查询结果。</p>
          <label class="ai-query-label" for="ai-json-input">AI 生成的查询 JSON</label>
          <textarea class="ai-query-input" id="ai-json-input" rows="5" spellcheck="false" placeholder='例如：{"teacher":"黄萱菁","limit":50}'></textarea>
          <p id="ai-json-status" role="status">等待 AI 生成 JSON。</p>
          <div id="ai-json-actions" hidden>
            <div class="ai-actions"><a class="ai-action-link" id="ai-open-api" target="_blank" rel="noopener">打开查询接口</a><button class="ai-action-btn" id="ai-copy-url" type="button">复制接口 URL</button></div>
            <code class="ai-url" id="ai-api-url"></code>
          </div>
          <p class="ai-fallback">获取结果后，可将接口返回的 JSON 交给 AI 整理。若接口无法访问，可使用本站课程列表；联网限制不会因更换指令而消失。</p>
        </div>
      </div>`;
  }

  function renderPlatform() {
    const item = platforms[activePlatform];
    document.getElementById('ai-platform-name').textContent = item.label;
    document.getElementById('ai-platform-note').textContent = item.note;
    document.querySelectorAll('.ai-platform-tab').forEach(button => {
      const selected = button.dataset.platform === activePlatform;
      button.classList.toggle('on', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
    const query = document.getElementById('ai-query-input').value.trim();
    document.getElementById('ai-copy-prompt').disabled = !schema || !query;
    if (schema) document.getElementById('ai-platform-prompt').textContent = query
      ? buildPrompt(query, schema) : '请先输入课程需求。';
  }

  function renderJson() {
    generatedUrl = '';
    const actions = document.getElementById('ai-json-actions');
    const open = document.getElementById('ai-open-api');
    const status = document.getElementById('ai-json-status');
    const url = document.getElementById('ai-api-url');
    actions.hidden = true;
    open.removeAttribute('href');
    url.textContent = '';
    const text = document.getElementById('ai-json-input').value.trim();
    if (!text) { status.textContent = '等待 AI 生成 JSON。'; return; }
    try {
      parseFilters(text);
      // Preserve the original JSON so server validation can detect duplicate keys.
      generatedUrl = makeQueryUrl(text);
      open.href = generatedUrl;
      url.textContent = generatedUrl;
      actions.hidden = false;
      status.textContent = 'JSON 格式有效。接口会进一步校验字段及取值；请确认条件符合你的需求。';
    } catch (_) {
      status.textContent = '格式错误：请只粘贴 JSON 对象，不包含代码围栏、解释文字或自然语言。';
    }
  }

  async function loadSchema() {
    const status = document.getElementById('ai-schema-status');
    const retry = document.getElementById('ai-retry-schema');
    retry.hidden = true;
    status.textContent = '正在加载查询格式…';
    try {
      const response = await fetch('query-schema.json?v=2');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const value = await response.json();
      if (value.type !== 'object' || !value.properties) throw new Error('Invalid schema');
      schema = value;
      status.textContent = '';
      renderPlatform();
    } catch (_) {
      status.textContent = '查询格式加载失败，请重试。';
      retry.hidden = false;
    }
  }

  async function copyText(text, button) {
    const label = button.textContent;
    let copied = false;
    button.disabled = true;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
    } catch (_) {
      const area = document.createElement('textarea');
      area.value = text;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try { copied = document.execCommand('copy'); } catch (_) { /* Manual copy remains available. */ }
      area.remove();
    }
    button.textContent = copied ? '已复制' : '复制失败，请手动选择文本';
    setTimeout(() => {
      button.textContent = label;
      button.disabled = false;
      renderPlatform();
    }, 1400);
  }

  function setAiUrl() {
    const params = new URLSearchParams(location.search);
    params.set('view', 'ai');
    params.delete('w');
    history.replaceState(null, '', location.pathname + '?' + params.toString());
  }

  function showAiView() {
    if (typeof closeAllDropdowns === 'function') closeAllDropdowns();
    aiBtn.classList.add('on');
    listBtn?.classList.remove('on');
    calBtn?.classList.remove('on');
    if (listView) listView.style.display = 'none';
    if (calView) calView.style.display = 'none';
    aiView.style.display = '';
    if (toolbar) toolbar.style.display = 'none';
    setAiUrl();
  }

  function leaveAiView() {
    aiBtn.classList.remove('on');
    aiView.style.display = 'none';
    if (toolbar) toolbar.style.display = '';
  }


  injectStyles();
  buildAiView();
  renderPlatform();
  aiBtn.addEventListener('click', showAiView);
  listBtn?.addEventListener('click', leaveAiView);
  calBtn?.addEventListener('click', leaveAiView);
  document.querySelector('.ai-platform-tabs').addEventListener('click', event => {
    const button = event.target.closest('.ai-platform-tab');
    if (!button || !platforms[button.dataset.platform]) return;
    activePlatform = button.dataset.platform;
    renderPlatform();
  });
  document.getElementById('ai-query-input').addEventListener('input', () => {
    document.getElementById('ai-json-input').value = '';
    renderJson();
    renderPlatform();
  });
  document.getElementById('ai-json-input').addEventListener('input', renderJson);
  document.getElementById('ai-copy-prompt').addEventListener('click', event => {
    copyText(document.getElementById('ai-platform-prompt').textContent, event.currentTarget);
  });
  document.getElementById('ai-copy-url').addEventListener('click', event => {
    if (generatedUrl) copyText(generatedUrl, event.currentTarget);
  });
  document.getElementById('ai-retry-schema').addEventListener('click', loadSchema);
  if (new URLSearchParams(location.search).get('view') === 'ai') showAiView();
  loadSchema();
})();
