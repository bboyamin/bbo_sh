import os
import json
import requests
import urllib3
from dotenv import load_dotenv

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# .env 환경 변수 로드
load_dotenv()
FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

# ===================================================
# 1단계: 파이썬이 실행할 "진짜 복지 자격 조회" 함수 선언
# ===================================================
def check_welfare_eligibility(age: int, region: str, is_employed: bool, children_count: int) -> list:
    """
    민원인의 세부 조건(나이, 거주지역, 직업여부, 자녀수)을 판별하여 
    신청 가능한 복지 서비스를 리스트로 반환하는 진짜 함수입니다.
    """
    print(f"\n[파이썬 시스템] ⚙️ 복지 조회 함수가 호출되었습니다.")
    print(f"[파이썬 시스템] ⚙️ 입력 데이터 -> 나이: {age}세, 지역: '{region}', 직업여부: {is_employed}, 자녀수: {children_count}명")
    
    eligible_benefits = []

    # 1. 어르신 무상 교통카드 조건 체크 (만 65세 이상, 서울 거주)
    if age >= 65 and "서울" in region:
        eligible_benefits.append({
            "혜택명": "어르신 무상 교통카드 지원",
            "내용": "서울시에 거주하는 만 65세 이상 어르신에게 지하철 무임승차가 가능한 우대용 교통카드를 발급합니다."
        })

    # 2. 청년 희망 저축통장 조건 체크 (만 19세~34세, 근로 중)
    if 19 <= age <= 34 and is_employed:
        eligible_benefits.append({
            "혜택명": "청년 희망 저축통장 지원",
            "내용": "근로 중인 청년의 자산 형성을 돕기 위해, 저축액에 상응하는 정부 지원금을 추가 매칭 적립해 드립니다."
        })

    # 3. 다자녀 양육 수당 지원 조건 체크 (자녀 2명 이상)
    if children_count >= 2:
        eligible_benefits.append({
            "혜택명": "다자녀 양육 수당 지원",
            "내용": "자녀가 2명 이상인 다자녀 가구를 대상으로 매월 일정 금액의 보육 및 양육 수당을 지급합니다."
        })

    print(f"[파이썬 시스템] ⚙️ 조회 결과: 총 {len(eligible_benefits)}건의 혜택이 검색되었습니다.\n")
    return eligible_benefits

# ===================================================
# 2단계: AI에게 넘겨줄 "도구 설명서" 작성 (여러 타입 포함)
# ===================================================
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "check_welfare_eligibility",
            "description": "사용자의 인적 사항(나이, 거주 지역, 근로 여부, 자녀 수)을 바탕으로 현재 신청 가능한 맞춤형 행정 복지 혜택 목록을 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "age": {
                        "type": "integer",
                        "description": "민원인의 만 나이 (예: 29)"
                    },
                    "region": {
                        "type": "string",
                        "description": "민원인의 거주 행정 지역명 (예: 서울, 경기도, 부산 등)"
                    },
                    "is_employed": {
                        "type": "boolean",
                        "description": "민원인이 현재 직장에 다니거나 근로 중인지 여부 (True 또는 False)"
                    },
                    "children_count": {
                        "type": "integer",
                        "description": "민원인의 자녀 수 (자녀가 없으면 0)"
                    }
                },
                "required": ["age", "region", "is_employed", "children_count"]
            }
        }
    }
]

# ==========================================
# 3단계: 메인 실행 흐름 (AI와 대화)
# ==========================================
def run_welfare_bot():
    headers = {
        "Authorization": f"Bearer {FACTCHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 민원인의 복잡한 실전 질문
    user_question = "안녕하세요. 저는 올해 29살이고 현재 서울에서 회사에 다니고 있습니다. 아직 아이는 없는데 제가 신청할 수 있는 정부 지원 혜택이 있을까요?"
    
    print(f"👤 민원인: \"{user_question}\"")
    
    messages = [
        {"role": "user", "content": user_question}
    ]
    
    # 1차 호출: AI에게 도구 설명서와 함께 질문 전달
    print("\n🤖 [1차 호출] AI에게 민원인 질문 분석과 도구 조회를 요청하는 중...")
    payload = {
        "model": "gpt-5.4",
        "messages": messages,
        "tools": tools_schema,
        "tool_choice": "auto",
        "temperature": 0.1
    }
    
    response = requests.post(
        f"{FACTCHAT_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        verify=False,
        timeout=15
    )
    response.raise_for_status()
    response_json = response.json()
    
    ai_message = response_json['choices'][0]['message']
    
    # AI가 도구 실행을 감지했는지 확인 (None이거나 비어있지 않은지 검사)
    if ai_message.get('tool_calls'):
        tool_call = ai_message['tool_calls'][0]
        function_name = tool_call['function']['name']
        
        # AI가 추출한 파라미터 해석
        function_args = json.loads(tool_call['function']['arguments'])
        
        print(f"👉 AI 분석 완료! 도구 실행 필요 판정:")
        print(f"   - 호출할 도구: {function_name}")
        print(f"   - 분석된 파라미터: {json.dumps(function_args, ensure_ascii=False)}")
        
        # 파이썬에서 진짜 복지 자격 조회 실행
        if function_name == "check_welfare_eligibility":
            # AI가 문자열에서 파싱해 준 안전한 변수들
            age_val = function_args.get("age")
            region_val = function_args.get("region")
            is_employed_val = function_args.get("is_employed")
            children_count_val = function_args.get("children_count")
            
            # 실제 파이썬 함수 실행
            welfare_results = check_welfare_eligibility(
                age=age_val,
                region=region_val,
                is_employed=is_employed_val,
                children_count=children_count_val
            )
            
            # 대화 기록에 누적
            messages.append(ai_message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": json.dumps(welfare_results, ensure_ascii=False)  # JSON 형태의 검색 결과 전달
            })
            
            # 2차 호출: 최종 결과 조합 요청
            print("🤖 [2차 호출] 복지 혜택 조회 데이터를 AI에게 전달하여 최종 답변 생성을 요청하는 중...")
            payload_2 = {
                "model": "gpt-5.4",
                "messages": messages,
                "temperature": 0.3
            }
            
            response_2 = requests.post(
                f"{FACTCHAT_BASE_URL}/chat/completions",
                headers=headers,
                json=payload_2,
                verify=False,
                timeout=15
            )
            response_2.raise_for_status()
            final_response = response_2.json()['choices'][0]['message']['content']
            
            print(f"\n🤖 AI 최종 안내 답변:\n{final_response}")
    else:
        print(f"\n🤖 AI 답변: \"{ai_message['content']}\"")

if __name__ == "__main__":
    if not FACTCHAT_API_KEY:
        print("❌ 에러: FACTCHAT_API_KEY가 .env에 없습니다.")
    else:
        run_welfare_bot()
