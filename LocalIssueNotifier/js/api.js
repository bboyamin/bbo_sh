/**
 * IssueApi Deep Module
 * Interface for backend endpoint collection and FactChat Gateway AI OnDemandSummary.
 */
const IssueApi = (() => {
  const FACTCHAT_ENDPOINT = 'https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions';

  return {
    /**
     * Collect issues dynamically for the provided keywords
     * @param {string[]} keywordsList 
     * @returns {Promise<Array>}
     */
    async fetchKeywordIssues(keywordsList) {
      try {
        const kwParam = encodeURIComponent(keywordsList.join(','));
        const res = await fetch(`/api/collect?keywords=${kwParam}&v=` + Date.now());
        if (res.ok) {
          const liveData = await res.json();
          if (Array.isArray(liveData) && liveData.length >= 10) {
            return liveData;
          }
        }
      } catch (err) {
        console.warn('Live API collect error, loading default dataset:', err);
      }
      return await this.loadDefaultIssues();
    },

    /**
     * Load initial issues from static json file
     * @returns {Promise<Array>}
     */
    async loadDefaultIssues() {
      try {
        const res = await fetch('./data/issues.json?v=' + Date.now(), { cache: 'no-store' });
        if (res.ok) {
          return await res.json();
        }
        throw new Error(`Data load returned HTTP ${res.status}`);
      } catch (err) {
        console.error('IssueApi.loadDefaultIssues error:', err);
        return [];
      }
    },

    /**
     * Generate On-Demand 3-line AI summary via FactChat Gateway
     * @param {Object} params { title, keyword, content, apiKey }
     * @returns {Promise<{ summary: string[], is_negative: boolean }>}
     */
    async generateSummary({ title, keyword = '용인시', content = '', apiKey }) {
      if (!apiKey) {
        throw new Error('FactChat API Key is missing');
      }

      const prompt = `아래 이슈 기사를 읽고 핵심 요약 3줄(번호 1,2,3 형태)과 부정/위험 여부를 판단해 JSON으로 응답해 주세요.
[제목]: ${title}
[키워드]: ${keyword}
[내용]: ${(content || title).slice(0, 1500)}
JSON 응답 형식: {"summary": ["요약1", "요약2", "요약3"], "is_negative": true 또는 false}`;

      const res = await fetch(FACTCHAT_ENDPOINT, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'gpt-5.5',
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.3
        })
      });

      if (!res.ok) {
        throw new Error(`FactChat API returned HTTP ${res.status}`);
      }

      const data = await res.json();
      const aiText = data.choices[0].message.content.trim();
      let summary = [];
      let is_negative = false;

      if (aiText.includes('{') && aiText.includes('}')) {
        const jsonStr = aiText.substring(aiText.indexOf('{'), aiText.lastIndexOf('}') + 1);
        const parsed = JSON.parse(jsonStr);
        summary = parsed.summary || [];
        is_negative = parsed.is_negative || false;
      } else {
        summary = aiText.split('\n').map(l => l.replace(/^[-\s\d.]*/, '').trim()).filter(l => l).slice(0, 3);
      }

      return { summary, is_negative };
    }
  };
})();
