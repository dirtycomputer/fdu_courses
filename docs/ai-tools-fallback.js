'use strict';

(() => {
  const STATIC_URL = 'https://dirtycomputer.github.io/fdu_courses/data/latest.json';
  const DOMESTIC_PLATFORMS = new Set(['doubao', 'deepseek']);

  function selectedPlatform() {
    return document.querySelector('.ai-platform-tab.on')?.dataset.platform || '';
  }

  function queryText() {
    const input = document.getElementById('ai-query-input');
    return (input?.value || '').trim() || '查询课程';
  }

  function liveUrl() {
    return document.getElementById('ai-api-url')?.textContent?.trim() || '';
  }

  function platformLabel(key) {
    return key === 'doubao' ? '豆包' : 'DeepSeek';
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
    if (!button) return;
    const old = button.textContent;
    button.textContent = '已复制';
    setTimeout(() => { button.textContent = old; }, 1200);
  }

  function ensureStaticActions() {
    const actions = document.querySelector('#ai-platform-card .ai-actions');
    if (!actions || document.getElementById('ai-open-static')) return;

    const open = document.createElement('a');
    open.id = 'ai-open-static';
    open.className = 'ai-action-link ai-static-action';
    open.href = STATIC_URL;
    open.target = '_blank';
    open.rel = 'noopener';
    open.textContent = '打开静态 latest.json';

    const copy = document.createElement('button');
    copy.id = 'ai-copy-static-url';
    copy.className = 'ai-action-btn ai-static-action';
    copy.type = 'button';
    copy.textContent = '复制静态 URL';
    copy.addEventListener('click', () => copyText(STATIC_URL, copy));

    actions.append(open, copy);
  }

  function removeStaticActions() {
    document.querySelectorAll('.ai-static-action').forEach(el => el.remove());
  }

  function renderFallback() {
    const platform = selectedPlatform();
    if (!DOMESTIC_PLATFORMS.has(platform)) {
      removeStaticActions();
      return;
    }

    const query = queryText();
    const live = liveUrl();
    const label = platformLabel(platform);
    const prompt = document.getElementById('ai-platform-prompt');
    const note = document.getElementById('ai-platform-note');
    const fallback = document.querySelector('#ai-platform-card .ai-fallback');

    if (note) {
      note.textContent = `${label} 的联网出口可能无法访问 vercel.app。请先尝试实时 API；若访问失败，立即改读 GitHub Pages 的 latest.json 静态快照。静态快照可以查询课程，但其中 enrolled / limit 不是实时人数。`;
    }

    if (prompt) {
      prompt.textContent = `请查询复旦大学课程。我的需求是：${query}\n\n请严格按以下顺序执行：\n\n第一步：优先尝试实时 API\n${live}\n\n如果能成功读取该 URL 返回的 JSON：\n- 核对 parsed 是否符合我的需求。\n- 只依据 API 返回的数据回答。\n- 输出课程名称、教师、学分、学位类型、校区、星期/节次、教室、教学周。\n- 输出最新 enrolled / limit 和 enrollment_updated_at。\n\n第二步：如果因为当前模型的联网能力、网络出口或域名限制而无法访问 fducourses.vercel.app，不要停止，也不要凭记忆回答；请立即改为尝试读取 GitHub Pages 静态数据：\n${STATIC_URL}\n\n如果能读取 latest.json：\n- 只依据其中 courses 数据筛选并回答“${query}”。\n- 告诉我该静态数据的 generatedAt。\n- 可以显示 JSON 中已有的 enrolled / limit，但必须明确标注“静态快照人数，不是实时选课人数”。\n- 不得把 generatedAt 冒充 enrollment_updated_at，也不得声称人数是 5 分钟实时数据。\n\n第三步：如果实时 API 和 GitHub Pages 静态数据都无法访问，请明确说明“当前无法访问两个数据源，因此无法可靠查询”，不要根据训练数据、搜索摘要或猜测生成课程。`;
    }

    if (fallback) {
      fallback.innerHTML = `<strong>国内模型降级路径：</strong>先尝试 Vercel 实时 API；若模型访问失败，改读 GitHub Pages 静态课程库。静态库地址：<code class="ai-url">${STATIC_URL}</code><div style="margin-top:8px">注意：静态库里的 <code>enrolled / limit</code> 只代表 <code>generatedAt</code> 对应的历史快照，不能当作当前实时名额。</div>`;
    }

    ensureStaticActions();
  }

  function scheduleRender() {
    setTimeout(renderFallback, 0);
  }

  document.addEventListener('click', event => {
    if (event.target.closest('.ai-platform-tab')) scheduleRender();
  });
  document.addEventListener('input', event => {
    if (event.target.id === 'ai-query-input') scheduleRender();
  });

  if (new URLSearchParams(location.search).get('view') === 'ai') {
    scheduleRender();
  }
})();
