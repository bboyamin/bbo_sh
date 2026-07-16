import os
import re
import xml.etree.ElementTree as ET
import requests
import urllib3
import streamlit as st
from dotenv import load_dotenv

# ==========================================
# 0. 환경 세팅 및 SSL 안정화
# ==========================================
st.set_page_config(page_title="행정 자문관 - 법제처 Direct Open API RAG", page_icon="🏛️", layout="wide")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

LAW_OC = os.getenv("LAW_OC") or "a11223344556677"
FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

# CSS 스틸-그레이 & 오피스 그린 관공서 특화 프리미엄 테마 주입
st.markdown("""
<style>
    /* 스트림릿 기본 상단 헤더 흰색 바 제거 */
    [data-testid="stHeader"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        height: 0px !important;
        min-height: 0px !important;
        display: none !important;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    .stApp {
        background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
        font-family: 'Noto Sans KR', sans-serif;
    }
    .brand-title {
        background: linear-gradient(90deg, #1e3a8a 0%, #0d9488 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        margin-bottom: 1.0rem;
    }
    .system-status {
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 1rem;
    }
    .status-ok {
        background-color: #d1fae5;
        color: #065f46;
        border: 1px solid #10b981;
    }
    .status-err {
        background-color: #fee2e2;
        color: #991b1b;
        border: 1px solid #ef4444;
    }
    
    /* 사이드바 개별 삭제 ❌ 버튼 미니멀 플랫 스타일링 */
    div[data-testid="stSidebar"] div[data-testid="stColumn"] button {
        border: none !important;
        background-color: transparent !important;
        color: #ef4444 !important;
        padding: 0 !important;
        margin-top: 4px !important;
        line-height: 1 !important;
        font-size: 14px !important;
        box-shadow: none !important;
        transition: transform 0.2s ease, color 0.2s ease !important;
        min-height: auto !important;
        height: auto !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stColumn"] button:hover {
        color: #b91c1c !important;
        background-color: transparent !important;
        transform: scale(1.2);
    }
    div[data-testid="stSidebar"] div[data-testid="stColumn"] button:active {
        background-color: transparent !important;
    }
    
    /* [프리미엄 챗봇 가독성 스킨 시스템] */
    /* 1. 사용자 질문 전체 카드 디자인 */
    div[data-testid="stChatMessage"]:has(.user-trigger) {
        background-color: #eff6ff !important; /* 부드러운 스카이블루 배경 */
        border-left: 5px solid #3b82f6 !important; /* 블루 칼라 바 */
        border-radius: 12px !important;
        padding: 16px !important;
        margin-top: 12px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    
    /* 2. AI 자문 의견서 전체 카드 디자인 */
    div[data-testid="stChatMessage"]:has(.assistant-trigger) {
        background-color: #ffffff !important; /* 순백색 기안 보고서 배경 */
        border-left: 5px solid #0d9488 !important; /* 오피스 그린 세로선 바 */
        border: 1px solid #e5e7eb !important;
        border-top-left-radius: 4px !important;
        border-bottom-left-radius: 4px !important;
        border-top-right-radius: 12px !important;
        border-bottom-right-radius: 12px !important;
        padding: 20px !important;
        margin-top: 12px !important;
        margin-bottom: 25px !important; /* 다음 질문과의 충분한 마진 확보 */
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
    }
    
    /* 대화 턴 변경 구분용 그라데이션 선 효과 */
    div[data-testid="stChatMessage"]:has(.assistant-trigger)::after {
        content: "" !important;
        display: block !important;
        width: 100% !important;
        height: 1px !important;
        background: radial-gradient(circle, #d1d5db 0%, rgba(209, 213, 219, 0) 100%) !important;
        margin-top: 25px !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 법제처 HTTP Open API 연계 모듈 (Direct REST Client)
# ==========================================
@st.cache_data(show_spinner=False)
def clean_html_tags(text: str) -> str:
    if not text:
        return ""
    # 모든 HTML 태그(<...>)를 제거하고 공백을 정돈합니다.
    return re.sub(r'<[^>]*>', '', text).strip()

def search_law_api(query: str, search_target: str, page: int = 1) -> list:
    """
    search_target: 'elaw' (국가법령), 'ordin' (자치법규), 'admrul' (행정규칙), 'prec' (판례)
    """
    url = "http://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": LAW_OC,
        "target": search_target,
        "query": query,
        "pageNo": page,
        "numOfRows": 20,
        "type": "XML"
    }
    
    try:
        res = requests.get(url, params=params, verify=False, timeout=8)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        
        results = []
        # 각 카테고리별 XML 노드 탐색 방식 다변화
        if search_target == "elaw":
            for item in root.findall(".//law"):
                results.append({
                    "title": clean_html_tags(item.findtext("법령명한글", "이름 없음")),
                    "mst": item.findtext("법령일련번호", ""),
                    "detail": f"{clean_html_tags(item.findtext('법령구분명', ''))} | 공포일: {item.findtext('공포일자', '')}",
                    "type": "law"
                })
        elif search_target == "ordin":
            for item in root.findall(".//law"):
                results.append({
                    "title": clean_html_tags(item.findtext("자치법규명", "이름 없음")),
                    "mst": item.findtext("자치법규일련번호", ""),
                    "detail": f"{clean_html_tags(item.findtext('지자체기관명', '지자체 미상'))} | 공포일: {item.findtext('공포일자', '')}",
                    "type": "ordinance"
                })
        elif search_target == "admrul":
            for item in root.findall(".//admrul"):
                results.append({
                    "title": clean_html_tags(item.findtext("행정규칙명", "이름 없음")),
                    "mst": item.findtext("행정규칙일련번호", ""),
                    "detail": f"{clean_html_tags(item.findtext('행정규칙종류', ''))} | 발령일자: {item.findtext('발령일자', '')}",
                    "type": "admrul"
                })
        elif search_target == "prec":
            for item in root.findall(".//prec"):
                raw_case_no = clean_html_tags(item.findtext("사건번호", "번호 미상"))
                raw_case_name = clean_html_tags(item.findtext("사건명", "사건명 없음"))
                results.append({
                    "title": f"[{raw_case_no}] {raw_case_name}",
                    "mst": item.findtext("판례일련번호", ""),
                    "detail": f"{clean_html_tags(item.findtext('법원명', ''))} | 선고일자: {item.findtext('선고일자', '')}",
                    "type": "prec"
                })
        return [r for r in results if r["mst"]]
    except Exception as e:
        st.sidebar.error(f"⚠️ API 통신 실패: {e}")
        return []

@st.cache_data(show_spinner=False)
def fetch_body_api(mst: str, doc_type: str) -> str:
    """
    특정 MST/ID 코드를 기반으로 법제처에서 본문 XML을 수집 및 핵심 조항 파싱 정제
    doc_type: 'law', 'ordinance', 'admrul', 'prec'
    """
    url = "http://www.law.go.kr/DRF/lawService.do"
    
    # 4대 카테고리별 올바른 파라미터 매핑 (교차 검증 성공 규격)
    params_map = {
        "law": {"target": "law", "key": "MST"},
        "ordinance": {"target": "ordin", "key": "MST"},
        "admrul": {"target": "admrul", "key": "ID"},
        "prec": {"target": "prec", "key": "ID"}
    }
    
    if doc_type not in params_map:
        return "[오류] 올바르지 않은 문서 타입"
        
    cfg = params_map[doc_type]
    params = {
        "OC": LAW_OC,
        "target": cfg["target"],
        cfg["key"]: mst,
        "type": "XML"
    }
    
    try:
        res = requests.get(url, params=params, verify=False, timeout=10)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        
        body_text = ""
        
        # 1. 국가법령 (law) 파싱
        if doc_type == "law":
            title = root.findtext(".//법령명한글") or "법령 제명 미상"
            body_text += f"=== {title} ===\n"
            for node in root.findall(".//조문단위"):
                jo_title = node.findtext("조문내용", "").strip()
                if jo_title:
                    body_text += f"{jo_title}\n"
                    # 하부 항(Paragraph) 수집
                    for hang in node.findall("항"):
                        hang_text = hang.findtext("항내용", "").strip()
                        if hang_text:
                            body_text += f"  {hang_text}\n"
                            # 항 하부 호(Sub-paragraph) 수집
                            for ho in hang.findall("호"):
                                ho_text = ho.findtext("호내용", "").strip()
                                if ho_text:
                                    body_text += f"    {ho_text}\n"
                                    # 호 하부 목 수집
                                    for mok in ho.findall("목"):
                                        mok_text = mok.findtext("목내용", "").strip()
                                        if mok_text:
                                            body_text += f"      {mok_text}\n"
                    # 조문 직속 호/목이 있는 케이스 보완
                    for ho in node.findall("호"):
                        ho_text = ho.findtext("호내용", "").strip()
                        if ho_text:
                            body_text += f"  {ho_text}\n"
                            
        # 1-2. 자치조례 (ordinance) 파싱
        elif doc_type == "ordinance":
            title = root.findtext(".//자치법규명") or "조례 제명 미상"
            body_text += f"=== {title} ===\n"
            # 조례의 실제 개별 조문 노드는 <조> 이며, <조제목>과 <조내용>을 담고 있음
            for node in root.findall(".//조"):
                jo_title = node.findtext("조제목", "").strip()
                jo_content = node.findtext("조내용", "").strip()
                if jo_title:
                    body_text += f"{jo_title}\n"
                if jo_content:
                    body_text += f"{jo_content}\n"
            
            # 부칙 내용 보완
            for node in root.findall(".//부칙내용"):
                txt = node.text.strip() if node.text else ""
                if txt:
                    body_text += f"\n[부칙]\n{txt}\n"
                            
        # 2. 행정규칙 (admrul) 파싱
        elif doc_type == "admrul":
            title = root.findtext(".//행정규칙명") or "행정규칙 제명 미상"
            body_text += f"=== {title} ===\n"
            # 행정규칙은 조문단위 태그가 없고, 직접 조문내용 목록이 제공됨
            for node in root.findall(".//조문내용"):
                txt = node.text.strip() if node.text else ""
                if txt:
                    body_text += f"{txt}\n"
            
            # 부칙 내용 보완
            for node in root.findall(".//부칙내용"):
                txt = node.text.strip() if node.text else ""
                if txt:
                    body_text += f"\n[부칙]\n{txt}\n"
                    
        # 3. 판례 (prec) 파싱 (PrecService XML 파싱)
        elif doc_type == "prec":
            case_no = root.findtext(".//사건번호") or "사건번호 미상"
            case_name = root.findtext(".//사건명") or "사건명 없음"
            body_text += f"=== 판례: [{case_no}] {case_name} ===\n"
            
            p_사항 = root.findtext(".//판시사항")
            p_요지 = root.findtext(".//판결요지")
            p_조문 = root.findtext(".//참조조문")
            p_내용 = root.findtext(".//판례내용")
            
            if p_사항: body_text += f"[판시사항]\n{clean_html_tags(p_사항)}\n\n"
            if p_요지: body_text += f"[판결요지]\n{clean_html_tags(p_요지)}\n\n"
            if p_조문: body_text += f"[참조조문]\n{clean_html_tags(p_조문)}\n\n"
            if p_내용: body_text += f"[판결전문]\n{clean_html_tags(p_내용)[:4000]}\n" # 판례 전문 포함
            
        return body_text if body_text.strip() else "[본문 데이터 없음]"
    except Exception as e:
        return f"[오류] 본문 로드 실패: {e}"

# ==========================================
# 2. 시스템 인증 헬스 체크
# ==========================================
def check_system_health():
    # 1. 법제처 API 키 검사 (기본 공용키가 아닌지)
    law_status = LAW_OC and LAW_OC != "a123456789001"
    # 2. FactChat 연결 검사
    fc_status = bool(FACTCHAT_API_KEY)
    
    if law_status and fc_status:
        st.markdown('<div class="system-status status-ok">🟢 시스템 정상 (법제처 Direct API & FactChat 서버 연동 완료)</div>', unsafe_allow_html=True)
    else:
        warn_msg = "⚠️ 시스템 점검 필요:"
        if not law_status: warn_msg += " [법제처 API키 공용 또는 누락]"
        if not fc_status: warn_msg += " [FactChat API키 누락]"
        st.markdown(f'<div class="system-status status-err">{warn_msg}</div>', unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 검색 및 장착 엔진
# ==========================================
st.sidebar.markdown("### 🔍 법제처 데이터 실시간 검색")

# 검색 카테고리 선택
category = st.sidebar.radio(
    "검색 대상 설정",
    ["국가법령", "지방자치조례", "행정규칙(고시/예규)", "사법부 판례"],
    index=0
)

# 카테고리 맵핑
target_map = {
    "국가법령": "elaw",
    "지방자치조례": "ordin",
    "행정규칙(고시/예규)": "admrul",
    "사법부 판례": "prec"
}

search_keyword = st.sidebar.text_input("검색 키워드 입력", placeholder="예: 개인정보, 주차장")

# 세션 상태 관리 (장착한 문서 리스트 및 페이지 번호)
if "selected_docs" not in st.session_state:
    st.session_state.selected_docs = {}  # {mst: {"title": title, "type": type}}

if "search_page" not in st.session_state:
    st.session_state.search_page = 1
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "last_category" not in st.session_state:
    st.session_state.last_category = ""

# 검색어 또는 카테고리가 달라진 경우 검색 페이지 1로 리셋
current_query = search_keyword.strip()
if current_query != st.session_state.last_query or category != st.session_state.last_category:
    st.session_state.search_page = 1
    st.session_state.last_query = current_query
    st.session_state.last_category = category

if current_query:
    with st.sidebar.status("📡 법제처 Open API 검색 중...", expanded=True):
        search_target = target_map[category]
        search_results = search_law_api(current_query, search_target, page=st.session_state.search_page)
        
        if search_results:
            st.write(f"검색 결과 (총 {len(search_results)}건 / 페이지: {st.session_state.search_page}):")
            for item in search_results:
                mst = item["mst"]
                title = item["title"]
                detail = item["detail"]
                dtype = item["type"]
                
                # 체크박스 상태 바인딩
                is_selected = mst in st.session_state.selected_docs
                # [동적 위젯 키 재마운트 기법]
                # 위젯 키에 장착 여부 상태(True/False)를 동적으로 반영하여, 상태 변경 시 강제 재렌더링을 유도해 잔상을 완벽 차단합니다.
                cb_key = f"cb_widget_{mst}_{is_selected}"
                
                cb = st.checkbox(
                    f"{title}\n({detail})",
                    value=is_selected,
                    key=cb_key
                )
                
                # 체크박스 상태 변화에 따라 세션에 즉시 반영
                if cb and not is_selected:
                    st.session_state.selected_docs[mst] = {"title": title, "type": dtype}
                    st.rerun()
                elif not cb and is_selected:
                    st.session_state.selected_docs.pop(mst, None)
                    st.rerun()
                    
            # 페이징 제어 버튼 영역
            st.write("---")
            col1, col2 = st.columns(2)
            
            # 이전 페이지
            if st.session_state.search_page > 1:
                if col1.button("⬅️ 이전 20건", use_container_width=True):
                    st.session_state.search_page -= 1
                    st.rerun()
            else:
                col1.button("⬅️ 이전 20건", disabled=True, use_container_width=True)
                
            # 다음 페이지 (20건 가득 채워져서 왔으면 다음 페이지가 존재할 가능성이 높음)
            if len(search_results) >= 20:
                if col2.button("다음 20건 ➡️", use_container_width=True):
                    st.session_state.search_page += 1
                    st.rerun()
            else:
                col2.button("다음 20건 ➡️", disabled=True, use_container_width=True)
                
            st.caption(f"현재 페이지 번호: {st.session_state.search_page} page")
        else:
            st.info("검색된 법령이 없습니다. 키워드를 변경해 보세요.")

# 장착된 법령 패널
st.sidebar.markdown("---")
st.sidebar.markdown(f"### 🧳 장착된 법무 지식베이스 ({len(st.session_state.selected_docs)}건)")

if st.session_state.selected_docs:
    for mst, doc in list(st.session_state.selected_docs.items()):
        dtype_badge = "🏛️" if doc["type"] == "law" else "🏡" if doc["type"] == "ordinance" else "📜" if doc["type"] == "admrul" else "⚖️"
        
        # 개별 선택 삭제가 가능하도록 컬럼 배치
        col_item, col_btn = st.sidebar.columns([8, 2])
        col_item.caption(f"{dtype_badge} {doc['title']}")
        
        # 삭제 버튼 클릭 시 처리
        if col_btn.button("❌", key=f"del_{mst}", help="장착 제외"):
            # 1. 지식베이스에서 즉시 제외
            st.session_state.selected_docs.pop(mst, None)
            # (동적 키 재마운트 적용으로 별도의 세션 강제 pop이 전혀 필요 없음!)
            st.rerun()
        
    st.sidebar.write("")
    if st.sidebar.button("🗑️ 장착된 법령 전체 초기화", use_container_width=True):
        st.session_state.selected_docs = {}
        st.rerun()
else:
    st.sidebar.info("사이드바 검색창에서 법령을 검색한 후 체크박스를 선택하여 에이전트에 장착해 주세요.")

# API 미색인 최신 법령 보조용 수동 입력창
st.sidebar.markdown("---")
manual_text = st.sidebar.text_area(
    "📝 미검색/최신 조문 직접 추가",
    placeholder="법제처 API에 아직 반영되지 않은 신규 법률이나 별도 행정 지침이 있다면 여기에 본문을 복사해서 붙여넣어 주시면 RAG 지식베이스에 즉시 함께 반영됩니다.",
    height=180
)

# ==========================================
# 4. 메인 화면 렌더링 및 RAG 융합 질의
# ==========================================
st.markdown('<div class="brand-title">🏛️ 행정 자문관 - 법제처 Direct Open API RAG</div>', unsafe_allow_html=True)

check_system_health()

tab_chat, tab_docs = st.tabs(["💬 AI 행정 상담실", "📖 실시간 장착 법령 원문 확인"])

# RAG용 다중 장착 조문 통합 텍스트 빌드
context_str = ""
if st.session_state.selected_docs:
    # 각 문서들의 상세 내용을 가져와 병합
    for mst, doc in st.session_state.selected_docs.items():
        with st.spinner(f"📡 '{doc['title']}' 본문 수집 중..."):
            doc_body = fetch_body_api(mst, doc["type"])
            context_str += f"\n\n{doc_body}\n"

if manual_text.strip():
    context_str += f"\n\n=== [수동 추가 참고 지식] ===\n{manual_text.strip()}\n"

# 탭 2: 원문 확인 패널
with tab_docs:
    has_docs = False
    if st.session_state.selected_docs:
        has_docs = True
        st.markdown("### 🔎 장착된 조문/판례의 원문 팩트 대조")
        for mst, doc in st.session_state.selected_docs.items():
            with st.expander(f"📄 {doc['title']} (MST: {mst}) 원문 확인"):
                st.text_area("상세 조문", value=fetch_body_api(mst, doc["type"]), height=300, key=f"viewer_{mst}")
                
    if manual_text.strip():
        has_docs = True
        st.markdown("### 📝 수동으로 직접 추가한 조문 팩트 대조")
        with st.expander("📄 직접 추가한 조문 본문"):
            st.text_area("상세 본문", value=manual_text.strip(), height=250, key="viewer_manual")
            
    if not has_docs:
        st.info("현재 장착된 법령이 없습니다. 사이드바에서 법규를 장착하거나 최신 조문을 수동 추가하시면 실시간 원문이 여기에 표출됩니다.")

# 탭 1: AI 챗봇 상담
with tab_chat:
    # 세션 히스토리 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        
    def scroll_to_bottom():
        # 스트림릿 최외각 스크롤을 최하단으로 당기는 자바스크립트 주입
        js = """
        <script>
            function scrollToBottom() {
                const scrollContainers = window.parent.document.querySelectorAll("section.main");
                scrollContainers.forEach(container => {
                    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                });
            }
            scrollToBottom();
            setTimeout(scrollToBottom, 300);
            setTimeout(scrollToBottom, 800);
        </script>
        """
        st.components.v1.html(js, height=0)
        
    # 1. 누적된 대화 이력을 화면 상단에 순차적으로 렌더링 (구분 식별자 주입)
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            trigger = '<span class="user-trigger"></span>' if msg["role"] == "user" else '<span class="assistant-trigger"></span>'
            st.markdown(f'{trigger}{msg["content"]}', unsafe_allow_html=True)
            
    # 2. 사용자 질문 입력창 (대화 이력 하단 고정)
    if prompt := st.chat_input("장착된 법률/조례를 바탕으로 AI 행정 자문관에게 질문해 보세요..."):
        # 사용자의 질문 즉시 화면 렌더링 및 이력 누적
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(f'<span class="user-trigger"></span>{prompt}', unsafe_allow_html=True)
        # 질문 전송 즉시 스크롤을 맨 아래로 당겨 로딩 스피너 확보
        scroll_to_bottom()
            
        # 어시스턴트 실시간 RAG 자문 분석 및 답변 생성
        with st.chat_message("assistant"):
            scroll_to_bottom() # AI 답변 시작 시점에도 스크롤 재정돈
            if not context_str.strip():
                warn_msg = "⚠️ 현재 장착된 법규가 없습니다. 사이드바에서 법규를 장착하시면 이를 토대로 법적 근거가 포함된 답변을 해 드립니다."
                st.warning(f'<span class="assistant-trigger"></span>{warn_msg}', unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": warn_msg})
            else:
                with st.spinner("🤖 AI 행정 자문관이 조문과 판례를 교차 분석하여 전문 의견서를 작성 중입니다. (최대 1~2분 소요)..."):
                    # 공무원용 고도화 전문 프롬프팅
                    system_prompt = f"""
                    당신은 대한민국 최고의 공공 행정 전문 비서이자 정부 법률 자문관이다.
                    사용자는 공공 기관의 현직 공무원이다.
                    
                    제공된 [실시간 법제처 연계 원문 데이터]를 바탕으로 철저히 팩트에만 근거하여 전문적이고 상세하게 답변해라.
                    
                    [답변 작성 시 절대 지침]
                    1. 출처 명시: 답변하는 모든 규제 한도, 절차, 수치에 대해서는 조문 제X조 제X항 등의 명확한 근거 출처를 괄호 「」로 팩트 뒤에 붙여라. (예: ...위탁 기간은 5년 이내로 한다. 「용인시 공용버스터미널 운영 및 관리 조례 제4조제2항」)
                    2. 공문서식 표(Table) 활용: 지표, 수치, 위반 등급별 벌칙 기준 등은 가급적 마크다운 표로 깔끔하게 규격화하여 보고서식으로 렌더링해라.
                    3. 사실 대조: [실시간 법제처 연계 원문 데이터]에 나오지 않는 규정은 절대 임의로 지어내어 그럴 것이라고 넘겨짚지 말고, 제공되지 않은 영역이라고 선을 긋고 한계를 명확히 설명해라.
                    4. 어조: 매우 정중하고 품위 있는 대한민국 공무원 기안체 및 전문 법무 자문 톤을 구사해라.
                    
                    [실시간 법제처 연계 원문 데이터]
                    {context_str}
                    """
                    
                    api_messages = [{"role": "system", "content": system_prompt}]
                    # 최근 대화 맥락 주입
                    for m in st.session_state.chat_history[-5:]:
                        api_messages.append({"role": m["role"], "content": m["content"]})
                        
                    headers = {
                        "Authorization": f"Bearer {FACTCHAT_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "gpt-5.4",
                        "messages": api_messages,
                        "temperature": 0.1
                    }
                    
                    try:
                        res = requests.post(f"{FACTCHAT_BASE_URL}/chat/completions", headers=headers, json=payload, verify=False, timeout=120)
                        res.raise_for_status()
                        answer = res.json()['choices'][0]['message']['content']
                        
                        st.markdown(f'<span class="assistant-trigger"></span>{answer}', unsafe_allow_html=True)
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                        
                        # 텍스트 파일 저장용 내보내기 다운로드 버튼 제공 (편의사항)
                        st.download_button(
                            label="📥 AI 행정 자문 의견서 다운로드 (.txt)",
                            data=answer,
                            file_name="AI_행정자문의견서.txt",
                            mime="text/plain",
                            key=f"dl_btn_{len(st.session_state.chat_history)}"
                        )
                    except Exception as e:
                        err_txt = f"⚠️ FactChat API 연동에 실패했습니다. (사유: {e})"
                        st.error(err_txt)
                        st.session_state.chat_history.append({"role": "assistant", "content": err_txt})
        
        # [핵심] 답변 누적 직후 즉시 리런하여 스크롤 위치 및 질문창 위치를 완벽하게 정돈
        st.rerun()
