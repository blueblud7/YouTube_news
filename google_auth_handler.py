#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
구글 OAuth 인증 및 유튜브 API 연동 핸들러
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import streamlit as st
from config import get_youtube_api_key

# OAuth 2.0 스코프
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

# 토큰 파일 경로
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'

class GoogleAuthHandler:
    def __init__(self):
        self.creds = None
        self.youtube_service = None
        
    def authenticate(self):
        """구글 OAuth 인증을 수행합니다."""
        # 토큰이 이미 있는지 확인
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                self.creds = pickle.load(token)
        
        # 유효한 자격 증명이 없거나 만료된 경우
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    st.error("credentials.json 파일이 필요합니다. Google Cloud Console에서 다운로드하세요.")
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # 토큰을 파일에 저장
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(self.creds, token)
        
        # YouTube API 서비스 생성
        try:
            self.youtube_service = build('youtube', 'v3', credentials=self.creds)
            return True
        except Exception as e:
            st.error(f"YouTube API 서비스 생성 중 오류: {str(e)}")
            return False
    
    def get_subscriptions(self, max_results=50):
        """사용자의 구독 채널 목록을 가져옵니다."""
        if not self.youtube_service:
            if not self.authenticate():
                return []
        
        try:
            subscriptions = []
            next_page_token = None
            
            while len(subscriptions) < max_results:
                request = self.youtube_service.subscriptions().list(
                    part='snippet',
                    mine=True,
                    maxResults=min(50, max_results - len(subscriptions)),
                    pageToken=next_page_token
                )
                
                response = request.execute()
                
                for item in response['items']:
                    subscription = {
                        'channel_id': item['snippet']['resourceId']['channelId'],
                        'channel_title': item['snippet']['title'],
                        'channel_description': item['snippet']['description'],
                        'thumbnail_url': item['snippet']['thumbnails']['default']['url'],
                        'subscribed_at': item['snippet']['publishedAt']
                    }
                    subscriptions.append(subscription)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return subscriptions
            
        except HttpError as e:
            st.error(f"구독 목록 가져오기 중 오류: {str(e)}")
            return []
    
    def search_videos_by_keyword(self, keyword, time_filter='1w', max_results=50):
        """키워드로 최신 동영상을 검색합니다."""
        if not self.youtube_service:
            if not self.authenticate():
                return []
        
        try:
            # 시간 필터 설정
            published_after = None
            if time_filter == '1d':
                published_after = datetime.now() - timedelta(days=1)
            elif time_filter == '1w':
                published_after = datetime.now() - timedelta(weeks=1)
            elif time_filter == '1m':
                published_after = datetime.now() - timedelta(days=30)
            elif time_filter == 'latest':
                published_after = datetime.now() - timedelta(hours=6)  # 최신 6시간
            
            published_after_str = published_after.isoformat() + 'Z' if published_after else None
            
            videos = []
            next_page_token = None
            
            while len(videos) < max_results:
                request = self.youtube_service.search().list(
                    part='snippet',
                    q=keyword,
                    type='video',
                    order='date',
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=next_page_token,
                    publishedAfter=published_after_str
                )
                
                response = request.execute()
                
                for item in response['items']:
                    video = {
                        'video_id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'channel_id': item['snippet']['channelId'],
                        'channel_title': item['snippet']['channelTitle'],
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    }
                    videos.append(video)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return videos
            
        except HttpError as e:
            st.error(f"동영상 검색 중 오류: {str(e)}")
            return []
    
    def get_subscription_videos(self, time_filter='1w', max_results=50):
        """구독 채널의 최신 동영상을 가져옵니다."""
        if not self.youtube_service:
            if not self.authenticate():
                return []
        
        try:
            # 구독 채널 목록 가져오기
            subscriptions = self.get_subscriptions(max_results=100)
            if not subscriptions:
                return []
            
            # 시간 필터 설정
            published_after = None
            if time_filter == '1d':
                published_after = datetime.now() - timedelta(days=1)
            elif time_filter == '1w':
                published_after = datetime.now() - timedelta(weeks=1)
            elif time_filter == '1m':
                published_after = datetime.now() - timedelta(days=30)
            elif time_filter == 'latest':
                published_after = datetime.now() - timedelta(hours=6)
            
            published_after_str = published_after.isoformat() + 'Z' if published_after else None
            
            all_videos = []
            
            # 각 구독 채널의 최신 동영상 가져오기
            for subscription in subscriptions:
                try:
                    request = self.youtube_service.search().list(
                        part='snippet',
                        channelId=subscription['channel_id'],
                        type='video',
                        order='date',
                        maxResults=10,  # 채널당 최대 10개
                        publishedAfter=published_after_str
                    )
                    
                    response = request.execute()
                    
                    for item in response['items']:
                        video = {
                            'video_id': item['id']['videoId'],
                            'title': item['snippet']['title'],
                            'description': item['snippet']['description'],
                            'channel_id': item['snippet']['channelId'],
                            'channel_title': item['snippet']['channelTitle'],
                            'published_at': item['snippet']['publishedAt'],
                            'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                            'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                            'subscription': subscription['channel_title']
                        }
                        all_videos.append(video)
                        
                        if len(all_videos) >= max_results:
                            break
                    
                    if len(all_videos) >= max_results:
                        break
                        
                except HttpError as e:
                    st.warning(f"채널 {subscription['channel_title']}의 동영상 가져오기 실패: {str(e)}")
                    continue
            
            # 발행일 기준으로 정렬
            all_videos.sort(key=lambda x: x['published_at'], reverse=True)
            return all_videos[:max_results]
            
        except HttpError as e:
            st.error(f"구독 동영상 가져오기 중 오류: {str(e)}")
            return []
    
    def get_video_details(self, video_id):
        """동영상의 상세 정보를 가져옵니다."""
        if not self.youtube_service:
            if not self.authenticate():
                return None
        
        try:
            request = self.youtube_service.videos().list(
                part='snippet,statistics',
                id=video_id
            )
            
            response = request.execute()
            
            if response['items']:
                item = response['items'][0]
                return {
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_id': item['snippet']['channelId'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0)),
                    'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                    'url': f"https://www.youtube.com/watch?v={item['id']}"
                }
            
            return None
            
        except HttpError as e:
            st.error(f"동영상 상세 정보 가져오기 중 오류: {str(e)}")
            return None

# 전역 인스턴스
auth_handler = GoogleAuthHandler() 