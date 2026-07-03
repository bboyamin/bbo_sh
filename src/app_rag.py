import os
import json
import asyncio
import requests
import urllib3
import streamlit as st
from dotenv import load_dotenv
import concurrent.futures

# 로컬 HWPX/PDF 파서 및 SQLite RAG 엔진 임포트
from parser import extract_text_from_file
from rag_engine import (
    index_document, 
    search_relevant_contexts, 
    get_indexed_files, 
    delete_all_documents
)

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# API 설정 로드
FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

# 🎨 스트림릿 페이지 설정 및 수려한 단독 브랜드 테마 적용
st.set_page_config(
    page_title="📂 HWPX/PDF 지능형 행정 비서",
    page_icon="📂",
    layout="centered"
)

# 프리미엄 쉐도우 및 그라데이션이 적용된 매트 네이비 테마 CSS 주입
st.markdown("""
<style>
    /* 기본 바디 영역 마진 패딩 최적화 */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 7.5rem !important;
        max-width: 750px !important;
    }

    /* 프리미엄 브랜드 타이틀 스타일 */
    .brand-title {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
        letter-spacing: -0.05rem;
    }

    .brand-subtitle {
        font-size: 0.98rem;
        color: #5a6e7f;
        margin-bottom: 2rem;
        font-weight: 500;
    }

    /* 입체형 정보 안내 카드 */
    .guide-card {
        background: #ffffff;
        border: 1px solid #e1e8ed;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        margin-bottom: 1.5rem;
    }

    .guide-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e3c72;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* 알약 칩 스타일 공통 정의 */
    div.stButton > button {
        background: #ffffff !important;
        color: #2b5298 !important;
        border: 1px solid #c8d6e5 !important;
        border-radius: 20px !important;
        padding: 0.4rem 0.9rem !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
        height: auto !important;
        width: 100% !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    
    div.stButton > button:hover {
        background: #f4f7fc !important;
        border-color: #2a5298 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(42, 82, 152, 0.15) !important;
    }

    /* 모바일 반응형 조정 */
    @media (max-width: 640px) {
        .brand-title {
            font-size: 1.8rem;
        }
        .brand-subtitle {
            font-size: 0.88rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# 🎓 대시보드 헤더 렌더링
st.markdown('<div class="brand-title">📂 HWPX/PDF 지능형 행정 문서 비서</div>', unsafe_allow_html=True)
st.markdown('<div class="brand-subtitle">한글(HWPX) 및 PDF 문서를 로컬에서 고속 파싱하여 왜곡 없이 지식 조회를 지원하는 스마트 워크스페이스입니다.</div>', unsafe_allow_html=True)

# ===================================================
# 📁 [RAG 지식베이스] 업로더 상태 리셋용 세션 변수 정의
# ===================================================
if "rag_uploader_key" not in st.session_state:
    st.session_state.rag_uploader_key = 0

# ===================================================
# 📁 [RAG 지식베이스] 사이드바 드래그 앤 드롭 업로더 구성
# ===================================================
with st.sidebar:
    st.markdown("### 📥 행정 문서 지식베이스")
    st.markdown("여기에 HWPX 및 PDF 문서를 업로드해 두시면, AI가 문서를 참조하여 한층 더 정밀한 답변을 제공합니다.")
    
    # st.session_state.rag_uploader_key 회전을 통해 위젯 전체 강제 리셋 지원
    uploaded_files = st.file_uploader(
        "문서 업로드 (.hwpx, .pdf)",
        type=["hwpx", "pdf"],
        accept_multiple_files=True,
        key=f"rag_uploader_{st.session_state.rag_uploader_key}"
    )
    
    if uploaded_files:
        temp_dir = "./temp_docs"
        os.makedirs(temp_dir, exist_ok=True)
        
        for uploaded_file in uploaded_files:
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            
            # 중복 인덱싱 방지용 캐싱 세션 체크
            indexed_key = f"rag_idx_{uploaded_file.name}_{uploaded_file.size}"
            if indexed_key not in st.session_state:
                with st.spinner(f"'{uploaded_file.name}' 분석 중..."):
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                        
                    extracted_text = extract_text_from_file(temp_path)
                    if not extracted_text.startswith("[오류]"):
                        num_chunks = index_document(uploaded_file.name, extracted_text)
                        st.session_state[indexed_key] = True
                        st.success(f"✅ {uploaded_file.name} ({num_chunks}개 조각) 분석 완료!")
                    else:
                        st.error(f"❌ {uploaded_file.name} 분석 실패: {extracted_text}")
                        
    # 등록된 문서 목록 실시간 렌더링
    indexed_list = get_indexed_files()
    if indexed_list:
        st.markdown("#### 📚 현재 연동된 지식 문서:")
        for f_name in indexed_list:
            st.markdown(f"**📄 {f_name}**")
            
        st.write("")
        if st.button("🚨 지식베이스 전체 초기화", use_container_width=True):
            if delete_all_documents():
                for k in list(st.session_state.keys()):
                    if k.startswith("rag_idx_"):
                        del st.session_state[k]
                # 업로더 위젯 키 값 증가로 브라우저 상의 파일 드래그 존 즉각 포맷
                st.session_state.rag_uploader_key += 1
                st.success("지식베이스가 리셋되었습니다!")
                st.rerun()

# 대화 기록 초기화
if "rag_chat_history" not in st.session_state:
    st.session_state.rag_chat_history = []

# 💡 대화 역사가 비어 있을 때 가이드 안내 카드 출력
if not st.session_state.rag_chat_history:
    st.markdown("""
    <div class="guide-card">
        <div class="guide-header">💡 HWPX/PDF 스마트 문서 비서 사용법</div>
        1. 왼쪽 사이드바의 <b>[문서 업로드]</b> 공간에 한글(HWPX) 또는 PDF 보고서를 넣어주세요.<br>
        2. 문서 적재가 완료되면 채팅창에 문서 관련 궁금한 질문을 직접 자유롭게 작성해 보세요.<br>
        3. AI가 로컬 지식 문서 내에서 정확한 원본 구절을 탐색하여 <b>출처 표기 및 마크다운 표 브리핑</b>을 수행합니다.
    </div>
    """, unsafe_allow_html=True)

# 기존 대화 렌더링
for message in st.session_state.rag_chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ⌨️ 대화 입력창 처리
user_input = st.chat_input("연동한 행정 문서에 대해 질문해 보세요... (예: 신청 기간이 언제야?)")

active_query = None
if user_input:
    active_query = user_input

if active_query:
    # 1. 유저 질문 렌더링 및 저장
    with st.chat_message("user"):
        st.markdown(active_query)
    st.session_state.rag_chat_history.append({"role": "user", "content": active_query})
    
    # 2. AI RAG 로직 구동
    with st.chat_message("assistant"):
        with st.spinner("로컬 문서 지식 탐색 및 실시간 데이터 요약 중..."):
            
            # SQLite RAG 엔진 매칭 검색
            contexts = search_relevant_contexts(active_query, n_results=3)
            
            rag_context_str = ""
            if contexts:
                rag_context_str = "\n\n[참조된 로컬 행정 문서 내용]\n"
                for c in contexts:
                    rag_context_str += f"- 출처: {c['filename']} (조각 {c['chunk_index'] + 1})\n  내용: {c['text'].strip()}\n\n"
            
            # RAG 전용 고가독성 시스템 프롬프트 정의
            system_instruction = (
                "너는 최고의 스마트 행정 문서 분석가 비서인 'RAG 스마트 문서 비서'이다.\n\n"
                "답변을 작성할 때 가독성을 극적으로 끌어올려 사용자가 한눈에 파악할 수 있도록 반드시 다음 규칙을 절대적으로 준수해라:\n"
                "1. **표(Table) 형식의 적극적인 활용**: 신청 자격 요건, 제출 서류 및 수치 데이터, 주요 일정 등은 가급적 마크다운 표(Table)를 짜서 구조적으로 정렬하여 나타낼 것.\n"
                "2. **굵은 강조와 이모지**: 주요 마감 기한, 특이사항, 제출 시 유의사항 등 핵심 정보는 글씨를 **굵게 강조**하고 내용에 알맞은 시각적 이모지(🍱, 📅, 📊, 📂, 📌, ⚠️ 등)를 붙여라.\n"
                "3. **구분선과 문단 쪼개기**: 답변이 긴 경우 반드시 가로 구분선(---)과 소제목(### 📂 제출 서류 리스트 등)을 사용하여 챕터를 읽기 좋게 끊어서 제공해라.\n"
                "4. **[참조 문서 내용 인용 지침]**: 만약 아래에 '[참조된 로컬 행정 문서 내용]'이 주어진 경우, 다른 거짓 지식을 합성하지 말고 철저하게 해당 텍스트 내용만을 토대로 답변을 완성해라. 그리고 답변 맨 마지막에 반드시 이모지 📌 와 함께 **'이 내용은 [참조한 파일명]의 조각 내용을 토대로 작성되었습니다.'** 라는 출처를 굵은 텍스트로 남겨라.\n"
                "5. **완결성**: 대화의 흐름에 맞추어 전문적이고 신뢰감 넘치며 친근하게 답해라."
            )
            
            if rag_context_str:
                system_instruction += rag_context_str
                
            headers = {
                "Authorization": f"Bearer {FACTCHAT_API_KEY}",
                "Content-Type": "application/json"
            }
            
            api_messages = [{"role": "system", "content": system_instruction}]
            # RAG 전용 대화기록 패킹
            for chat in st.session_state.rag_chat_history:
                if chat["role"] in ["user", "assistant"]:
                    api_messages.append({"role": chat["role"], "content": chat["content"]})
                    
            try:
                payload = {
                    "model": "gpt-5.4",
                    "messages": api_messages,
                    "temperature": 0.15
                }
                
                response = requests.post(
                    f"{FACTCHAT_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    verify=False,
                    timeout=40
                )
                response.raise_for_status()
                response_json = response.json()
                final_response = response_json['choices'][0]['message']['content']
                
                st.markdown(final_response)
                st.session_state.rag_chat_history.append({"role": "assistant", "content": final_response})
                st.rerun() # 🌟 완료 즉시 Rerun하여 하단 플로팅 칩 바가 알맞게 갱신 고정 노출되도록 유도
                
            except Exception as e:
                err_text = f"⚠️ **연동 중 일시적 오류가 발생했습니다.** (사유: {e})\n\n잠시 후 다시 질문해 주시거나 검색 방식을 간결하게 시도해 주시기 바랍니다."
                st.markdown(err_text)
