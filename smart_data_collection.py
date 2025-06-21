#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
스마트 데이터 수집 시스템
대규모 채널 업데이트를 효율적으로 처리
"""

import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sqlite3
import json

class SmartDataCollector:
    def __init__(self, db_path: str = "youtube_news.db"):
        self.db_path = db_path
        self.api_quota_limit = 10000  # 기본 할당량
        self.api_quota_used = 0
        self.api_quota_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
    def initialize_db(self):
        """스마트 수집을 위한 데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 채널 우선순위 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_priority (
                channel_id TEXT PRIMARY KEY,
                title TEXT,
                subscriber_count INTEGER,
                upload_frequency REAL,
                last_upload_time TEXT,
                priority_score REAL,
                last_checked TEXT,
                next_check_time TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # API 할당량 추적 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_quota_tracking (
                date TEXT PRIMARY KEY,
                quota_used INTEGER DEFAULT 0,
                quota_limit INTEGER DEFAULT 10000,
                last_reset TEXT
            )
        ''')
        
        # 수집 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                collection_time TEXT,
                videos_found INTEGER,
                api_calls_used INTEGER,
                success BOOLEAN,
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def calculate_channel_priority(self, channel_data: Dict) -> float:
        """채널 우선순위 점수 계산"""
        score = 0.0
        
        # 구독자 수 (0-50점)
        subscriber_count = channel_data.get('subscriber_count', 0)
        if subscriber_count > 1000000:
            score += 50
        elif subscriber_count > 100000:
            score += 30
        elif subscriber_count > 10000:
            score += 15
        else:
            score += 5
        
        # 업로드 빈도 (0-30점)
        upload_frequency = channel_data.get('upload_frequency', 0)
        if upload_frequency > 5:  # 하루 5개 이상
            score += 30
        elif upload_frequency > 1:  # 하루 1개 이상
            score += 20
        elif upload_frequency > 0.1:  # 주 1개 이상
            score += 10
        else:
            score += 5
        
        # 마지막 업로드 시간 (0-20점)
        last_upload = channel_data.get('last_upload_time')
        if last_upload:
            last_upload_dt = datetime.fromisoformat(last_upload)
            hours_since_upload = (datetime.now() - last_upload_dt).total_seconds() / 3600
            
            if hours_since_upload < 24:
                score += 20
            elif hours_since_upload < 168:  # 1주일
                score += 10
            else:
                score += 5
        
        return score
    
    def update_channel_priority(self, channel_id: str, channel_data: Dict):
        """채널 우선순위 업데이트"""
        priority_score = self.calculate_channel_priority(channel_data)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO channel_priority 
            (channel_id, title, subscriber_count, upload_frequency, 
             last_upload_time, priority_score, last_checked, next_check_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            channel_id,
            channel_data.get('title', ''),
            channel_data.get('subscriber_count', 0),
            channel_data.get('upload_frequency', 0),
            channel_data.get('last_upload_time'),
            priority_score,
            datetime.now().isoformat(),
            self.calculate_next_check_time(priority_score)
        ))
        
        conn.commit()
        conn.close()
    
    def calculate_next_check_time(self, priority_score: float) -> str:
        """우선순위에 따른 다음 체크 시간 계산"""
        now = datetime.now()
        
        if priority_score >= 80:  # 고우선순위
            next_check = now + timedelta(hours=1)
        elif priority_score >= 60:  # 중우선순위
            next_check = now + timedelta(hours=3)
        elif priority_score >= 40:  # 저우선순위
            next_check = now + timedelta(hours=6)
        else:  # 최저우선순위
            next_check = now + timedelta(hours=12)
        
        return next_check.isoformat()
    
    def get_channels_to_check(self, max_channels: int = 100) -> List[Dict]:
        """체크할 채널 목록 가져오기 (우선순위 기반)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT channel_id, title, priority_score, next_check_time
            FROM channel_priority
            WHERE is_active = 1 
            AND next_check_time <= ?
            ORDER BY priority_score DESC, next_check_time ASC
            LIMIT ?
        ''', (datetime.now().isoformat(), max_channels))
        
        channels = []
        for row in cursor.fetchall():
            channels.append({
                'channel_id': row[0],
                'title': row[1],
                'priority_score': row[2],
                'next_check_time': row[3]
            })
        
        conn.close()
        return channels
    
    def estimate_api_calls_needed(self, channels: List[Dict]) -> int:
        """필요한 API 호출 수 추정"""
        # 채널별 동영상 검색: 100 units
        # 동영상 상세 정보: 1 unit per video (평균 10개 동영상)
        total_calls = len(channels) * (100 + 10)  # 채널당 110 units
        return total_calls
    
    def check_quota_availability(self, needed_calls: int) -> bool:
        """할당량 확인"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT quota_used, quota_limit FROM api_quota_tracking 
            WHERE date = ?
        ''', (today,))
        
        result = cursor.fetchone()
        if result:
            quota_used, quota_limit = result
        else:
            quota_used = 0
            quota_limit = self.api_quota_limit
        
        conn.close()
        
        return (quota_used + needed_calls) <= quota_limit
    
    def update_quota_usage(self, used_calls: int):
        """할당량 사용량 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT OR REPLACE INTO api_quota_tracking (date, quota_used, quota_limit)
            VALUES (?, COALESCE((SELECT quota_used FROM api_quota_tracking WHERE date = ?), 0) + ?, ?)
        ''', (today, today, used_calls, self.api_quota_limit))
        
        conn.commit()
        conn.close()
    
    def log_collection(self, channel_id: str, videos_found: int, api_calls_used: int, success: bool, error_message: str = None):
        """수집 로그 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO collection_log 
            (channel_id, collection_time, videos_found, api_calls_used, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            channel_id,
            datetime.now().isoformat(),
            videos_found,
            api_calls_used,
            success,
            error_message
        ))
        
        conn.commit()
        conn.close()
    
    def smart_collection_strategy(self, youtube_service, max_channels_per_batch: int = 50):
        """스마트 수집 전략 실행"""
        print(f"🚀 스마트 데이터 수집 시작: {datetime.now()}")
        
        # 1. 체크할 채널 목록 가져오기
        channels_to_check = self.get_channels_to_check(max_channels_per_batch)
        
        if not channels_to_check:
            print("✅ 체크할 채널이 없습니다.")
            return
        
        print(f"📋 {len(channels_to_check)}개 채널을 체크합니다.")
        
        # 2. 필요한 API 호출 수 추정
        estimated_calls = self.estimate_api_calls_needed(channels_to_check)
        print(f"📊 예상 API 호출: {estimated_calls} units")
        
        # 3. 할당량 확인
        if not self.check_quota_availability(estimated_calls):
            print(f"⚠️ 할당량 부족! 예상 {estimated_calls} units 필요")
            # 우선순위가 높은 채널만 선택
            channels_to_check = channels_to_check[:max_channels_per_batch // 2]
            estimated_calls = self.estimate_api_calls_needed(channels_to_check)
            print(f"🔄 {len(channels_to_check)}개 채널로 조정")
        
        # 4. 채널별 데이터 수집
        total_api_calls = 0
        total_videos_found = 0
        
        for i, channel in enumerate(channels_to_check):
            try:
                print(f"📺 [{i+1}/{len(channels_to_check)}] {channel['title']} 처리 중...")
                
                # 채널의 최신 동영상 검색 (100 units)
                search_response = youtube_service.search().list(
                    part="snippet",
                    channelId=channel['channel_id'],
                    type="video",
                    order="date",
                    maxResults=10
                ).execute()
                
                api_calls_used = 100  # 검색 비용
                videos_found = len(search_response.get('items', []))
                
                # 동영상 상세 정보 수집 (1 unit per video)
                for video in search_response.get('items', []):
                    video_id = video['id']['videoId']
                    
                    # 동영상 상세 정보 가져오기 (1 unit)
                    video_response = youtube_service.videos().list(
                        part="snippet,statistics",
                        id=video_id
                    ).execute()
                    
                    api_calls_used += 1
                    
                    # 여기서 동영상 데이터를 저장하거나 처리
                    if video_response.get('items'):
                        video_data = video_response['items'][0]
                        # TODO: 동영상 데이터 저장 로직
                
                total_api_calls += api_calls_used
                total_videos_found += videos_found
                
                # 로그 기록
                self.log_collection(
                    channel['channel_id'], 
                    videos_found, 
                    api_calls_used, 
                    True
                )
                
                # 채널 우선순위 업데이트
                channel_data = {
                    'title': channel['title'],
                    'subscriber_count': 0,  # 실제로는 API로 가져와야 함
                    'upload_frequency': videos_found / 7,  # 주간 평균
                    'last_upload_time': datetime.now().isoformat()
                }
                self.update_channel_priority(channel['channel_id'], channel_data)
                
                print(f"✅ {videos_found}개 동영상 발견, {api_calls_used} units 사용")
                
                # API 할당량 보호를 위한 지연
                time.sleep(random.uniform(0.1, 0.5))
                
            except Exception as e:
                print(f"❌ {channel['title']} 처리 실패: {str(e)}")
                self.log_collection(
                    channel['channel_id'], 
                    0, 
                    0, 
                    False, 
                    str(e)
                )
        
        # 5. 할당량 사용량 업데이트
        self.update_quota_usage(total_api_calls)
        
        print(f"🎉 수집 완료!")
        print(f"📊 총 API 호출: {total_api_calls} units")
        print(f"📺 총 동영상 발견: {total_videos_found}개")
        print(f"⏰ 다음 배치 예정: {datetime.now() + timedelta(hours=1)}")

# 사용 예시
if __name__ == "__main__":
    collector = SmartDataCollector()
    collector.initialize_db()
    
    # YouTube 서비스 객체가 필요합니다
    # from auto_oauth_setup import auto_oauth_setup
    # youtube_service = auto_oauth_setup.get_youtube_service()
    # collector.smart_collection_strategy(youtube_service) 