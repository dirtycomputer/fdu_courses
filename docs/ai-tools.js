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

  aiBtn.addEventListener('click', showAiView);
  listBtn?.addEventListener('click', leaveAiView);
  calBtn?.addEventListener('click', leaveAiView);

  document.querySelectorAll('.ai-copy').forEach(button => {
    button.addEventListener('click', () => {
      const target = document.getElementById(button.dataset.copyTarget || '');
      if (target) copyText(target.textContent.trim(), button);
    });
  });

  if (new URLSearchParams(location.search).get('view') === 'ai') {
    showAiView();
  }
})();
