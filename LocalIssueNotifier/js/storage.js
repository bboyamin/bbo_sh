/**
 * StorageManager Deep Module
 * Interface to manage persistent client state (UserKeywords, ScrappedIssues, NotifySettings, FactChat API Key)
 */
const StorageManager = (() => {
  const KEYS = {
    KEYWORDS: 'user_keywords',
    SCRAPS: 'scrapped_issues',
    NOTIFY: 'notify_settings',
    FACTCHAT_KEY: 'factchat_api_key'
  };

  const DEFAULT_KEYWORDS = ['용인시', '처인구', '용인특례시'];
  const DEFAULT_NOTIFY = { realtime: true, negative: true, briefing: true };
  const DEFAULT_FACTCHAT_KEY = '';

  function safeGetJSON(key, fallback) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : fallback;
    } catch (e) {
      console.warn(`StorageManager error reading ${key}:`, e);
      return fallback;
    }
  }

  function safeSetJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.warn(`StorageManager error writing ${key}:`, e);
    }
  }

  return {
    getKeywords() {
      try {
        const item = localStorage.getItem(KEYS.KEYWORDS);
        if (item === null) return DEFAULT_KEYWORDS;
        const parsed = JSON.parse(item);
        return Array.isArray(parsed) ? parsed : DEFAULT_KEYWORDS;
      } catch (e) {
        return DEFAULT_KEYWORDS;
      }
    },

    saveKeywords(keywords) {
      safeSetJSON(KEYS.KEYWORDS, keywords);
    },

    addKeyword(kw) {
      const current = this.getKeywords();
      if (!current.includes(kw)) {
        current.push(kw);
        this.saveKeywords(current);
      }
      return current;
    },

    removeKeyword(kw) {
      const current = this.getKeywords().filter(k => k !== kw);
      this.saveKeywords(current);
      return current;
    },

    getScraps() {
      return safeGetJSON(KEYS.SCRAPS, []);
    },

    saveScraps(scraps) {
      safeSetJSON(KEYS.SCRAPS, scraps);
    },

    toggleScrap(itemOrTitle) {
      const title = typeof itemOrTitle === 'string' ? itemOrTitle : itemOrTitle.title;
      if (!title) return { isScrapped: false, scraps: this.getScraps() };

      const scraps = this.getScraps();
      const existingIdx = scraps.findIndex(s => s.title === title);

      let isScrapped = false;
      if (existingIdx >= 0) {
        scraps.splice(existingIdx, 1);
        isScrapped = false;
      } else {
        const newItem = typeof itemOrTitle === 'object' ? itemOrTitle : { title };
        scraps.push(newItem);
        isScrapped = true;
      }

      this.saveScraps(scraps);
      return { isScrapped, scraps };
    },

    isScrapped(title) {
      if (!title) return false;
      return this.getScraps().some(s => s.title === title);
    },

    getNotifySettings() {
      return safeGetJSON(KEYS.NOTIFY, DEFAULT_NOTIFY);
    },

    saveNotifySettings(settings) {
      safeSetJSON(KEYS.NOTIFY, settings);
    },

    getFactChatKey() {
      try {
        const stored = localStorage.getItem(KEYS.FACTCHAT_KEY);
        return (stored || DEFAULT_FACTCHAT_KEY).trim();
      } catch (e) {
        return DEFAULT_FACTCHAT_KEY;
      }
    },

    saveFactChatKey(key) {
      try {
        if (key && key.trim()) {
          localStorage.setItem(KEYS.FACTCHAT_KEY, key.trim());
        } else {
          localStorage.removeItem(KEYS.FACTCHAT_KEY);
        }
      } catch (e) {
        console.warn('StorageManager error saving FactChat Key:', e);
      }
    }
  };
})();
