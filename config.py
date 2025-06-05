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

# YouTube API Keys
YOUTUBE_API_KEYS = [
    os.getenv("YOUTUBE_API_KEY"),
    os.getenv("YOUTUBE_API_KEY_2"),
    os.getenv("YOUTUBE_API_KEY_3"),
    os.getenv("YOUTUBE_API_KEY_4"),
    os.getenv("YOUTUBE_API_KEY_5"),
    os.getenv("YOUTUBE_API_KEY_6"),
    os.getenv("YOUTUBE_API_KEY_7"),
    os.getenv("YOUTUBE_API_KEY_8"),
    os.getenv("YOUTUBE_API_KEY_9"),
    os.getenv("YOUTUBE_API_KEY_10"),
    os.getenv("YOUTUBE_API_KEY_11"),
]
# None 값을 필터링하여 실제 키만 리스트에 남깁니다.
YOUTUBE_API_KEYS = [key for key in YOUTUBE_API_KEYS if key]

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not YOUTUBE_API_KEYS:
    print("경고: YouTube API 키가 .env.local 또는 .env 파일에 설정되어 있지 않습니다.")
if not OPENAI_API_KEY:
    print("경고: OpenAI API 키가 .env.local 또는 .env 파일에 설정되어 있지 않습니다.")

# 현재 사용 중인 YouTube API 키 인덱스 (키 로테이션을 위해)
# 이 값은 youtube_handler.py에서 관리될 예정입니다.
# 여기서는 단순히 첫 번째 키를 사용하도록 초기화합니다.
CURRENT_YOUTUBE_API_KEY_INDEX = 0 

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

def get_youtube_api_key():
    """
    현재 설정된 YouTube API 키를 반환합니다.
    키 로테이션 로직은 youtube_handler.py에서 처리할 예정입니다.
    """
    if not YOUTUBE_API_KEYS:
        # 실제 운영 환경에서는 로깅 또는 더 강력한 오류 처리가 필요합니다.
        print("오류: 사용 가능한 YouTube API 키가 없습니다.")
        return None
    
    # 현재는 항상 첫 번째 키를 반환하도록 되어 있으나,
    # 추후 youtube_handler에서 CURRENT_YOUTUBE_API_KEY_INDEX를 업데이트하여
    # 키를 순환시키는 로직을 구현해야 합니다.
    # 예: 실제 API 호출 시 할당량 오류가 발생하면 인덱스를 변경하고 재시도.
    # 여기서는 config 모듈이 상태를 직접 변경하기보다는,
    # youtube_handler가 키를 요청하고, 상태(인덱스)를 관리하는 것이 더 적절할 수 있습니다.
    # 또는, 이 함수 자체가 로테이션 로직을 포함할 수도 있습니다.
    # 지금은 가장 단순한 형태로, 첫 번째 유효한 키 또는 현재 인덱스의 키를 반환합니다.
    
    # 이 예시에서는 CURRENT_YOUTUBE_API_KEY_INDEX를 직접 사용하지 않고,
    # youtube_handler가 키 리스트(YOUTUBE_API_KEYS)를 직접 참조하고
    # 자체적으로 인덱스를 관리하도록 설계하는 것이 더 나을 수 있습니다.
    # 우선은 첫 번째 키를 반환하거나, config 내의 인덱스를 사용하는 간단한 형태로 둡니다.
    # 하지만 이 인덱스는 외부에서 변경 가능해야 합니다.
    
    # 전역 변수를 수정하는 대신, 이 함수는 단순히 현재 인덱스의 키를 반환하고,
    # 인덱스 관리는 이 함수를 호출하는 쪽(youtube_handler)에서 담당하도록 합니다.
    # 또는, 이 함수가 호출될 때마다 다음 키를 반환하도록 상태를 가질 수도 있습니다.
    # 사용자 요구사항은 "할당량을 다 쓰면 다음 키를 사용하는 것"이므로,
    # 키를 제공하는 중앙 지점에서 순환 및 상태 관리가 필요합니다.

    # 현재 구현에서는 config.py가 직접 키 인덱스를 변경하지 않습니다.
    # youtube_handler.py에서 YOUTUBE_API_KEYS 리스트와 CURRENT_YOUTUBE_API_KEY_INDEX를
    # 직접 참조하거나, 이들을 관리하는 별도의 클래스/객체를 사용하는 것이 좋습니다.
    # 임시로, 현재 인덱스에 해당하는 키를 반환하는 형태로 두겠습니다.
    # 실제 키 순환 로직은 youtube_handler에서 구현됩니다.
    if CURRENT_YOUTUBE_API_KEY_INDEX < len(YOUTUBE_API_KEYS):
        return YOUTUBE_API_KEYS[CURRENT_YOUTUBE_API_KEY_INDEX]
    else:
        # 이 경우는 모든 키를 시도했거나 인덱스가 잘못된 경우입니다.
        # youtube_handler에서 이 상황을 처리해야 합니다.
        print("오류: 유효한 YouTube API 키 인덱스를 벗어났습니다.")
        return None


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
    print(f"로드된 YouTube API 키 개수: {len(YOUTUBE_API_KEYS)}")
    
    # YOUTUBE_API_KEYS 리스트가 비어있지 않은 경우에만 키 정보 출력
    if YOUTUBE_API_KEYS:
        print(f"사용 가능한 모든 YouTube API 키: {YOUTUBE_API_KEYS}")
        # get_youtube_api_key() 함수 테스트
        # 이 테스트는 CURRENT_YOUTUBE_API_KEY_INDEX의 초기값(0)에 따라 첫 번째 키를 보여줍니다.
        print(f"현재 선택된 YouTube API 키 (get_youtube_api_key()): {get_youtube_api_key()}")
    else:
        print("사용 가능한 YouTube API 키가 없습니다.")
        
    print(f"OpenAI API 키 (get_openai_api_key()): {get_openai_api_key() if OPENAI_API_KEY else '없음'}")
    
    # 구성 파일 테스트
    config = load_config()
    print(f"구성 파일 내용: {config}") 