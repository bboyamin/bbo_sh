import os
import json
import requests
import urllib3
from dotenv import load_dotenv

# SSL 경고 비활성화 (사내망 연동 시 필요)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# .env 환경 변수 로드
load_dotenv()
FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL") or "https://factchat-cloud.mindlogic.ai/v1/gateway"

# ==========================================
# 1단계: 파이썬이 실행할 "진짜 도구(함수)" 선언
# ==========================================
def get_office_phone_number(department: str) -> str:
    """
    파이썬이 실제로 내부 딕셔너리에서 전화번호를 조회하는 진짜 함수입니다.
    """
    phone_book = {
        "홍보과": "02-123-4567",
        "복지과": "02-765-4321",
        "행정지원과": "02-999-8888"
    }
    print(f"\n[파이썬 시스템] ⚙️ 진짜 함수가 호출되었습니다. 입력값(부서): '{department}'")
    result = phone_book.get(department, "등록되지 않은 부서입니다.")
    print(f"[파이썬 시스템] ⚙️ 진짜 함수 실행 결과 반환: '{result}'\n")
    return result

# ==========================================
# 2단계: AI에게 넘겨줄 "도구 설명서" 작성
# ==========================================
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_office_phone_number",
            "description": "지정된 행정 부서의 내선 전화번호를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "조회할 부서 이름 (예: 홍보과, 복지과, 행정지원과)"
                    }
                },
                "required": ["department"]
            }
        }
    }
]

# ==========================================
# 3단계: 메인 실행 흐름 (AI와 대화)
# ==========================================
def run_test():
    headers = {
        "Authorization": f"Bearer {FACTCHAT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. 사용자의 질문 설정
    user_question = "홍보과 전화번호 좀 알려줄래?"
    print(f"👤 사용자: \"{user_question}\"")
    
    # 대화 기록(Messages) 초기화
    messages = [
        {"role": "user", "content": user_question}
    ]
    
    # 2. 1차 API 호출: 질문과 함께 '도구 설명서(tools)'를 보냅니다.
    print("\n🤖 [1차 호출] AI에게 질문과 도구 설명서를 전달하는 중...")
    payload = {
        "model": "gpt-5.4",
        "messages": messages,
        "tools": tools_schema,     # AI에게 도구 설명서를 함께 제공!
        "tool_choice": "auto",     # AI가 알아서 도구를 쓸지 말지 결정하도록 함
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
    
    # AI가 보낸 응답 메시지 추출
    ai_message = response_json['choices'][0]['message']
    
    # 3. AI가 "도구를 사용하고 싶다"고 요청했는지 확인 (None이거나 비어있지 않은지 검사)
    if ai_message.get('tool_calls'):
        tool_call = ai_message['tool_calls'][0]
        function_name = tool_call['function']['name']
        # AI가 도구에 넣으라고 지정한 입력 파라미터 (예: {"department": "홍보과"})
        function_args = json.loads(tool_call['function']['arguments'])
        department_arg = function_args.get("department")
        
        print(f"👉 AI 판단: \"스스로는 답을 모르니 '{function_name}' 도구를 실행해야겠어! 파라미터는 '{department_arg}'로 줘.\"")
        
        # 4. 파이썬에서 진짜 함수 실행하기
        if function_name == "get_office_phone_number":
            tool_result = get_office_phone_number(department_arg)
            
            # 5. 2차 API 호출 준비
            # 대화 기록에 [AI의 도구 호출 요청]과 [진짜 파이썬이 실행한 결과]를 차례대로 누적시킵니다.
            messages.append(ai_message) # AI의 요청 추가
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": tool_result  # 진짜 파이썬이 찾은 전화번호값 전달
            })
            
            # 2차 API 호출: 이제 결과 데이터도 대화 기록에 들어있으므로, 최종 답변을 요구합니다.
            print("🤖 [2차 호출] 도구 실행 결과를 포함해 AI에게 최종 대화를 요청하는 중...")
            payload_2 = {
                "model": "gpt-5.4",
                "messages": messages,
                "temperature": 0.1
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
            
            print(f"\n🤖 AI 최종 답변: \"{final_response}\"")
    else:
        # 도구를 안 쓰고 그냥 답변했을 경우
        print(f"\n🤖 AI 답변: \"{ai_message['content']}\"")

if __name__ == "__main__":
    if not FACTCHAT_API_KEY:
        print("❌ 에러: FACTCHAT_API_KEY가 .env에 없습니다.")
    else:
        run_test()
