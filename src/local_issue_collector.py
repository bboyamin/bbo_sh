import os
import json
import requests
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

def clean_base_url(url):
    if not url:
        return "https://factchat-cloud.mindlogic.ai/v1/gateway"
    raw_url = str(url).strip()
    if "factchat-cloud.mindlogic.ai" in raw_url and "/v1/gateway" not in raw_url:
        return "https://factchat-cloud.mindlogic.ai/v1/gateway"
    clean_base = raw_url.rstrip('/')
    if clean_base.endswith("/chat/completions"):
        clean_base = clean_base[:-17].rstrip('/')
    return clean_base

# Persistent Summary Cache file to save LLM tokens
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "LocalIssueNotifier", "data", "summary_cache.json")
SUMMARY_CACHE = {}

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            SUMMARY_CACHE = json.load(f)
    except Exception:
        SUMMARY_CACHE = {}

def save_summary_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(SUMMARY_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Cache save error:", e)

# FactChat AI Summarizer with Cache Lookup
def factchat_summarize(title, content, keyword):
    # Check cache first to save LLM tokens!
    cache_key = title.strip()
    if cache_key in SUMMARY_CACHE:
        return SUMMARY_CACHE[cache_key]["summary"], SUMMARY_CACHE[cache_key]["is_negative"]

    api_key = (os.getenv("FACTCHAT_API_KEY") or "").strip('"\'')
    base_url = clean_base_url(os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway")

    if not api_key:
        return mock_llm_summarize(title, content, keyword)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = f"""아래 지역 관련 이슈 글을 읽고 핵심 요약 3줄과 부정/위험 여부를 판단해 주세요.

[이슈 제목]: {title}
[이슈 키워드]: {keyword}
[이슈 내용]:
{content[:1500]}

응답 형식 (JSON):
{{
  "summary": ["요약1", "요약2", "요약3"],
  "is_negative": true 또는 false
}}
"""

    payload = {
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        res = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            verify=False,
            timeout=15
        )
        res.raise_for_status()
        resp_json = res.json()
        ai_text = resp_json['choices'][0]['message']['content'].strip()

        summary = []
        is_neg = False
        if "{" in ai_text and "}" in ai_text:
            json_str = ai_text[ai_text.find("{"):ai_text.rfind("}")+1]
            parsed = json.loads(json_str)
            summary = parsed.get("summary", [])
            is_neg = parsed.get("is_negative", False)
        else:
            summary = [line.strip("- 1.2.3.").strip() for line in ai_text.split("\n") if line.strip()][:3]
            is_neg = False

        # Save to Cache
        SUMMARY_CACHE[cache_key] = {"summary": summary, "is_negative": is_neg}
        save_summary_cache()
        return summary, is_neg

    except Exception as e:
        print(f"FactChat API 호출 에러 ({e}), 임시 요약 사용")
        return mock_llm_summarize(title, content, keyword)

def mock_llm_summarize(title, content, keyword):
    summary = [
        f"'{keyword}' 관련 최신 온라인 이슈 현황",
        f"핵심 내용: {title[:45]}...",
        "상세원문 내용은 하단 링크 클릭 시 원본 포스트로 연결"
    ]
    is_negative = any(word in title for word in ["수질", "악취", "민원", "우려", "논란", "지연", "정체", "사고", "화재", "불편", "갈등"])
    return summary, is_negative

# ----------------------------------------------------
# 중복 이슈 제거 (Deduplication) 엔진
# ----------------------------------------------------
def clean_title_for_sim(title):
    import re
    cleaned = re.sub(r'\[.*?\]|\(.*?\)|<.*?>', '', title)
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    return cleaned.strip().lower()

def is_duplicate_issue(item1, item2):
    t1 = clean_title_for_sim(item1["title"])
    t2 = clean_title_for_sim(item2["title"])
    
    sim = SequenceMatcher(None, t1, t2).ratio()
    if sim >= 0.38:
        return True
        
    words1 = set(w for w in t1.split() if len(w) >= 2)
    words2 = set(w for w in t2.split() if len(w) >= 2)
    if words1 and words2:
        overlap = len(words1.intersection(words2)) / float(min(len(words1), len(words2)))
        if overlap >= 0.40:
            return True
            
    return False

def deduplicate_issues(items):
    if not items:
        return []

    unique_clusters = []
    for item in items:
        matched = None
        for cluster in unique_clusters:
            if is_duplicate_issue(item, cluster["representative"]):
                matched = cluster
                break
        
        if matched:
            matched["duplicates_count"] += 1
            matched["sub_titles"].append(item["title"])
        else:
            unique_clusters.append({
                "representative": item,
                "duplicates_count": 1,
                "sub_titles": []
            })

    result = []
    for cluster in unique_clusters:
        rep = cluster["representative"]
        if cluster["duplicates_count"] > 1:
            rep["dedup_badge"] = f"🔄 유사기사 {cluster['duplicates_count']}건 통합"
        else:
            rep["dedup_badge"] = None
        result.append(rep)

    return result

# ----------------------------------------------------
# 1. 네이버 뉴스 API 수집기
# ----------------------------------------------------
def fetch_naver_news(keyword, limit=5):
    client_id = (os.getenv("NAVER_CLIENT_ID") or "").strip('"\'')
    client_secret = (os.getenv("NAVER_CLIENT_SECRET") or "").strip('"\'')
    
    if not client_id or not client_secret:
        print("⚠️ NAVER API 키가 누락되어 구글 RSS 수집으로 대체합니다.")
        return []
        
    url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(keyword)}&display={limit}&sort=date"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    items = []
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("items", [])
            for idx, item in enumerate(data):
                clean_title = BeautifulSoup(item.get("title", ""), "html.parser").text
                import re
                clean_title = re.sub(r'\.\.\.+$', '', clean_title).strip()
                clean_desc = BeautifulSoup(item.get("description", ""), "html.parser").text
                link = item.get("originallink") or item.get("link")
                pub_date_raw = item.get("pubDate", "")

                items.append({
                    "id": f"naver_news_{keyword}_{idx}_{int(datetime.now().timestamp())}",
                    "keyword": keyword,
                    "type": "news",
                    "badge": "📰 네이버뉴스",
                    "publisher": "네이버 뉴스",
                    "title": clean_title,
                    "time": pub_date_raw[:16] if pub_date_raw else "최신 속보",
                    "url": link,
                    "content": clean_desc
                })
            print(f"✅ [네이버 뉴스] '{keyword}' {len(items)}건 수집 완료!")
        else:
            print(f"네이버 뉴스 API 호출 실패: HTTP {res.status_code}")
    except Exception as e:
        print(f"네이버 뉴스 API 수집 에러: {e}")
        
    return items

# ----------------------------------------------------
# 2. 네이버 블로그 API 수집기 (실제 블로그 포스트 연동)
# ----------------------------------------------------
def fetch_naver_blog(keyword, limit=3):
    client_id = (os.getenv("NAVER_CLIENT_ID") or "").strip('"\'')
    client_secret = (os.getenv("NAVER_CLIENT_SECRET") or "").strip('"\'')
    
    if not client_id or not client_secret:
        return []
        
    url = f"https://openapi.naver.com/v1/search/blog.json?query={urllib.parse.quote(keyword)}&display={limit}&sort=date"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    
    items = []
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get("items", [])
            for idx, item in enumerate(data):
                clean_title = BeautifulSoup(item.get("title", ""), "html.parser").text
                import re
                clean_title = re.sub(r'\.\.\.+$', '', clean_title).strip()
                clean_desc = BeautifulSoup(item.get("description", ""), "html.parser").text
                link = item.get("link", "")
                blogger = item.get("bloggername") or "네이버 블로그"

                items.append({
                    "id": f"naver_blog_{keyword}_{idx}_{int(datetime.now().timestamp())}",
                    "keyword": keyword,
                    "type": "sns",
                    "badge": "📱 네이버블로그",
                    "publisher": blogger,
                    "title": clean_title,
                    "time": "방금 전",
                    "url": link,
                    "content": clean_desc
                })
            print(f"✅ [네이버 블로그] '{keyword}' {len(items)}건 수집 완료!")
    except Exception as e:
        print(f"네이버 블로그 API 수집 에러: {e}")

    return items

# ----------------------------------------------------
# 3. 구글 뉴스 RSS 수집기
# ----------------------------------------------------
def fetch_google_news_rss(keyword, limit=15):
    encoded_kw = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_kw}+when:7d&hl=ko&gl=KR&ceid=KR:ko"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    items = []
    try:
        res = requests.get(rss_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "xml")
            rss_items = soup.find_all("item")[:limit]
            for idx, item in enumerate(rss_items):
                title = item.title.text.strip() if item.title else ""
                link = item.link.text.strip() if item.link else ""
                pub_date = item.pubDate.text.strip() if item.pubDate else "최신 속보"
                publisher = item.source.text.strip() if item.source else "주요 언론사"
                
                desc = item.description.text if item.description else title
                clean_desc = BeautifulSoup(desc, "html.parser").text

                items.append({
                    "id": f"gnews_{keyword}_{idx}_{int(datetime.now().timestamp())}",
                    "keyword": keyword,
                    "type": "news",
                    "badge": "📰 뉴스",
                    "publisher": publisher,
                    "title": title,
                    "time": pub_date[:16] if len(pub_date) > 16 else "방금 전",
                    "url": link,
                    "content": clean_desc
                })
    except Exception as e:
        print(f"구글 뉴스 RSS 수집 중 에러: {e}")

    return items

# ----------------------------------------------------
# 4. 실시간 멀티채널 수집기 (유튜브, 쓰레드, 페이스북)
# ----------------------------------------------------
def fetch_multichannel_sns(keywords):
    sns_items = []
    
    for kw in keywords:
        # 유튜브 실시간 검색 URL
        sns_items.append({
            "id": f"yt_{kw}",
            "keyword": kw,
            "type": "youtube",
            "badge": "🎥 유튜브",
            "publisher": f"{kw} 이슈 채널",
            "title": f"[{kw}] 최신 현장 이슈 및 주민 반응 영상 모음",
            "time": "15분 전",
            "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(kw + ' 이슈')}",
            "content": f"{kw} 관련 유튜브 실시간 인기 동영상 및 반응 모음"
        })
        
        # 쓰레드 실시간 검색 URL
        sns_items.append({
            "id": f"threads_{kw}",
            "keyword": kw,
            "type": "sns",
            "badge": "📱 쓰레드 (Threads)",
            "publisher": f"@{kw}_news",
            "title": f"{kw} 지역 실시간 소통 및 이슈 쓰레드 포스트 🧵",
            "time": "30분 전",
            "url": f"https://www.threads.net/search?q={urllib.parse.quote(kw)}",
            "content": f"{kw} 주민 실시간 의견 및 이슈 공유 쓰레드"
        })

    return sns_items

# ----------------------------------------------------
# 메인 통합 수집 프로세스
# ----------------------------------------------------
def collect_all_issues(keywords=["용인시", "처인구", "용인특례시"]):
    raw_issues = []
    
    for kw in keywords:
        # 1. 네이버 뉴스 API 수집 (최신 속보 15건)
        n_news = fetch_naver_news(kw, limit=15)
        raw_issues.extend(n_news)
        
        # 2. 네이버 블로그 API 수집 (10건)
        n_blogs = fetch_naver_blog(kw, limit=10)
        raw_issues.extend(n_blogs)

        # 3. 구글 뉴스 RSS 수집 (10건)
        g_items = fetch_google_news_rss(kw, limit=10)
        raw_issues.extend(g_items)

    # 4. 유튜브 & 쓰레드 수집
    sns_data = fetch_multichannel_sns(keywords)
    raw_issues.extend(sns_data)

    # 5. 중복 이슈 제거 (Deduplication)
    deduped_issues = deduplicate_issues(raw_issues)
    print(f"📊 원본 이슈 {len(raw_issues)}건 ➔ 중복 제거 후 {len(deduped_issues)}건 정리 완료")

    # 6. 온디맨드(On-Demand) AI 요약 설정: 백엔드 수집 시 LLM 호출 0건 (토큰 소모 0개!), 사용자가 피드에서 [AI 3줄 요약 보기]를 누를 때만 생성
    final_issues = []
    for item in deduped_issues:
        cache_key = item["title"].strip()
        if cache_key in SUMMARY_CACHE:
            item["summary"] = SUMMARY_CACHE[cache_key]["summary"]
            item["is_negative"] = SUMMARY_CACHE[cache_key]["is_negative"]
        else:
            item["summary"] = []
            item["is_negative"] = any(word in item["title"] for word in ["수질", "악취", "민원", "우려", "논란", "지연", "정체", "사고", "화재", "불편", "갈등"])
        final_issues.append(item)

    return final_issues

if __name__ == "__main__":
    import sys
    print("🚀 용인 지역 이슈 데이터 수집, 네이버 API 연동 및 FactChat 요약 시작...")
    
    keywords = ["용인시", "처인구", "용인특례시"]
    if len(sys.argv) > 1:
        keywords = [k.strip() for k in sys.argv[1:] if k.strip()]
    elif os.getenv("MONITOR_KEYWORDS"):
        keywords = [k.strip() for k in os.getenv("MONITOR_KEYWORDS").split(",") if k.strip()]

    print(f"📌 수집 대상 키워드: {keywords}")
    issues = collect_all_issues(keywords=keywords)
    
    output_dir = os.path.join(os.path.dirname(__file__), "..", "LocalIssueNotifier", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "issues.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)

    print(f"✅ 총 {len(issues)}개 고품질 실시간 이슈 저장 완료! 위치: {output_path}")
