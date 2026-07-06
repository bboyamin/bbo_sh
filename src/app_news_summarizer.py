import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import streamlit as st
from datetime import datetime

# .env 파일로부터 환경 변수 로드
load_dotenv()

# Streamlit 페이지 테마 및 프리미엄 라이트 레이아웃 설정
st.set_page_config(
    page_title="전자신문 지면 브리핑",
    page_icon="📰",
    layout="centered", # 1열 가운데 정렬로 모바일과 웹 모두 가독성 극대화
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 0. 토스/애플 서비스 스타일의 극단적 미니멀리즘(Premium Light) CSS 적용
# -------------------------------------------------------------
st.markdown("""
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
<style>
    /* 전체 배경: 세련된 순백색과 미세한 소프트 그레이 톤 */
    html, body, [class*="css"], .stApp {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    
    /* 심플하고 단정한 메인 타이틀 */
    .main-title {
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        letter-spacing: -0.5px !important;
        margin-top: 20px;
        margin-bottom: 8px;
        text-align: left;
    }
    
    .main-subtitle {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 32px;
        line-height: 1.5;
        text-align: left;
    }
    
    /* 지면 구분선 및 단정한 텍스트 */
    .section-header {
        font-size: 15px;
        font-weight: 800;
        color: #64748b;
        margin-top: 40px;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 6px;
    }
    
    /* 은은한 캡슐 배지 (토스 스타일) */
    .article-meta {
        font-size: 10px;
        font-weight: 700;
        color: #64748b;
        background-color: #f1f5f9;
        padding: 3px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 10px;
    }
    
    /* 요약 박스: 튀지 않는 미색 그레이 박스 디자인 */
    .summary-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        font-size: 14.5px;
        line-height: 1.6;
        color: #334155;
        margin-top: 8px;
        margin-bottom: 12px;
    }
    
    /* 탭 헤더: 얇은 회색 라인 및 세련된 미니멀 탭 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 1px solid #f1f5f9;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        color: #94a3b8;
        font-weight: 700;
        font-size: 14px;
        padding: 8px 4px;
        transition: all 0.15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #0f172a;
    }
    .stTabs [aria-selected="true"] {
        color: #0f172a !important;
        border-bottom: 2px solid #0f172a !important;
    }
    
    /* Streamlit 기본 버튼을 보더리스(Borderless) 기사 행 스타일로 개조 */
    div.stButton > button {
        background: transparent !important;
        color: #334155 !important;
        border: none !important;
        border-bottom: 1px solid #f1f5f9 !important;
        border-radius: 0px !important;
        padding: 14px 4px !important;
        text-align: left !important;
        width: 100% !important;
        box-shadow: none !important;
        transition: all 0.15s ease !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        margin-bottom: 0px;
    }
    div.stButton > button:hover {
        color: #000000 !important;
        background: #f8fafc !important;
        padding-left: 8px !important;
    }
    
    /* 보조 링크 버튼 (세련된 아웃라인 스타일) */
    .stLinkButton > a {
        background: #ffffff !important;
        color: #475569 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        transition: all 0.15s !important;
    }
    .stLinkButton > a:hover {
        color: #0f172a !important;
        border-color: #0f172a !important;
        background: #f8fafc !important;
    }
    
    /* 사이드바 심플 튜닝 */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc !important;
        border-right: 1px solid #e2e8f0;
    }
    
    /* 메인 폼 패딩 조율 */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# FactChat API 설정
FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

# -------------------------------------------------------------
# 1. 크롤링 및 요약 비즈니스 로직
# -------------------------------------------------------------

@st.cache_data(ttl=3600)  # 지면 목록은 1시간 캐싱
def get_news_list_by_date(ymd_str):
    url = f"https://pdf.etnews.com/pdf_today.html?ymd={ymd_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
            
        soup = BeautifulSoup(res.text, "html.parser")
        pdf_list = soup.find("ul", class_="pdf_list")
        if not pdf_list:
            return None
            
        boxes = pdf_list.find_all("div", class_="box")
        categorized_news = {}
        
        for box in boxes:
            section_title_el = box.find("dt")
            if not section_title_el:
                continue
            section_title = section_title_el.text.strip()
            
            links = box.find_all("a", target="_blank")
            articles = []
            for link in links:
                title = link.text.strip()
                href = link.get("href", "")
                if href.startswith("//"):
                    href = "https:" + href
                
                if title and href:
                    articles.append({"title": title, "url": href})
                    
            if articles:
                categorized_news[section_title] = articles
                
        return categorized_news
    except Exception as e:
        st.error(f"데이터 로드 중 에러: {e}")
        return None

def get_article_body(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code != 200:
            return None
            
        soup = BeautifulSoup(res.text, "html.parser")
        content_div = soup.find("article") or soup.find("div", class_="article_txt") or soup.find("div", class_="article_body")
        
        if content_div:
            for s in content_div(["script", "style", "iframe", "ins"]):
                s.extract()
            return content_div.text.strip()
        else:
            return soup.text[:2000].strip()
    except Exception:
        return None

def ai_summarize(title, content):
    if not FACTCHAT_API_KEY:
        return "⚠️ .env 파일에 FACTCHAT_API_KEY가 없습니다."
        
    headers = {
        "Authorization": f"Bearer {FACTCHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""아래 뉴스 기사를 읽고 핵심 요약 리스트 3줄(1, 2, 3 번호 형태)을 한국어로 작성해 주세요. 
사족이나 안내문구는 전부 빼고 오직 요약 리스트만 응답해 주세요.

[기사 제목]: {title}
[기사 본문]:
{content[:2500]}
"""

    payload = {
        "model": "gpt-5.4",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.post(
            f"{FACTCHAT_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            verify=False,
            timeout=25
        )
        response.raise_for_status()
        response_json = response.json()
        return response_json['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"❌ 요약 실패 ({e})"

# -------------------------------------------------------------
# 2. UI 구성 (토스 피드처럼 깔끔한 1클릭 전개형 구조)
# -------------------------------------------------------------

# 세션 상태 초기화 (요약 내역 보존)
if "summaries" not in st.session_state:
    st.session_state.summaries = {}
if "selected_article" not in st.session_state:
    st.session_state.selected_article = None

# 사이드바 레이아웃 (미니멀 날짜 조절)
st.sidebar.markdown("### 📅 지면 날짜 선택")
selected_date = st.sidebar.date_input(
    "조회 날짜",
    value=datetime.today(),
    max_value=datetime.today(),
    label_visibility="collapsed"
)
ymd_str = selected_date.strftime("%Y%m%d")

# 메인 타이틀 영역
st.markdown('<div class="main-title">📰 전자신문 지면 브리핑</div>', unsafe_allow_html=True)
st.markdown(f'<div class="main-subtitle">{selected_date.strftime("%Y년 %m월 %d일")} 자 전자신문 지면 기사입니다. 기사명을 누르면 AI 요약본이 아래로 즉시 확장됩니다.</div>', unsafe_allow_html=True)

# 실시간 기사 수집 실행
with st.spinner("뉴스 목록을 가져오는 중..."):
    categorized_data = get_news_list_by_date(ymd_str)

if not categorized_data:
    st.warning(f"📅 {selected_date.strftime('%Y-%m-%d')} 날짜의 지면 정보가 없습니다. (신문 휴간일 또는 네트워크 지연)")
else:
    # 탭 메뉴 제공
    tab_list, tab_summary = st.tabs(["📝 오늘자 지면 목록", "💡 모아둔 요약 리포트"])
    
    # [탭 1] 지면별 기사 목록 (토스 아티클 피드 스타일)
    with tab_list:
        sections = list(categorized_data.keys())
        selected_section = st.selectbox(
            "📖 지면 필터링",
            ["전체 지면 보기"] + sections,
            label_visibility="collapsed"
        )
        
        st.write("")
        
        for section, articles in categorized_data.items():
            if selected_section != "전체 지면 보기" and selected_section != section:
                continue
                
            # 심플하고 단정한 지면 헤더 선
            st.markdown(f'<div class="section-header">{section}</div>', unsafe_allow_html=True)
            
            for idx, art in enumerate(articles):
                btn_key = f"feed_{ymd_str}_{section.replace(' ', '_')}_{idx}"
                is_active = (st.session_state.selected_article == btn_key)
                
                # 활성화되었을 때, 텍스트가 굵어지는 동적 스타일 추가
                if is_active:
                    st.markdown(f"""
                    <style>
                        div.stButton > button[key*="{btn_key}"] {{
                            font-weight: 700 !important;
                            color: #0f172a !important;
                            background-color: #f8fafc !important;
                            border-left: 3px solid #0f172a !important;
                            padding-left: 8px !important;
                        }}
                    </style>
                    """, unsafe_allow_html=True)
                
                # 1클릭 보더리스 텍스트 행 버튼
                if st.button(f"📄  {art['title']}", key=btn_key):
                    if is_active:
                        st.session_state.selected_article = None
                    else:
                        st.session_state.selected_article = btn_key
                    st.rerun()
                
                # 활성화되었을 때 내용 노출 (차분한 미색 컨테이너 블록)
                if st.session_state.selected_article == btn_key:
                    st.markdown('<div style="padding: 12px 8px 16px 12px;">', unsafe_allow_html=True)
                    st.markdown(f'<span class="article-meta">📌 {section}</span>', unsafe_allow_html=True)
                    
                    # 이미 요약된 결과 출력
                    if art["title"] in st.session_state.summaries:
                        summary_data = st.session_state.summaries[art["title"]]["summary"]
                        st.markdown(f'<div class="summary-box">{summary_data}</div>', unsafe_allow_html=True)
                        
                        col_action1, col_action2 = st.columns([1, 1])
                        with col_action1:
                            st.link_button("🌐 신문 기사 원문 보기", art["url"], use_container_width=True)
                        with col_action2:
                            st.download_button(
                                label="💾 이 요약본 파일 저장",
                                data=summary_data,
                                file_name=f"요약_{art['title'][:10]}.txt",
                                mime="text/plain",
                                key=f"dl_{btn_key}",
                                use_container_width=True
                            )
                    # 요약 내역이 없을 때 최초 1회 실시간 요약 (Lazy Loading)
                    else:
                        with st.spinner("요약 작성 중..."):
                            content = get_article_body(art["url"])
                            if content:
                                result = ai_summarize(art["title"], content)
                                st.session_state.summaries[art["title"]] = {
                                    "url": art["url"],
                                    "section": section,
                                    "summary": result
                                }
                                st.rerun()
                            else:
                                st.error("기사 본문을 불러오지 못했습니다.")
                                
                    st.markdown('</div>', unsafe_allow_html=True)
            
    # [탭 2] 요약 리포트 모음 탭 (심플 라이트 테마)
    with tab_summary:
        st.subheader("📝 실시간 AI 뉴스 브리핑 리포트")
        st.markdown("지면 목록에서 읽어본 기사들의 요약본이 실시간 종합 보고서 형태로 취합되는 대시보드입니다.")
        
        if not st.session_state.summaries:
            st.info("지면 목록 탭에서 관심 있는 기사 제목을 클릭해 보세요! 요약 결과가 자동으로 이 리포트에 취합됩니다.")
        else:
            report_md = f"# 📝 {selected_date.strftime('%Y-%m-%d')} AI 뉴스 요약 리포트\n\n"
            
            for title, info in st.session_state.summaries.items():
                st.markdown(f"#### 📌 [{title}]({info['url']})")
                st.markdown(f'<span class="article-meta">지면: {info["section"]}</span>', unsafe_allow_html=True)
                st.markdown(f'<div class="summary-box">{info["summary"]}</div>', unsafe_allow_html=True)
                st.write("")
                report_md += f"## [{title}]({info['url']}) ({info['section']})\n\n{info['summary']}\n\n---\n\n"
                
            st.write("---")
            
            col_action1, col_action2 = st.columns([2, 1])
            with col_action1:
                st.download_button(
                    label="📥 오늘자 요약 리포트 전체 다운로드 (.md)",
                    data=report_md,
                    file_name=f"AI_요약리포트_{ymd_str}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col_action2:
                if st.button("🗑️ 요약 리포트 내역 비우기", use_container_width=True):
                    st.session_state.summaries = {}
                    st.session_state.selected_article = None
                    st.rerun()
