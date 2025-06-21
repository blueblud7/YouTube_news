#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
자동 OAuth 설정 도구 - 개선된 버전
"""

import streamlit as st
import webbrowser
import requests
import json
import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

class AutoOAuthSetup:
    def __init__(self):
        self.youtube_service = None
        self.authenticated = False
        self.access_token = None
        self.refresh_token = None
        self.user_email = None
        self.user_info = None
        self.credentials = None
        self.token_expiry = None
        
        # YouTube API 스코프
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
        
    def setup_oauth_automatically(self):
        """자동 OAuth 설정 - 개선된 버전"""
        st.markdown("### 🔐 구글 로그인 설정")
        st.markdown("아래 방법 중 하나를 선택하여 구글 계정으로 로그인하세요.")
        
        # 세션에서 oauth_method 확인
        oauth_method = st.session_state.get('oauth_method', 'playground')
        
        # 방법 선택
        if oauth_method == "direct":
            method = "🔑 Access Token 직접 입력"
        elif oauth_method == "advanced":
            method = "⚙️ 고급 OAuth 설정 (권장)"
        else:
            method = "🌐 Google OAuth Playground (간단)"
        
        # 방법 선택 (세션 상태에 따라 자동 선택)
        method = st.radio(
            "로그인 방법 선택",
            [
                "🌐 Google OAuth Playground (간단)",
                "🔑 Access Token 직접 입력",
                "⚙️ 고급 OAuth 설정 (권장)"
            ],
            index=0 if oauth_method == "playground" else (1 if oauth_method == "direct" else 2),
            key="oauth_method_radio"
        )
        
        if method == "🌐 Google OAuth Playground (간단)":
            return self._setup_oauth_playground()
        elif method == "🔑 Access Token 직접 입력":
            return self._setup_access_token()
        else:
            return self._setup_advanced_oauth()
    
    def _setup_oauth_playground(self):
        """Google OAuth Playground를 통한 설정 - 개선된 버전"""
        st.markdown("#### 🌐 Google OAuth Playground 사용법")
        
        # 주의사항 표시
        st.warning("""
        ⚠️ **주의사항**
        - OAuth Playground에서 얻은 토큰은 1시간 후 만료됩니다
        - 만료 후에는 다시 새로운 토큰을 발급받아야 합니다
        - 더 안정적인 사용을 위해서는 '고급 OAuth 설정'을 권장합니다
        """)
        
        # 1단계: OAuth Playground 링크
        st.markdown("**1단계: Google OAuth Playground 접속**")
        oauth_url = "https://developers.google.com/oauthplayground/"
        if st.button("🔗 OAuth Playground 열기", key="open_oauth_playground"):
            webbrowser.open(oauth_url)
        
        st.markdown(f"또는 직접 링크를 클릭하세요: [Google OAuth Playground]({oauth_url})")
        
        # 2단계: 설정 안내
        st.markdown("""
        **2단계: OAuth Playground에서 설정**
        
        1. **스코프 설정**: 오른쪽 패널에서 다음 스코프를 선택하세요:
           - `YouTube Data API v3` → `https://www.googleapis.com/auth/youtube.readonly`
        
        2. **Authorize APIs 클릭**: "Authorize APIs" 버튼을 클릭하세요
        
        3. **구글 계정으로 로그인**: 구글 계정을 선택하고 권한을 허용하세요
        
        4. **Exchange authorization code for tokens 클릭**: "Exchange authorization code for tokens" 버튼을 클릭하세요
        
        5. **Access Token 복사**: 생성된 Access Token을 복사하세요
        """)
        
        # 3단계: Access Token 입력
        st.markdown("**3단계: Access Token 입력**")
        access_token = st.text_input(
            "Access Token을 입력하세요:",
            type="password",
            placeholder="ya29.a0AfB_byC...",
            key="access_token_input"
        )
        
        if st.button("🔐 로그인 테스트", key="test_login"):
            if access_token:
                return self._test_and_save_token(access_token)
            else:
                st.error("Access Token을 입력해주세요.")
        
        return False
    
    def _setup_access_token(self):
        """Access Token 직접 입력 - 개선된 버전"""
        st.markdown("#### 🔑 Access Token 직접 입력")
        st.markdown("이미 가지고 있는 Access Token이 있다면 직접 입력할 수 있습니다.")
        
        st.warning("⚠️ Access Token은 1시간 후 만료되므로 주기적으로 갱신이 필요합니다.")
        
        access_token = st.text_input(
            "Access Token:",
            type="password",
            placeholder="ya29.a0AfB_byC...",
            key="direct_access_token"
        )
        
        if st.button("🔐 로그인 테스트", key="test_direct_token"):
            if access_token:
                return self._test_and_save_token(access_token)
            else:
                st.error("Access Token을 입력해주세요.")
        
        return False
    
    def _setup_advanced_oauth(self):
        """고급 OAuth 설정 - Refresh Token 포함"""
        st.markdown("#### ⚙️ 고급 OAuth 설정")
        st.markdown("이 방법은 Refresh Token을 포함하여 더 안정적인 로그인을 제공합니다.")
        
        # OAuth 클라이언트 설정 파일 확인
        if not os.path.exists('credentials.json'):
            st.error("""
            ❌ **OAuth 클라이언트 설정 파일이 없습니다**
            
            고급 OAuth 설정을 사용하려면 다음이 필요합니다:
            
            1. **Google Cloud Console**에서 프로젝트 생성
            2. **YouTube Data API v3** 활성화
            3. **OAuth 2.0 클라이언트 ID** 생성
            4. **credentials.json** 파일 다운로드
            
            자세한 설정 방법은 [Google Cloud Console](https://console.cloud.google.com/)을 참조하세요.
            """)
            
            if st.button("📖 설정 가이드 보기", key="show_guide"):
                st.markdown("""
                ### 📖 OAuth 클라이언트 설정 가이드
                
                1. **Google Cloud Console 접속**: https://console.cloud.google.com/
                2. **새 프로젝트 생성** 또는 기존 프로젝트 선택
                3. **API 및 서비스** → **라이브러리**에서 **YouTube Data API v3** 활성화
                4. **사용자 인증 정보** → **사용자 인증 정보 만들기** → **OAuth 2.0 클라이언트 ID**
                5. **애플리케이션 유형**: 데스크톱 앱 선택
                6. **credentials.json** 파일 다운로드하여 프로젝트 루트에 저장
                """)
            
            return False
        
        # OAuth 플로우 실행
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', self.SCOPES)
            
            # 로컬 서버에서 인증
            credentials = flow.run_local_server(port=8080)
            
            if credentials:
                return self._test_and_save_advanced_credentials(credentials)
            else:
                st.error("OAuth 인증에 실패했습니다.")
                return False
                
        except Exception as e:
            st.error(f"OAuth 설정 중 오류 발생: {str(e)}")
            return False
    
    def _test_and_save_token(self, access_token):
        """토큰 테스트 및 저장 - 개선된 버전"""
        try:
            # Credentials 객체 생성
            self.credentials = Credentials(access_token)
            
            # YouTube API 서비스 생성
            self.youtube_service = build('youtube', 'v3', credentials=self.credentials)
            
            # 테스트 API 호출
            request = self.youtube_service.channels().list(
                part="snippet",
                mine=True
            )
            
            response = request.execute()
            
            if response and 'items' in response and response['items']:
                # 로그인 성공
                self.authenticated = True
                self.access_token = access_token
                
                # 사용자 정보 저장
                channel_info = response['items'][0]['snippet']
                self.user_email = channel_info.get('title', 'Unknown')
                self.user_info = {
                    'authenticated': True,
                    'timestamp': datetime.now().isoformat(),
                    'email': self.user_email,
                    'channel_id': response['items'][0]['id'],
                    'token_type': 'access_token_only',
                    'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
                }
                
                st.success(f"✅ 로그인 성공! 환영합니다, {self.user_email}님!")
                st.info("⚠️ 이 토큰은 1시간 후 만료됩니다. 만료 후 다시 로그인해주세요.")
                return True
            else:
                st.error("❌ 로그인 실패: 유효하지 않은 Access Token입니다.")
                return False
                
        except HttpError as e:
            if e.resp.status == 401:
                st.error("❌ 토큰이 만료되었거나 유효하지 않습니다. 새로운 토큰을 발급받아주세요.")
            else:
                st.error(f"❌ API 오류: {str(e)}")
            return False
        except Exception as e:
            st.error(f"❌ 오류: {str(e)}")
            return False
    
    def _test_and_save_advanced_credentials(self, credentials):
        """고급 자격 증명 테스트 및 저장"""
        try:
            # YouTube API 서비스 생성
            self.youtube_service = build('youtube', 'v3', credentials=credentials)
            
            # 테스트 API 호출
            request = self.youtube_service.channels().list(
                part="snippet",
                mine=True
            )
            
            response = request.execute()
            
            if response and 'items' in response and response['items']:
                # 로그인 성공
                self.authenticated = True
                self.credentials = credentials
                self.access_token = credentials.token
                self.refresh_token = credentials.refresh_token
                
                # 사용자 정보 저장
                channel_info = response['items'][0]['snippet']
                self.user_email = channel_info.get('title', 'Unknown')
                self.user_info = {
                    'authenticated': True,
                    'timestamp': datetime.now().isoformat(),
                    'email': self.user_email,
                    'channel_id': response['items'][0]['id'],
                    'token_type': 'oauth2_with_refresh',
                    'expires_at': credentials.expiry.isoformat() if credentials.expiry else None
                }
                
                st.success(f"✅ 로그인 성공! 환영합니다, {self.user_email}님!")
                st.success("🎉 Refresh Token이 포함되어 있어 자동 갱신이 가능합니다!")
                return True
            else:
                st.error("❌ 로그인 실패: API 응답이 올바르지 않습니다.")
                return False
                
        except Exception as e:
            st.error(f"❌ 오류: {str(e)}")
            return False
    
    def login_with_saved_credentials(self, saved_creds):
        """저장된 자격 증명으로 로그인 - 개선된 버전"""
        try:
            token_type = saved_creds.get('token_type', 'access_token_only')
            
            if token_type == 'oauth2_with_refresh':
                # Refresh Token이 있는 경우
                refresh_token = saved_creds.get('refresh_token')
                if not refresh_token:
                    return False
                
                # Credentials 객체 생성
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=saved_creds.get('client_id'),
                    client_secret=saved_creds.get('client_secret')
                )
                
                # 토큰 갱신 시도
                if credentials.expired:
                    credentials.refresh(Request())
                
                return self._test_and_save_advanced_credentials(credentials)
                
            else:
                # Access Token만 있는 경우
                access_token = saved_creds.get('access_token')
                if not access_token:
                    return False
                
                # 토큰 만료 확인
                expires_at = saved_creds.get('expires_at')
                if expires_at:
                    expiry_time = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiry_time:
                        st.warning("저장된 토큰이 만료되었습니다. 새로운 토큰을 발급받아주세요.")
                        return False
                
                return self._test_and_save_token(access_token)
            
        except Exception as e:
            st.error(f"저장된 자격 증명으로 로그인 실패: {str(e)}")
            return False
    
    def save_credentials_permanently(self, filename):
        """로그인 정보를 영구 저장 - 개선된 버전"""
        try:
            if not self.authenticated:
                return False
            
            credentials_data = {
                'email': self.user_email,
                'saved_at': datetime.now().isoformat(),
                'channel_id': self.user_info.get('channel_id') if self.user_info else None,
                'token_type': self.user_info.get('token_type', 'access_token_only'),
                'expires_at': self.user_info.get('expires_at')
            }
            
            if self.user_info.get('token_type') == 'oauth2_with_refresh':
                # OAuth2 with Refresh Token
                credentials_data.update({
                    'refresh_token': self.refresh_token,
                    'client_id': self.credentials.client_id,
                    'client_secret': self.credentials.client_secret
                })
            else:
                # Access Token only
                credentials_data['access_token'] = self.access_token
            
            with open(filename, 'w') as f:
                json.dump(credentials_data, f, indent=2)
            
            return True
            
        except Exception as e:
            st.error(f"자격 증명 저장 실패: {str(e)}")
            return False
    
    def get_credentials(self):
        """OAuth2 credentials 반환 - 토큰 갱신 포함"""
        if not self.credentials:
            return None
        
        # 토큰 만료 확인 및 갱신
        if hasattr(self.credentials, 'expired') and self.credentials.expired:
            try:
                self.credentials.refresh(Request())
                st.info("🔄 토큰이 자동으로 갱신되었습니다.")
            except Exception as e:
                st.error(f"토큰 갱신 실패: {str(e)}")
                return None
        
        return self.credentials
    
    def get_subscription_videos(self, time_filter="latest", max_results=50):
        """구독 채널의 최신 동영상 가져오기 - 개선된 버전"""
        try:
            if not self.authenticated or not self.youtube_service:
                st.error("먼저 구글 로그인을 해주세요.")
                return None
            
            # 자격 증명 상태 확인 및 갱신
            if not self._ensure_valid_credentials():
                return None
            
            # 구독 채널 목록 가져오기
            subscriptions_response = self.youtube_service.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=50
            ).execute()
            
            if not subscriptions_response.get('items'):
                st.warning("구독한 채널이 없습니다.")
                return None
            
            # 시간 필터 설정
            if time_filter == "latest":
                # 최신 6시간
                time_threshold = datetime.now() - timedelta(hours=6)
            elif time_filter == "1d":
                time_threshold = datetime.now() - timedelta(days=1)
            elif time_filter == "1w":
                time_threshold = datetime.now() - timedelta(weeks=1)
            elif time_filter == "1m":
                time_threshold = datetime.now() - timedelta(days=30)
            else:
                time_threshold = datetime.now() - timedelta(hours=6)
            
            videos = []
            
            # 진행 상황 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 각 구독 채널에서 최신 동영상 가져오기
            for i, subscription in enumerate(subscriptions_response['items']):
                channel_id = subscription['snippet']['resourceId']['channelId']
                channel_title = subscription['snippet']['title']
                
                # 진행 상황 업데이트
                progress = (i + 1) / len(subscriptions_response['items'])
                progress_bar.progress(progress)
                status_text.text(f"채널 '{channel_title}'에서 동영상 가져오는 중... ({i+1}/{len(subscriptions_response['items'])})")
                
                try:
                    # 채널의 최신 동영상 검색
                    search_response = self.youtube_service.search().list(
                        part="snippet",
                        channelId=channel_id,
                        type="video",
                        order="date",
                        maxResults=10
                    ).execute()
                    
                    for item in search_response.get('items', []):
                        published_at = datetime.fromisoformat(
                            item['snippet']['publishedAt'].replace('Z', '+00:00')
                        )
                        
                        # 시간 필터 적용
                        if published_at >= time_threshold:
                            video_info = {
                                'video_id': item['id']['videoId'],
                                'title': item['snippet']['title'],
                                'description': item['snippet']['description'],
                                'channel_title': item['snippet']['channelTitle'],
                                'published_at': item['snippet']['publishedAt'],
                                'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                                'subscription': channel_title
                            }
                            videos.append(video_info)
                            
                            if len(videos) >= max_results:
                                break
                    
                    if len(videos) >= max_results:
                        break
                        
                except HttpError as e:
                    if e.resp.status == 403:
                        st.warning(f"채널 '{channel_title}'에 대한 접근 권한이 없습니다.")
                    else:
                        st.warning(f"채널 '{channel_title}'에서 동영상을 가져오는 중 오류: {str(e)}")
                    continue
                except Exception as e:
                    st.warning(f"채널 '{channel_title}'에서 동영상을 가져오는 중 오류: {str(e)}")
                    continue
            
            # 진행 상황 완료
            progress_bar.progress(1.0)
            status_text.text("완료!")
            
            # 발행일 기준으로 정렬
            videos.sort(key=lambda x: x['published_at'], reverse=True)
            
            return videos[:max_results]
            
        except HttpError as e:
            if e.resp.status == 401:
                st.error("❌ 인증이 만료되었습니다. 다시 로그인해주세요.")
                self.authenticated = False
            else:
                st.error(f"구독 채널 동영상 가져오기 실패: {str(e)}")
            return None
        except Exception as e:
            st.error(f"구독 채널 동영상 가져오기 실패: {str(e)}")
            return None
    
    def search_videos_by_keyword(self, keyword, time_filter="latest", max_results=50):
        """키워드로 동영상 검색 - 개선된 버전"""
        try:
            if not self.youtube_service:
                st.error("YouTube API 서비스가 초기화되지 않았습니다.")
                return None
            
            # 자격 증명 상태 확인 및 갱신
            if not self._ensure_valid_credentials():
                return None
            
            # 시간 필터 설정
            if time_filter == "latest":
                # 최신 6시간
                published_after = datetime.now() - timedelta(hours=6)
            elif time_filter == "1d":
                published_after = datetime.now() - timedelta(days=1)
            elif time_filter == "1w":
                published_after = datetime.now() - timedelta(weeks=1)
            elif time_filter == "1m":
                published_after = datetime.now() - timedelta(days=30)
            else:
                published_after = datetime.now() - timedelta(hours=6)
            
            # ISO 형식으로 변환
            published_after_str = published_after.isoformat() + 'Z'
            
            # 동영상 검색
            search_response = self.youtube_service.search().list(
                part="snippet",
                q=keyword,
                type="video",
                order="date",
                publishedAfter=published_after_str,
                maxResults=max_results
            ).execute()
            
            videos = []
            for item in search_response.get('items', []):
                video_info = {
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail_url': item['snippet']['thumbnails']['medium']['url'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                }
                videos.append(video_info)
            
            return videos
            
        except HttpError as e:
            if e.resp.status == 401:
                st.error("❌ 인증이 만료되었습니다. 다시 로그인해주세요.")
                self.authenticated = False
            else:
                st.error(f"키워드 검색 실패: {str(e)}")
            return None
        except Exception as e:
            st.error(f"키워드 검색 실패: {str(e)}")
            return None
    
    def _ensure_valid_credentials(self):
        """자격 증명이 유효한지 확인하고 필요시 갱신"""
        if not self.credentials:
            return False
        
        try:
            # 토큰 만료 확인 및 갱신
            if hasattr(self.credentials, 'expired') and self.credentials.expired:
                if hasattr(self.credentials, 'refresh_token') and self.credentials.refresh_token:
                    # Refresh Token이 있으면 자동 갱신
                    self.credentials.refresh(Request())
                    st.info("🔄 토큰이 자동으로 갱신되었습니다.")
                else:
                    # Refresh Token이 없으면 수동 갱신 필요
                    st.error("❌ 토큰이 만료되었습니다. 다시 로그인해주세요.")
                    self.authenticated = False
                    return False
            
            return True
            
        except Exception as e:
            st.error(f"자격 증명 확인 중 오류: {str(e)}")
            self.authenticated = False
            return False
    
    def check_token_status(self):
        """토큰 상태 확인 및 정보 표시"""
        if not self.authenticated:
            return False
        
        try:
            if not self.credentials:
                return False
            
            # 토큰 정보 표시
            token_info = {
                'authenticated': self.authenticated,
                'email': self.user_email,
                'token_type': self.user_info.get('token_type', 'unknown'),
                'expires_at': self.user_info.get('expires_at', 'unknown')
            }
            
            if hasattr(self.credentials, 'expired'):
                token_info['is_expired'] = self.credentials.expired
                token_info['can_refresh'] = hasattr(self.credentials, 'refresh_token') and self.credentials.refresh_token is not None
            
            return token_info
            
        except Exception as e:
            st.error(f"토큰 상태 확인 중 오류: {str(e)}")
            return False
    
    def refresh_token_manually(self):
        """수동으로 토큰 갱신"""
        try:
            if not self.credentials or not hasattr(self.credentials, 'refresh_token'):
                st.error("Refresh Token이 없어 자동 갱신이 불가능합니다.")
                return False
            
            if not self.credentials.expired:
                st.info("토큰이 아직 유효합니다.")
                return True
            
            # 토큰 갱신
            self.credentials.refresh(Request())
            st.success("✅ 토큰이 성공적으로 갱신되었습니다!")
            
            # 사용자 정보 업데이트
            if self.user_info:
                self.user_info['timestamp'] = datetime.now().isoformat()
                if hasattr(self.credentials, 'expiry') and self.credentials.expiry:
                    self.user_info['expires_at'] = self.credentials.expiry.isoformat()
            
            return True
            
        except Exception as e:
            st.error(f"토큰 갱신 실패: {str(e)}")
            return False

# 전역 인스턴스
auto_oauth_setup = AutoOAuthSetup() 