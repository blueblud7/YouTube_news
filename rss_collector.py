#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
YouTube RSS 피드 수집 시스템
API 할당량 없이 채널 업데이트 수집
"""

import feedparser
import requests
import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import streamlit as st

class YouTubeRSSCollector:
    def __init__(self, db_path: str = "youtube_news.db"):
        self.db_path = db_path
        self.base_rss_url = "https://www.youtube.com/feeds/videos.xml"
        
    def initialize_db(self):
        """RSS 수집을 위한 데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # RSS 채널 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rss_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE,
                channel_handle TEXT,
                title TEXT,
                rss_url TEXT,
                last_checked TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # RSS 동영상 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rss_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                channel_id TEXT,
                title TEXT,
                description TEXT,
                published_at TEXT,
                thumbnail_url TEXT,
                video_url TEXT,
                duration TEXT,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES rss_channels (channel_id)
            )
        ''')
        
        # RSS 키워드 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rss_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """YouTube URL에서 채널 ID 추출"""
        patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_channel_handle_from_id(self, channel_id: str) -> Optional[str]:
        """채널 ID로부터 핸들 추출 (RSS URL 생성용)"""
        # 채널 ID가 이미 핸들 형태인 경우
        if channel_id.startswith('@'):
            return channel_id[1:]
        
        # 채널 ID가 UC로 시작하는 경우 (실제 채널 ID)
        # 이 경우 RSS URL을 직접 사용
        return None
    
    def generate_rss_url(self, channel_identifier: str) -> str:
        """채널 식별자로부터 RSS URL 생성"""
        if channel_identifier.startswith('UC'):
            # 실제 채널 ID인 경우
            return f"{self.base_rss_url}?channel_id={channel_identifier}"
        else:
            # 핸들이거나 사용자명인 경우
            return f"{self.base_rss_url}?user={channel_identifier}"
    
    def add_channel(self, channel_url: str, title: str = None) -> bool:
        """채널 추가"""
        try:
            # 채널 ID 추출
            channel_id = self.extract_channel_id_from_url(channel_url)
            if not channel_id:
                st.error("유효한 YouTube 채널 URL이 아닙니다.")
                return False
            
            # 핸들 추출
            channel_handle = self.get_channel_handle_from_id(channel_id)
            
            # RSS URL 생성
            rss_url = self.generate_rss_url(channel_id)
            
            # 데이터베이스에 저장
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO rss_channels 
                (channel_id, channel_handle, title, rss_url, last_checked)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                channel_id,
                channel_handle,
                title or f"Channel {channel_id}",
                rss_url,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            st.success(f"✅ 채널 '{title or channel_id}'이(가) 추가되었습니다.")
            return True
            
        except Exception as e:
            st.error(f"채널 추가 실패: {str(e)}")
            return False
    
    def add_keyword(self, keyword: str) -> bool:
        """키워드 추가"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO rss_keywords (keyword)
                VALUES (?)
            ''', (keyword,))
            
            conn.commit()
            conn.close()
            
            st.success(f"✅ 키워드 '{keyword}'이(가) 추가되었습니다.")
            return True
            
        except Exception as e:
            st.error(f"키워드 추가 실패: {str(e)}")
            return False
    
    def get_all_channels(self) -> List[Dict]:
        """모든 RSS 채널 목록 가져오기"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, channel_id, channel_handle, title, rss_url, 
                   last_checked, is_active, created_at
            FROM rss_channels
            ORDER BY created_at DESC
        ''')
        
        channels = []
        for row in cursor.fetchall():
            channels.append({
                'id': row[0],
                'channel_id': row[1],
                'channel_handle': row[2],
                'title': row[3],
                'rss_url': row[4],
                'last_checked': row[5],
                'is_active': bool(row[6]),
                'created_at': row[7]
            })
        
        conn.close()
        return channels
    
    def get_all_keywords(self) -> List[Dict]:
        """모든 RSS 키워드 목록 가져오기"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, keyword, is_active, created_at
            FROM rss_keywords
            ORDER BY created_at DESC
        ''')
        
        keywords = []
        for row in cursor.fetchall():
            keywords.append({
                'id': row[0],
                'keyword': row[1],
                'is_active': bool(row[2]),
                'created_at': row[3]
            })
        
        conn.close()
        return keywords
    
    def fetch_channel_rss(self, channel_id: str, rss_url: str) -> List[Dict]:
        """채널 RSS 피드 가져오기"""
        try:
            # RSS 피드 파싱
            feed = feedparser.parse(rss_url)
            
            videos = []
            for entry in feed.entries:
                # 비디오 ID 추출
                video_id = entry.get('yt_videoid')
                if not video_id:
                    # URL에서 비디오 ID 추출
                    video_url = entry.get('link', '')
                    video_id_match = re.search(r'v=([a-zA-Z0-9_-]+)', video_url)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                    else:
                        continue
                
                # 이미 수집된 비디오인지 확인
                if self.is_video_exists(video_id):
                    continue
                
                # 비디오 정보 구성
                video_info = {
                    'video_id': video_id,
                    'channel_id': channel_id,
                    'title': entry.get('title', ''),
                    'description': entry.get('summary', ''),
                    'published_at': entry.get('published', ''),
                    'thumbnail_url': entry.get('media_thumbnail', [{}])[0].get('url', ''),
                    'video_url': entry.get('link', ''),
                    'duration': entry.get('media_content', [{}])[0].get('duration', ''),
                    'view_count': 0,  # RSS에서는 제공되지 않음
                    'like_count': 0   # RSS에서는 제공되지 않음
                }
                
                videos.append(video_info)
            
            return videos
            
        except Exception as e:
            st.error(f"RSS 피드 가져오기 실패 ({channel_id}): {str(e)}")
            return []
    
    def is_video_exists(self, video_id: str) -> bool:
        """비디오가 이미 존재하는지 확인"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM rss_videos WHERE video_id = ?', (video_id,))
        exists = cursor.fetchone() is not None
        
        conn.close()
        return exists
    
    def save_videos(self, videos: List[Dict]) -> int:
        """비디오 정보 저장"""
        if not videos:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for video in videos:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO rss_videos 
                    (video_id, channel_id, title, description, published_at, 
                     thumbnail_url, video_url, duration, view_count, like_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video['video_id'],
                    video['channel_id'],
                    video['title'],
                    video['description'],
                    video['published_at'],
                    video['thumbnail_url'],
                    video['video_url'],
                    video['duration'],
                    video['view_count'],
                    video['like_count']
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                    
            except Exception as e:
                st.warning(f"비디오 저장 실패 ({video['video_id']}): {str(e)}")
        
        conn.commit()
        conn.close()
        
        return saved_count
    
    def update_channel_last_checked(self, channel_id: str):
        """채널 마지막 체크 시간 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE rss_channels 
            SET last_checked = ? 
            WHERE channel_id = ?
        ''', (datetime.now().isoformat(), channel_id))
        
        conn.commit()
        conn.close()
    
    def collect_all_channels(self) -> Dict:
        """모든 채널에서 RSS 수집"""
        channels = self.get_all_channels()
        active_channels = [c for c in channels if c['is_active']]
        
        if not active_channels:
            st.warning("활성화된 RSS 채널이 없습니다.")
            return {'total_channels': 0, 'total_videos': 0, 'new_videos': 0}
        
        st.info(f"📡 {len(active_channels)}개 채널에서 RSS 피드를 수집합니다...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_videos = 0
        total_new_videos = 0
        
        for i, channel in enumerate(active_channels):
            status_text.text(f"채널 '{channel['title']}' 처리 중... ({i+1}/{len(active_channels)})")
            
            # RSS 피드 가져오기
            videos = self.fetch_channel_rss(channel['channel_id'], channel['rss_url'])
            
            if videos:
                # 새 비디오 저장
                new_videos = self.save_videos(videos)
                total_videos += len(videos)
                total_new_videos += new_videos
                
                # 마지막 체크 시간 업데이트
                self.update_channel_last_checked(channel['channel_id'])
                
                st.success(f"✅ {channel['title']}: {len(videos)}개 비디오, {new_videos}개 새 비디오")
            else:
                st.info(f"ℹ️ {channel['title']}: 새 비디오 없음")
            
            # 진행률 업데이트
            progress = (i + 1) / len(active_channels)
            progress_bar.progress(progress)
        
        status_text.text("완료!")
        
        result = {
            'total_channels': len(active_channels),
            'total_videos': total_videos,
            'new_videos': total_new_videos
        }
        
        st.success(f"🎉 RSS 수집 완료! {result['new_videos']}개 새 비디오 발견")
        return result
    
    def get_recent_videos(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """최근 비디오 가져오기"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT v.*, c.title as channel_title
            FROM rss_videos v
            JOIN rss_channels c ON v.channel_id = c.channel_id
            WHERE v.published_at >= ?
            ORDER BY v.published_at DESC
            LIMIT ?
        ''', (cutoff_time.isoformat(), limit))
        
        videos = []
        for row in cursor.fetchall():
            videos.append({
                'video_id': row[1],
                'channel_id': row[2],
                'title': row[3],
                'description': row[4],
                'published_at': row[5],
                'thumbnail_url': row[6],
                'video_url': row[7],
                'duration': row[8],
                'view_count': row[9],
                'like_count': row[10],
                'channel_title': row[12]
            })
        
        conn.close()
        return videos
    
    def search_videos_by_keyword(self, keyword: str, hours: int = 24) -> List[Dict]:
        """키워드로 비디오 검색"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT v.*, c.title as channel_title
            FROM rss_videos v
            JOIN rss_channels c ON v.channel_id = c.channel_id
            WHERE (v.title LIKE ? OR v.description LIKE ?)
            AND v.published_at >= ?
            ORDER BY v.published_at DESC
        ''', (f'%{keyword}%', f'%{keyword}%', cutoff_time.isoformat()))
        
        videos = []
        for row in cursor.fetchall():
            videos.append({
                'video_id': row[1],
                'channel_id': row[2],
                'title': row[3],
                'description': row[4],
                'published_at': row[5],
                'thumbnail_url': row[6],
                'video_url': row[7],
                'duration': row[8],
                'view_count': row[9],
                'like_count': row[10],
                'channel_title': row[12]
            })
        
        conn.close()
        return videos

# 전역 인스턴스
rss_collector = YouTubeRSSCollector()

def main():
    """RSS 수집기 메인 실행 함수"""
    print("🎯 YouTube RSS 수집기 시작")
    
    # 데이터베이스 초기화
    rss_collector.initialize_db()
    print("✅ 데이터베이스 초기화 완료")
    
    # 등록된 채널 확인
    channels = rss_collector.get_all_channels()
    print(f"📺 등록된 채널: {len(channels)}개")
    for channel in channels:
        print(f"  - {channel['title']} ({channel['channel_id']})")
    
    # 등록된 키워드 확인
    keywords = rss_collector.get_all_keywords()
    print(f"🔍 등록된 키워드: {len(keywords)}개")
    for keyword in keywords:
        print(f"  - {keyword['keyword']}")
    
    if channels:
        print("\n📡 RSS 피드 수집 시작...")
        result = rss_collector.collect_all_channels()
        print(f"✅ 수집 완료: {result['new_videos']}개 새 비디오")
    else:
        print("⚠️ 등록된 채널이 없습니다.")
    
    if keywords:
        print("\n🔍 키워드 검색 결과:")
        for keyword in keywords:
            videos = rss_collector.search_videos_by_keyword(keyword['keyword'], hours=24)
            print(f"  - '{keyword['keyword']}': {len(videos)}개 비디오")
            for video in videos[:3]:  # 최대 3개만 표시
                print(f"    * {video['title']} ({video['channel_title']})")

if __name__ == "__main__":
    main() 