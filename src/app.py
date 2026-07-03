import os
import json
import asyncio
import requests
import urllib3
import streamlit as st
import random
from dotenv import load_dotenv
import concurrent.futures
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수 로드 (.env 파일)
load_dotenv()

# st.secrets 에 안전하게 접근하는 헬퍼 함수 (Streamlit Cloud 배포 및 로컬 .env 호환)
def get_secret_safe(key):
    try:
        return st.secrets[key]
    except Exception:
        return None

# API 키 및 설정 로드
FACTCHAT_API_KEY = get_secret_safe("FACTCHAT_API_KEY") or os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = get_secret_safe("FACTCHAT_BASE_URL") or os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

SCHOOLINFO_API_KEY = get_secret_safe("SCHOOLINFO_API_KEY") or os.getenv("SCHOOLINFO_API_KEY")
NEIS_API_KEY = get_secret_safe("NEIS_API_KEY") or os.getenv("NEIS_API_KEY")

# ===================================================
# [하이브리드 경로 감지] OS별 실행 파일 경로 설정
# ===================================================
def get_mcp_executable_path(package_name, script_rel_path):
    # 1. 윈도우용 수동 작업 공간 경로
    win_path = f"C:/mcp-workspace/node_modules/{package_name}/{script_rel_path}"
    # 2. 맥북 / 리눅스 클라우드 서버용 로컬 프로젝트 경로
    local_path = os.path.abspath(f"node_modules/{package_name}/{script_rel_path}")
    
    if os.path.exists(win_path):
        return win_path
    return local_path

# ===================================================
# [비동기 안전 실행 헬퍼] Streamlit 스레드 충돌 방지
# ===================================================
def run_async_safe(coro):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()

# ===================================================
# [MCP 연동 코어] schoolinfo-mcp 실행 및 툴 호출
# ===================================================
async def execute_school_mcp_async(tool_name, arguments):
    schoolinfo_bin = get_mcp_executable_path("schoolinfo-mcp", "dist/mcp.js")
    
    # 윈도우/맥/리눅스 공통으로 Node.js를 기반 실행기로 지정
    node_cmd = "node"
    if os.name != 'nt': # Unix/Mac 환경의 경우 절대경로가 있으면 사용
        node_cmd = "/usr/local/bin/node" if os.path.exists("/usr/local/bin/node") else "node"
        
    env_vars = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    }
    
    # 발급받은 API 키들을 환경변수로 주입
    school_env = env_vars.copy()
    if SCHOOLINFO_API_KEY:
        school_env["SCHOOLINFO_API_KEY"] = SCHOOLINFO_API_KEY
    if NEIS_API_KEY:
        school_env["NEIS_API_KEY"] = NEIS_API_KEY
        
    params = StdioServerParameters(command=node_cmd, args=[schoolinfo_bin], env=school_env)

    # stdio_client를 사용해 백그라운드 구동 후 도구 실행
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name=tool_name, arguments=arguments)
            # content 내용 중 텍스트 포맷들만 병합
            return "\n".join([content.text for content in result.content if hasattr(content, 'text')])

def execute_mcp_tool(tool_name, arguments):
    try:
        return run_async_safe(execute_school_mcp_async(tool_name, arguments))
    except Exception as e:
        err_msg = str(e)
        if "quota exceeded" in err_msg or "apiKey" in err_msg or "429" in err_msg:
            return f"[도구 실행 실패] 학교알리미/NEIS API의 호출 무료 한도가 소진되었습니다. API 키 설정을 확인해 주십시오."
        return f"[도구 실행 실패] 학교 정보를 조회하는 중 예외가 발생했습니다: {err_msg}"

# ===================================================
# [동적 도구 수집 및 캐싱] 단 1회만 스키마 긁어오기 (속도 극대화)
# ===================================================
def bootstrap_node_dependencies():
    # 배포 서버 환경에서 schoolinfo-mcp 모듈이 없을 때 자동 설치하는 자가 세팅 헬퍼
    if not os.path.exists("node_modules/schoolinfo-mcp"):
        try:
            import subprocess
            subprocess.run(["npm", "install"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Failed to bootstrap npm package: {e}")

@st.cache_resource(show_spinner="스쿨 에이전트 엔진 로드 중...")
def discover_school_mcp_tools():
    bootstrap_node_dependencies() # 🌟 배포 환경 NPM 빌드 자동 부트스트랩 호출
    schoolinfo_bin = get_mcp_executable_path("schoolinfo-mcp", "dist/mcp.js")
    
    node_cmd = "node"
    if os.name != 'nt':
        node_cmd = "/usr/local/bin/node" if os.path.exists("/usr/local/bin/node") else "node"
    env_vars = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")}
    
    school_env = env_vars.copy()
    if SCHOOLINFO_API_KEY:
        school_env["SCHOOLINFO_API_KEY"] = SCHOOLINFO_API_KEY
    if NEIS_API_KEY:
        school_env["NEIS_API_KEY"] = NEIS_API_KEY
        
    params = StdioServerParameters(command=node_cmd, args=[schoolinfo_bin], env=school_env)
    openai_tools = []
    
    async def discover():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                server_tools = await session.list_tools()
                for t in server_tools.tools:
                    # OpenAI Tool Calling 규격으로 변환
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema
                        }
                    })
    try:
        run_async_safe(discover())
    except Exception as e:
        print(f"Failed to load tools for korean-school: {e}")
        
    return openai_tools

# 도구 스키마 로드
tools_schema = discover_school_mcp_tools()

# ===================================================
# Streamlit 프리미엄 CSS 테마 및 레이아웃 설정
# ===================================================
st.set_page_config(page_title="BBOYAMIN 스마트 스쿨 에이전트", page_icon="🎓", layout="centered")

# [랜덤 예시 질문 생성 풀] 외대부고 & 용인 성서중학교 맞춤형
def get_random_school_chips():
    pool = [
        ("🍱 외대부고 급식", "용인한국외국어대학교부설고등학교의 오늘(또는 최근) 급식 메뉴를 조회해서 깔끔한 리스트 형태로 보여줘."),
        ("📅 외대부고 일정", "용인한국외국어대학교부설고등학교의 이번 달 주요 학사일정이나 행사 계획을 조회해 줘."),
        ("🍱 용인성서 급식", "용인시 수지구에 위치한 성서중학교의 오늘 급식 메뉴가 뭔지 조회해 줄래?"),
        ("📅 용인성서 일정", "용인시 수지구에 위치한 성서중학교의 이번 달 주요 학사일정 및 행사 계획을 조회해 줘."),
        ("🌾 외대부고 대체급식", "용인한국외국어대학교부설고등학교의 최근 급식 식단과 함께 알레르기 유발 유무나 대체 정보가 있는지 확인해줘."),
        ("📊 용인성서 통계", "용인시 수지구에 위치한 성서중학교의 전체 학생 수와 남학생, 여학생 비율 등 학교알리미 공시 정보를 알려줘."),
        ("📅 외대부고 방학식", "용인한국외국어대학교부설고등학교의 올해 학사 일정 중 여름방학, 겨울방학 방학식 및 개학식 날짜가 언제인지 찾아줘."),
        ("🎭 용인성서 동아리", "용인시 수지구에 위치한 성서중학교의 자율동아리 수나 동아리 활동 현황에 대한 학교알리미 공시 정보를 조회해 줘."),
        ("🍱 용인성서 주간식단", "용인시 수지구에 위치한 성서중학교의 이번 주 전체 급식 식단표를 조회해서 일자별로 표로 정리해 줘."),
        ("🏫 외대부고 기본정보", "용인한국외국어대학교부설고등학교의 전체 교직원 수, 학급당 학생 수 등 학교 기본 현황을 학교알리미 공시 정보에서 조회해 줘.")
    ]
    return random.sample(pool, 4)

# 칩 세션 캐싱 초기화
if "current_chips" not in st.session_state:
    st.session_state.current_chips = get_random_school_chips()

# 고급 CSS 주입 (에메랄드 & 딥 블루 학업 특화 테마, Glassmorphism 말풍선, 프리미엄 호버 버튼 모션)
st.markdown("""
<style>
    /* 전체 배경 스타일 - 맑고 신뢰감을 주는 에메랄드 소프트 그라데이션 */
    .stApp {
        background: linear-gradient(135deg, #e6f4ea 0%, #f4fbf7 100%);
    }
    
    /* 타이틀 그라데이션 및 닉네임 강조 */
    .brand-title {
        background: linear-gradient(90deg, #0f766e 0%, #1d4ed8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        text-align: center;
        margin-bottom: 0.2rem;
        font-family: 'Inter', sans-serif;
    }
    
    .brand-subtitle {
        text-align: center;
        color: #374151;
        font-size: 1.0rem;
        margin-bottom: 1.5rem;
    }

    /* 반투명 유리 재질(Glassmorphism) 카드 디자인 */
    .glass-card {
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 0.9rem;
        border: 1px solid rgba(255, 255, 255, 0.5);
        box-shadow: 0 4px 20px rgba(15, 118, 110, 0.08);
        margin-bottom: 1.0rem;
    }

    /* 프리미엄 칩 버튼 스타일 - 부드럽게 색이 차오르는 모션과 입체 호버 섀도우 (가로 최적화) */
    div.stButton > button {
        background: #ffffff !important;
        color: #0f766e !important;
        border: 1px solid #14b8a6 !important;
        border-radius: 18px !important;
        padding: 0.35rem 0.5rem !important;
        font-size: 0.8rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 5px rgba(15, 118, 110, 0.05) !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block !important;
        margin: 0 auto !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #0f766e 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border-color: transparent !important;
        box-shadow: 0 6px 18px rgba(15, 118, 110, 0.25) !important;
        transform: translateY(-2px) !important;
    }
    div.stButton > button:active {
        transform: translateY(0) !important;
    }

    /* 하단 고정 추천 칩 컨테이너 */
    .fixed-bottom-chips-container {
        position: fixed;
        bottom: 12px;
        left: 50%;
        transform: translateX(-50%);
        width: 100%;
        max-width: 730px;
        z-index: 999990;
        padding: 0 1.2rem;
        background: transparent;
    }

    /* 입력창을 칩 바의 높이만큼 위로 올림 */
    .stChatInputContainer {
        bottom: 65px !important;
        transition: bottom 0.2s ease;
    }

    /* 모바일 반응형 최적화 미디어 쿼리 */
    @media (max-width: 640px) {
        .brand-title {
            font-size: 1.7rem;
        }
        .brand-subtitle {
            font-size: 0.88rem;
        }
        .glass-card {
            padding: 0.75rem;
            border-radius: 12px;
        }
        div.stButton > button {
            font-size: 0.75rem !important;
            padding: 0.3rem 0.4rem !important;
        }
        .fixed-bottom-chips-container {
            bottom: 8px;
            padding: 0 0.6rem;
        }
        .stChatInputContainer {
            bottom: 58px !important;
        }
    }
</style>
""", unsafe_allow_html=True)



# 🎓 대시보드 헤더 렌더링
st.markdown('<div class="brand-title">🎓 BBOYAMIN 스마트 스쿨 에이전트</div>', unsafe_allow_html=True)
st.markdown('<div class="brand-subtitle">학교알리미 공시 및 나이스(NEIS) 실시간 급식·학사일정을 한 번에 파악하는 지능형 비서입니다.</div>', unsafe_allow_html=True)

# 대화 기록 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "안녕하세요! **BBOYAMIN** 스쿨 에이전트입니다. 외대부고, 용인 성서중학교의 실시간 급식 메뉴나 학사일정을 편안하게 터치하여 질문해보세요! 😊"}
    ]

# 칩 클릭 이벤트를 받기 위한 세션 변수
if "active_query_trigger" not in st.session_state:
    st.session_state.active_query_trigger = ""

# 🍱 공용 칩 렌더링 컴포넌트 함수 정의 (가로 한 줄 4열)
def render_example_chips_ui(prefix_id):
    if prefix_id == "bottom":
        st.markdown('<div class="fixed-bottom-chips-container">', unsafe_allow_html=True)
        
    cols = st.columns(4)
    chips = st.session_state.current_chips
    
    for i in range(4):
        with cols[i]:
            label, query = chips[i]
            if st.button(label, key=f"{prefix_id}_chip_btn_{i}", use_container_width=True):
                st.session_state.active_query_trigger = query
                st.session_state.current_chips = get_random_school_chips() # 클릭 즉시 새 추천 질문으로 교체
                st.rerun()
                
    if prefix_id == "bottom":
        st.markdown('</div>', unsafe_allow_html=True)



# 💬 채팅 내역 화면에 출력
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# [하단 칩 자동 주입] 첫 페이지 진입 시점 포함, 언제나 입력창 최하단 아래에 추천 알약 버튼이 바로 보이도록 고정
render_example_chips_ui("bottom")

# ⌨️ 사용자 입력창 처리
user_input = st.chat_input("질문을 작성해 보세요... (예: 외대부고 급식)")

# 칩 클릭 상태이거나 사용자가 직접 타이핑해서 엔터를 친 경우
active_query = None
if user_input:
    active_query = user_input
    st.session_state.active_query_trigger = "" # 덮어쓰기 초기화
elif st.session_state.active_query_trigger:
    active_query = st.session_state.active_query_trigger
    st.session_state.active_query_trigger = "" # 사용 후 초기화



if active_query:
    # 1. 사용자 질문을 화면에 띄우고 세션에 저장
    with st.chat_message("user"):
        st.markdown(active_query)
    st.session_state.chat_history.append({"role": "user", "content": active_query})
    
    # 2. AI 응답 생성 (에이전틱 툴 연쇄 호출 루프 작동)
    with st.chat_message("assistant"):
        with st.spinner("학교 정보 분석 및 실시간 데이터 조회 중..."):
            
            headers = {
                "Authorization": f"Bearer {FACTCHAT_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # BBOYAMIN님 맞춤형 초고성능 프리미엄 시각적 포맷 가이드를 강제하는 시스템 프롬프트 주입
            system_instruction = (
                "너는 최고의 스마트 스쿨 비서인 'BBOYAMIN 스마트 스쿨 에이전트'이다.\n\n"
                "답변을 작성할 때 가독성을 극적으로 끌어올려 BBOYAMIN님이 한눈에 파악할 수 있도록 반드시 다음 규칙을 절대적으로 준수해라:\n"
                "1. **표(Table) 형식의 적극적인 활용**: 식단 메뉴, 요일별 급식, 학사 일정(날짜와 행사명), 통계 데이터 등은 가급적 마크다운 표(Table)를 짜서 구조적으로 정렬하여 나타낼 것.\n"
                "2. **굵은 강조와 이모지**: 주요 시험 기간, 방학식/개학식 날짜, 특이사항, 칼로리 정보 등 핵심 정보는 글씨를 **굵게 강조**하고 내용에 알맞은 시각적 이모지(🍱, 📅, 📊, 🌾, 🏫 등)를 풍성하게 붙여라.\n"
                "3. **구분선과 문단 쪼개기**: 답변이 긴 경우 반드시 가로 구분선(---)과 소제목(### 🍱 최근 급식 정보 등)을 사용하여 챕터를 읽기 좋게 끊어서 제공해라.\n"
                "4. **완결성**: 대화의 흐름에 맞추어 전문적이고 신뢰감 넘치며 친근하게 답해라."
            )
            
            api_messages = [{"role": "system", "content": system_instruction}]
            for chat in st.session_state.chat_history:
                if chat["role"] in ["user", "assistant"]:
                    api_messages.append({"role": chat["role"], "content": chat["content"]})
            
            try:
                # 에이전틱 루핑 에이전트 시작 (최대 5회 연속 툴 호출 지원)
                max_iterations = 5
                iteration = 0
                current_messages = api_messages.copy()
                
                while iteration < max_iterations:
                    iteration += 1
                    
                    payload = {
                        "model": "gpt-5.4",
                        "messages": current_messages,
                        "tools": tools_schema if tools_schema else None,
                        "tool_choice": "auto" if tools_schema else None,
                        "temperature": 0.2
                    }
                    
                    response = requests.post(
                        f"{FACTCHAT_BASE_URL}/chat/completions",
                        headers=headers,
                        json=payload,
                        verify=False,
                        timeout=35
                    )
                    response.raise_for_status()
                    response_json = response.json()
                    ai_message = response_json['choices'][0]['message']
                    
                    # OpenAI / FactChat Gateway 규격 준수를 위한 클린업
                    clean_ai_message = {
                        "role": "assistant",
                        "content": ai_message.get("content") or ""
                    }
                    if ai_message.get("tool_calls"):
                        clean_ai_message["tool_calls"] = ai_message["tool_calls"]
                        
                    current_messages.append(clean_ai_message)
                    
                    # AI가 도구 실행을 명한 경우
                    if ai_message.get('tool_calls'):
                        tool_calls = ai_message['tool_calls']
                        
                        # 지시받은 모든 툴 콜(병렬 툴 포함)을 누수 없이 전량 순차적으로 처리하여 제출
                        total_calls = len(tool_calls)
                        for idx, tool_call in enumerate(tool_calls):
                            function_name = tool_call['function']['name']
                            function_args = json.loads(tool_call['function']['arguments'])
                            
                            # 병렬 호출일 경우 서브 번호(예: 2-1단계, 2-2단계)를 부착해 중복 오해 불식 및 가시성 극대화
                            step_label = f"{iteration}-{idx + 1}" if total_calls > 1 else f"{iteration}"
                            
                            st.info(f"🎓 **[도구 실행 ({step_label}단계)]** 에이전트가 데이터를 조회합니다.\n"
                                    f"- 실행 도구: `{function_name}`\n"
                                    f"- 입력 인자: `{json.dumps(function_args, ensure_ascii=False)}`")
                            
                            # 실제 schoolinfo-mcp 툴 가동하여 실행
                            mcp_result = execute_mcp_tool(
                                tool_name=function_name,
                                arguments=function_args
                            )
                            
                            # 실행 결과를 히스토리에 얹어 1:1 매핑 유지
                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": function_name,
                                "content": mcp_result
                            })
                    else:
                        # 더 이상의 도구 실행 지시가 없는 최종 일반 답변 완성 시 루프 종료
                        final_response = ai_message['content']
                        st.markdown(final_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                        st.rerun() # 🌟 답변 출력 완료 즉시 렌더링을 갱신하여 최하단 입력창 아래에 칩 바가 정돈되어 노출되도록 함!
                        break
                        
            except Exception as e:
                # 400 에러 등의 예외가 났을 때 화면 크래시를 내지 않고 챗봇 말풍선으로 안전하게 오류를 반환하여 복구
                err_text = f"⚠️ **연동 중 일시적 오류가 발생했습니다.** (사유: {e})\n\n잠시 후 다시 질문해 주시거나 검색 방식을 간결하게 시도해 주시기 바랍니다."
                st.markdown(err_text)
                st.session_state.chat_history.append({"role": "assistant", "content": err_text})
                import traceback
                traceback.print_exc()
