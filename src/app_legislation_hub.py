import os
import re
import json
import asyncio
import requests
import urllib3
import streamlit as st
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ===================================================
# 0. 초기 세팅 및 네트워크 안정화
# ===================================================
st.set_page_config(page_title="🏛️ 지능형 법제처 AI 에이전트", page_icon="🏛️", layout="centered")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv(dotenv_path="/Users/bboyamin/my_project/factchat_project/.env")

FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"
LAW_OC = os.getenv("LAW_OC") or "a11223344556677"

# 🎨 미니멀 & 가독성 극대화 테마 CSS 주입
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    .citation-tag {
        color: #1E88E5;
        font-size: 0.88em;
        font-weight: 700;
        background-color: #E3F2FD;
        padding: 2px 6px;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ===================================================
# 1. 법제처 MCP API 비동기 수집 코어
# ===================================================
async def fetch_legislation_list_only_mcp(query_str: str) -> str:
    npx_cmd = "npx"
    for p in ["/usr/local/bin/npx", "/usr/bin/npx", "/opt/homebrew/bin/npx"]:
        if os.path.exists(p):
            npx_cmd = p
            break
            
    server_params = StdioServerParameters(
        command=npx_cmd,
        args=["-y", "korean-law-mcp"],
        env={"LAW_OC": LAW_OC, "PATH": f"/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:{os.environ.get('PATH', '')}"}
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name="search_law", arguments={"query": query_str})
                out = ""
                for content in result.content:
                    if hasattr(content, 'text'):
                        out += content.text + "\n"
                return out
    except Exception as e:
        return f"[오류] 목록 검색 실패: {e}"

def run_legislation_list_only(query_str: str) -> str:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch_legislation_list_only_mcp(query_str))
        loop.close()
        return result
    except Exception as e:
        return f"[오류] 목록 비동기 에러: {e}"

async def fetch_single_legislation_body_mcp(best_id: str, mode: str, jo: str = None) -> str:
    npx_cmd = "npx"
    for p in ["/usr/local/bin/npx", "/usr/bin/npx", "/opt/homebrew/bin/npx"]:
        if os.path.exists(p):
            npx_cmd = p
            break
            
    server_params = StdioServerParameters(
        command=npx_cmd,
        args=["-y", "korean-law-mcp"],
        env={"LAW_OC": LAW_OC, "PATH": f"/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:{os.environ.get('PATH', '')}"}
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                detail_output = ""
                if mode == "ordin":
                    params = {"id": best_id}
                    if jo:
                        params["jo"] = jo
                    detail_result = await session.call_tool(
                        name="execute_tool",
                        arguments={"tool_name": "get_ordinance", "params": params}
                    )
                    for content in detail_result.content:
                        if hasattr(content, 'text'):
                            detail_output += content.text + "\n"
                else:
                    detail_tool = "get_law_text"
                    detail_tool_obj = next((t for t in tools_response.tools if t.name == detail_tool), None)
                    arguments_payload = {}
                    
                    if detail_tool_obj and hasattr(detail_tool_obj, 'inputSchema') and "properties" in detail_tool_obj.inputSchema:
                        properties = detail_tool_obj.inputSchema["properties"]
                        if "mst" in properties:
                            arguments_payload["mst"] = best_id
                        elif "lawId" in properties:
                            arguments_payload["lawId"] = best_id
                        elif "id" in properties:
                            arguments_payload["id"] = best_id
                        else:
                            first_key = list(properties.keys())[0] if properties else "mst"
                            arguments_payload[first_key] = best_id
                            
                        if jo and "jo" in properties:
                            arguments_payload["jo"] = jo
                    else:
                        arguments_payload["mst"] = best_id
                        if jo:
                            arguments_payload["jo"] = jo
                            
                    detail_result = await session.call_tool(name=detail_tool, arguments=arguments_payload)
                    for content in detail_result.content:
                        if hasattr(content, 'text'):
                            detail_output += content.text + "\n"
                return detail_output
    except Exception as e:
        return f"[오류] 본문 획득 에러: {e}"

def run_single_legislation_body_fetch(best_id: str, mode: str, jo: str = None) -> str:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch_single_legislation_body_mcp(best_id, mode, jo))
        loop.close()
        return result
    except Exception as e:
        return f"[오류] 본문 비동기 에러: {e}"

# ===================================================
# 2. 챗봇 인라인 에이전트 라우팅 함수 (지능형 RAG)
# ===================================================
def agentic_law_fetch(user_prompt: str) -> dict:
    """
    사용자의 질문을 읽고 백그라운드에서 법제처 MCP를 자동 탐색하여
    연관된 법률/조례의 핵심 조문 본문 텍스트를 실시간으로 획득하여 반환합니다.
    """
    headers = {"Authorization": f"Bearer {FACTCHAT_API_KEY}", "Content-Type": "application/json"}
    
    # 2-1. 1차 휴리스틱(Heuristic) 감지기 작동 (레이텐시 0ms, 무오류 구조)
    law_name = "NONE"
    specific_jo = "NONE"
    keyword = user_prompt
    
    # 겹낫표 감지
    bracket_match = re.search(r'「([^」]+)」', user_prompt)
    if bracket_match:
        law_name = bracket_match.group(1).strip()
    else:
        # 대표적인 주요 법령명 감지 키워드 사전
        candidates = [
            "개인정보 보호법", "개인정보보호법", "근로기준법", "도로교통법", 
            "주차장 조례", "주차장 설치 및 관리 조례", "도시공원 조례", "공원 조례",
            "상가건물 임대차보호법", "주택임대차보호법", "지방자치법", "민법", "형법", "상법"
        ]
        for cand in candidates:
            if cand in user_prompt:
                law_name = cand
                break
                
    # 질문 속에서 "제X조" 감지
    jo_match = re.search(r'제\s*(\d+)\s*조', user_prompt)
    if jo_match:
        specific_jo = f"제{jo_match.group(1)}조"
        
    # 만약 1차 휴리스틱에서 법령명을 특정하지 못한 경우에만 2차로 지능형 LLM 분석기 가동
    if law_name == "NONE":
        system_analyzer = (
            "너는 사용자의 질문을 분석하여 법제처 MCP를 검색하기 위한 최적의 파라미터를 추출하는 지능형 법무 분석기이다.\n"
            "반드시 JSON 형식으로만 응답해야 하며, 그 외의 설명이나 마크다운 백틱은 절대 붙이지 마라.\n\n"
            "분석해야 하는 필드:\n"
            "1. 'law_name': 질문에서 요구하거나 유추되는 정확한 법률/조례명 (예: '용인시 주차장 설치 및 관리 조례' 또는 '근로기준법').\n"
            "   만약 지자체 관련 질문인데 시/도가 누락되어 있다면 질문의 맥락을 고려해 '용인시 주차장 설치 및 관리 조례' 등으로 보정하여 채워라.\n"
            "2. 'keyword': 질문의 핵심 요약 검색어 (예: '노상주차장 설치기준', '근로시간').\n"
            "3. 'specific_jo': 질문에 직접 언급되었거나 유추되는 특정 조항 번호 (예: '제17조', '제50조'). 없다면 'NONE'으로 채워라.\n\n"
            "출력 JSON 규격:\n"
            "{\"law_name\": \"...\", \"keyword\": \"...\", \"specific_jo\": \"...\"}"
        )
        try:
            payload = {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": system_analyzer},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.01
            }
            res = requests.post(f"{FACTCHAT_BASE_URL}/chat/completions", headers=headers, json=payload, verify=False, timeout=12)
            res.raise_for_status()
            raw_json = res.json()['choices'][0]['message']['content'].strip()
            raw_json = re.sub(r'^```json\s*|```$', '', raw_json, flags=re.MULTILINE).strip()
            analysis = json.loads(raw_json)
            law_name = analysis.get("law_name", "NONE")
            keyword = analysis.get("keyword", "NONE")
            specific_jo = analysis.get("specific_jo", "NONE")
        except Exception:
            law_name = "NONE"
            keyword = "NONE"
            specific_jo = "NONE"
            
    # 개인정보보호법 띄어쓰기 표준화
    if law_name == "개인정보보호법":
        law_name = "개인정보 보호법"
    
    if law_name == "NONE" or not law_name:
        return {"content": f"[오류] 질문 분석 실패 (사용자의 질문에서 어떤 법령/조례를 매칭해야 할지 AI 분석기가 판정하지 못했습니다. 질문 내용: '{user_prompt}')", "titles": []}
        
    # 2-2. 1단계: 법제처 검색 쿼리 실행 (점진적 단순화 및 재시도 루프)
    # 검색 쿼리 점진적 축소 후보군 구축
    search_candidates = [law_name]
    
    # "공영" <-> "공용" 교차 보완
    if "공영" in law_name:
        search_candidates.append(law_name.replace("공영", "공용"))
    elif "공용" in law_name:
        search_candidates.append(law_name.replace("공용", "공영"))
        
    # 뒤쪽 상투 어구 제거
    clean_name = re.sub(r'(?:의\s*)?(?:운영\s*및\s*)?(?:설치\s*및\s*)?(?:관리\s*)?(?:조례|시행규칙|규칙|법|법률)$', '', law_name).strip()
    if clean_name and clean_name != law_name:
        search_candidates.append(clean_name)
        if "공영" in clean_name:
            search_candidates.append(clean_name.replace("공영", "공용"))
        elif "공용" in clean_name:
            search_candidates.append(clean_name.replace("공용", "공영"))
            
    # 단어 쪼개서 추가 축소
    words = clean_name.split()
    if len(words) >= 3:
        search_candidates.append(" ".join(words[:2]))
        search_candidates.append(words[1])
    elif len(words) == 2:
        search_candidates.append(words[1])
        
    # 중복 제거 및 순서 보존
    seen = set()
    final_queries = []
    for q in search_candidates:
        q_clean = q.strip()
        if q_clean and q_clean not in seen and len(q_clean) >= 2:
            seen.add(q_clean)
            final_queries.append(q_clean)
            
    # 순차 재시도 작동
    search_raw = ""
    last_query_used = law_name
    for query in final_queries:
        last_query_used = query
        search_raw = run_legislation_list_only(query)
        
        # 목록을 정상적으로 1건 이상 찾았다면 즉시 검색 완료로 간주하고 중단
        if "[오류]" not in search_raw and search_raw.strip() and "결과가 없습니다" not in search_raw and "찾지 못했습니다" not in search_raw:
            break
            
    if "[오류]" in search_raw:
        return {"content": search_raw, "titles": []}
        
    # 만약 지자체 조례 실패 시 경기도/용인시 보정 후 최종 재검색
    if "찾지 못했습니다" in search_raw or "결과가 없습니다" in search_raw or not search_raw.strip():
        if "조례" in law_name and not any(w in law_name for w in ["서울특별시", "경기도", "용인시"]):
            last_query_used = f"용인시 {law_name}"
            search_raw = run_legislation_list_only(last_query_used)
            if "[오류]" in search_raw:
                return {"content": search_raw, "titles": []}
                
    search_keyword = last_query_used
            
    best_id = None
    eval_mode = "law"
    resolved_title = law_name
    
    if "[오류]" not in search_raw and search_raw.strip():
        # 자치법규(ordin) vs 중앙법령(law) 여부 판정
        is_ordin = any(w in law_name for w in ["조례", "시행규칙", "규칙", "지자체"])
        eval_mode = "ordin" if is_ordin else "law"
        
        # 1. 1순위: MST 코드만 전체 라인에서 우선 수색 (중앙법령은 무조건 MST가 매칭되어야 본문 조회가 작동)
        for line in search_raw.split('\n'):
            if "시행예정" in line or "개정 시행예정" in line:
                continue
            id_match = re.search(r'MST\:\s*(\d{5,8})', line, re.IGNORECASE)
            if id_match:
                best_id = id_match.group(1)
                
                # 제명 추출 시도
                title_match = re.search(r'(?:\d+\.\s*|\]\s*)([^\(\[-]+)', line)
                if title_match:
                    candidate_title = title_match.group(1).strip()
                    if len(candidate_title) > 2:
                        resolved_title = candidate_title
                break
                
        # 2. 2순위: MST가 존재하지 않는 자치조례/시행규칙에 한하여 대괄호 ID [ID] 및 법령ID 수색
        if not best_id:
            for line in search_raw.split('\n'):
                if "시행예정" in line or "개정 시행예정" in line:
                    continue
                
                # 1) [ID] 자치법규 탐색
                id_match = re.search(r'\[(\d{5,8})\]', line)
                # 2) 법령ID/ordinanceId 등 탐색
                if not id_match:
                    id_match = re.search(r'(?:법령ID|ordinanceId|id|ID)[\s\:\=\'\"\`]*(\d{5,8})', line, re.IGNORECASE)
                    
                if id_match:
                    best_id = id_match.group(1)
                    
                    title_match = re.search(r'(?:\d+\.\s*|\]\s*)([^\(\[-]+)', line)
                    if title_match:
                        candidate_title = title_match.group(1).strip()
                        if len(candidate_title) > 2:
                            resolved_title = candidate_title
                    break
                
    if not best_id:
        return {"content": f"[오류] 법령 매칭 실패 (AI가 추론한 법령명: '{law_name}', 검색어: '{search_keyword}', 특정조항: '{specific_jo}', 결과 원본: {search_raw[:300]})", "titles": []}
        
    # 2-3. 2단계: 본문 및 특정 조항 자동 수집
    context_data = ""
    
    # 1) 만약 질문에 명시된 특정 조항(specific_jo)이 있다면 곧바로 해당 조항 본문 낚아채기
    if specific_jo != "NONE" and specific_jo:
        with st.spinner(f"📡 {resolved_title} {specific_jo} 조문 수집 중..."):
            clause_text = run_single_legislation_body_fetch(best_id, eval_mode, specific_jo)
            if "[오류]" not in clause_text and clause_text.strip() and "찾을 수 없습니다" not in clause_text:
                context_data += f"\n\n[실시간 보충 조문 - {resolved_title} {specific_jo}]\n{clause_text.strip()}\n"
                
    # 2) 전체 목차(Index) 우선 로드
    with st.spinner(f"📡 {resolved_title} 구조 분석 중..."):
        index_text = run_single_legislation_body_fetch(best_id, eval_mode)
        if "[오류]" not in index_text and index_text.strip():
            context_data += f"\n\n==================================================\n"
            context_data += f"📖 연동 법령: {resolved_title} (ID/MST: {best_id})\n"
            context_data += f"==================================================\n"
            context_data += index_text.strip() + "\n"
            
            # 질문의 성격(특정 단답식 vs. 전체 요약/개요식)에 따라 선별 가이드 분기
            is_broad_query = any(w in user_prompt for w in ["요약", "정리", "개요", "전체", "구조", "특징", "설명해줘"])
            
            if is_broad_query:
                system_index_picker = (
                    "너는 아래 제공된 [법령 목차]에서 해당 법령/조례의 전체적인 목적, 핵심 규정 및 뼈대가 되는 주요 조항(예: 목적, 정의, 설치기준, 요금/감면기준, 위탁운영 등)을 요약하기 위해 반드시 본문 내용을 조회해 봐야 하는 핵심 조항 번호(제X조) 최대 8~10개를 선별해 주는 도우미이다.\n"
                    "가장 핵심이 되는 기둥 조항 번호들만 쉼표(,)로 구분하여 딱 출력해라. (예: 제1조, 제2조, 제5조, 제10조, 제17조)\n"
                    "설명이나 다른 문자 없이 딱 조항 번호들만 반환해라."
                )
            else:
                system_index_picker = (
                    "너는 아래 제공된 [법령 목차]에서 사용자의 질문을 해결하기 위해 반드시 세부 본문 내용을 조회해 봐야 하는 가장 관련 깊은 조항 번호(제X조) 최대 3개를 선별해 주는 도우미이다.\n"
                    "가장 관련이 깊은 조항 번호들만 쉼표(,)로 구분하여 딱 출력해라. (예: 제17조, 제21조)\n"
                    "만약 관련 조항을 찾을 수 없다면 오직 'NONE'이라고만 출력해라.\n"
                    "설명이나 다른 문자 없이 딱 조항 번호들만 반환해라."
                )
                
            user_prompt_index = f"사용자 질문: {user_prompt}\n\n[법령 목차]\n{index_text[:3000]}"
            
            try:
                payload = {
                    "model": "gpt-5.4",
                    "messages": [
                        {"role": "system", "content": system_index_picker},
                        {"role": "user", "content": user_prompt_index}
                    ],
                    "temperature": 0.05
                }
                res = requests.post(f"{FACTCHAT_BASE_URL}/chat/completions", headers=headers, json=payload, verify=False, timeout=10)
                res.raise_for_status()
                auto_jos_str = res.json()['choices'][0]['message']['content'].strip().replace('"', '').replace("'", "")
            except Exception:
                auto_jos_str = "NONE"
                
            if auto_jos_str and auto_jos_str != "NONE":
                auto_jos = [j.strip() for j in auto_jos_str.split(",") if j.strip()]
                for jo_num in auto_jos:
                    if jo_num == specific_jo: continue # 중복 조회 방지
                    with st.spinner(f"📡 연관 조항 [{resolved_title} {jo_num}] 본문 실시간 수집 중..."):
                        clause_text = run_single_legislation_body_fetch(best_id, eval_mode, jo_num)
                        if "[오류]" not in clause_text and clause_text.strip() and "찾을 수 없습니다" not in clause_text:
                            context_data += f"\n\n[실시간 보충 조문 - {resolved_title} {jo_num}]\n{clause_text.strip()}\n"

    return {"content": context_data, "titles": [resolved_title]}

# ===================================================
# 3. 메인 UI 화면 구성
# ===================================================
st.title("🏛️ 지능형 법제처 AI 에이전트")
st.markdown("질문만 입력하시면 AI가 자동으로 관련 조례/법령을 검색하여 실시간 조문을 가져와 완벽히 교차 검토해 줍니다.")

# 세션 히스토리 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 대화 기록 렌더링 (익스팬더로 근거 조문 100% 대조 제공)
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)
        if msg["role"] == "assistant" and msg.get("context"):
            with st.expander("🔍 이번 답변에 사용된 법제처 근거 조문 확인"):
                with st.container(height=300):
                    st.text(msg["context"])

# 질문 입력 처리
if prompt := st.chat_input("자치법규나 법령에 대해 무엇이든 질문해 보세요..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        # 3-1. Agentic Law Fetcher 백그라운드 구동
        fetched = agentic_law_fetch(prompt)
        context_str = fetched.get("content", "")
        titles = fetched.get("titles", [])
        
        if "[오류]" in context_str or not context_str.strip():
            # 법제처 데이터 획득 실패 시 에러 로그 직접 출력
            err_msg = context_str if context_str.strip() else "[오류] 연동된 컨텍스트가 비어 있습니다."
            answer = f"❌ 법제처 실시간 데이터 연동에 실패했습니다.\n\n**에러 상세 내용:**\n{err_msg}\n\n질문 내의 법규 명칭을 좀 더 구체적으로 명시해 주시거나 잠시 후 다시 시도해 주세요."
            st.error(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer, "context": ""})
        else:
            # 3-2. 확보된 법령 본문을 토대로 최종 행정 답변 생성
            with st.spinner("적재된 조문들을 교차 분석하여 정밀 답변 작성 중..."):
                system_prompt = f"""
                당신은 대한민국 최고의 법무 행정 전문가 비서이다.
                제공된 [실시간 법제처 수집 조문 데이터]를 대조하여 사실에 근거해서 질문에 답변해라.
                
                [답변 작성 필수 지침]
                1. 철저한 조문 대조: 제공되지 않은 법령 내용은 절대 유추하여 지어내지 말 것.
                2. 표(Table) 활용: 금액 한도, 세부 규격 치수(폭, 길이), 서식 등은 가급적 마크다운 표로 깔끔하게 정리해 가독성을 높일 것.
                3. 출처 명시: 답변의 핵심 팩트 뒤에는 반드시 대괄호 「」를 사용하여 근거 조항을 표기할 것. (예: ...해야 한다. 「용인시 주차장 설치 및 관리 조례 제17조」)
                4. 말투: 정중하고 명확한 전문적인 어조를 사용할 것.
                
                [실시간 법제처 수집 조문 데이터]
                {context_str}
                """
                
                api_messages = [{"role": "system", "content": system_prompt}]
                # 컨텍스트 압축을 위해 최근 대화 히스토리만 전달
                for m in st.session_state.chat_history[-5:]:
                    if m["role"] in ["user", "assistant"]:
                        api_messages.append({"role": m["role"], "content": m["content"]})
                        
                headers = {"Authorization": f"Bearer {FACTCHAT_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "gpt-5.4",
                    "messages": api_messages,
                    "temperature": 0.1
                }
                
                try:
                    res = requests.post(f"{FACTCHAT_BASE_URL}/chat/completions", headers=headers, json=payload, verify=False, timeout=40)
                    res.raise_for_status()
                    answer = res.json()['choices'][0]['message']['content']
                    
                    # 출처 태그 이펙트 및 출력
                    def format_citations(text):
                        p = r'\[([^\]]+)\]'
                        r_tag = r'<span class="citation-tag">[\1]</span>'
                        return re.sub(p, r_tag, text)
                        
                    formatted_answer = format_citations(answer)
                    st.markdown(formatted_answer, unsafe_allow_html=True)
                    
                    # 근거 조문 아코디언 뷰
                    with st.expander("🔍 이번 답변에 사용된 법제처 근거 조문 확인"):
                        with st.container(height=300):
                            st.text(context_str)
                            
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": formatted_answer,
                        "context": context_str
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 답변 생성 통신 오류: {e}")
