/**
 * Application Controller & UI View Coordinator
 */
let deferredPrompt = null;
let currentIssues = [];
let currentCategory = 'all';
let currentNavTab = 'feed'; // 'feed' or 'bookmark'
let currentKeyword = '용인시';

// Initialize Keyword Chips UI
function renderKeywordChips() {
  const userKeywords = StorageManager.getKeywords();
  const mainChips = document.getElementById('keywordChips');
  const settingsChips = document.getElementById('settingsKeywordChips');

  if (!userKeywords.includes(currentKeyword)) {
    currentKeyword = userKeywords.length ? userKeywords[0] : '';
  }

  if (mainChips) {
    let html = '';
    userKeywords.forEach(kw => {
      const isActive = currentKeyword === kw;
      html += `
        <span class="chip ${isActive ? 'active' : ''}" onclick="selectKeyword('${kw}')">
          # ${kw}
          <span class="chip-delete" onclick="removeKeyword('${kw}', event)" title="${kw} 삭제">✕</span>
        </span>
      `;
    });
    html += `<span class="chip-add" onclick="addNewKeyword()">+ 추가</span>`;
    mainChips.innerHTML = html;
  }

  if (settingsChips) {
    let settingsHtml = '';
    userKeywords.forEach(kw => {
      settingsHtml += `
        <span class="chip active">
          # ${kw}
          <span class="chip-delete" onclick="removeKeyword('${kw}', event)" title="${kw} 삭제">✕</span>
        </span>
      `;
    });
    settingsHtml += `<span class="chip-add" onclick="addNewKeyword()">+ 새 키워드 등록</span>`;
    settingsChips.innerHTML = settingsHtml;
  }
}

async function fetchKeywordIssues(keywordsList) {
  try {
    currentIssues = await IssueApi.fetchKeywordIssues(keywordsList);
    renderIssues();
    showToast(`✅ 최신 소식 수집이 완료되었습니다.`);
  } catch (err) {
    console.warn('Keyword collect error:', err);
  }
}

async function selectKeyword(kw) {
  currentKeyword = kw;
  renderKeywordChips();

  const hasItems = currentIssues.some(item => item.keyword === kw || (item.title && item.title.includes(kw)));
  renderIssues();

  if (!hasItems) {
    showToast(`🔄 '${kw}' 최신 소식 수집 중...`);
    const keywords = StorageManager.getKeywords();
    await fetchKeywordIssues(keywords);
  }
}

async function addNewKeyword() {
  const input = prompt('추가할 모니터링 키워드나 지역명을 입력하세요 (예: 수지구, 기흥구, 동백동):', '');
  if (!input) return;
  const kw = input.trim().replace(/^#\s*/, '');
  if (!kw) return;

  const currentKeywords = StorageManager.getKeywords();
  if (currentKeywords.includes(kw)) {
    selectKeyword(kw);
    return;
  }

  const updated = StorageManager.addKeyword(kw);
  currentKeyword = kw;
  renderKeywordChips();
  renderIssues();

  showToast(`🔄 '${kw}' 실시간 관련 콘텐츠 수집 중...`);
  await fetchKeywordIssues(updated);
}

function removeKeyword(kw, event) {
  if (event) event.stopPropagation();
  if (!confirm(`'${kw}' 키워드를 모니터링 목록에서 삭제하시겠습니까?`)) return;

  const updated = StorageManager.removeKeyword(kw);

  if (currentKeyword === kw) {
    currentKeyword = updated.length ? updated[0] : '';
  }

  renderKeywordChips();
  renderIssues();
  showToast(`'# ${kw}' 키워드가 삭제되었습니다.`);
}

function updateScrapBadge() {
  const badge = document.getElementById('scrapBadge');
  const scraps = StorageManager.getScraps();
  if (badge) {
    if (scraps.length > 0) {
      badge.textContent = scraps.length;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

function switchNavTab(tab, btn) {
  currentNavTab = tab;
  const navBtns = document.querySelectorAll('.app-bottom-nav .nav-item');
  navBtns.forEach(b => {
    if (!b.innerText.includes('설정')) {
      b.classList.remove('active');
    }
  });
  if (btn) btn.classList.add('active');

  const categoryTabs = document.querySelector('.category-tabs');
  const keywordChips = document.querySelector('.keyword-chips');
  if (tab === 'bookmark') {
    if (categoryTabs) categoryTabs.style.display = 'none';
    if (keywordChips) keywordChips.style.display = 'none';
  } else {
    if (categoryTabs) categoryTabs.style.display = 'flex';
    if (keywordChips) keywordChips.style.display = 'flex';
  }

  renderIssues();
}

function renderIssues() {
  const container = document.getElementById('feedContainer');
  if (!container) return;

  updateScrapBadge();
  const scraps = StorageManager.getScraps();

  // --- Bookmark View (보관함) ---
  if (currentNavTab === 'bookmark') {
    let html = `
      <div class="realtime-bar" style="background:#FFFBEB; border-color:#FDE68A; color:#D97706;">
        <div class="realtime-indicator">
          <span>⭐ 내가 보관한 주요 이슈 (${scraps.length}건)</span>
        </div>
        <span style="font-size: 11px; opacity: 0.8;">보관함</span>
      </div>
    `;

    if (scraps.length === 0) {
      html += `
        <div style="text-align:center; padding: 60px 20px; color: var(--text-sub);">
          <p style="font-size:36px; margin-bottom:12px;">⭐</p>
          <p style="font-size:15px; font-weight:700; color:var(--text-main); margin-bottom:6px;">보관된 이슈가 없습니다.</p>
          <p style="font-size:12px; color:#64748B;">실시간 피드에서 관심 있는 이슈 카드의 <strong>[⭐ 스크랩]</strong> 버튼을 눌러 나만의 보관함에 담아보세요!</p>
        </div>
      `;
    } else {
      scraps.forEach(item => {
        const badgeClass = item.type === 'news' ? 'source-news' : (item.type === 'youtube' ? 'source-youtube' : 'source-sns');
        const hasPreSummary = item.summary && item.summary.length > 0;
        const summaryItems = hasPreSummary ? item.summary.map(s => `<li>${s}</li>`).join('') : '';
        const isNegBadge = item.is_negative ? `<span class="is-neg-tag" style="background:#FEF2F2; color:#EF4444; border:1px solid #FECACA; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; margin-left:6px;">🚨 관심 이슈</span>` : '';
        
        let linkText = '원문 보기 ↗';
        if (item.type === 'youtube') linkText = '영상 재생 ↗';
        else if (item.type === 'sns') linkText = '포스트 보기 ↗';

        const titleAttr = (item.title || '').replace(/"/g, '&quot;');
        const contentAttr = (item.content || item.title || '').replace(/"/g, '&quot;');

        html += `
          <div class="issue-card" data-category="${item.type}" data-title="${titleAttr}" data-content="${contentAttr}" data-keyword="${item.keyword || '용인시'}">
            <div class="card-top">
              <span class="source-tag ${badgeClass}">${item.badge || '📰 이슈'} · ${item.publisher || '소식'} ${isNegBadge}</span>
              <span class="card-time">${item.time || '보관됨'}</span>
            </div>
            <h3 class="card-title">${item.title}</h3>
            
            <button class="ai-summary-toggle-btn" onclick="toggleOnDemandAiSummary(this)">
              ✨ AI 3줄 요약 보기 ▾
            </button>

            <div class="ai-summary-box" style="display: none;" data-generated="${hasPreSummary ? 'true' : 'false'}">
              <div class="ai-summary-head">✨ FactChat AI 핵심 3줄 요약</div>
              <ul class="ai-summary-list">
                ${summaryItems}
              </ul>
            </div>

            <div class="card-footer">
              <div class="card-btns">
                <button class="card-action-btn scrapped" onclick="toggleScrap(this, '${titleAttr}')">★ 스크랩됨</button>
                <button class="card-action-btn" onclick="shareArticle('${(item.title || '').replace(/'/g, "")}')">🔗 공유</button>
              </div>
              <a href="${item.url || '#'}" target="_blank" rel="noopener noreferrer" class="link-btn" onclick="openContentUrl('${item.url || '#'}', event)">${linkText}</a>
            </div>
          </div>
        `;
      });
    }

    container.innerHTML = html;
    updateClock();
    return;
  }

  // --- Realtime Feed View (실시간 피드) ---
  const userKeywords = StorageManager.getKeywords();
  if (userKeywords.length === 0) {
    let emptyHtml = `
      <div class="realtime-bar">
        <div class="realtime-indicator">
          <div class="live-dot"></div>
          <span>접속 시점 기준 실시간 이슈 피드</span>
        </div>
        <span style="font-size: 11px; opacity: 0.8;" id="updateTimestamp">방금 업데이트</span>
      </div>
      <div style="text-align:center; padding: 50px 20px; color: var(--text-sub);">
        <p style="font-size:32px; margin-bottom:10px;">📌</p>
        <p style="font-size:15px; font-weight:700; color:var(--text-main); margin-bottom:6px;">등록된 모니터링 키워드가 없습니다.</p>
        <p style="font-size:12px; color:#64748B;">상단의 <strong>[+ 추가]</strong> 버튼을 눌러 모니터링할 지역 또는 관심 키워드를 추가해 주세요!</p>
      </div>
    `;
    container.innerHTML = emptyHtml;
    updateClock();
    return;
  }

  if (!currentIssues.length) return;

  const filtered = currentIssues.filter(item => {
    const matchCat = (currentCategory === 'all' || item.type === currentCategory);
    const matchKw = (currentKeyword === '전체' || item.keyword === currentKeyword || (item.title && item.title.includes(currentKeyword)));
    return matchCat && matchKw;
  });

  // Update category tab counts
  const counts = {
    all: currentIssues.length,
    news: currentIssues.filter(i => i.type === 'news').length,
    youtube: currentIssues.filter(i => i.type === 'youtube').length,
    sns: currentIssues.filter(i => i.type === 'sns').length
  };

  const tabs = document.querySelectorAll('.tab-btn');
  if (tabs.length >= 4) {
    tabs[0].textContent = `전체 (${counts.all})`;
    tabs[1].textContent = `📰 뉴스 (${counts.news})`;
    tabs[2].textContent = `🎥 유튜브 (${counts.youtube})`;
    tabs[3].textContent = `📱 SNS (${counts.sns})`;
  }

  let html = `
    <div class="realtime-bar">
      <div class="realtime-indicator">
        <div class="live-dot"></div>
        <span>접속 시점 기준 실시간 이슈 피드</span>
      </div>
      <span style="font-size: 11px; opacity: 0.8;" id="updateTimestamp">방금 업데이트</span>
    </div>
  `;

  if (filtered.length === 0) {
    html += `
      <div style="text-align:center; padding: 40px 20px; color: var(--text-sub);">
        <p style="font-size:24px; margin-bottom:8px;">🔍</p>
        <p style="font-size:14px; font-weight:600;">선택하신 조건에 일치하는 이슈가 없습니다.</p>
      </div>
    `;
  } else {
    filtered.forEach(item => {
      const badgeClass = item.type === 'news' ? 'source-news' : (item.type === 'youtube' ? 'source-youtube' : 'source-sns');
      const hasPreSummary = item.summary && item.summary.length > 0;
      const summaryItems = hasPreSummary ? item.summary.map(s => `<li>${s}</li>`).join('') : '';
      const isNegBadge = item.is_negative ? `<span class="is-neg-tag" style="background:#FEF2F2; color:#EF4444; border:1px solid #FECACA; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; margin-left:6px;">🚨 관심 이슈</span>` : '';
      const dedupBadge = item.dedup_badge ? `<span style="background:#F1F5F9; color:#475569; border:1px solid #CBD5E1; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; margin-left:6px;">${item.dedup_badge}</span>` : '';
      
      let linkText = '원문 보기 ↗';
      if (item.type === 'youtube') linkText = '영상 재생 ↗';
      else if (item.type === 'sns') linkText = '포스트 보기 ↗';

      const titleAttr = (item.title || '').replace(/"/g, '&quot;');
      const contentAttr = (item.content || item.title || '').replace(/"/g, '&quot;');
      const isScrapped = StorageManager.isScrapped(item.title);
      const scrapBtnHtml = isScrapped
        ? `<button class="card-action-btn scrapped" onclick="toggleScrap(this, '${titleAttr}')">★ 스크랩됨</button>`
        : `<button class="card-action-btn" onclick="toggleScrap(this, '${titleAttr}')">⭐ 스크랩</button>`;

      html += `
        <div class="issue-card" data-category="${item.type}" data-title="${titleAttr}" data-content="${contentAttr}" data-keyword="${item.keyword || '용인시'}">
          <div class="card-top">
            <span class="source-tag ${badgeClass}">${item.badge} · ${item.publisher} ${isNegBadge} ${dedupBadge}</span>
            <span class="card-time">${item.time}</span>
          </div>
          <h3 class="card-title">${item.title}</h3>
          
          <button class="ai-summary-toggle-btn" onclick="toggleOnDemandAiSummary(this)">
            ✨ AI 3줄 요약 보기 ▾
          </button>

          <div class="ai-summary-box" style="display: none;" data-generated="${hasPreSummary ? 'true' : 'false'}">
            <div class="ai-summary-head">✨ FactChat AI 핵심 3줄 요약</div>
            <ul class="ai-summary-list">
              ${summaryItems}
            </ul>
          </div>

          <div class="card-footer">
            <div class="card-btns">
              ${scrapBtnHtml}
              <button class="card-action-btn" onclick="shareArticle('${(item.title || '').replace(/'/g, "")}')">🔗 공유</button>
            </div>
            <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="link-btn" onclick="openContentUrl('${item.url}', event)">${linkText}</a>
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
  updateClock();
}

function switchCategory(cat, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentCategory = cat;
  renderIssues();
}

function triggerNotificationTest() {
  const push = document.getElementById('pushBanner');
  if (push) {
    push.classList.add('show');
    setTimeout(() => push.classList.remove('show'), 4500);
  }

  if ('Notification' in window) {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted' && navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready.then(registration => {
          registration.showNotification('🔔 용인 핫이슈 실시간 알림', {
            body: '[처인구] 반도체 클러스터 우회도로 확장 착공 공식 발표 - FactChat 3줄 요약 수신완료',
            icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="%232563eb"/><text x="50" y="65" font-size="50" font-weight="bold" text-anchor="middle" fill="white">🔔</text></svg>',
            vibrate: [200, 100, 200]
          });
        });
      }
    });
  }
}

function toggleSettingsModal() {
  const modal = document.getElementById('settingsModal');
  if (modal) modal.classList.toggle('show');
}

function toggleScrap(btn, title) {
  const card = btn.closest('.issue-card');
  if (!title && card) {
    title = card.dataset.title || '';
  }
  if (!title) return;

  let targetItem = currentIssues.find(item => item.title === title);
  if (!targetItem && card) {
    targetItem = {
      title: title,
      url: card.querySelector('.link-btn') ? card.querySelector('.link-btn').href : '#',
      publisher: '용인 소식',
      time: '보관됨',
      type: card.dataset.category || 'news',
      badge: '📰 보관',
      keyword: card.dataset.keyword || '용인시'
    };
  }

  const { isScrapped } = StorageManager.toggleScrap(targetItem || title);

  if (isScrapped) {
    btn.classList.add('scrapped');
    btn.innerHTML = '★ 스크랩됨';
    showToast('⭐ 보관함에 스크랩되었습니다.');
  } else {
    btn.classList.remove('scrapped');
    btn.innerHTML = '⭐ 스크랩';
    showToast('보관함에서 취소되었습니다.');
  }

  updateScrapBadge();

  if (currentNavTab === 'bookmark') {
    renderIssues();
  }
}

function showToast(msg) {
  let toast = document.getElementById('appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.className = 'app-toast';
    const appScreen = document.querySelector('.app-screen');
    if (appScreen) appScreen.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2500);
}

function shareArticle(title, url) {
  const shareUrl = url || window.location.href;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(shareUrl).then(() => {
      showToast(`🔗 링크가 클립보드에 복사되었습니다.`);
    }).catch(() => {
      showToast(`🔗 공유 링크 복사 완료`);
    });
  } else {
    showToast(`🔗 '${(title || '').slice(0, 15)}...' 링크가 복사되었습니다.`);
  }
}

function updateNotifySetting(key, inputElem) {
  const settings = StorageManager.getNotifySettings();
  settings[key] = inputElem.checked;
  StorageManager.saveNotifySettings(settings);
  const labelStr = key === 'realtime' ? '실시간 속보' : (key === 'negative' ? '관심/위험 이슈' : '정기 브리핑');
  showToast(`${labelStr} 알림이 ${inputElem.checked ? 'ON 설정' : 'OFF 해제'}되었습니다.`);
}

function togglePasswordVisibility() {
  const input = document.getElementById('factchatApiKeyInput');
  if (input) input.type = input.type === 'password' ? 'text' : 'password';
}

function initFactChatKeyUI() {
  const input = document.getElementById('factchatApiKeyInput');
  const badge = document.getElementById('factchatKeyBadge');
  const savedKey = StorageManager.getFactChatKey();

  if (input && savedKey) {
    input.value = savedKey;
  }
  if (badge) {
    if (savedKey) {
      badge.className = 'api-key-badge active';
      badge.textContent = '✅ 연동됨';
    } else {
      badge.className = 'api-key-badge warning';
      badge.textContent = '⚠️ 키 입력 필요';
    }
  }
}

function saveFactchatKey() {
  const input = document.getElementById('factchatApiKeyInput');
  const badge = document.getElementById('factchatKeyBadge');
  const keyVal = input ? input.value.trim() : '';

  StorageManager.saveFactChatKey(keyVal);
  if (keyVal) {
    if (badge) {
      badge.className = 'api-key-badge active';
      badge.textContent = '✅ 연동됨';
    }
    showToast('🔑 FactChat API 키가 안전하게 저장되었습니다!');
  } else {
    if (badge) {
      badge.className = 'api-key-badge warning';
      badge.textContent = '⚠️ 키 입력 필요';
    }
    showToast('⚠️ API 키를 입력하지 않으면 AI 3줄 요약 기능이 제한됩니다.');
  }
}

function showKeyIssuanceGuide() {
  alert(`[사내 FactChat API 개인 키 발급 안내]\n\n1. 사내 FactChat 개발자 포털(https://factchat-cloud.mindlogic.ai/v1/gateway) 접속\n2. 사내 계정 로그인 후 [마이페이지 -> API 키 관리] 메뉴 이동\n3. [신규 개인 발급키 생성] 클릭 후 생성된 키 복사 (fc_key_...)\n4. 본 앱의 설정창 [사내 FactChat API 개인 키 설정] 입력란에 붙여넣고 [저장]을 누르시면 AI 3줄 요약 기능이 즉시 연동됩니다.`);
}

async function toggleOnDemandAiSummary(btn) {
  const card = btn.closest('.issue-card');
  const summaryBox = card.querySelector('.ai-summary-box');
  if (!summaryBox) return;

  const isVisible = summaryBox.style.display !== 'none';
  if (isVisible) {
    summaryBox.style.display = 'none';
    btn.innerHTML = '✨ AI 3줄 요약 보기 ▾';
    return;
  }

  const isGenerated = summaryBox.dataset.generated === 'true';
  if (isGenerated) {
    summaryBox.style.display = 'block';
    btn.innerHTML = '✨ AI 3줄 요약 접기 ▴';
    return;
  }

  const title = card.dataset.title || '';
  const content = card.dataset.content || title;
  const keyword = card.dataset.keyword || '용인시';
  const apiKey = StorageManager.getFactChatKey();

  btn.innerHTML = '✨ FactChat AI 3줄 요약 생성 중...';
  btn.disabled = true;

  try {
    const { summary, is_negative } = await IssueApi.generateSummary({ title, keyword, content, apiKey });
    const listHtml = summary.map(s => `<li>${s}</li>`).join('');
    summaryBox.querySelector('.ai-summary-list').innerHTML = listHtml;
    summaryBox.style.display = 'block';
    summaryBox.dataset.generated = 'true';
    btn.innerHTML = '✨ AI 3줄 요약 접기 ▴';
    btn.disabled = false;

    if (is_negative) {
      const sourceTag = card.querySelector('.source-tag');
      if (sourceTag && !sourceTag.querySelector('.is-neg-tag')) {
        sourceTag.innerHTML += `<span class="is-neg-tag" style="background:#FEF2F2; color:#EF4444; border:1px solid #FECACA; font-size:10px; font-weight:700; padding:2px 6px; border-radius:10px; margin-left:6px;">🚨 관심 이슈</span>`;
      }
    }
  } catch (err) {
    console.error('On-Demand AI Summary Error:', err);
    btn.innerHTML = '✨ AI 3줄 요약 보기 ▾';
    btn.disabled = false;
    alert('FactChat API 요약 생성 중 오류가 발생했습니다. 설정에서 API 키를 확인해 주세요.');
  }
}

function openContentUrl(url, event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  if (url && url !== '#') {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const timeElem = document.getElementById('liveTime');
  const tsElem = document.getElementById('updateTimestamp');
  if (timeElem) timeElem.textContent = `${hours}:${minutes}`;
  if (tsElem) tsElem.textContent = `${hours}:${minutes} 기준 최신`;
}

function installPWA() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        alert('용인 핫이슈 모니터 앱 설치가 시작되었습니다!');
      }
      deferredPrompt = null;
    });
  } else {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
      alert('📱 [아이폰 PWA 앱 설치 안내]\n\n하단 사파리 브라우저의 [공유] 버튼(↑)을 누르신 후 목록에서 [홈 화면에 추가 (+)]를 클릭하시면 스마트폰 바탕화면에 앱으로 등록됩니다.');
    } else {
      alert('📱 [앱 설치 안내]\n\n모바일 크롬/웨일 브라우저 상단 우측 메뉴(⋮) ➔ [앱 설치] 또는 [홈 화면에 추가]를 누르시면 스마트폰 바탕화면에 앱이 설치됩니다.');
    }
  }
}

// Lifecycle Init
document.addEventListener('DOMContentLoaded', () => {
  renderKeywordChips();
  updateScrapBadge();
  initFactChatKeyUI();
  
  // Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./sw.js')
        .then((reg) => console.log('PWA Service Worker registered:', reg.scope))
        .catch((err) => console.log('SW Registration failed:', err));
    });
  }

  // PWA Prompt Listener
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
  });

  // Clock Timer
  setInterval(updateClock, 1000);
  updateClock();

  // Load Issues
  IssueApi.loadDefaultIssues().then(issues => {
    currentIssues = issues;
    renderKeywordChips();
    renderIssues();
  });
});
