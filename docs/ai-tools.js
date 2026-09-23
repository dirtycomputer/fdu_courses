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

  const API_BASE = 'https://fducourses.vercel.app';
  const DEFAULT_QUERY = '查询黄萱菁老师的所有课程';

  const platforms = {
    chatgpt: {
      label: 'ChatGPT',
      badge: '支持网页访问时推荐',
      note: '适用于具备网页访问/联网能力的 ChatGPT 会话。若当前会话没有网页访问能力，文字 Prompt 本身无法绕过该限制。',
      prompt(query, askUrl) {
        return `请使用你的网页访问能力，实际读取 ${API_BASE}/llms.txt，并按照其中的接口说明查询复旦大学当前学期课程。\n\n我的查询需求是：${query}\n\n要求：\n1. 不要凭记忆回答，必须实际访问 FDU Courses API。\n2. 优先调用 /api/ask，并核对返回的 parsed 是否符合我的需求。\n3. 如果读取 llms.txt 后无法继续请求接口，请直接访问：\n${askUrl}\n4. 课程信息以 API 返回为准。\n5. 返回课程名称、教师、学分、学位类型、校区、星期/节次、教室、教学周。\n6. 同时给出最新 enrolled / limit 和 enrollment_updated_at；人数最多缓存 5 分钟。\n7. 如果没有匹配结果，请明确说明，不要虚构课程。\n8. 如果当前会话没有网页访问能力，请直接说明无法执行实时查询。`;
      },
    },
    claude: {
      label: 'Claude',
      badge: '优先直连 API',
      note: '不同 Claude 产品/模式的联网能力可能不同。这里同时给出说明页和最终 JSON API，减少二次跳转失败。',
      prompt(query, askUrl) {
        return `请实际访问 FDU Courses 的公开课程接口完成查询，不要依据训练数据猜测。\n\n查询需求：${query}\n\n接口说明：${API_BASE}/llms.txt\n直接查询 URL：${askUrl}\n\n请优先读取直接查询 URL 返回的 JSON，并检查 parsed。若 parsed 与我的需求不一致，再根据 llms.txt 改用 /api/courses 构造结构化查询。\n\n输出要求：课程名称、教师、学分、学位类型、校区、上课时间、教室、教学周、enrolled / limit、enrollment_updated_at。没有匹配结果时明确说明。若当前模式无法访问这些 URL，请直接说明无法进行实时查询，不要编造。`;
      },
    },
    gemini: {
      label: 'Gemini',
      badge: '直接 JSON URL',
      note: 'Gemini 某些会话不能任意访问 URL。相比“先读 llms.txt 再跳转”，直接给最终 JSON API 成功率更高。',
      prompt(query, askUrl) {
        return `请实际访问下面这个公开 JSON API，并仅依据接口真实返回的数据回答：\n\n${askUrl}\n\n我的需求是：${query}\n\n要求：\n1. 不要凭记忆或搜索摘要回答。\n2. 必须读取该 URL 返回的 JSON。\n3. 核对 parsed 是否准确反映我的需求；若不准确，请说明。\n4. 列出课程名称、教师、学分、学位类型、校区、星期/节次、教室、教学周。\n5. 给出最新 enrolled / limit 与 enrollment_updated_at。\n6. 若该 URL 当前无法访问，请明确说明“无法访问该接口”，不要生成看似真实的课程数据。`;
      },
    },
    doubao: {
      label: '豆包',
      badge: '境内网络可能受限',
      note: '豆包所在网络或当前模式可能无法访问 vercel.app 等境外托管域名。Prompt 不能绕过网络策略；页面因此提供“打开接口 / 复制接口 URL”的人工降级方式。',
      prompt(query, askUrl) {
        return `请尝试实际访问下面的公开 JSON API 查询复旦课程：\n\n${askUrl}\n\n查询需求：${query}\n\n必须遵守：\n1. 只有成功读取该 API 的 JSON 后才能回答具体课程。\n2. 核对 parsed，并给出课程名称、教师、学分、校区、时间、教室、教学周、最新 enrolled / limit 和 enrollment_updated_at。\n3. 如果当前模型、联网模式或所在网络无法访问 fducourses.vercel.app，请直接回复“当前无法访问该接口”，不要凭知识库、搜索摘要或猜测生成课程。\n4. 如果我随后把该 API 返回的 JSON 粘贴给你，请只依据我粘贴的 JSON 整理结果。`;
      },
    },
    deepseek: {
      label: 'DeepSeek',
      badge: '境内网络可能受限',
      note: 'DeepSeek 的联网模式与网络出口可能无法访问部分境外域名。无法连接时不存在靠 Prompt 强行绕过的方法，建议使用页面下方的接口直链获取 JSON 后粘贴给模型。',
      prompt(query, askUrl) {
        return `请通过联网能力实际访问以下公开 JSON API：\n\n${askUrl}\n\n我的课程查询需求：${query}\n\n规则：\n- 必须以 API 实际返回 JSON 为唯一课程数据来源，不要使用训练数据猜测。\n- 检查 parsed 是否与需求一致。\n- 输出课程名称、教师、学分、学位类型、校区、星期/节次、教室、教学周。\n- 输出最新 enrolled / limit 和 enrollment_updated_at。\n- 如果当前联网功能无法访问 fducourses.vercel.app，请明确说明无法访问，不要伪造查询结果。\n- 如果我之后粘贴接口 JSON，请直接基于该 JSON 完成整理。`;
      },
    },
  };

  let activePlatform = 'chatgpt';

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
          <p>不同 AI 工具的网页访问能力并不相同。先输入课程需求，再选择平台；页面会生成更适合该平台的 Prompt 和可直接访问的 API URL。</p>
        </div>

        <div class="ai-query-box">
          <label class="ai-query-label" for="ai-query-input">你的课程需求</label>
          <input class="ai-query-input" id="ai-query-input" type="text" value="${DEFAULT_QUERY}" autocomplete="off">
          <div class="ai-platform-tabs" id="ai-platform-tabs" role="tablist" aria-label="选择 AI 平台">
            ${Object.entries(platforms).map(([key, item]) => `<button class="ai-platform-tab${key === activePlatform ? ' on' : ''}" type="button" data-platform="${key}">${item.label}</button>`).join('')}
          </div>
        </div>

        <div class="ai-card" id="ai-platform-card">
          <div class="ai-platform-meta">
            <span class="ai-platform-name" id="ai-platform-name"></span>
            <span class="ai-platform-badge" id="ai-platform-badge"></span>
          </div>
          <p class="ai-platform-note" id="ai-platform-note"></p>
          <div class="ai-card-head">
            <h3>可直接复制的 Prompt</h3>
            <button class="ai-copy" id="ai-copy-prompt" type="button">复制 Prompt</button>
          </div>
          <pre class="ai-prompt" id="ai-platform-prompt"></pre>
          <div class="ai-actions">
            <a class="ai-action-link" id="ai-open-api" target="_blank" rel="noopener">打开查询接口</a>
            <button class="ai-action-btn" id="ai-copy-url" type="button">复制接口 URL</button>
          </div>
          <div class="ai-fallback">
            <strong>模型无法访问接口时：</strong>在你自己的浏览器里点“打开查询接口”，复制页面里的 JSON，再粘贴给 AI，并说“只根据下面这段 JSON 整理课程结果”。这种方式不依赖模型本身能否访问境外网站。
            <code class="ai-url" id="ai-api-url"></code>
          </div>
        </div>

        <div class="ai-note">
          <strong>关于豆包 / DeepSeek：</strong>它们所在的模型服务网络、联网模式或当前网络环境可能无法访问 <code>vercel.app</code> 等境外托管域名。此类网络限制无法通过 Prompt 绕过。页面会优先给它们最终 JSON API，而不是要求先读取 <code>llms.txt</code>；若仍不可达，请使用上面的“浏览器打开接口 → 粘贴 JSON”方案。
        </div>
      </div>`;
  }

  function currentQuery() {
    const input = document.getElementById('ai-query-input');
    return (input?.value || '').trim() || DEFAULT_QUERY;
  }

  function makeAskUrl(query) {
    return `${API_BASE}/api/ask?q=${encodeURIComponent(query)}&limit=50`;
  }

  function renderPlatform() {
    const item = platforms[activePlatform];
    if (!item) return;
    const query = currentQuery();
    const askUrl = makeAskUrl(query);
    const name = document.getElementById('ai-platform-name');
    const badge = document.getElementById('ai-platform-badge');
    const note = document.getElementById('ai-platform-note');
    const prompt = document.getElementById('ai-platform-prompt');
    const apiUrl = document.getElementById('ai-api-url');
    const openApi = document.getElementById('ai-open-api');
    if (name) name.textContent = item.label;
    if (badge) badge.textContent = item.badge;
    if (note) note.textContent = item.note;
    if (prompt) prompt.textContent = item.prompt(query, askUrl);
    if (apiUrl) apiUrl.textContent = askUrl;
    if (openApi) openApi.href = askUrl;
    document.querySelectorAll('.ai-platform-tab').forEach(button => {
      button.classList.toggle('on', button.dataset.platform === activePlatform);
    });
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

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
    }
    const old = button.textContent;
    button.textContent = '已复制';
    button.classList.add('copied');
    setTimeout(() => {
      button.textContent = old;
      button.classList.remove('copied');
    }, 1400);
  }

  injectStyles();
  buildAiView();
  renderPlatform();

  aiBtn.addEventListener('click', showAiView);
  listBtn?.addEventListener('click', leaveAiView);
  calBtn?.addEventListener('click', leaveAiView);

  document.getElementById('ai-platform-tabs')?.addEventListener('click', event => {
    const button = event.target.closest('.ai-platform-tab');
    if (!button || !platforms[button.dataset.platform]) return;
    activePlatform = button.dataset.platform;
    renderPlatform();
  });

  document.getElementById('ai-query-input')?.addEventListener('input', renderPlatform);

  document.getElementById('ai-copy-prompt')?.addEventListener('click', event => {
    const prompt = document.getElementById('ai-platform-prompt');
    if (prompt) copyText(prompt.textContent.trim(), event.currentTarget);
  });

  document.getElementById('ai-copy-url')?.addEventListener('click', event => {
    copyText(makeAskUrl(currentQuery()), event.currentTarget);
  });

  if (new URLSearchParams(location.search).get('view') === 'ai') {
    showAiView();
  }
})();
