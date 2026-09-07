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
    renderKeywordChips();
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

async function refreshFeed() {
  const realtimeBar = document.querySelector('.realtime-bar');
  const feedContainer = document.getElementById('feedContainer');
  
  showToast('🔄 최신 소식 수집 및 업데이트 중...');
  
  if (realtimeBar) {
    realtimeBar.style.opacity = '0.7';
    const textElem = realtimeBar.querySelector('.realtime-indicator span');
    if (textElem) textElem.innerHTML = '실시간 이슈 피드 <span class="spin-icon">🔄</span> <strong>수집 중...</strong>';
  }
  if (feedContainer) {
    feedContainer.style.opacity = '0.5';
  }

  const userKeywords = StorageManager.getKeywords();
  try {
    if (userKeywords.length > 0) {
      currentIssues = await IssueApi.fetchKeywordIssues(userKeywords);
    }
  } catch (err) {
    console.warn('Refresh error:', err);
  } finally {
    renderKeywordChips();
    renderIssues();
    if (feedContainer) {
      feedContainer.style.opacity = '1';
    }
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    showToast(`✅ 실시간 피드 업데이트 완료 (${timeStr})`);
  }
}

async function switchNavTab(tab, btn) {
  const isAlreadyFeed = (currentNavTab === 'feed' && tab === 'feed');
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
    renderIssues();
  } else {
    if (categoryTabs) categoryTabs.style.display = 'flex';
    if (keywordChips) keywordChips.style.display = 'flex';

    if (isAlreadyFeed) {
      await refreshFeed();
    } else {
      renderIssues();
    }
  }
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
        const urlAttr = (item.url || '#').replace(/'/g, "\\'");

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
                <button class="card-action-btn" onclick="shareArticle('${titleAttr}', '${urlAttr}')">🔗 공유</button>
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

  const keywordFiltered = currentIssues.filter(item => {
    if (currentKeyword === '전체') return true;
    if (item.keyword === currentKeyword) return true;
    if ((currentKeyword === '용인시' || currentKeyword === '용인특례시') && (item.keyword === '용인시' || item.keyword === '용인특례시')) return true;
    const searchSpace = ((item.title || '') + ' ' + (item.content || '') + ' ' + (item.publisher || '')).toLowerCase();
    return searchSpace.includes(currentKeyword.toLowerCase());
  });

  // Calculate category tab counts based strictly on the selected keyword's contents
  const counts = {
    all: keywordFiltered.length,
    news: keywordFiltered.filter(i => i.type === 'news').length,
    youtube: keywordFiltered.filter(i => i.type === 'youtube').length,
    sns: keywordFiltered.filter(i => i.type === 'sns').length
  };

  const tabs = document.querySelectorAll('.tab-btn');
  if (tabs.length >= 4) {
    tabs[0].textContent = `전체 (${counts.all})`;
    tabs[1].textContent = `📰 뉴스 (${counts.news})`;
    tabs[2].textContent = `🎥 유튜브 (${counts.youtube})`;
    tabs[3].textContent = `📱 SNS (${counts.sns})`;
  }

  // Filter list by current category tab
  const filtered = keywordFiltered.filter(item => {
    return currentCategory === 'all' || item.type === currentCategory;
  });

  const now = new Date();
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

  let html = `
    <div class="realtime-bar" onclick="refreshFeed()" style="cursor: pointer;" title="클릭 시 최신 소식 실시간 새로고침">
      <div class="realtime-indicator">
        <div class="live-dot"></div>
        <span>실시간 이슈 피드 🔄 <strong>새로고침</strong></span>
      </div>
      <span style="font-size: 11px; opacity: 0.9;" id="updateTimestamp">${timeStr} 갱신 완료</span>
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
      const urlAttr = (item.url || '#').replace(/'/g, "\\'");
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
              <button class="card-action-btn" onclick="shareArticle('${titleAttr}', '${urlAttr}')">🔗 공유</button>
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

async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    showToast('⚠️ 이 브라우저는 푸시 알림을 지원하지 않습니다.');
    return false;
  }
  
  if (Notification.permission === 'granted') {
    return true;
  }
  
  if (Notification.permission !== 'denied') {
    try {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        showToast('✅ 알림 권한이 허용되었습니다!');
        return true;
      }
    } catch (e) {
      console.error('Notification permission request error:', e);
    }
  }

  showToast('⚠️ 아이폰/브라우저 [설정 > 알림]에서 알림을 허용해주세요.');
  return false;
}

async function triggerRealPushNotification(title, body, targetUrl) {
  const push = document.getElementById('pushBanner');
  if (push) {
    const titleElem = push.querySelector('.push-title span:first-child');
    const descElem = push.querySelector('.push-desc');
    if (titleElem) titleElem.textContent = title;
    if (descElem) descElem.textContent = body;

    if (targetUrl && targetUrl.startsWith('http')) {
      push.style.cursor = 'pointer';
      push.onclick = () => window.open(targetUrl, '_blank', 'noopener,noreferrer');
    } else {
      push.style.cursor = 'default';
      push.onclick = null;
    }

    push.classList.add('show');
    setTimeout(() => push.classList.remove('show'), 6000);
  }

  showToast(`🔔 ${title}`);

  if ('Notification' in window) {
    let perm = Notification.permission;
    if (perm === 'default') {
      try {
        perm = await Notification.requestPermission();
      } catch (e) {}
    }

    if (perm === 'granted') {
      const finalUrl = (targetUrl && targetUrl.startsWith('http')) ? targetUrl : window.location.href;
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready.then(registration => {
          registration.showNotification(title, {
            body: body,
            icon: './apple-touch-icon.png',
            badge: './apple-touch-icon.png',
            vibrate: [200, 100, 200],
            data: { url: finalUrl }
          });
        });
      } else {
        try {
          const n = new Notification(title, {
            body: body,
            icon: './apple-touch-icon.png',
            data: { url: finalUrl }
          });
          n.onclick = (e) => {
            e.preventDefault();
            window.open(finalUrl, '_blank', 'noopener,noreferrer');
            window.focus();
          };
        } catch (e) {
          console.log('Fallback Notification error:', e);
        }
      }
    }
  }
}

async function triggerNotificationTest() {
  await requestNotificationPermission();
  const topItem = currentIssues.length ? currentIssues[0] : null;
  const testTitle = topItem ? topItem.title : `[${currentKeyword || '용인시'}] 실시간 주요 속보`;
  const testUrl = topItem ? topItem.url : 'https://news.naver.com';

  triggerRealPushNotification(
    `🔔 [속보 알림] #${topItem ? topItem.keyword : (currentKeyword || '용인시')}`,
    testTitle,
    testUrl
  );
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

async function shareArticle(title, url) {
  const articleUrl = (url && url !== '#') ? url : window.location.href;
  const cleanTitle = (title || '용인 핫이슈').replace(/&quot;/g, '"');
  const shareData = {
    title: cleanTitle,
    text: `[용인 핫이슈 모니터] ${cleanTitle}`,
    url: articleUrl
  };

  if (navigator.share) {
    try {
      await navigator.share(shareData);
      showToast('🔗 원문 링크 공유가 완료되었습니다.');
      return;
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('Web Share API error:', err);
      } else {
        return;
      }
    }
  }

  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(articleUrl);
      showToast('🔗 콘텐츠 원문 링크가 클립보드에 복사되었습니다!');
      return;
    } catch (err) {
      console.warn('Clipboard write error:', err);
    }
  }

  prompt('아래 콘텐츠 원문 링크를 복사하여 공유하세요:', articleUrl);
}

function updateNotifySetting(key, inputElem) {
  const settings = StorageManager.getNotifySettings();
  settings[key] = inputElem.checked;
  StorageManager.saveNotifySettings(settings);
  const labelStr = key === 'realtime' ? '실시간 속보' : (key === 'negative' ? '관심/위험 이슈' : '정기 브리핑');
  showToast(`${labelStr} 알림이 ${inputElem.checked ? 'ON 설정' : 'OFF 해제'}되었습니다.`);
}

function updateNotifyInterval(selectElem) {
  const val = parseInt(selectElem.value, 10) || 15;
  const settings = StorageManager.getNotifySettings();
  settings.intervalMinutes = val;
  StorageManager.saveNotifySettings(settings);

  startAutoPolling();
  showToast(`⏱️ 푸시 알림 주기가 ${val}분 마다로 설정되었습니다.`);
}

let autoPollingTimer = null;

function startAutoPolling() {
  if (autoPollingTimer) clearInterval(autoPollingTimer);

  const settings = StorageManager.getNotifySettings();
  const intervalMin = settings.intervalMinutes || 15;
  const intervalMs = intervalMin * 60 * 1000;

  autoPollingTimer = setInterval(async () => {
    const notifySettings = StorageManager.getNotifySettings();
    if (!notifySettings || !notifySettings.realtime) return;

    const userKeywords = StorageManager.getKeywords();
    if (!userKeywords || userKeywords.length === 0) return;

    try {
      const latestIssues = await IssueApi.fetchKeywordIssues(userKeywords);
      if (latestIssues && latestIssues.length > 0) {
        const previousTitles = new Set(currentIssues.map(i => i.title));
        const newItems = latestIssues.filter(i => !previousTitles.has(i.title));

        currentIssues = latestIssues;
        renderKeywordChips();
        renderIssues();

        if (newItems.length > 0) {
          const topItem = newItems[0];
          triggerRealPushNotification(
            `🔔 [신규 속보] #${topItem.keyword || '용인시'} 새 이슈`,
            topItem.title,
            topItem.url
          );
        }
      }
    } catch (err) {
      console.warn('Auto polling check error:', err);
    }
  }, intervalMs);
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
  const seconds = String(now.getSeconds()).padStart(2, '0');
  const timeElem = document.getElementById('liveTime');
  const tsElem = document.getElementById('updateTimestamp');
  if (timeElem) timeElem.textContent = `${hours}:${minutes}`;
  if (tsElem && !tsElem.textContent.includes('갱신 완료')) {
    tsElem.textContent = `${hours}:${minutes}:${seconds} 갱신 완료`;
  }
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

  // Initialize notification interval UI
  const notifySettings = StorageManager.getNotifySettings();
  const selectElem = document.getElementById('notifyIntervalSelect');
  if (selectElem && notifySettings.intervalMinutes) {
    selectElem.value = String(notifySettings.intervalMinutes);
  }

  // Clock Timer
  setInterval(updateClock, 1000);
  updateClock();

  // Start auto-polling with user preferred interval (default 15 min)
  startAutoPolling();

  // Initial Load Issues
  IssueApi.loadDefaultIssues().then(issues => {
    currentIssues = issues;
    renderKeywordChips();
    renderIssues();
  });
});
