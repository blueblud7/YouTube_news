import os
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.exceptions import DefaultCredentialsError
import re

# config.py에서 API 키 리스트와 현재 키 인덱스를 가져옵니다.
# config.py를 직접 수정하는 대신, 키 관리 로직을 이 핸들러 내에 구현합니다.
try:
    from config import YOUTUBE_API_KEYS
except ImportError:
    print("오류: config.py 파일을 찾을 수 없거나 YOUTUBE_API_KEYS를 가져올 수 없습니다.")
    YOUTUBE_API_KEYS = []

if not YOUTUBE_API_KEYS:
    print("경고: youtube_handler.py에서 사용할 YouTube API 키가 로드되지 않았습니다.")

# 현재 사용 중인 YouTube API 키 인덱스
# 이 변수는 youtube_handler 모듈 내에서 관리됩니다.
current_api_key_index = 0
youtube_service = None

def get_youtube_service():
    """
    YouTube API 서비스 클라이언트를 반환합니다.
    API 키 할당량 초과 시 자동으로 다음 키로 전환합니다.
    사용 가능한 모든 키를 소진하면 None을 반환합니다.
    """
    global current_api_key_index
    global youtube_service

    if not YOUTUBE_API_KEYS:
        print("오류: 사용 가능한 YouTube API 키가 없습니다.")
        return None

    for i in range(len(YOUTUBE_API_KEYS)):
        api_key_to_try = YOUTUBE_API_KEYS[current_api_key_index]
        try:
            print(f"YouTube API 키 ({current_api_key_index + 1}/{len(YOUTUBE_API_KEYS)})로 서비스 빌드 시도: ...{api_key_to_try[-6:]}")
            service = googleapiclient.discovery.build(
                "youtube", "v3", developerKey=api_key_to_try
            )
            print(f"YouTube API 서비스가 성공적으로 빌드되었습니다. (키: ...{api_key_to_try[-6:]})")
            youtube_service = service
            return youtube_service
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 403: # Forbidden
                error_details = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
                reason = e.resp_reason if hasattr(e, 'resp_reason') else str(e)
                if 'quotaExceeded' in error_details or 'dailyLimitExceeded' in error_details or \
                   'keyInvalid' in error_details or 'keyExpired' in error_details or \
                   'disabledPermissions' in error_details or 'accessNotConfigured' in error_details:
                    print(f"API 키 ({current_api_key_index + 1}) 할당량 초과, 유효하지 않음 또는 권한 문제: {reason} - {error_details}")
                    current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS)
                    print(f"다음 API 키 ({current_api_key_index + 1})로 전환합니다.")
                    if i == len(YOUTUBE_API_KEYS) - 1: # 모든 키를 시도했음
                        print("오류: 모든 YouTube API 키의 할당량이 초과되었거나 유효하지 않습니다.")
                        youtube_service = None
                        return None
                    continue # 다음 키로 재시도
            print(f"YouTube API 서비스 빌드 중 HttpError 발생 (키 인덱스: {current_api_key_index}): {e}")
            # 다른 HttpError의 경우에도 다음 키로 넘어갈지, 아니면 에러를 발생시킬지 결정 필요
            # 여기서는 우선 다음 키로 넘어가도록 처리
            current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS)
            if i == len(YOUTUBE_API_KEYS) - 1:
                print("오류: 모든 YouTube API 키 시도 후에도 서비스 빌드 실패 (HttpError).")
                youtube_service = None
                return None
        except DefaultCredentialsError:
            # 이 에러는 보통 API 키가 아닌 다른 인증 방식 문제일 때 발생하나, 키 관련 문제일 수도 있음
            print(f"API 키 ({current_api_key_index + 1}) 관련 DefaultCredentialsError 발생. 다음 키로 전환합니다.")
            current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS)
            if i == len(YOUTUBE_API_KEYS) - 1:
                print("오류: 모든 YouTube API 키 시도 후에도 서비스 빌드 실패 (DefaultCredentialsError).")
                youtube_service = None
                return None
        except Exception as e:
            print(f"YouTube API 서비스 빌드 중 예상치 못한 오류 발생 (키 인덱스: {current_api_key_index}): {e}")
            current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS) # 일단 다음 키로
            if i == len(YOUTUBE_API_KEYS) - 1:
                print("오류: 모든 YouTube API 키 시도 후에도 서비스 빌드 실패 (일반 오류).")
                youtube_service = None
                return None
    
    print("오류: YouTube API 서비스 클라이언트를 생성할 수 없습니다 (모든 키 시도 실패).")
    youtube_service = None
    return None

def get_channel_info_by_handle(handle: str):
    """
    YouTube 채널 핸들(@)을 사용하여 채널 정보를 가져옵니다.
    (예: '@Understanding')
    """
    service = get_youtube_service()
    if not service:
        return None

    # 핸들 앞의 '@' 제거
    clean_handle = handle[1:] if handle.startswith('@') else handle

    try:
        # 핸들을 사용하여 채널 검색 (YouTube API v3에는 직접적인 forHandle 파라미터가 없음)
        # search.list를 사용하여 채널 타입으로 검색하고, customUrl 또는 title을 비교.
        # 또는 channels.list에 id 대신 다른 식별자를 사용할 수 있는지 확인 필요.
        # 현재 API 문서를 기준으로, search가 핸들에 가장 가까운 접근 방식.
        
        # Channels: list API는 `forUsername` 파라미터가 있었지만 deprecated 되었고,
        # `id` 또는 `managedByMe`만 받습니다. 핸들 직접 조회는 아직 없는 것으로 보입니다.
        # 따라서, 검색을 통해 채널을 찾고 핸들과 비교하는 방식이 현재로선 최선.
        search_response = service.search().list(
            q=clean_handle, # 순수 핸들 문자열로 검색
            part="snippet",
            type="channel",
            maxResults=5 # 정확도를 위해 여러 개를 가져와 비교할 수 있음
        ).execute()

        if not search_response.get("items"):
            print(f"핸들 '{handle}'에 대한 검색 결과가 없습니다.")
            return None

        for item in search_response.get("items", []):
            channel_id = item["snippet"]["channelId"]
            # 채널 ID로 상세 정보 조회 (customUrl 등을 얻기 위해)
            channel_details_response = service.channels().list(
                part="snippet,statistics,brandingSettings", # brandingSettings.channel.customUrl은 없음. snippet.customUrl 확인
                id=channel_id
            ).execute()

            if channel_details_response.get("items"):
                channel_data = channel_details_response["items"][0]["snippet"]
                channel_stats = channel_details_response["items"][0].get("statistics", {})
                
                retrieved_custom_url = channel_data.get("customUrl") # @가 붙어 있을 수 있음
                retrieved_title = channel_data.get("title")

                # print(f"검색된 채널 후보: title='{retrieved_title}', customUrl='{retrieved_custom_url}', ID='{channel_id}'")

                # 핸들과 customUrl 비교 (customUrl은 @를 포함할 수 있음)
                # customUrl은 유저가 설정한 URL이므로, 핸들과 다를 수도 있음.
                # 핸들은 시스템에 의해 유니크하게 부여되는 것에 가까움.
                # API 응답의 snippet.customUrl이 핸들 형식(@handle)인지 확인
                if retrieved_custom_url and (retrieved_custom_url.lower() == handle.lower() or retrieved_custom_url.lower() == f"@{clean_handle}".lower()):
                    print(f"핸들 '{handle}'과 customUrl '{retrieved_custom_url}'이 일치하는 채널을 찾았습니다.")
                    return {
                        "type": "channel",
                        "id": channel_id,
                        "title": retrieved_title,
                        "description": channel_data.get("description"),
                        "custom_url": retrieved_custom_url, # API가 제공하는 customUrl
                        "handle_used": handle, # 사용자가 입력한 핸들
                        "subscriber_count": channel_stats.get("subscriberCount"),
                        "video_count": channel_stats.get("videoCount"),
                        "published_at": channel_data.get("publishedAt")
                    }
        
        # 정확한 customUrl 매칭이 안된 경우, 검색 결과 중 제목이 유사한 것을 고려
        # 또는, 사용자가 요청한 '@언더스탠딩'의 경우, customUrl이 '@underst裵ndingnews' 일 수도 있음
        # 첫번째 결과가 가장 관련성 높을 가능성이 큼
        if search_response.get("items"):
            print(f"핸들 '{handle}'과 정확히 일치하는 customUrl을 가진 채널을 찾지 못했습니다. 가장 유사한 검색 결과를 반환합니다.")
            first_item_channel_id = search_response.get("items")[0]["snippet"]["channelId"]
            
            # 첫번째 검색 결과의 상세 정보 다시 조회
            channel_details_response = service.channels().list(
                part="snippet,statistics",
                id=first_item_channel_id
            ).execute()

            if channel_details_response.get("items"):
                channel_data = channel_details_response["items"][0]["snippet"]
                channel_stats = channel_details_response["items"][0].get("statistics", {})
                return {
                    "type": "channel",
                    "id": first_item_channel_id,
                    "title": channel_data.get("title"),
                    "description": channel_data.get("description"),
                    "custom_url": channel_data.get("customUrl"),
                    "handle_used": handle,
                    "subscriber_count": channel_stats.get("subscriberCount"),
                    "video_count": channel_stats.get("videoCount"),
                    "published_at": channel_data.get("publishedAt")
                }
        
        print(f"핸들 '{handle}'에 해당하는 채널을 최종적으로 찾지 못했습니다.")
        return None

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"채널 정보 조회 중 HttpError 발생 (핸들: {handle}): {e} - {error_content}")
        if e.resp.status == 403 and ('quotaExceeded' in error_content or 'dailyLimitExceeded' in error_content):
            print("할당량 초과로 채널 정보 조회 실패. 다음 키로 시도해야 합니다.")
            # get_youtube_service()가 다음 호출 시 자동으로 키를 변경할 것임.
            # 이 함수를 재귀적으로 호출하거나, 호출하는 쪽에서 재시도 로직을 넣어야 함.
            # 여기서는 일단 None 반환.
        return None
    except Exception as e:
        print(f"채널 정보 조회 중 예상치 못한 오류 발생 (핸들: {handle}): {e}")
        return None


def search_videos_by_keyword(keyword: str, channel_id: str = None, max_results=15):
    """
    키워드로 동영상을 검색합니다. 특정 채널 내에서 검색할 수도 있습니다.
    max_results: 최대 검색 결과 수 (기본값 15)
    """
    service = get_youtube_service()
    if not service:
        return None
    try:
        search_params = {
            'q': keyword,
            'part': "snippet",
            'type': "video",
            'maxResults': max_results,
            'order': 'date'  # 날짜순으로 정렬하여 최신 영상부터 가져옵니다
        }
        if channel_id:
            search_params['channelId'] = channel_id
            print(f"채널 ID '{channel_id}' 내에서 키워드 '{keyword}'로 동영상 검색 중...")
        else:
            print(f"키워드 '{keyword}'로 전체 동영상 검색 중...")

        search_response = service.search().list(**search_params).execute()

        videos = []
        for item in search_response.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_id": item["snippet"]["channelId"], # 검색 결과에서 채널 ID도 가져옴
                "channel_title": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"]
            })
        print(f"키워드 '{keyword}' (채널 ID: {channel_id if channel_id else '전체'})로 {len(videos)}개의 동영상 검색됨.")
        return videos
    except googleapiclient.errors.HttpError as e:
        print(f"동영상 검색 중 HttpError 발생 (키워드: {keyword}): {e}")
        return None
    except Exception as e:
        print(f"동영상 검색 중 예상치 못한 오류 발생 (키워드: {keyword}): {e}")
        return None

def get_info_by_url(url: str):
    """
    YouTube URL (채널 또는 비디오)을 분석하여 정보를 가져옵니다.
    Fallback 로직: 전체 정보 조회 실패 시 snippet만으로 재시도합니다.
    """
    global current_api_key_index
    from urllib.parse import urlparse, parse_qs

    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    try:
        # YouTube 핸들 URL (@username)
        if '@' in url and ('channel' not in url and 'user' not in url and 'c/' not in url):
            if len(path_parts) > 0 and path_parts[0].startswith('@'):
                handle = path_parts[0]  # URL의 첫번째 경로가 핸들
                print(f"URL에서 채널 핸들 추출: {handle}")
                return get_channel_info_by_handle(handle)
            else:
                # URL에서 @username 형식 찾기
                for part in url.split('/'):
                    if part.startswith('@'):
                        handle = part
                        print(f"URL에서 채널 핸들 추출: {handle}")
                        return get_channel_info_by_handle(handle)
        
        # YouTube 채널 URL (채널 ID)
        elif 'youtube.com/channel/' in url:
            channel_id = path_parts[1] if len(path_parts) > 1 else None
            if channel_id:
                print(f"URL에서 채널 ID 추출: {channel_id}")
                service = get_youtube_service()
                if not service:
                    return None
                
                channel_response = service.channels().list(
                    part="snippet,statistics",
                    id=channel_id
                ).execute()
                
                if channel_response.get("items"):
                    channel_data = channel_response["items"][0]["snippet"]
                    channel_stats = channel_response["items"][0].get("statistics", {})
                    return {
                        "type": "channel",
                        "id": channel_id,
                        "title": channel_data.get("title"),
                        "description": channel_data.get("description"),
                        "custom_url": channel_data.get("customUrl"),
                        "subscriber_count": channel_stats.get("subscriberCount"),
                        "video_count": channel_stats.get("videoCount"),
                        "published_at": channel_data.get("publishedAt")
                    }
        
        # YouTube 사용자 URL (레거시 유형)
        elif 'youtube.com/user/' in url or 'youtube.com/c/' in url:
            username = path_parts[1] if len(path_parts) > 1 else None
            if username:
                print(f"URL에서 사용자명 추출: {username}")
                # 사용자명으로 채널 검색
                service = get_youtube_service()
                if not service:
                    return None
                
                search_response = service.search().list(
                    part="snippet",
                    q=username,
                    type="channel",
                    maxResults=1
                ).execute()
                
                if search_response.get("items"):
                    channel_id = search_response["items"][0]["snippet"]["channelId"]
                    channel_response = service.channels().list(
                        part="snippet,statistics",
                        id=channel_id
                    ).execute()
                    
                    if channel_response.get("items"):
                        channel_data = channel_response["items"][0]["snippet"]
                        channel_stats = channel_response["items"][0].get("statistics", {})
                        return {
                            "type": "channel",
                            "id": channel_id,
                            "title": channel_data.get("title"),
                            "description": channel_data.get("description"),
                            "custom_url": channel_data.get("customUrl"),
                            "subscriber_count": channel_stats.get("subscriberCount"),
                            "video_count": channel_stats.get("videoCount"),
                            "published_at": channel_data.get("publishedAt")
                        }
        
        # YouTube 비디오 URL (watch?v=VIDEO_ID)
        elif 'youtube.com/watch' in url:
            query = parse_qs(parsed_url.query)
            video_id = query.get('v', [''])[0]
            if video_id:
                print(f"URL에서 비디오 ID 추출: {video_id} (watch)")
                return get_video_info(video_id)
        
        # YouTube 단축 URL (youtu.be/VIDEO_ID)
        elif 'youtu.be/' in url:
            video_id = path_parts[0] if path_parts else None
            if video_id:
                print(f"단축 URL에서 비디오 ID 추출: {video_id}")
                return get_video_info(video_id)
                
        # YouTube 쇼츠 URL (youtube.com/shorts/VIDEO_ID)
        elif 'youtube.com/shorts/' in url:
            video_id = path_parts[1] if len(path_parts) > 1 else None
            if video_id:
                print(f"쇼츠 URL에서 비디오 ID 추출: {video_id}")
                return get_video_info(video_id)
                
        # YouTube 임베드 URL (youtube.com/embed/VIDEO_ID)
        elif 'youtube.com/embed/' in url:
            video_id = path_parts[1] if len(path_parts) > 1 else None
            if video_id:
                print(f"임베드 URL에서 비디오 ID 추출: {video_id}")
                return get_video_info(video_id)
                
        print(f"URL '{url}'을 분석할 수 없거나 지원하지 않는 형식입니다.")
        return None
    
    except Exception as e:
        print(f"URL 분석 중 오류 발생: {e}")
        return None

def extract_video_id(url: str) -> str:
    """
    YouTube URL에서 비디오 ID를 추출합니다.
    다양한 형식의 URL을 지원합니다:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    """
    from urllib.parse import urlparse, parse_qs
    
    if not url:
        raise ValueError("URL이 비어 있습니다")
    
    parsed_url = urlparse(url)
    
    # youtube.com/watch?v=VIDEO_ID 형식
    if "youtube.com/watch" in url:
        query = parse_qs(parsed_url.query)
        video_id = query.get("v", [""])[0]
        if not video_id:
            raise ValueError(f"YouTube 비디오 ID를 찾을 수 없습니다: {url}")
        return video_id
    
    # youtu.be/VIDEO_ID 형식 (단축 URL)
    elif "youtu.be/" in url:
        video_id = parsed_url.path.strip("/")
        if not video_id:
            raise ValueError(f"YouTube 비디오 ID를 찾을 수 없습니다: {url}")
        return video_id
    
    # youtube.com/embed/VIDEO_ID 형식
    elif "youtube.com/embed/" in url:
        video_id = parsed_url.path.split("/")[-1]
        if not video_id:
            raise ValueError(f"YouTube 비디오 ID를 찾을 수 없습니다: {url}")
        return video_id
    
    # youtube.com/v/VIDEO_ID 형식
    elif "youtube.com/v/" in url:
        video_id = parsed_url.path.split("/")[-1]
        if not video_id:
            raise ValueError(f"YouTube 비디오 ID를 찾을 수 없습니다: {url}")
        return video_id
    
    # youtube.com/shorts/VIDEO_ID 형식
    elif "youtube.com/shorts/" in url:
        video_id = parsed_url.path.split("/")[-1]
        if not video_id:
            raise ValueError(f"YouTube 비디오 ID를 찾을 수 없습니다: {url}")
        return video_id
    
    else:
        raise ValueError(f"지원되지 않는 YouTube URL 형식: {url}")

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def get_video_transcript(video_id: str, preferred_languages=None) -> tuple:
    """
    비디오 ID로 자막을 추출합니다.
    
    :param video_id: YouTube 비디오 ID
    :param preferred_languages: 선호하는 언어 코드 리스트 (예: ['ko', 'en'])
    :return: (자막 텍스트, 언어 코드) 또는 (None, None)
    """
    if not preferred_languages:
        preferred_languages = ['ko', 'en']  # 기본값: 한국어 우선, 영어 차선
    
    print(f"비디오 ID '{video_id}'의 자막 추출 중...")
    transcript_text = None
    used_language = None
    
    try:
        # 1. 모든 가능한 자막 리스트 가져오기
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        except Exception as e:
            print(f"자막 목록 조회 실패: {e}")
            transcript_list = None
        
        # 2. 선호 언어 순서대로 시도
        if transcript_list:
            # 2.1 수동 생성된 자막 먼저 시도 (선호 언어 순)
            for lang in preferred_languages:
                try:
                    for transcript in transcript_list:
                        if transcript.language_code == lang and not transcript.is_generated:
                            transcript_data = transcript.fetch()
                            transcript_text = " ".join([t['text'] for t in transcript_data])
                            used_language = lang
                            print(f"수동 생성된 {lang} 자막을 찾았습니다.")
                            break
                    if transcript_text:
                        break
                except Exception as e:
                    print(f"{lang} 수동 자막 추출 실패: {e}")
                    
            # 2.2 자동 생성된 자막 시도 (선호 언어 순)
            if not transcript_text:
                for lang in preferred_languages:
                    try:
                        for transcript in transcript_list:
                            if transcript.language_code == lang and transcript.is_generated:
                                transcript_data = transcript.fetch()
                                transcript_text = " ".join([t['text'] for t in transcript_data])
                                used_language = lang
                                print(f"자동 생성된 {lang} 자막을 찾았습니다.")
                                break
                        if transcript_text:
                            break
                    except Exception as e:
                        print(f"{lang} 자동 자막 추출 실패: {e}")
            
            # 2.3 번역 가능한 자막 시도 (우선 언어로 번역)
            if not transcript_text and transcript_list:
                try:
                    # 첫 번째 자막을 선호 언어로 번역 시도
                    for transcript in transcript_list:
                        try:
                            translated = transcript.translate(preferred_languages[0])
                            transcript_data = translated.fetch()
                            transcript_text = " ".join([t['text'] for t in transcript_data])
                            used_language = preferred_languages[0] + " (번역됨)"
                            print(f"{transcript.language_code}에서 {preferred_languages[0]}로 번역된 자막을 사용합니다.")
                            break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"자막 번역 실패: {e}")
        
        # 3. 직접 API 호출 시도 (list_transcripts가 실패한 경우)
        if not transcript_text:
            for lang in preferred_languages:
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    transcript_text = " ".join([t['text'] for t in transcript])
                    used_language = lang
                    print(f"직접 API 호출로 {lang} 자막을 찾았습니다.")
                    break
                except Exception:
                    continue
        
        # 결과 출력
        if transcript_text:
            print(f"자막 내용 (일부): {transcript_text[:200]}...")  # 자막의 첫 200자만 출력 (디버깅용)
        else:
            print(f"비디오 ID '{video_id}'에 대해 자막을 찾을 수 없습니다.")
    except TranscriptsDisabled:
        print(f"비디오 ID '{video_id}'는 자막 기능이 비활성화되었습니다.")
    except Exception as e:
        print(f"자막 추출 중 예외 발생: {e}")
    
    return (transcript_text, used_language) if transcript_text else (None, None)

def get_video_info(video_id: str):
    """
    YouTube 비디오 ID로 비디오 정보를 가져옵니다.
    실패 시 fallback 로직: 전체 정보 조회 실패 시 snippet만으로 재시도합니다.
    """
    global current_api_key_index
    
    # 모든 API 키 시도
    for attempt in range(len(YOUTUBE_API_KEYS)):
        service = get_youtube_service()
        if not service: 
            break
        
        print(f"비디오 정보 조회 시도 {attempt + 1}/{len(YOUTUBE_API_KEYS)} (키 인덱스: {current_api_key_index})")
        
        try:
            video_response = service.videos().list(
                part="snippet,contentDetails,statistics", 
                id=video_id
            ).execute()
            
            if video_response and video_response.get("items"):
                item = video_response["items"][0]
                return {
                    "type": "video", 
                    "id": item["id"], 
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"], 
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"], 
                    "published_at": item["snippet"]["publishedAt"],
                    "duration": item["contentDetails"]["duration"],
                    "view_count": item.get("statistics", {}).get("viewCount"),
                    "like_count": item.get("statistics", {}).get("likeCount"),
                }
            else:
                print(f"항목 없음 (시도 {attempt + 1}). 다음 키 시도.")
                if attempt < len(YOUTUBE_API_KEYS) - 1:
                    current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS)
                    print(f"빈 응답으로 다음 API 키 인덱스 수동 변경: {current_api_key_index}")
                elif attempt == len(YOUTUBE_API_KEYS) - 1:
                    print(f"모든 키로 전체 정보 조회 실패 (ID: {video_id}). Fallback 시도 예정.")
                    
        except googleapiclient.errors.HttpError as e:
            print(f"HttpError (시도 {attempt + 1}): {e}")
            if e.resp.status == 404: 
                return None  # 404면 비디오 없음
            if attempt == len(YOUTUBE_API_KEYS) - 1: 
                print("모든 키로 HttpError. Fallback 시도 예정.")
                
        except Exception as e:
            print(f"일반 오류 (시도 {attempt + 1}): {e}")
            if attempt < len(YOUTUBE_API_KEYS) - 1:
                current_api_key_index = (current_api_key_index + 1) % len(YOUTUBE_API_KEYS)
            elif attempt == len(YOUTUBE_API_KEYS) - 1: 
                print("모든 키로 일반 오류. Fallback 시도 예정.")
    
    # ---- Fallback 로직: snippet만 조회 ----
    print(f"ID {video_id}에 대해 'snippet'만으로 Fallback 재시도.")
    current_api_key_index = 0 
    service = get_youtube_service()
    
    if service:
        print(f"'snippet' 정보 조회 (키 인덱스 {current_api_key_index}, Fallback)")
        try:
            video_response = service.videos().list(part="snippet", id=video_id).execute()
            
            if video_response and video_response.get("items"):
                item = video_response["items"][0]
                print(f"Fallback 성공: 'snippet' 정보 (ID: {video_id})")
                return {
                    "type": "video", 
                    "id": item["id"], 
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"], 
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"], 
                    "published_at": item["snippet"]["publishedAt"],
                }
            else: 
                print(f"Fallback: ID {video_id} 항목 없음.")
                
        except googleapiclient.errors.HttpError as e: 
            print(f"Fallback HttpError: {e}")
            
        except Exception as e: 
            print(f"Fallback 일반 오류: {e}")
            
    else: 
        print("Fallback 서비스 객체 없음.")
        
    return None  # 모든 시도 실패

def extract_channel_handle(url):
    """
    YouTube 채널 URL에서 채널 핸들 또는 ID를 추출합니다.
    
    :param url: YouTube 채널 URL
    :return: 채널 핸들 또는 ID (추출 실패 시 None)
    """
    if not url:
        return None
        
    # 채널 URL 패턴들
    patterns = [
        r'youtube\.com/@([^/?&]+)',  # 새 형식: https://www.youtube.com/@channelname
        r'youtube\.com/channel/([^/?&]+)',  # 채널 ID: https://www.youtube.com/channel/UC...
        r'youtube\.com/c/([^/?&]+)',  # 사용자 지정 URL: https://www.youtube.com/c/customname
        r'youtube\.com/user/([^/?&]+)'  # 레거시 사용자 URL: https://www.youtube.com/user/username
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_latest_videos_from_channel(channel_id: str, max_results=10):
    """
    채널 ID를 통해 최신 동영상 목록을 가져옵니다.
    max_results: 최대 결과 수 (기본값 10)
    """
    service = get_youtube_service()
    if not service:
        return None
    try:
        search_params = {
            'channelId': channel_id,
            'part': "snippet",
            'type': "video",
            'maxResults': max_results,
            'order': 'date'  # 날짜순으로 정렬하여 최신 영상부터 가져옵니다
        }
        print(f"채널 ID '{channel_id}'의 최신 동영상 {max_results}개를 가져오는 중...")

        search_response = service.search().list(**search_params).execute()

        videos = []
        for item in search_response.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_id": item["snippet"]["channelId"],
                "channel_title": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"]
            })
        print(f"채널 ID '{channel_id}'에서 {len(videos)}개의 동영상을 찾았습니다.")
        return videos
    except googleapiclient.errors.HttpError as e:
        print(f"채널의 동영상 목록 조회 중 HttpError 발생 (채널 ID: {channel_id}): {e}")
        return None
    except Exception as e:
        print(f"채널의 동영상 목록 조회 중 예상치 못한 오류 발생 (채널 ID: {channel_id}): {e}")
        return None

if __name__ == '__main__':
    print("=== 시작 ===")
    try:
        from youtube_handler import extract_video_id
        print("모듈 임포트 성공!")
        print(extract_video_id("https://youtu.be/irFqOYrdHy0"))
    except Exception as e:
        print(f"에러 발생: {e}")
    print("=== 종료 ===")

    print("youtube_handler.py 직접 실행 테스트")
    
    if not YOUTUBE_API_KEYS:
        print("테스트를 진행할 수 없습니다. .env.local 또는 .env 파일에 YouTube API 키를 설정하세요.")
    else:
        print(f"로드된 YouTube API 키 개수: {len(YOUTUBE_API_KEYS)}")
        
        # 테스트 1: 채널 핸들로 정보 가져오기
        print("\n--- 채널 핸들로 정보 가져오기 테스트 ---")
        # 실제 핸들로 테스트 시에는 올바른 핸들을 사용하세요.
        # 참고: @Understanding의 경우 실제 customUrl은 @UnderstandingYT일 수 있습니다.
        # 핸들 검색은 customUrl과 일치하거나, 제목이 매우 유사한 것을 찾습니다.
        understanding_handle = "@understanding" # 소문자로 통일해서 테스트
        print(f"테스트할 채널 핸들: {understanding_handle}")
        understanding_channel_info = get_channel_info_by_handle(understanding_handle)
        if understanding_channel_info:
            print(f"  채널명: {understanding_channel_info['title']}")
            print(f"  채널 ID: {understanding_channel_info['id']}")
            print(f"  Custom URL: {understanding_channel_info.get('custom_url')}")
            print(f"  구독자 수: {understanding_channel_info.get('subscriber_count', '정보 없음')}")
        else:
            print(f"{understanding_handle} 채널 정보를 가져오지 못했습니다.")

        # 없는 핸들 테스트
        # fake_handle_info = get_channel_info_by_handle("@없는채널XYZ123없는채널")
        # if fake_handle_info:
        #     print(f"없는 채널 테스트 결과 (오류 예상): {fake_handle_info.get('title')}")
        # else:
        #     print("@없는채널XYZ123없는채널 정보를 가져오지 못했습니다 (예상된 결과).")


        # 테스트 2: 키워드로 동영상 검색
        print("\n--- 키워드로 동영상 검색 테스트 ---")
        keyword_to_search = "오건영"
        print(f"테스트할 키워드: {keyword_to_search}")
        videos_by_keyword = search_videos_by_keyword(keyword_to_search, max_results=2)
        if videos_by_keyword:
            for video in videos_by_keyword:
                print(f"  - 제목: {video['title']} (채널: {video['channel_title']}, ID: {video['video_id']})")
        else:
            print(f"'{keyword_to_search}' 키워드로 동영상 검색 결과를 가져오지 못했습니다.")

        # 특정 채널 내에서 키워드 검색 (위에서 @understanding 채널 정보를 가져왔다면)
        # if understanding_channel_info and understanding_channel_info.get('id'):
        #     print(f"\n--- '{understanding_channel_info['title']}' 채널 내 키워드 '{keyword_to_search}' 검색 ---")
        #     videos_in_channel = search_videos_by_keyword(keyword_to_search, channel_id=understanding_channel_info['id'], max_results=2)
        #     if videos_in_channel:
        #         for video in videos_in_channel:
        #             print(f"  - 제목: {video['title']} (ID: {video['video_id']})")
        #     else:
        #         print(f"채널 내 검색 결과를 가져오지 못했습니다.")
        # else:
        #     print("\n@understanding 채널 정보가 없어 채널 내 검색을 스킵합니다.")


        # 테스트 3: URL로 정보 가져오기
        print("\n--- URL로 정보 가져오기 테스트 ---")
        # 채널 URL (ID 기반)
        # channel_url_id = "https://www.youtube.com/channel/UCMHowardHughes" # 예: Howard Hughes 채널
        # print(f"테스트할 채널 URL (ID): {channel_url_id}")
        # info_from_channel_url_id = get_info_by_url(channel_url_id)
        # if info_from_channel_url_id:
        #     print(f"  URL 유형: {info_from_channel_url_id.get('type')}, 제목: {info_from_channel_url_id.get('title')}")
        # else:
        #     print(f"  {channel_url_id} 정보 가져오기 실패")

        # 채널 URL (핸들 기반)
        channel_url_handle = "https://www.youtube.com/@understanding"
        print(f"테스트할 채널 URL (핸들): {channel_url_handle}")
        info_from_channel_url_handle = get_info_by_url(channel_url_handle)
        if info_from_channel_url_handle:
            print(f"  URL 유형: {info_from_channel_url_handle.get('type')}, 제목: {info_from_channel_url_handle.get('title')}, ID: {info_from_channel_url_handle.get('id')}")
        else:
            print(f"  {channel_url_handle} 정보 가져오기 실패")
            
        # 비디오 URL
        video_url_watch = "https://www.youtube.com/watch?v=irFqOYrdHy0" # 새 테스트 URL (예시)
        print(f"테스트할 비디오 URL (watch): {video_url_watch}")
        info_from_video_url_watch = get_info_by_url(video_url_watch)
        if info_from_video_url_watch:
            print(f"  URL 유형: {info_from_video_url_watch.get('type')}, 제목: {info_from_video_url_watch.get('title')}")
            # 상세 정보가 있다면 추가로 출력 (duration, view_count 등)
            if 'duration' in info_from_video_url_watch:
                 print(f"  재생시간: {info_from_video_url_watch.get('duration')}, 조회수: {info_from_video_url_watch.get('view_count')}")
        else:
            print(f"  {video_url_watch} 정보 가져오기 실패")

        # 단축 비디오 URL 테스트도 다른 ID로 변경 가능하면 좋습니다. (예: 동일 비디오의 단축 URL)
        video_url_short = "https://youtu.be/irFqOYrdHy0"
        print(f"테스트할 비디오 URL (short): {video_url_short}")
        info_from_video_url_short = get_info_by_url(video_url_short)
        if info_from_video_url_short:
            print(f"  URL 유형: {info_from_video_url_short.get('type')}, 제목: {info_from_video_url_short.get('title')}")
            if 'duration' in info_from_video_url_short:
                 print(f"  재생시간: {info_from_video_url_short.get('duration')}, 조회수: {info_from_video_url_short.get('view_count')}")
        else:
            print(f"  {video_url_short} 정보 가져오기 실패")
            
        # 잘못된 URL
        # invalid_url = "https://example.com/notyoutube"
        # print(f"테스트할 잘못된 URL: {invalid_url}")
        # info_from_invalid_url = get_info_by_url(invalid_url)
        # if not info_from_invalid_url:
        #     print(f"  {invalid_url} 정보 가져오기 실패 (예상된 결과)")


    print("\nyoutube_handler.py 테스트 완료") 