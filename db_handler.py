import sqlite3
from datetime import datetime, timedelta
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
        since_time = datetime.now() - timedelta(hours=hours)
        since_timestamp = since_time.isoformat()
    
    # 새 비디오 가져오기
    new_videos = get_new_videos_since(since_timestamp)
    
    # 채널별 그룹화
    channels = {}
    for video in new_videos:
        channel = video['channel_title']
        if channel not in channels:
            channels[channel] = []
        channels[channel].append(video)
    
    # 리포트 데이터 구성
    report = {
        'generated_at': datetime.now().isoformat(),
        'since': since_timestamp,
        'total_videos': len(new_videos),
        'channels': channels,
        'videos': new_videos
    }
    
    return report

# 데이터베이스 초기화 (모듈 로드 시 실행)
initialize_db() 