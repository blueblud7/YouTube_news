import os
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.exceptions import DefaultCredentialsError
import re

def get_youtube_service(credentials):
    """
    YouTube API 서비스 클라이언트를 반환합니다.
    OAuth2 인증을 사용합니다.
    """
    try:
        print("YouTube API 서비스 빌드 시도 (OAuth2)")
        service = googleapiclient.discovery.build(
            "youtube", "v3", credentials=credentials
        )
        print("YouTube API 서비스가 성공적으로 빌드되었습니다. (OAuth2)")
        return service
    except Exception as e:
        print(f"YouTube API 서비스 빌드 중 오류 발생: {e}")
        return None

def get_channel_info_by_handle(handle: str, credentials):
    """
    YouTube 채널 핸들(@)을 사용하여 채널 정보를 가져옵니다.
    (예: '@Understanding')
    """
    # 핸들 앞의 '@' 제거
    clean_handle = handle[1:] if handle.startswith('@') else handle

    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        # 핸들을 사용하여 채널 검색
        search_response = service.search().list(
            q=clean_handle,
            part="snippet",
            type="channel",
            maxResults=5
        ).execute()

        if not search_response.get("items"):
            print(f"핸들 '{handle}'에 대한 검색 결과가 없습니다.")
            return None

        for item in search_response.get("items", []):
            channel_id = item["snippet"]["channelId"]
            # 채널 ID로 상세 정보 조회
            channel_details_response = service.channels().list(
                part="snippet,statistics,brandingSettings",
                id=channel_id
            ).execute()

            if channel_details_response.get("items"):
                channel_data = channel_details_response["items"][0]["snippet"]
                channel_stats = channel_details_response["items"][0].get("statistics", {})
                
                retrieved_custom_url = channel_data.get("customUrl")
                retrieved_title = channel_data.get("title")

                # 핸들과 customUrl 비교
                if retrieved_custom_url and (retrieved_custom_url.lower() == handle.lower() or retrieved_custom_url.lower() == f"@{clean_handle}".lower()):
                    print(f"핸들 '{handle}'과 customUrl '{retrieved_custom_url}'이 일치하는 채널을 찾았습니다.")
                    return {
                        "type": "channel",
                        "id": channel_id,
                        "title": retrieved_title,
                        "description": channel_data.get("description"),
                        "custom_url": retrieved_custom_url,
                        "handle_used": handle,
                        "subscriber_count": channel_stats.get("subscriberCount"),
                        "video_count": channel_stats.get("videoCount"),
                        "published_at": channel_data.get("publishedAt")
                    }
        
        # 정확한 customUrl 매칭이 안된 경우, 검색 결과 중 제목이 유사한 것을 고려
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
        return None
    except Exception as e:
        print(f"채널 정보 조회 중 예상치 못한 오류 발생 (핸들: {handle}): {e}")
        return None

def search_videos_by_keyword(keyword: str, credentials, channel_id: str = None, max_results=15):
    """
    키워드로 YouTube 동영상을 검색합니다.
    channel_id가 제공되면 해당 채널에서만 검색합니다.
    """
    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        # 검색 쿼리 구성
        if channel_id:
            # 특정 채널에서 검색
            search_response = service.search().list(
                part="snippet",
                q=keyword,
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=max_results
            ).execute()
        else:
            # 전체 검색
            search_response = service.search().list(
                part="snippet",
                q=keyword,
                type="video",
                order="date",
                maxResults=max_results
            ).execute()

        videos = []
        for item in search_response.get("items", []):
            video_info = {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_id": item["snippet"]["channelId"],
                "channel_title": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnails": item["snippet"]["thumbnails"]
            }
            videos.append(video_info)

        return videos

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"동영상 검색 중 HttpError 발생: {e} - {error_content}")
        return None
    except Exception as e:
        print(f"동영상 검색 중 예상치 못한 오류 발생: {e}")
        return None

def get_info_by_url(url: str, credentials):
    """
    YouTube URL에서 동영상 또는 채널 정보를 추출합니다.
    """
    # 동영상 URL 패턴
    video_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)'
    ]
    
    # 채널 URL 패턴
    channel_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/c/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/user/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/(@[a-zA-Z0-9_-]+)'
    ]

    # 동영상 URL 확인
    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return get_video_info(video_id, credentials)

    # 채널 URL 확인
    for pattern in channel_patterns:
        match = re.search(pattern, url)
        if match:
            channel_identifier = match.group(1)
            return get_channel_info(channel_identifier, credentials)

    print(f"지원되지 않는 YouTube URL 형식입니다: {url}")
    return None

def extract_video_id(url: str) -> str:
    """
    YouTube URL에서 동영상 ID를 추출합니다.
    """
    # 동영상 URL 패턴들
    patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_video_transcript(video_id: str, credentials, preferred_languages=None) -> tuple:
    """
    YouTube 동영상의 자막을 가져옵니다.
    """
    if preferred_languages is None:
        preferred_languages = ['ko', 'en']

    service = get_youtube_service(credentials)
    if not service:
        return None, None

    try:
        # 자막 트랙 목록 가져오기
        captions_response = service.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        if not captions_response.get("items"):
            print(f"동영상 {video_id}에 자막이 없습니다.")
            return None, None

        # 선호 언어 순서대로 자막 찾기
        for lang in preferred_languages:
            for caption in captions_response["items"]:
                if caption["snippet"]["language"] == lang:
                    caption_id = caption["id"]
                    
                    # 자막 내용 가져오기
                    transcript_response = service.captions().download(
                        id=caption_id,
                        tfmt='srt'
                    ).execute()
                    
                    return transcript_response, lang

        # 선호 언어가 없으면 첫 번째 자막 사용
        first_caption = captions_response["items"][0]
        caption_id = first_caption["id"]
        lang = first_caption["snippet"]["language"]
        
        transcript_response = service.captions().download(
            id=caption_id,
            tfmt='srt'
        ).execute()
        
        return transcript_response, lang

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"자막 가져오기 중 HttpError 발생: {e} - {error_content}")
        return None, None
    except Exception as e:
        print(f"자막 가져오기 중 예상치 못한 오류 발생: {e}")
        return None, None

def get_video_info(video_id: str, credentials):
    """
    YouTube 동영상의 상세 정보를 가져옵니다.
    """
    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        # 동영상 정보 가져오기
        video_response = service.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        ).execute()

        if not video_response.get("items"):
            print(f"동영상 {video_id}를 찾을 수 없습니다.")
            return None

        video_data = video_response["items"][0]
        snippet = video_data["snippet"]
        statistics = video_data.get("statistics", {})
        content_details = video_data.get("contentDetails", {})

        return {
            "type": "video",
            "id": video_id,
            "title": snippet["title"],
            "description": snippet["description"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "thumbnails": snippet["thumbnails"],
            "view_count": statistics.get("viewCount"),
            "like_count": statistics.get("likeCount"),
            "comment_count": statistics.get("commentCount"),
            "duration": content_details.get("duration"),
            "tags": snippet.get("tags", [])
        }

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"동영상 정보 가져오기 중 HttpError 발생: {e} - {error_content}")
        return None
    except Exception as e:
        print(f"동영상 정보 가져오기 중 예상치 못한 오류 발생: {e}")
        return None

def extract_channel_handle(url):
    """
    YouTube 채널 URL에서 핸들을 추출합니다.
    """
    # @핸들 패턴
    handle_pattern = r'(?:https?://)?(?:www\.)?youtube\.com/(@[a-zA-Z0-9_-]+)'
    match = re.search(handle_pattern, url)
    if match:
        return match.group(1)
    return None

def get_channel_info(channel_identifier, credentials):
    """
    채널 ID, 사용자명, 또는 핸들로 채널 정보를 가져옵니다.
    """
    # 핸들인 경우
    if channel_identifier.startswith('@'):
        return get_channel_info_by_handle(channel_identifier, credentials)
    
    # 채널 ID인 경우 (UC로 시작하는 24자리 문자열)
    if channel_identifier.startswith('UC') and len(channel_identifier) == 24:
        return get_channel_info_by_id(channel_identifier, credentials)
    
    # 사용자명인 경우
    return get_channel_info_by_username(channel_identifier, credentials)

def get_channel_info_by_id(channel_id: str, credentials):
    """
    채널 ID로 채널 정보를 가져옵니다.
    """
    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        response = service.channels().list(
            part="snippet,statistics,brandingSettings",
            id=channel_id
        ).execute()

        if not response.get("items"):
            print(f"채널 ID {channel_id}에 해당하는 채널을 찾을 수 없습니다.")
            return None

        channel_data = response["items"][0]["snippet"]
        channel_stats = response["items"][0].get("statistics", {})

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

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"채널 정보 조회 중 HttpError 발생 (ID: {channel_id}): {e} - {error_content}")
        return None
    except Exception as e:
        print(f"채널 정보 조회 중 예상치 못한 오류 발생 (ID: {channel_id}): {e}")
        return None

def get_channel_info_by_username(username: str, credentials):
    """
    사용자명으로 채널 정보를 가져옵니다.
    """
    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        response = service.channels().list(
            part="snippet,statistics,brandingSettings",
            forUsername=username
        ).execute()

        if not response.get("items"):
            print(f"사용자명 {username}에 해당하는 채널을 찾을 수 없습니다.")
            return None

        channel_data = response["items"][0]["snippet"]
        channel_stats = response["items"][0].get("statistics", {})
        channel_id = response["items"][0]["id"]

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

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"채널 정보 조회 중 HttpError 발생 (사용자명: {username}): {e} - {error_content}")
        return None
    except Exception as e:
        print(f"채널 정보 조회 중 예상치 못한 오류 발생 (사용자명: {username}): {e}")
        return None

def get_latest_videos_from_channel(channel_id: str, credentials, max_results=10):
    """
    특정 채널의 최신 동영상 목록을 가져옵니다.
    """
    service = get_youtube_service(credentials)
    if not service:
        return None

    try:
        # 채널의 업로드 재생목록 ID 가져오기
        channel_response = service.channels().list(
            part="contentDetails",
            id=channel_id
        ).execute()

        if not channel_response.get("items"):
            print(f"채널 ID {channel_id}에 해당하는 채널을 찾을 수 없습니다.")
            return None

        uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # 업로드 재생목록에서 동영상 가져오기
        playlist_response = service.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        ).execute()

        videos = []
        for item in playlist_response.get("items", []):
            video_info = {
                "video_id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnails": item["snippet"]["thumbnails"]
            }
            videos.append(video_info)

        return videos

    except googleapiclient.errors.HttpError as e:
        error_content = e.content.decode('utf-8') if hasattr(e.content, 'decode') else str(e.content)
        print(f"채널 동영상 목록 가져오기 중 HttpError 발생: {e} - {error_content}")
        return None
    except Exception as e:
        print(f"채널 동영상 목록 가져오기 중 예상치 못한 오류 발생: {e}")
        return None 