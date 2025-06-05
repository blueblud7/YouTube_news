import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import os

# 데이터베이스 파일 경로 (프로젝트 루트에 저장)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_news.db")

def initialize_db():
    """데이터베이스와 테이블을 초기화합니다."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            channel_title TEXT NOT NULL,
            published_at TEXT NOT NULL,
            duration TEXT NOT NULL,
            view_count INTEGER NOT NULL,
            transcript TEXT,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # 요약 정보를 저장하는 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL,
            summary_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            UNIQUE (video_id, summary_type)
        )
    """)
    
    # 채널 정보를 저장하는 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            handle TEXT,
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # 키워드 정보를 저장하는 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
    """)
    
    # 뉴스 사설을 저장하는 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            news_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            video_ids TEXT,
            style TEXT DEFAULT 'basic',
            word_count INTEGER DEFAULT 1000,
            language TEXT DEFAULT 'ko',
            keywords TEXT
        )
    """)
    
    # 추출된 키워드를 저장하는 테이블 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extracted_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (keyword)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"데이터베이스 초기화 완료: {DB_PATH}")

def save_video_data(video_data: Dict[str, Any], transcript: Optional[str] = None):
    """
    비디오 정보와 자막을 데이터베이스에 저장합니다.
    
    :param video_data: YouTube API에서 가져온 비디오 정보 (snippet, statistics 등 포함)
    :param transcript: 비디오 자막 (없으면 None)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # video_data 유효성 검사
    if not video_data:
        print("비디오 데이터가 없습니다.")
        conn.close()
        return False
        
    if 'id' not in video_data:
        print("비디오 ID가 없습니다.")
        conn.close()
        return False
    
    # 중복 저장 방지: 이미 존재하는 비디오 ID는 무시
    cursor.execute("SELECT id FROM videos WHERE id = ?", (video_data["id"],))
    if cursor.fetchone():
        print(f"비디오 ID {video_data['id']}는 이미 저장되었습니다.")
        conn.close()
        return False
    
    try:
        # get_info_by_url로 가져온 데이터 구조 처리
        video_id = video_data["id"]
        
        # 필드 존재 여부 확인 (직접 API 응답을 사용하는 경우)
        if "snippet" in video_data and "contentDetails" in video_data and "statistics" in video_data:
            title = video_data["snippet"]["title"]
            channel_id = video_data["snippet"]["channelId"]
            channel_title = video_data["snippet"]["channelTitle"]
            published_at = video_data["snippet"]["publishedAt"]
            duration = video_data["contentDetails"]["duration"]
            view_count = int(video_data["statistics"]["viewCount"])
        # get_info_by_url에서 이미 추출된 필드를 사용하는 경우 
        else:
            title = video_data.get("title", "제목 없음")
            channel_id = video_data.get("channel_id", "채널 ID 없음")
            channel_title = video_data.get("channel_title", "채널명 없음")
            published_at = video_data.get("published_at", datetime.now().isoformat())
            duration = video_data.get("duration", "PT0S")
            view_count = int(video_data.get("view_count", 0))
        
        # 데이터 저장
        cursor.execute("""
            INSERT INTO videos (
                id, title, channel_id, channel_title, published_at,
                duration, view_count, transcript, url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_id,
            title,
            channel_id,
            channel_title,
            published_at,
            duration,
            view_count,
            transcript,
            f"https://www.youtube.com/watch?v={video_id}",
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        print(f"비디오 ID {video_id}를 데이터베이스에 저장했습니다.")
        return True
    except Exception as e:
        print(f"비디오 데이터 저장 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def get_video_data(video_id: str) -> Optional[Dict[str, Any]]:
    """
    비디오 ID로 저장된 데이터를 조회합니다.
    
    :param video_id: 조회할 비디오 ID
    :return: 비디오 정보 (없으면 None)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "title": row[1],
        "channel_id": row[2],
        "channel_title": row[3],
        "published_at": row[4],
        "duration": row[5],
        "view_count": row[6],
        "transcript": row[7],
        "url": row[8],
        "created_at": row[9]
    }

def save_summary_to_db(video_id: str, summary_type: str, content: str) -> bool:
    """
    비디오 요약 정보를 데이터베이스에 저장합니다.
    
    :param video_id: 비디오 ID
    :param summary_type: 요약 유형 (summary, analysis_economic, analysis_simple, analysis_complex 등)
    :param content: 요약 또는 분석 내용
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 먼저 비디오가 존재하는지 확인
        cursor.execute("SELECT id FROM videos WHERE id = ?", (video_id,))
        if not cursor.fetchone():
            print(f"비디오 ID {video_id}가 데이터베이스에 존재하지 않습니다.")
            conn.close()
            return False
        
        # 이미 해당 유형의 요약이 있는지 확인
        cursor.execute("SELECT id FROM summaries WHERE video_id = ? AND summary_type = ?", 
                       (video_id, summary_type))
        existing = cursor.fetchone()
        
        if existing:
            # 기존 요약 업데이트
            cursor.execute("""
                UPDATE summaries 
                SET content = ?, created_at = ? 
                WHERE video_id = ? AND summary_type = ?
            """, (content, datetime.now().isoformat(), video_id, summary_type))
            print(f"비디오 ID {video_id}의 {summary_type} 요약이 업데이트되었습니다.")
        else:
            # 새 요약 삽입
            cursor.execute("""
                INSERT INTO summaries (video_id, summary_type, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (video_id, summary_type, content, datetime.now().isoformat()))
            print(f"비디오 ID {video_id}의 {summary_type} 요약이 저장되었습니다.")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"요약 데이터 저장 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def get_summaries_for_video(video_id: str) -> Dict[str, str]:
    """
    비디오 ID에 대한 모든 요약/분석 정보를 가져옵니다.
    
    :param video_id: 비디오 ID
    :return: 요약 유형별 내용을 담은 딕셔너리
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT summary_type, content 
        FROM summaries 
        WHERE video_id = ?
    """, (video_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    return {row[0]: row[1] for row in results}

def get_new_videos_since(since_timestamp: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    특정 시간 이후에 추가된 새로운 비디오 목록을 가져옵니다.
    
    :param since_timestamp: 이 시간 이후에 생성된 비디오 (ISO 형식)
    :param limit: 최대 비디오 수
    :return: 비디오 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT v.id, v.title, v.channel_title, v.published_at, v.view_count, 
               length(v.transcript) as transcript_length,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE v.created_at > ? AND v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
        LIMIT ?
    """
    
    cursor.execute(query, (since_timestamp, limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_videos_by_channel(channel_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    특정 채널의 비디오 목록을 가져옵니다.
    
    :param channel_id: 채널 ID
    :param limit: 최대 비디오 수
    :return: 비디오 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT v.id, v.title, v.channel_title, v.published_at, v.view_count, 
               length(v.transcript) as transcript_length,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE v.channel_id = ? AND v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
        LIMIT ?
    """
    
    cursor.execute(query, (channel_id, limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_videos_by_keyword(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    제목에 특정 키워드가 포함된 비디오 목록을 가져옵니다.
    
    :param keyword: 검색 키워드
    :param limit: 최대 비디오 수
    :return: 비디오 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT v.id, v.title, v.channel_title, v.published_at, v.view_count, 
               length(v.transcript) as transcript_length,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE v.title LIKE ? AND v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
        LIMIT ?
    """
    
    cursor.execute(query, (f'%{keyword}%', limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def generate_report(since_timestamp: str = None, hours: int = 12) -> Dict[str, Any]:
    """
    특정 기간 내의 새로운 콘텐츠에 대한 리포트를 생성합니다.
    
    :param since_timestamp: 이 시간 이후의 콘텐츠 (ISO 형식, None이면 현재 시간 - hours)
    :param hours: 몇 시간 전부터의 콘텐츠 (since_timestamp가 None일 때 사용)
    :return: 리포트 데이터
    """
    if since_timestamp is None:
        # 현재 시간에서 지정된 시간을 뺌
        since_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        since_timestamp = since_time.isoformat()
    else:
        # since_timestamp에 시간대 정보가 없으면 UTC로 가정
        if '+' not in since_timestamp and '-' not in since_timestamp[-6:] and 'Z' not in since_timestamp:
            since_timestamp = datetime.fromisoformat(since_timestamp).replace(tzinfo=timezone.utc).isoformat()
        elif 'Z' in since_timestamp:
            since_timestamp = since_timestamp.replace('Z', '+00:00')
    
    # ISO 형식 문자열을 datetime 객체로 변환
    since_datetime = datetime.fromisoformat(since_timestamp)
    
    # 데이터베이스 연결
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 지정된 시간 이후에 추가된 비디오 조회 (channels 테이블 JOIN 없이)
    cursor.execute("""
        SELECT *
        FROM videos v
        WHERE v.created_at > ?
        ORDER BY v.published_at DESC
    """, (since_timestamp,))
    
    videos_data = []
    for row in cursor.fetchall():
        video_data = dict(row)
        
        # 자막 길이 계산
        transcript_length = len(video_data.get("transcript", "")) if video_data.get("transcript") else 0
        video_data["transcript_length"] = transcript_length
        
        # 요약 정보 가져오기 (summaries 테이블 사용)
        cursor.execute("""
            SELECT summary_type, content
            FROM summaries
            WHERE video_id = ?
        """, (video_data["id"],))
        
        summaries = {}
        for analysis_row in cursor.fetchall():
            summaries[analysis_row["summary_type"]] = analysis_row["content"]
        
        video_data["summaries"] = summaries
        videos_data.append(video_data)
    
    # 채널별로 비디오 그룹화
    channels_data = {}
    for video in videos_data:
        channel_title = video.get("channel_title", "알 수 없는 채널")
        if channel_title not in channels_data:
            channels_data[channel_title] = []
        channels_data[channel_title].append({
            "id": video.get("id"),
            "title": video.get("title"),
            "published_at": video.get("published_at"),
            "view_count": video.get("view_count"),
            "transcript_length": video.get("transcript_length"),
            "summaries": video.get("summaries", {})
        })
    
    conn.close()
    
    # 리포트 데이터 구성
    report_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since_timestamp,
        "hours": hours if since_timestamp is None else None,
        "total_videos": len(videos_data),
        "channels": channels_data,
        "videos": [{
            "id": v.get("id"),
            "title": v.get("title"),
            "channel_id": v.get("channel_id"),
            "channel_title": v.get("channel_title"),
            "published_at": v.get("published_at"),
            "view_count": v.get("view_count")
        } for v in videos_data]
    }
    
    return report_data

def get_all_channels() -> List[Dict[str, Any]]:
    """
    저장된 모든 채널 목록을 가져옵니다.
    
    :return: 채널 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, channel_id, title, handle, description, created_at
        FROM channels
        ORDER BY title
    """)
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def add_channel(channel_id: str, title: str, handle: str = None, description: str = None) -> bool:
    """
    새 채널을 추가합니다.
    
    :param channel_id: 채널 ID
    :param title: 채널 제목
    :param handle: 채널 핸들 (없으면 None)
    :param description: 채널 설명 (없으면 None)
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 이미 존재하는 채널인지 확인
        cursor.execute("SELECT id FROM channels WHERE channel_id = ?", (channel_id,))
        if cursor.fetchone():
            print(f"채널 ID {channel_id}는 이미 저장되었습니다.")
            conn.close()
            return False
        
        # 새 채널 추가
        cursor.execute("""
            INSERT INTO channels (channel_id, title, handle, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, title, handle, description, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"채널 '{title}'을(를) 추가했습니다.")
        return True
    except Exception as e:
        print(f"채널 추가 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def delete_channel(channel_id: str) -> bool:
    """
    채널을 삭제합니다.
    
    :param channel_id: 삭제할 채널 ID
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 채널이 존재하는지 확인
        cursor.execute("SELECT id FROM channels WHERE channel_id = ?", (channel_id,))
        if not cursor.fetchone():
            print(f"채널 ID {channel_id}가 존재하지 않습니다.")
            conn.close()
            return False
        
        # 채널 삭제
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        
        conn.commit()
        conn.close()
        print(f"채널 ID {channel_id}을(를) 삭제했습니다.")
        return True
    except Exception as e:
        print(f"채널 삭제 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def search_channels_by_keyword(keyword: str) -> List[Dict[str, Any]]:
    """
    키워드로 채널을 검색합니다.
    
    :param keyword: 검색 키워드
    :return: 채널 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, channel_id, title, handle, description, created_at
        FROM channels
        WHERE title LIKE ? OR description LIKE ?
        ORDER BY title
    """, (f'%{keyword}%', f'%{keyword}%'))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_all_keywords() -> List[Dict[str, Any]]:
    """
    저장된 모든 키워드 목록을 가져옵니다.
    
    :return: 키워드 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, keyword, created_at
        FROM keywords
        ORDER BY keyword
    """)
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def add_keyword(keyword: str) -> bool:
    """
    새 키워드를 추가합니다.
    
    :param keyword: 키워드
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 이미 존재하는 키워드인지 확인
        cursor.execute("SELECT id FROM keywords WHERE keyword = ?", (keyword,))
        if cursor.fetchone():
            print(f"키워드 '{keyword}'는 이미 저장되었습니다.")
            conn.close()
            return False
        
        # 새 키워드 추가
        cursor.execute("""
            INSERT INTO keywords (keyword, created_at)
            VALUES (?, ?)
        """, (keyword, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"키워드 '{keyword}'을(를) 추가했습니다.")
        return True
    except Exception as e:
        print(f"키워드 추가 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def delete_keyword(keyword_id: int) -> bool:
    """
    키워드를 삭제합니다.
    
    :param keyword_id: 삭제할 키워드 ID
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 키워드가 존재하는지 확인
        cursor.execute("SELECT id FROM keywords WHERE id = ?", (keyword_id,))
        if not cursor.fetchone():
            print(f"키워드 ID {keyword_id}가 존재하지 않습니다.")
            conn.close()
            return False
        
        # 키워드 삭제
        cursor.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        
        conn.commit()
        conn.close()
        print(f"키워드 ID {keyword_id}을(를) 삭제했습니다.")
        return True
    except Exception as e:
        print(f"키워드 삭제 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def search_videos_by_keyword(keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    제목이나 자막에 특정 키워드가 포함된 비디오 목록을 가져옵니다.
    
    :param keyword: 검색 키워드
    :param limit: 최대 비디오 수
    :return: 비디오 정보 목록
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT v.id, v.title, v.channel_title, v.published_at, v.view_count, 
               length(v.transcript) as transcript_length,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE (v.title LIKE ? OR v.transcript LIKE ?) AND v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
        LIMIT ?
    """
    
    cursor.execute(query, (f'%{keyword}%', f'%{keyword}%', limit))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def is_video_in_db(video_id: str) -> bool:
    """
    비디오 ID가 데이터베이스에 있는지 확인합니다.
    
    :param video_id: 비디오 ID
    :return: 존재 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM videos WHERE id = ?", (video_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def analyze_video(video_id: str, analysis_type: str) -> bool:
    """
    비디오를 분석하고 결과를 데이터베이스에 저장합니다.
    
    :param video_id: 비디오 ID
    :param analysis_type: 분석 유형
    :return: 성공 여부
    """
    from llm_handler import summarize_transcript, analyze_transcript_with_type
    
    try:
        # 비디오 정보 가져오기
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT transcript FROM videos WHERE id = ?", (video_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result[0]:
            print(f"비디오 ID {video_id}에 대한 자막이 없습니다.")
            return False
        
        transcript = result[0]
        
        # 분석 수행
        if analysis_type == "summary":
            result_text = summarize_transcript(transcript, analysis_type=analysis_type)
        else:
            result_text = analyze_transcript_with_type(transcript, analysis_type)
        
        # 결과 저장
        return save_summary_to_db(video_id, analysis_type, result_text)
    
    except Exception as e:
        print(f"비디오 분석 중 오류 발생: {e}")
        return False

def save_news_article(title: str, content: str, news_type: str = "economic", video_ids: List[str] = None, style: str = "basic", word_count: int = 1000, language: str = "ko", keywords: List[str] = None) -> bool:
    """
    뉴스 사설을 데이터베이스에 저장합니다.
    
    :param title: 뉴스 사설 제목
    :param content: 뉴스 사설 내용
    :param news_type: 뉴스 유형 (economic, political, social 등)
    :param video_ids: 사설 생성에 사용된 비디오 ID 목록
    :param style: 리포트 스타일 (basic, concise, editorial, news, research)
    :param word_count: 글자수
    :param language: 언어 (ko, en)
    :param keywords: 사용된 키워드 목록
    :return: 성공 여부
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 비디오 ID 목록을 쉼표로 구분된 문자열로 변환
        video_ids_str = ",".join(video_ids) if video_ids else None
        
        # 키워드 목록을 쉼표로 구분된 문자열로 변환
        keywords_str = ",".join(keywords) if keywords else None
        
        # 테이블에 필요한 필드가 존재하는지 확인
        cursor.execute("PRAGMA table_info(news)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 모든 필드가 있는지 확인
        required_fields = ['style', 'word_count', 'language', 'keywords']
        missing_fields = [field for field in required_fields if field not in columns]
        
        # 누락된 필드가 있으면 추가
        for field in missing_fields:
            if field == 'keywords':
                cursor.execute("ALTER TABLE news ADD COLUMN keywords TEXT")
            elif field not in columns:
                default_value = "'basic'" if field == 'style' else "1000" if field == 'word_count' else "'ko'" if field == 'language' else "NULL"
                cursor.execute(f"ALTER TABLE news ADD COLUMN {field} {get_field_type(field)} DEFAULT {default_value}")
        
        # 모든 필드를 포함하여 뉴스 사설 저장
        cursor.execute("""
            INSERT INTO news (title, content, news_type, created_at, video_ids, style, word_count, language, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            content,
            news_type,
            datetime.now().isoformat(),
            video_ids_str,
            style,
            word_count,
            language,
            keywords_str
        ))
        
        conn.commit()
        conn.close()
        print(f"뉴스 사설 '{title}'이(가) 데이터베이스에 저장되었습니다.")
        return True
    except Exception as e:
        print(f"뉴스 사설 저장 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def get_field_type(field_name: str) -> str:
    """필드 이름에 따른 적절한 데이터 타입을 반환합니다."""
    if field_name == 'word_count':
        return 'INTEGER'
    else:
        return 'TEXT'

def get_latest_news(news_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    최신 뉴스 사설을 가져옵니다.
    
    :param news_type: 뉴스 유형 (None이면 모든 유형)
    :param limit: 최대 결과 수
    :return: 뉴스 사설 목록
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(news)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 기본 필드
        fields = "id, title, content, news_type, created_at, video_ids"
        
        # 추가 필드가 존재하면 포함
        if 'style' in columns:
            fields += ", style"
        if 'word_count' in columns:
            fields += ", word_count"
        if 'language' in columns:
            fields += ", language"
        if 'keywords' in columns:
            fields += ", keywords"
        
        if news_type:
            cursor.execute(f"""
                SELECT {fields}
                FROM news
                WHERE news_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (news_type, limit))
        else:
            cursor.execute(f"""
                SELECT {fields}
                FROM news
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 결과를 딕셔너리 목록으로 변환
        news_list = []
        for row in rows:
            news_item = {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "news_type": row[3],
                "created_at": row[4],
                "video_ids": row[5].split(",") if row[5] else []
            }
            
            # 추가 필드가 결과에 있으면 포함
            field_index = 6
            if 'style' in columns and field_index < len(row):
                news_item["style"] = row[field_index]
                field_index += 1
            if 'word_count' in columns and field_index < len(row):
                news_item["word_count"] = row[field_index]
                field_index += 1
            if 'language' in columns and field_index < len(row):
                news_item["language"] = row[field_index]
                field_index += 1
            if 'keywords' in columns and field_index < len(row):
                news_item["keywords"] = row[field_index].split(",") if row[field_index] else []
            
            news_list.append(news_item)
        
        return news_list
    except Exception as e:
        print(f"뉴스 사설 조회 중 오류 발생: {e}")
        conn.close()
        return []

def get_news_by_id(news_id: int) -> Optional[Dict[str, Any]]:
    """
    특정 ID의 뉴스 사설을 가져옵니다.
    
    :param news_id: 뉴스 사설 ID
    :return: 뉴스 사설 정보 (없으면 None)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(news)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # 기본 필드
        fields = "id, title, content, news_type, created_at, video_ids"
        
        # 추가 필드가 존재하면 포함
        if 'style' in columns:
            fields += ", style"
        if 'word_count' in columns:
            fields += ", word_count"
        if 'language' in columns:
            fields += ", language"
        if 'keywords' in columns:
            fields += ", keywords"
        
        cursor.execute(f"""
            SELECT {fields}
            FROM news
            WHERE id = ?
        """, (news_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # 결과를 딕셔너리로 변환
        news_item = {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "news_type": row[3],
            "created_at": row[4],
            "video_ids": row[5].split(",") if row[5] else []
        }
        
        # 추가 필드가 결과에 있으면 포함
        field_index = 6
        if 'style' in columns and field_index < len(row):
            news_item["style"] = row[field_index]
            field_index += 1
        if 'word_count' in columns and field_index < len(row):
            news_item["word_count"] = row[field_index]
            field_index += 1
        if 'language' in columns and field_index < len(row):
            news_item["language"] = row[field_index]
            field_index += 1
        if 'keywords' in columns and field_index < len(row):
            news_item["keywords"] = row[field_index].split(",") if row[field_index] else []
        
        return news_item
    except Exception as e:
        print(f"뉴스 사설 조회 중 오류 발생: {e}")
        conn.close()
        return None

def generate_economic_news_from_recent_videos(hours: int = 24, style: str = "basic", word_count: int = 1000, language: str = "ko") -> Optional[Dict[str, Any]]:
    """
    최근 지정된 시간 내의 비디오 자막을 사용하여 경제 뉴스 사설을 생성합니다.
    
    :param hours: 몇 시간 이내의 비디오를 대상으로 할지 (기본값 24시간)
    :param style: 리포트 스타일 (basic, concise, editorial, news, research)
    :param word_count: 원하는 글자수 (대략적인 값)
    :param language: 언어 선택 (ko: 한국어, en: 영어)
    :return: 생성된 뉴스 사설 정보 (성공한 경우) 또는 None (실패한 경우)
    """
    from llm_handler import generate_economic_news
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 최근 비디오 조회 (timestamp를 datetime으로 비교)
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute("""
            SELECT id, title, transcript
            FROM videos
            WHERE created_at > ? AND transcript IS NOT NULL
            ORDER BY created_at DESC
        """, (since_time,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print(f"최근 {hours}시간 내에 자막이 있는 비디오가 없습니다.")
            return None
        
        # 비디오 정보 및 자막 추출
        video_ids = []
        transcripts = []
        
        for row in rows:
            video_id = row[0]
            transcript = row[2]
            
            if transcript:
                video_ids.append(video_id)
                transcripts.append(transcript)
        
        if not transcripts:
            print("자막이 있는 비디오가 없습니다.")
            return None
        
        # 경제 뉴스 사설 생성 (스타일, 글자수, 언어 옵션 추가)
        news_content = generate_economic_news(
            transcripts, 
            style=style, 
            word_count=word_count, 
            language=language
        )
        
        # 제목 추출 (첫 번째 줄을 제목으로 사용)
        lines = news_content.split('\n')
        title = lines[0].replace("#", "").strip()
        if not title or len(title) < 5:
            title = "오늘의 경제/주식 전망"
        
        # 뉴스 사설 저장
        if save_news_article(title, news_content, "economic", video_ids):
            # 저장된 뉴스 사설 정보 반환
            return {
                "title": title,
                "content": news_content,
                "news_type": "economic",
                "created_at": datetime.now().isoformat(),
                "video_ids": video_ids,
                "style": style,
                "language": language
            }
        else:
            return None
    except Exception as e:
        print(f"경제 뉴스 사설 생성 중 오류 발생: {e}")
        conn.close()
        return None

def extract_keywords_from_recent_videos(hours: int = 24, max_keywords: int = 15) -> List[str]:
    """
    최근 지정된 시간 내의 비디오 자막을 사용하여 키워드를 추출합니다.
    
    :param hours: 몇 시간 이내의 비디오를 대상으로 할지 (기본값 24시간)
    :param max_keywords: 추출할 최대 키워드 수
    :return: 추출된 키워드 목록
    """
    from llm_handler import extract_keywords_from_transcripts
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 최근 비디오 조회 (timestamp를 datetime으로 비교)
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute("""
            SELECT id, title, transcript
            FROM videos
            WHERE created_at > ? AND transcript IS NOT NULL
            ORDER BY created_at DESC
        """, (since_time,))
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"최근 {hours}시간 내에 자막이 있는 비디오가 없습니다.")
            conn.close()
            return []
        
        # 비디오 정보 및 자막 추출
        transcripts = []
        
        for row in rows:
            transcript = row[2]
            
            if transcript:
                transcripts.append(transcript)
        
        conn.close()
        
        if not transcripts:
            print("자막이 있는 비디오가 없습니다.")
            return []
        
        # 키워드 추출
        keywords = extract_keywords_from_transcripts(transcripts, max_keywords)
        
        # 추출된 키워드를 데이터베이스에 저장
        save_extracted_keywords(keywords)
        
        return keywords
    except Exception as e:
        print(f"키워드 추출 중 오류 발생: {e}")
        conn.close()
        return []

def save_extracted_keywords(keywords: List[str]) -> bool:
    """
    추출된 키워드를 데이터베이스에 저장합니다.
    
    :param keywords: 키워드 목록
    :return: 성공 여부
    """
    if not keywords:
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 현재 시간
        now = datetime.now().isoformat()
        
        # 키워드 저장
        for keyword in keywords:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO extracted_keywords (keyword, created_at)
                    VALUES (?, ?)
                """, (keyword, now))
            except Exception as e:
                print(f"키워드 '{keyword}' 저장 중 오류 발생: {e}")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"키워드 저장 중 오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

def get_all_extracted_keywords(limit: int = 50) -> List[Dict[str, Any]]:
    """
    저장된 모든 추출된 키워드를 가져옵니다.
    
    :param limit: 최대 결과 수
    :return: 키워드 목록
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, keyword, created_at
            FROM extracted_keywords
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 결과를 딕셔너리 목록으로 변환
        keywords = []
        for row in rows:
            keywords.append({
                "id": row[0],
                "keyword": row[1],
                "created_at": row[2]
            })
        
        return keywords
    except Exception as e:
        print(f"키워드 조회 중 오류 발생: {e}")
        conn.close()
        return []

def generate_news_by_keywords(keywords: List[str], hours: int = 24, style: str = "basic", word_count: int = 1000, language: str = "ko") -> Optional[Dict[str, Any]]:
    """
    선택된 키워드에 초점을 맞춰 경제 뉴스 사설을 생성합니다.
    
    :param keywords: 초점을 맞출 키워드 목록
    :param hours: 몇 시간 이내의 비디오를 대상으로 할지 (기본값 24시간)
    :param style: 리포트 스타일 (basic, concise, editorial, news, research)
    :param word_count: 원하는 글자수 (대략적인 값)
    :param language: 언어 선택 (ko: 한국어, en: 영어)
    :return: 생성된 뉴스 사설 정보 (성공한 경우) 또는 None (실패한 경우)
    """
    from llm_handler import generate_news_by_keywords
    
    if not keywords:
        print("키워드가 없어 뉴스를 생성할 수 없습니다.")
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 최근 비디오 조회 (timestamp를 datetime으로 비교)
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute("""
            SELECT id, title, transcript
            FROM videos
            WHERE created_at > ? AND transcript IS NOT NULL
            ORDER BY created_at DESC
        """, (since_time,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print(f"최근 {hours}시간 내에 자막이 있는 비디오가 없습니다.")
            return None
        
        # 비디오 정보 및 자막 추출
        video_ids = []
        transcripts = []
        
        for row in rows:
            video_id = row[0]
            transcript = row[2]
            
            if transcript:
                video_ids.append(video_id)
                transcripts.append(transcript)
        
        if not transcripts:
            print("자막이 있는 비디오가 없습니다.")
            return None
        
        # 키워드 기반 뉴스 사설 생성
        news_content = generate_news_by_keywords(
            transcripts,
            keywords,
            style=style,
            word_count=word_count,
            language=language
        )
        
        # 제목 추출 (첫 번째 줄을 제목으로 사용)
        lines = news_content.split('\n')
        title = lines[0].replace("#", "").strip()
        if not title or len(title) < 5:
            # 키워드를 사용하여 제목 생성
            keywords_str = ", ".join(keywords)
            title = f"{keywords_str}에 관한 경제/주식 전망"
        
        # 뉴스 사설 저장
        if save_news_article(
            title, 
            news_content, 
            "economic", 
            video_ids, 
            style=style, 
            word_count=word_count, 
            language=language,
            keywords=keywords
        ):
            # 저장된 뉴스 사설 정보 반환
            return {
                "title": title,
                "content": news_content,
                "news_type": "economic",
                "created_at": datetime.now().isoformat(),
                "video_ids": video_ids,
                "style": style,
                "language": language,
                "keywords": keywords
            }
        else:
            return None
    except Exception as e:
        print(f"키워드 기반 뉴스 사설 생성 중 오류 발생: {e}")
        return None

# 데이터베이스 초기화 (모듈 로드 시 실행)
initialize_db() 