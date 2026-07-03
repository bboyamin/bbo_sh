import os
import requests
import urllib3
from dotenv import load_dotenv

# SSL 경고 비활성화 (사내망 연동 시 필요할 수 있음)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수 로드
load_dotenv()

FACTCHAT_API_KEY = os.getenv("FACTCHAT_API_KEY")
FACTCHAT_BASE_URL = os.getenv("FACTCHAT_BASE_URL")

class FactChatClient:
    """
    사내 FactChat API Gateway 클라이언트 래퍼 클래스
    """
    def __init__(self):
        if not FACTCHAT_API_KEY:
            raise ValueError("FACTCHAT_API_KEY가 .env 파일에 설정되지 않았습니다.")
        self.api_key = FACTCHAT_API_KEY
        self.base_url = FACTCHAT_BASE_URL or "https://factchat-cloud.mindlogic.ai/v1/gateway"

    def ask_gpt(self, prompt: str, system_prompt: str = "You are a helpful assistant.", temperature: float = 0.3) -> str:
        """
        OpenAI 규격(gpt-5.4 등) 모델 호출 함수
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-5.4", # 필요시 gpt-5.5 등으로 변경 가능
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }

        try:
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=15)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"GPT 호출 실패: {e}"

    def ask_claude(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        """
        Anthropic 규격(claude-sonnet-4-5-20250929 등) 모델 호출 함수
        """
        # Anthropic 전용 엔드포인트
        url = "https://factchat-cloud.mindlogic.ai/v1/api/anthropic/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "claude-sonnet-4-5-20250929", # 사용 가능한 claude 모델 지정
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        # 시스템 프롬프트가 주어진 경우 payload에 추가
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=15)
            response.raise_for_status()
            return response.json()['content'][0]['text'].strip()
        except Exception as e:
            return f"Claude 호출 실패: {e}"

# --- 테스트 실행 영역 ---
if __name__ == "__main__":
    print("🚀 FactChat API 클라이언트 초기화 중...")
    try:
        client = FactChatClient()
        print("✅ 클라이언트 초기화 성공!")
        print("-" * 40)
        
        # 1. GPT-5.4 테스트
        print("[테스트 1] GPT-5.4 모델 호출 중...")
        gpt_response = client.ask_gpt("사내 AI 에이전트 뼈대 프로젝트 연결에 성공했어! 축하의 한마디 해줘.")
        print(f"🤖 GPT-5.4 응답:\n{gpt_response}\n")
        print("-" * 40)
        
        # 2. Claude Sonnet 테스트
        print("[테스트 2] Claude Sonnet 모델 호출 중...")
        claude_response = client.ask_claude("사내 AI 에이전트 뼈대 프로젝트 연결에 성공했어! 축하의 한마디 해줘.")
        print(f"🎨 Claude 응답:\n{claude_response}\n")
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ 초기화 에러: {e}")
