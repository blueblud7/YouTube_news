import os
import json
from dotenv import load_dotenv

# .env.local 파일에서 환경 변수를 로드합니다.
# .env.local 파일이 없다면 .env 파일을 찾습니다.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env.local')
if not os.path.exists(dotenv_path):
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

load_dotenv(dotenv_path=dotenv_path)

# 구성 파일 경로
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "youtube_news_config.json")

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("경고: OpenAI API 키가 .env.local 또는 .env 파일에 설정되어 있지 않습니다.")

def load_config():
    """구성 파일을 로드합니다."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"경고: 구성 파일 {CONFIG_FILE}을 읽는 중 오류가 발생했습니다. 기본 구성을 사용합니다.")
    
    # 기본 구성 반환
    default_config = {
        "channels": [],
        "keywords": [],
        "schedule_interval": 24,  # 시간 단위
        "last_run": None
    }
    save_config(default_config)
    return default_config

def save_config(config):
    """구성 파일을 저장합니다."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_openai_api_key():
    """OpenAI API 키를 반환합니다."""
    if not OPENAI_API_KEY:
        # 실제 운영 환경에서는 로깅 또는 더 강력한 오류 처리가 필요합니다.
        print("오류: OpenAI API 키가 설정되어 있지 않습니다.")
        return None
    return OPENAI_API_KEY

if __name__ == '__main__':
    # 테스트용: 로드된 키 출력
    print(f".env 파일 경로: {dotenv_path}")
    print(f".env 파일 존재 여부: {os.path.exists(dotenv_path)}")
    print(f"OpenAI API 키 (get_openai_api_key()): {get_openai_api_key() if OPENAI_API_KEY else '없음'}")
    
    # 구성 파일 테스트
    config = load_config()
    print(f"구성 파일 내용: {config}") 