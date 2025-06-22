#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
YouTube 뉴스 자막 수집 및 요약 시스템 웹 인터페이스
실행 방법: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import sqlite3
import os
import time
from datetime import datetime, timedelta, timezone
import re
import json
import matplotlib.pyplot as plt
import seaborn as sns
from db_handler import save_video_data, get_summaries_for_video, generate_report, get_all_channels, add_channel, delete_channel, search_channels_by_keyword, get_all_keywords, add_keyword, delete_keyword, search_videos_by_keyword, get_all_editorials, save_editorial, get_editorials_by_date_range, delete_editorial, initialize_db

# 프로젝트 모듈 임포트
from config import load_config
from youtube_handler import extract_video_id, get_info_by_url, get_video_transcript, extract_channel_handle, get_channel_info_by_handle
from db_handler import save_video_data, get_summaries_for_video, generate_report, get_all_channels, add_channel, delete_channel, search_channels_by_keyword, get_all_keywords, add_keyword, delete_keyword, search_videos_by_keyword, get_all_editorials, save_editorial, get_editorials_by_date_range, delete_editorial
from llm_handler import summarize_transcript, analyze_transcript_with_type, get_available_analysis_types
from main import collect_data, run_scheduler

# 데이터베이스 파일 경로
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_news.db")

# 페이지 설정
st.set_page_config(
    page_title="YouTube 자막 분석 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바 메뉴
def sidebar_menu():
    st.sidebar.title("YouTube 자막 분석 시스템")
    
    # OAuth2 인증 상태 표시
    if st.session_state.get('google_oauth_authenticated', False):
        st.sidebar.success("✅ Google OAuth2 인증 완료")
    else:
        st.sidebar.info("🔐 Google 로그인이 필요합니다")
    
    menu = st.sidebar.radio(
        "메뉴 선택",
        ["홈", "URL 처리", "채널 및 키워드 관리", "자막 분석", "키워드 분석", "저장된 분석 보기", "신규 콘텐츠 리포트", "저장된 리포트", "뉴스", "최신 영상 분석", "구글 로그인 및 최신 동영상"]
    )
    return menu

# 비디오 목록 가져오기
def get_videos_with_transcript(limit=50):
    """자막이 있는 비디오 목록을 가져옵니다."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT v.id, v.title, v.channel_title, length(v.transcript) as transcript_length, 
               v.published_at, v.view_count,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df

# 새 URL 처리 페이지
def url_processing_page():
    st.title("YouTube URL 처리")
    
    # OAuth2 인증 확인
    if not st.session_state.get('google_oauth_authenticated', False):
        st.error("⚠️ **Google OAuth2 인증 필요**\n\n이 기능을 사용하려면 먼저 Google 계정으로 로그인해야 합니다.\n\n**구글 로그인 및 최신 동영상** 탭에서 로그인 후 다시 시도해주세요.")
        return
    
    # 미리 채워진 URL이 있는지 확인
    prefill_url = getattr(st.session_state, 'prefill_url', '')
    
    with st.form("url_form"):
        url = st.text_input("YouTube URL 입력", placeholder="https://www.youtube.com/watch?v=...", value=prefill_url)
        analysis_types = st.multiselect(
            "분석 유형 선택",
            options=[t["code"] for t in get_available_analysis_types()],
            default=["summary"],
            format_func=lambda x: next((t["description"] for t in get_available_analysis_types() if t["code"] == x), x)
        )
        submitted = st.form_submit_button("처리 시작")
    
    # 미리 채워진 URL이 처리되면 세션에서 제거
    if prefill_url and 'prefill_url' in st.session_state:
        del st.session_state.prefill_url
    
    if submitted and url:
        try:
            # OAuth2 credentials 가져오기
            from auto_oauth_setup import auto_oauth_setup
            credentials = auto_oauth_setup.get_credentials()
            
            if not credentials:
                st.error("OAuth2 인증 정보를 가져올 수 없습니다. 다시 로그인해주세요.")
                return
            
            # 비디오 ID 추출
            video_id = extract_video_id(url)
            if not video_id:
                st.error("유효한 YouTube URL이 아닙니다.")
                return
            
            st.info(f"URL에서 추출한 비디오 ID: {video_id}")
            
            # 처리 과정 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 비디오 정보 가져오기
            status_text.text("비디오 정보 가져오는 중...")
            progress_bar.progress(10)
            
            video_info = get_info_by_url(f"https://www.youtube.com/watch?v={video_id}", credentials)
            if not video_info or not video_info.get("id"):
                st.error(f"비디오 ID {video_id}에서 정보를 가져오지 못했습니다.")
                return
            
            # 비디오 정보 표시
            progress_bar.progress(30)
            status_text.text("자막 추출 중...")
            
            # 자막 추출
            transcript, lang = get_video_transcript(video_id, credentials)
            
            if not transcript:
                st.error("해당 비디오에서 자막을 찾을 수 없습니다.")
                return
            
            progress_bar.progress(50)
            status_text.text("데이터베이스에 저장 중...")
            
            # 데이터베이스에 저장
            success = save_video_data(video_info, transcript)
            
            if not success:
                st.warning("비디오 정보가 이미 데이터베이스에 있습니다.")
            
            # 비디오 정보 표시
            st.subheader("비디오 정보")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**제목:** {video_info.get('title')}")
                st.write(f"**채널:** {video_info.get('channel_title')}")
                st.write(f"**게시일:** {video_info.get('published_at')}")
            with col2:
                st.write(f"**조회수:** {video_info.get('view_count'):,}")
                st.write(f"**자막 길이:** {len(transcript):,}자")
                st.write(f"**자막 언어:** {lang}")
            
            # 자막 일부 표시
            with st.expander("자막 미리보기 (처음 500자)"):
                st.text(transcript[:500] + "..." if len(transcript) > 500 else transcript)
            
            # 분석 처리
            if analysis_types:
                st.subheader("분석 결과")
                
                for i, analysis_type in enumerate(analysis_types):
                    progress_value = 50 + (i / len(analysis_types)) * 50
                    progress_bar.progress(int(progress_value))
                    status_text.text(f"{analysis_type} 분석 중...")
                    
                    with st.spinner(f"{analysis_type} 분석 중..."):
                        start_time = time.time()
                        
                        if analysis_type == "summary":
                            result = summarize_transcript(transcript, analysis_type=analysis_type)
                        else:
                            result = analyze_transcript_with_type(transcript, analysis_type)
                        
                        process_time = time.time() - start_time
                        
                        # 결과 표시
                        st.subheader(f"{analysis_type} 결과 (처리 시간: {process_time:.2f}초)")
                        st.markdown(result)
                        
                        # 데이터베이스에 저장
                        from db_handler import save_summary_to_db
                        save_summary_to_db(video_id, analysis_type, result)
            
            progress_bar.progress(100)
            status_text.text("처리 완료!")
            st.success("✅ URL 처리 및 분석이 완료되었습니다!")
            
        except Exception as e:
            st.error(f"처리 중 오류가 발생했습니다: {str(e)}")
            st.exception(e)

# 자막 분석 페이지
def transcript_analysis_page(selected_video_id=None):
    st.title("저장된 비디오 자막 분석")
    
    # 비디오 목록 가져오기
    videos_df = get_videos_with_transcript()
    
    if videos_df.empty:
        st.warning("자막이 있는 비디오가 없습니다.")
        return
    
    # 비디오 선택 (세션에서 선택된 비디오가 있으면 사용)
    if selected_video_id is None:
        selected_video = st.selectbox(
            "분석할 비디오 선택",
            options=videos_df["id"].tolist(),
            format_func=lambda x: f"{videos_df[videos_df['id'] == x]['title'].iloc[0]} ({videos_df[videos_df['id'] == x]['channel_title'].iloc[0]})"
        )
    else:
        if selected_video_id in videos_df["id"].tolist():
            selected_video = selected_video_id
            st.info(f"선택된 비디오: {videos_df[videos_df['id'] == selected_video]['title'].iloc[0]}")
        else:
            st.error("선택한 비디오를 찾을 수 없습니다.")
            selected_video = st.selectbox(
                "분석할 비디오 선택",
                options=videos_df["id"].tolist(),
                format_func=lambda x: f"{videos_df[videos_df['id'] == x]['title'].iloc[0]} ({videos_df[videos_df['id'] == x]['channel_title'].iloc[0]})"
            )
    
    if selected_video:
        # 선택된 비디오 정보 표시
        video_info = videos_df[videos_df["id"] == selected_video].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**제목:** {video_info['title']}")
            st.write(f"**채널:** {video_info['channel_title']}")
            st.write(f"**게시일:** {video_info['published_at']}")
        with col2:
            st.write(f"**조회수:** {video_info['view_count']:,}")
            st.write(f"**자막 길이:** {video_info['transcript_length']:,}자")
            st.write(f"**현재 분석 수:** {video_info['analysis_count']}")
        
        # 이미 분석된 유형 확인
        existing_summaries = get_summaries_for_video(selected_video)
        existing_types = list(existing_summaries.keys())
        
        # 분석 유형 선택
        available_types = [t["code"] for t in get_available_analysis_types()]
        new_types = [t for t in available_types if t not in existing_types]
        
        with st.form("analysis_form"):
            st.subheader("분석 옵션")
            
            analysis_types = st.multiselect(
                "분석 유형 선택",
                options=available_types,
                default=new_types[:1] if new_types else [],
                format_func=lambda x: next((t["description"] for t in get_available_analysis_types() if t["code"] == x), x)
            )
            
            force_reanalysis = st.checkbox("이미 분석된 유형도 다시 분석", value=False)
            
            submitted = st.form_submit_button("분석 시작")
        
        if submitted and analysis_types:
            # 선택된 분석 유형 처리
            filtered_types = analysis_types
            if not force_reanalysis:
                filtered_types = [t for t in analysis_types if t not in existing_types]
                if not filtered_types:
                    st.warning("모든 선택한 분석 유형이 이미 존재합니다. 새 분석 유형을 선택하거나 '이미 분석된 유형도 다시 분석' 옵션을 체크하세요.")
                    return
            
            # 자막 가져오기
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT transcript FROM videos WHERE id = ?", (selected_video,))
            transcript = cursor.fetchone()[0]
            conn.close()
            
            # 분석 처리
            progress_bar = st.progress(0)
            status_placeholder = st.empty()
            
            for i, analysis_type in enumerate(filtered_types):
                progress = int((i / len(filtered_types)) * 100)
                progress_bar.progress(progress)
                status_placeholder.text(f"{analysis_type} 분석 중...")
                
                with st.spinner(f"{analysis_type} 분석 중..."):
                    start_time = time.time()
                    
                    if analysis_type == "summary":
                        result = summarize_transcript(transcript, analysis_type=analysis_type)
                    else:
                        result = analyze_transcript_with_type(transcript, analysis_type)
                    
                    process_time = time.time() - start_time
                    
                    # 결과 표시
                    st.subheader(f"{analysis_type} 결과 (처리 시간: {process_time:.2f}초)")
                    st.markdown(result)
                    
                    # 데이터베이스에 저장
                    from db_handler import save_summary_to_db
                    save_summary_to_db(selected_video, analysis_type, result)
            
            progress_bar.progress(100)
            status_placeholder.text("분석 완료!")
            st.success("모든 분석이 완료되었습니다!")

# 저장된 분석 보기 페이지
def view_analysis_page(selected_video_id=None):
    st.title("저장된 분석 보기")
    
    # 비디오 목록 가져오기
    videos_df = get_videos_with_transcript()
    
    if videos_df.empty:
        st.warning("자막이 있는 비디오가 없습니다.")
        return
    
    # 비디오 선택 (URL 파라미터로 전달된 비디오 ID가 있으면 사용)
    if selected_video_id is not None and selected_video_id in videos_df["id"].tolist():
        selected_video = selected_video_id
        st.info(f"선택된 비디오: {videos_df[videos_df['id'] == selected_video]['title'].iloc[0]}")
    else:
        selected_video = st.selectbox(
            "비디오 선택",
            options=videos_df["id"].tolist(),
            format_func=lambda x: f"{videos_df[videos_df['id'] == x]['title'].iloc[0]} ({videos_df[videos_df['id'] == x]['channel_title'].iloc[0]})"
        )
    
    if selected_video:
        # 선택된 비디오 정보 표시
        video_info = videos_df[videos_df["id"] == selected_video].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**제목:** {video_info['title']}")
            st.write(f"**채널:** {video_info['channel_title']}")
        with col2:
            st.write(f"**게시일:** {video_info['published_at']}")
            st.write(f"**조회수:** {video_info['view_count']:,}")
        
        # 영상 링크
        st.markdown(f"[YouTube에서 보기](https://www.youtube.com/watch?v={selected_video})")
        
        # 저장된 분석 불러오기
        summaries = get_summaries_for_video(selected_video)
        
        if not summaries:
            st.warning("이 비디오에 대한 분석 결과가 없습니다.")
            return
        
        # 분석 유형 선택
        summary_type = st.selectbox(
            "분석 유형 선택",
            options=list(summaries.keys()),
            format_func=lambda x: next((t["description"] for t in get_available_analysis_types() if t["code"] == x), x)
        )
        
        if summary_type:
            # 선택된 분석 표시
            st.subheader(f"{summary_type} 결과")
            st.markdown(summaries[summary_type])

# 홈 페이지
def home_page():
    st.title("YouTube 자막 분석 시스템")
    
    # 시스템 개요
    st.markdown("""
    이 시스템은 YouTube 비디오의 자막을 수집하고 GPT-4o-mini를 사용하여 다양한 관점에서 요약 및 분석을 제공합니다.
    
    ## 주요 기능
    - YouTube URL을 입력하여 자막 수집 및 분석
    - 저장된 비디오의 자막 분석
    - 다양한 분석 유형 제공 (요약, 경제 분석, 간단 분석, 복합 분석)
    - 분석 결과 저장 및 조회
    
    ## 사용 방법
    1. 사이드바에서 원하는 메뉴를 선택하세요.
    2. URL 처리: YouTube URL을 입력하여 새 비디오를 처리합니다.
    3. 자막 분석: 이미 저장된 비디오의 자막을 다양한 관점에서 분석합니다.
    4. 저장된 분석 보기: 이전에 분석한 결과를 확인합니다.
    """)
    
    # 최근 처리된 비디오 표시
    st.subheader("최근 처리된 비디오")
    recent_videos = get_videos_with_transcript(limit=5)
    
    if recent_videos.empty:
        st.info("아직 처리된 비디오가 없습니다.")
    else:
        for i, video in recent_videos.iterrows():
            with st.container():
                col1, col2 = st.columns([1, 3])
                with col1:
                    # 썸네일 표시 (임베딩할 수 없으므로 링크로 대체)
                    st.markdown(f"[![Thumbnail](https://img.youtube.com/vi/{video['id']}/0.jpg)](https://www.youtube.com/watch?v={video['id']})")
                with col2:
                    st.markdown(f"**{video['title']}**")
                    st.markdown(f"채널: {video['channel_title']} | 조회수: {video['view_count']:,} | 분석: {video['analysis_count']}개")
                    st.markdown(f"[분석 보기](/?view={video['id']})")
                st.markdown("---")

# 채널 및 키워드 관리 페이지
def channel_keyword_management_page():
    """채널 및 키워드 관리 페이지 - RSS 기능 추가"""
    st.title("📺 채널 및 키워드 관리")
    
    # RSS 수집기 초기화
    from rss_collector import rss_collector
    rss_collector.initialize_db()
    
    # 탭 구조
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔗 RSS 채널 관리", 
        "🔍 RSS 키워드 관리", 
        "📡 RSS 수집 실행", 
        "📊 RSS 데이터 보기"
    ])
    
    with tab1:
        st.subheader("🔗 RSS 채널 관리")
        st.info("YouTube 채널 URL을 입력하면 RSS 피드로 자동 수집됩니다. (API 할당량 사용 안함)")
        
        # 새 채널 추가
        with st.form("add_rss_channel"):
            channel_url = st.text_input(
                "YouTube 채널 URL",
                placeholder="https://www.youtube.com/@channelname 또는 https://www.youtube.com/channel/UC...",
                help="채널 URL을 입력하세요. RSS 피드로 자동 수집됩니다."
            )
            channel_title = st.text_input(
                "채널 이름 (선택사항)",
                placeholder="채널의 표시 이름을 입력하세요",
                help="비워두면 자동으로 채널 ID가 사용됩니다."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("➕ 채널 추가")
            with col2:
                if st.form_submit_button("📡 RSS 테스트"):
                    if channel_url:
                        st.info("RSS 피드 테스트 기능은 개발 중입니다.")
        
        if submitted and channel_url:
            rss_collector.add_channel(channel_url, channel_title)
        
        # 채널 목록 표시
        st.markdown("### 📋 등록된 RSS 채널")
        channels = rss_collector.get_all_channels()
        
        if channels:
            for channel in channels:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{channel['title']}**")
                        st.markdown(f"`{channel['channel_id']}`")
                        if channel['last_checked']:
                            st.caption(f"마지막 체크: {channel['last_checked'][:19]}")
                    with col2:
                        status = "🟢 활성" if channel['is_active'] else "🔴 비활성"
                        st.markdown(status)
                    with col3:
                        if st.button("🗑️ 삭제", key=f"delete_channel_{channel['id']}"):
                            rss_collector.delete_channel(channel['channel_id'])
                            st.success(f"채널 '{channel['title']}'이(가) 삭제되었습니다.")
                            st.rerun()
                    st.markdown("---")
        else:
            st.info("등록된 RSS 채널이 없습니다. 위에서 채널을 추가해보세요!")
    
    with tab2:
        st.subheader("🔍 RSS 키워드 관리")
        st.info("관심 키워드를 등록하면 RSS 수집된 비디오에서 검색됩니다.")
        
        # 새 키워드 추가
        with st.form("add_rss_keyword"):
            keyword = st.text_input(
                "키워드",
                placeholder="예: AI, 기술, 뉴스, 게임...",
                help="관심 키워드를 입력하세요."
            )
            
            submitted = st.form_submit_button("➕ 키워드 추가")
        
        if submitted and keyword:
            rss_collector.add_keyword(keyword)
        
        # 키워드 목록 표시
        st.markdown("### 📋 등록된 키워드")
        keywords = rss_collector.get_all_keywords()
        
        if keywords:
            for keyword in keywords:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{keyword['keyword']}**")
                        st.caption(f"등록: {keyword['created_at'][:19]}")
                    
                    with col2:
                        status = "🟢 활성" if keyword['is_active'] else "🔴 비활성"
                        st.markdown(status)
                    
                    with col3:
                        if st.button("🗑️ 삭제", key=f"delete_keyword_{keyword['id']}"):
                            if rss_collector.delete_keyword(keyword['keyword']):
                                st.success(f"키워드 '{keyword['keyword']}'이(가) 삭제되었습니다.")
                                st.rerun()
                            else:
                                st.error("키워드 삭제에 실패했습니다.")
                    
                    st.markdown("---")
        else:
            st.info("등록된 키워드가 없습니다. 위에서 키워드를 추가해보세요!")
    
    with tab3:
        st.subheader("📡 RSS 수집 실행")
        st.info("등록된 모든 채널에서 RSS 피드를 수집합니다.")
        
        # 기간 선택 UI 추가
        st.markdown("### 📅 수집 기간 설정")
        
        col1, col2 = st.columns(2)
        
        with col1:
            collection_type = st.radio(
                "수집 방식",
                options=[
                    "🕐 최신 동영상만 (기본)",
                    "📅 특정 기간 동안"
                ],
                help="최신 동영상만 수집하거나 특정 기간 동안의 모든 동영상을 수집할 수 있습니다."
            )
        
        with col2:
            if collection_type == "📅 특정 기간 동안":
                days_back = st.slider(
                    "수집할 기간",
                    min_value=1,
                    max_value=90,
                    value=7,
                    help="최근 몇 일 동안의 동영상을 수집할지 선택하세요."
                )
                st.info(f"📅 최근 {days_back}일간의 동영상을 수집합니다.")
            else:
                days_back = 7  # 기본값
                st.info("🕐 최신 동영상만 수집합니다.")
        
        # 수집 실행 버튼
        st.markdown("### 🚀 수집 실행")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚀 RSS 수집 시작", key="start_rss_collection"):
                if collection_type == "📅 특정 기간 동안":
                    result = rss_collector.collect_channels_with_period(days_back)
                else:
                    result = rss_collector.collect_all_channels()
                
                if result['total_channels'] > 0:
                    st.success(f"""
                    📊 수집 결과:
                    - 처리된 채널: {result['total_channels']}개
                    - 발견된 비디오: {result['total_videos']}개
                    - 새로 저장된 비디오: {result['new_videos']}개
                    """)
                    
                    # 메인 DB 동기화
                    if st.button("🔄 메인 DB 동기화", key="sync_main_db"):
                        sync_result = rss_collector.sync_with_main_db()
                        st.success(f"✅ 메인 DB 동기화 완료: {sync_result['synced_videos']}개 비디오 동기화됨")
        
        with col2:
            if st.button("🔄 메인 DB 동기화", key="sync_main_db_standalone"):
                sync_result = rss_collector.sync_with_main_db()
                st.success(f"✅ 메인 DB 동기화 완료: {sync_result['synced_videos']}개 비디오 동기화됨")
        
        with col3:
            if st.button("📊 수집 통계", key="collection_stats"):
                channels = rss_collector.get_all_channels()
                keywords = rss_collector.get_all_keywords()
                recent_videos = rss_collector.get_recent_videos(hours=24)
                
                st.info(f"""
                📈 수집 통계:
                - 등록된 채널: {len(channels)}개
                - 등록된 키워드: {len(keywords)}개
                - 최근 24시간 수집: {len(recent_videos)}개 비디오
                """)
        
        # 수집 설정
        st.markdown("### ⚙️ 수집 설정")
        
        col1, col2 = st.columns(2)
        with col1:
            auto_collect = st.checkbox("자동 수집 활성화", value=False)
            if auto_collect:
                interval = st.selectbox(
                    "수집 간격",
                    options=[1, 3, 6, 12, 24],
                    format_func=lambda x: f"{x}시간",
                    index=2
                )
                st.info(f"자동 수집이 {interval}시간마다 실행됩니다.")
        
        with col2:
            max_videos_per_channel = st.number_input(
                "채널당 최대 비디오 수",
                min_value=5,
                max_value=50,
                value=20,
                help="각 채널에서 최대 몇 개의 비디오를 수집할지 설정합니다."
            )
    
    with tab4:
        st.subheader("📊 RSS 데이터 보기")
        
        # 시간 범위 선택 개선
        st.markdown("### 📅 데이터 조회 기간")
        
        col1, col2 = st.columns(2)
        
        with col1:
            time_filter_type = st.radio(
                "조회 방식",
                options=[
                    "⏰ 최근 시간",
                    "📅 특정 날짜 범위"
                ]
            )
        
        with col2:
            if time_filter_type == "⏰ 최근 시간":
                time_range = st.selectbox(
                    "시간 범위",
                    options=[1, 3, 6, 12, 24, 72, 168],
                    format_func=lambda x: f"최근 {x}시간" if x < 24 else f"최근 {x//24}일",
                    index=3
                )
                recent_videos = rss_collector.get_recent_videos(hours=time_range, limit=50)
            else:
                # 날짜 범위 선택
                col_a, col_b = st.columns(2)
                with col_a:
                    start_date = st.date_input(
                        "시작 날짜",
                        value=datetime.now() - timedelta(days=7),
                        max_value=datetime.now()
                    )
                with col_b:
                    end_date = st.date_input(
                        "종료 날짜",
                        value=datetime.now(),
                        max_value=datetime.now()
                    )
                
                if start_date and end_date:
                    start_str = start_date.isoformat()
                    end_str = end_date.isoformat()
                    recent_videos = rss_collector.get_videos_by_date_range(start_str, end_str)
                else:
                    recent_videos = []
        
        # 키워드 필터링
        st.markdown("### 🔍 키워드 필터링")
        
        # selected_keywords 변수 초기화
        selected_keywords = []
        
        keywords = rss_collector.get_all_keywords()
        if keywords:
            selected_keywords = st.multiselect(
                "키워드 선택 (여러 개 선택 가능)",
                options=[kw['keyword'] for kw in keywords],
                help="선택한 키워드가 포함된 비디오만 표시됩니다."
            )
            
            # 키워드 필터링 적용
            if selected_keywords:
                filtered_videos = []
                for keyword in selected_keywords:
                    keyword_videos = rss_collector.search_videos_by_keyword(keyword, hours=time_range if time_filter_type == "⏰ 최근 시간" else 24*7)
                    filtered_videos.extend(keyword_videos)
                
                # 중복 제거
                seen_ids = set()
                unique_videos = []
                for video in filtered_videos:
                    if video['video_id'] not in seen_ids:
                        seen_ids.add(video['video_id'])
                        unique_videos.append(video)
                
                recent_videos = unique_videos
        
        # 결과 표시
        if recent_videos:
            display_text = f"📺 조회 결과: {len(recent_videos)}개의 비디오"
            if selected_keywords:
                display_text += f" (키워드: {', '.join(selected_keywords)})"
            st.success(display_text)
            
            # 정렬 옵션
            col1, col2 = st.columns(2)
            with col1:
                sort_by = st.selectbox(
                    "정렬 기준",
                    options=["published_at", "title", "channel_title"],
                    format_func=lambda x: {"published_at": "업로드 날짜", "title": "제목", "channel_title": "채널명"}[x]
                )
            
            with col2:
                sort_order = st.radio("정렬 순서", ["내림차순", "오름차순"])
            
            # 정렬 적용
            reverse = sort_order == "내림차순"
            if sort_by == "published_at":
                recent_videos.sort(key=lambda x: x['published_at'], reverse=reverse)
            elif sort_by == "title":
                recent_videos.sort(key=lambda x: x['title'], reverse=reverse)
            elif sort_by == "channel_title":
                recent_videos.sort(key=lambda x: x['channel_title'], reverse=reverse)
            
            # 비디오 목록 표시
            for i, video in enumerate(recent_videos):
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        if video['thumbnail_url']:
                            st.image(video['thumbnail_url'], width=120)
                        else:
                            st.markdown("🖼️ 썸네일 없음")
                    
                    with col2:
                        st.markdown(f"**{video['title']}**")
                        st.markdown(f"**채널**: {video['channel_title']}")
                        st.markdown(f"**업로드**: {video['published_at'][:10]}")
                        
                        if video['description']:
                            desc_preview = video['description'][:100] + "..." if len(video['description']) > 100 else video['description']
                            st.markdown(f"📝 {desc_preview}")
                        
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.link_button("🔗 YouTube 보기", video['video_url'])
                        with col_b:
                            if st.button("📊 분석", key=f"analyze_{video['video_id']}"):
                                st.info("비디오 분석 기능은 개발 중입니다.")
                        with col_c:
                            if st.button("💾 저장", key=f"save_{video['video_id']}"):
                                st.info("비디오 저장 기능은 개발 중입니다.")
                    
                    st.markdown("---")
        else:
            st.info("해당 기간에 수집된 비디오가 없습니다.")

def newspaper_section():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Merriweather:wght@300;400;700&display=swap');
        
        .newspaper {
            font-family: 'Merriweather', serif;
            line-height: 1.6;
            color: #2c2c2c;
            background: #fafafa;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 0 30px rgba(0,0,0,0.1);
        }
        
        .masthead {
            font-family: 'Playfair Display', serif;
            font-size: 3rem;
            font-weight: 900;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .tagline {
            text-align: center;
            font-style: italic;
            color: #666;
            margin-bottom: 20px;
        }
        
        .date-edition {
            text-align: center;
            border-top: 1px solid #ddd;
            border-bottom: 1px solid #ddd;
            padding: 10px 0;
            margin-bottom: 30px;
        }
        
        .headline {
            font-family: 'Playfair Display', serif;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 15px;
        }
        
        .subheadline {
            font-size: 1.2rem;
            font-style: italic;
            color: #555;
            margin-bottom: 20px;
            border-left: 4px solid #d4af37;
            padding-left: 15px;
        }
        
        .article-text {
            column-count: 2;
            column-gap: 30px;
            text-align: justify;
            margin-bottom: 30px;
        }
        
        .sidebar {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        
        .sidebar-title {
            font-family: 'Playfair Display', serif;
            font-size: 1.4rem;
            font-weight: 700;
            margin-bottom: 15px;
            text-align: center;
            border-bottom: 2px solid #d4af37;
            padding-bottom: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="newspaper">', unsafe_allow_html=True)
    
    # 헤더
    st.markdown('<h1 class="masthead">데일리 뉴스</h1>', unsafe_allow_html=True)
    st.markdown('<p class="tagline">"신뢰할 수 있는 정보, 깊이 있는 분석"</p>', unsafe_allow_html=True)
    
    current_date = datetime.now().strftime("%Y년 %m월 %d일 %A")
    st.markdown(f'<div class="date-edition">{current_date}</div>', unsafe_allow_html=True)
    
    # 메인 콘텐츠
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<h2 class="headline">기술 혁신이 바꾸는 미래 사회</h2>', unsafe_allow_html=True)
        st.markdown('<p class="subheadline">인공지능과 자동화 기술이 가져올 변화와 우리의 준비</p>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="article-text">
            <p>21세기는 기술 혁신의 시대라고 불러도 과언이 아니다. 특히 인공지능, 머신러닝, 그리고 자동화 기술의 발전은 우리 사회 전반에 걸쳐 근본적인 변화를 가져오고 있다.</p>
            
            <p>전문가들은 향후 10년 내에 현재 존재하는 직업의 상당 부분이 자동화될 것이라고 전망하고 있다. 하지만 이것이 단순히 일자리 감소를 의미하지는 않는다. 새로운 기술의 도입은 동시에 새로운 형태의 일자리를 창출하기도 한다.</p>
            
            <p>교육계에서는 이러한 변화에 대비해 커리큘럼을 개편하고 있다. 단순 암기보다는 창의적 사고와 문제 해결 능력을 기르는 데 중점을 두고 있으며, 디지털 리터러시 교육을 강화하고 있다.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="sidebar">', unsafe_allow_html=True)
        st.markdown('<h3 class="sidebar-title">주요 뉴스</h3>', unsafe_allow_html=True)
        
        # 데이터베이스에서 최신 뉴스 가져오기
        editorials = get_all_editorials()
        if editorials:
            for editorial in editorials[:3]:
                st.markdown(f"**{editorial['title']}**")
                st.markdown(f"_{editorial['date']}_")
                st.markdown("---")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# 메인 함수
def main():
    # 세션 상태 초기화
    if 'google_oauth_authenticated' not in st.session_state:
        st.session_state.google_oauth_authenticated = False
        st.session_state.google_oauth_user_info = None
    
    # 데이터베이스 초기화
    initialize_db()
    
    # 구성 파일 로드
    config = load_config()
    
    # DB에서 채널 목록 가져오기
    db_channels = get_all_channels()
    db_channel_ids = [channel.get("channel_id") for channel in db_channels]
    
    # config.json에 있는 채널들을 DB에 추가 (OAuth2 인증 필요)
    # 이 부분은 OAuth2 인증 후에만 실행되어야 함
    if st.session_state.google_oauth_authenticated:
        from auto_oauth_setup import auto_oauth_setup
        credentials = auto_oauth_setup.get_credentials()
        
        if credentials:
            for channel_url in config["channels"]:
                handle = extract_channel_handle(channel_url)
                if handle:
                    channel_info = get_channel_info_by_handle(handle, credentials)
                    if channel_info and channel_info.get("id") and channel_info.get("id") not in db_channel_ids:
                        add_channel(
                            channel_id=channel_info.get("id"),
                            title=channel_info.get("title"),
                            handle=handle,
                            description=channel_info.get("description")
                        )
                        print(f"채널 '{channel_info.get('title')}' ({handle})가 DB에 추가되었습니다.")
    
    # 사이드바 메뉴 가져오기
    menu = sidebar_menu()
    
    # URL 파라미터 처리
    params = st.experimental_get_query_params()
    view_video = params.get("view", [None])[0]
    
    # 페이지 전환
    if menu == "홈":
        home_page()
    elif menu == "URL 처리":
        url_processing_page()
    elif menu == "채널 및 키워드 관리":
        channel_keyword_management_page()
    elif menu == "자막 분석":
        transcript_analysis_page()
    elif menu == "키워드 분석":
        keyword_analysis_page()
    elif menu == "저장된 분석 보기":
        if view_video:
            view_analysis_page(view_video)
        else:
            view_analysis_page()
    elif menu == "신규 콘텐츠 리포트":
        new_content_report_page()
    elif menu == "저장된 리포트":
        saved_reports_page()
    elif menu == "뉴스":
        news_page()
    elif menu == "최신 영상 분석":
        latest_videos_analysis_page()
    elif menu == "구글 로그인 및 최신 동영상":
        google_login_latest_videos_page()

def google_login_latest_videos_page():
    """구글 로그인을 통한 최신 동영상 검색 페이지 - 개선된 버전"""
    st.title("🔐 구글 로그인 및 최신 동영상")
    
    # 새로운 자동 OAuth 설정 핸들러 임포트
    from auto_oauth_setup import auto_oauth_setup
    
    # 영구 저장된 로그인 정보 확인
    saved_credentials_file = "saved_google_credentials.json"
    has_saved_credentials = os.path.exists(saved_credentials_file)
    
    # 세션 상태에서 로그인 정보 확인
    if 'google_oauth_authenticated' not in st.session_state:
        st.session_state.google_oauth_authenticated = False
        st.session_state.google_oauth_user_info = None
    
    # 저장된 자격 증명이 있으면 자동 로그인 시도
    if has_saved_credentials and not st.session_state.google_oauth_authenticated:
        try:
            with open(saved_credentials_file, 'r') as f:
                saved_creds = json.load(f)
            
            # 저장된 자격 증명으로 로그인 시도
            if auto_oauth_setup.login_with_saved_credentials(saved_creds):
                st.session_state.google_oauth_authenticated = True
                st.session_state.google_oauth_user_info = {
                    'authenticated': True,
                    'timestamp': datetime.now().isoformat(),
                    'email': saved_creds.get('email', 'Unknown')
                }
                st.success(f"✅ 저장된 계정으로 자동 로그인되었습니다: {saved_creds.get('email', 'Unknown')}")
        except Exception as e:
            st.warning(f"저장된 로그인 정보로 자동 로그인 실패: {str(e)}")
    
    # 로그인 상태 확인
    is_authenticated = st.session_state.google_oauth_authenticated or auto_oauth_setup.authenticated
    
    # 최초 접속 시 로그인 안내 표시
    if not is_authenticated:
        st.markdown("""
        ## 🎯 **YouTube 뉴스 시스템에 오신 것을 환영합니다!**
        
        ### 📋 **사용 가능한 기능들**
        
        **🔐 구글 로그인 후 사용 가능:**
        - 📺 **구독 채널 목록 확인**
        - 🎬 **구독 채널의 최신 동영상 가져오기**
        - 🔍 **키워드 기반 동영상 검색**
        
        **⚙️ API 키만으로 사용 가능:**
        - 🔍 **간단 키워드 검색**
        - 📊 **기본 동영상 정보 조회**
        """)
        
        # 저장된 자격 증명이 있는 경우
        if has_saved_credentials:
            st.markdown("### 🔑 **저장된 로그인 정보 발견!**")
            try:
                with open(saved_credentials_file, 'r') as f:
                    saved_creds = json.load(f)
                
                token_type = saved_creds.get('token_type', 'access_token_only')
                email = saved_creds.get('email', 'Unknown')
                
                if token_type == 'oauth2_with_refresh':
                    st.success(f"**등록된 계정**: {email} (자동 갱신 가능)")
                else:
                    st.info(f"**등록된 계정**: {email} (수동 갱신 필요)")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 저장된 계정으로 로그인", key="login_saved"):
                        if auto_oauth_setup.login_with_saved_credentials(saved_creds):
                            st.session_state.google_oauth_authenticated = True
                            st.session_state.google_oauth_user_info = {
                                'authenticated': True,
                                'timestamp': datetime.now().isoformat(),
                                'email': email
                            }
                            st.rerun()
                        else:
                            st.error("저장된 계정으로 로그인에 실패했습니다.")
                
                with col2:
                    if st.button("🗑️ 저장된 정보 삭제", key="delete_saved"):
                        try:
                            os.remove(saved_credentials_file)
                            st.success("저장된 로그인 정보가 삭제되었습니다.")
                            st.rerun()
                        except:
                            st.error("저장된 정보 삭제에 실패했습니다.")
            except:
                st.warning("저장된 로그인 정보를 읽을 수 없습니다.")
        
        # 새로운 로그인 옵션
        st.markdown("### 🔐 **새로운 구글 계정으로 로그인**")
        if has_saved_credentials:
            st.markdown("다른 구글 계정으로 로그인하려면 아래 방법을 사용하세요.")
        else:
            st.markdown("구글 계정으로 로그인하려면 아래 방법을 사용하세요.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🌐 OAuth Playground", key="new_oauth_login"):
                st.session_state.show_oauth_setup = True
                st.session_state.oauth_method = "playground"
                st.rerun()
        
        with col2:
            if st.button("🔑 Access Token", key="direct_token_login"):
                st.session_state.show_oauth_setup = True
                st.session_state.oauth_method = "direct"
                st.rerun()
        
        with col3:
            if st.button("⚙️ 고급 OAuth", key="advanced_oauth_login"):
                st.session_state.show_oauth_setup = True
                st.session_state.oauth_method = "advanced"
                st.rerun()
    
    # OAuth 설정 화면 표시
    if st.session_state.get('show_oauth_setup', False):
        st.markdown("### 🔐 새로운 구글 계정 로그인 설정")
        
        # 방법 선택
        oauth_method = st.session_state.get('oauth_method', 'playground')
        if oauth_method == "direct":
            method = "🔑 Access Token 직접 입력"
        elif oauth_method == "advanced":
            method = "⚙️ 고급 OAuth 설정 (권장)"
        else:
            method = "🌐 Google OAuth Playground (간단)"
        
        # OAuth 설정 실행
        if auto_oauth_setup.setup_oauth_automatically():
            st.session_state.google_oauth_authenticated = True
            st.session_state.google_oauth_user_info = {
                'authenticated': True,
                'timestamp': datetime.now().isoformat(),
                'email': auto_oauth_setup.user_email or 'Unknown'
            }
            st.session_state.show_oauth_setup = False
            
            # 로그인 정보 영구 저장
            if auto_oauth_setup.save_credentials_permanently(saved_credentials_file):
                st.success("✅ 로그인 정보가 영구 저장되었습니다!")
            
            st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("❌ 설정 취소", key="cancel_oauth_setup"):
                st.session_state.show_oauth_setup = False
                st.rerun()
        
        with col2:
            if st.button("🔄 다른 방법으로 시도", key="try_different_method"):
                st.session_state.show_oauth_setup = False
                st.rerun()
    
    # 로그인된 경우 탭 구조 표시
    if is_authenticated:
        # 로그인 상태 표시
        user_info = st.session_state.google_oauth_user_info or auto_oauth_setup.user_info
        if user_info:
            st.markdown(f"""
            ### ✅ **로그인 상태**
            - **계정**: {user_info.get('email', 'Unknown')}
            - **로그인 시간**: {user_info.get('timestamp', 'Unknown')}
            """)
        
        # 탭 구조
        tab1, tab2, tab3, tab4 = st.tabs([
            "🔑 로그인 상태", 
            "📺 구독 채널 동영상", 
            "🔍 키워드 검색", 
            "⚙️ 간단 검색 (API 키만)"
        ])
        
        with tab1:
            st.subheader("🔑 로그인 관리")
            
            if user_info:
                st.info(f"**현재 로그인된 계정**: {user_info.get('email', 'Unknown')}")
                st.info(f"**로그인 시간**: {user_info.get('timestamp', 'Unknown')}")
                
                # 토큰 상태 확인
                token_status = auto_oauth_setup.check_token_status()
                if token_status:
                    st.markdown("### 🔍 토큰 상태")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if token_status.get('token_type') == 'oauth2_with_refresh':
                            st.success("🔄 자동 갱신 가능")
                        else:
                            st.warning("⚠️ 수동 갱신 필요")
                    
                    with col2:
                        if token_status.get('is_expired', False):
                            st.error("❌ 토큰 만료됨")
                        else:
                            st.success("✅ 토큰 유효함")
                    
                    if token_status.get('expires_at') != 'unknown':
                        st.info(f"**만료 시간**: {token_status.get('expires_at')}")
                    
                    # 토큰 갱신 버튼
                    if token_status.get('can_refresh', False):
                        if st.button("🔄 토큰 갱신", key="refresh_token"):
                            if auto_oauth_setup.refresh_token_manually():
                                st.rerun()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔄 새로고침", key="refresh_login"):
                    st.rerun()
            
            with col2:
                if st.button("🚪 로그아웃", key="logout_button"):
                    st.session_state.google_oauth_authenticated = False
                    st.session_state.google_oauth_user_info = None
                    st.session_state.show_oauth_setup = False
                    st.rerun()
            
            with col3:
                if st.button("🗑️ 저장된 정보 삭제", key="delete_saved_from_tab"):
                    try:
                        if os.path.exists(saved_credentials_file):
                            os.remove(saved_credentials_file)
                            st.success("저장된 로그인 정보가 삭제되었습니다.")
                        else:
                            st.info("저장된 로그인 정보가 없습니다.")
                    except:
                        st.error("저장된 정보 삭제에 실패했습니다.")
        
        with tab2:
            st.subheader("📺 구독 채널 최신 동영상")
            
            if not is_authenticated:
                st.warning("먼저 구글 로그인을 해주세요.")
                st.info("💡 또는 '간단 검색 (API 키만)' 탭을 사용해보세요!")
            else:
                # 시간 필터 선택
                time_filter = st.selectbox(
                    "시간 범위 선택",
                    options=[
                        ("latest", "최신 (6시간 이내)"),
                        ("1d", "1일 이내"),
                        ("1w", "1주일 이내"),
                        ("1m", "1개월 이내")
                    ],
                    format_func=lambda x: x[1],
                    key="subscription_time_filter"
                )[0]
                
                # 최대 결과 수 선택
                max_results = st.slider("최대 동영상 수", 10, 100, 50, key="subscription_max_results")
                
                if st.button("구독 채널 동영상 가져오기", key="subscription_fetch"):
                    videos = auto_oauth_setup.get_subscription_videos(
                        time_filter=time_filter,
                        max_results=max_results
                    )
                    
                    if videos:
                        st.success(f"✅ {len(videos)}개의 동영상을 찾았습니다!")
                        
                        # 동영상 목록 표시
                        for i, video in enumerate(videos):
                            with st.container():
                                col1, col2 = st.columns([1, 3])
                                
                                with col1:
                                    st.image(video['thumbnail_url'], width=120)
                                
                                with col2:
                                    st.markdown(f"**{video['title']}**")
                                    st.markdown(f"**채널**: {video['channel_title']}")
                                    st.markdown(f"**구독 채널**: {video.get('subscription', 'Unknown')}")
                                    st.markdown(f"**업로드**: {video['published_at'][:10]}")
                                    
                                    if st.button(f"분석하기", key=f"analyze_subscription_{i}"):
                                        st.session_state.selected_video_url = video['url']
                                        st.rerun()
                                
                                st.markdown("---")
                    else:
                        st.warning("조건에 맞는 동영상을 찾을 수 없습니다.")
        
        with tab3:
            st.subheader("🔍 키워드 기반 동영상 검색")
            
            if not is_authenticated:
                st.warning("먼저 구글 로그인을 해주세요.")
                st.info("💡 또는 '간단 검색 (API 키만)' 탭을 사용해보세요!")
            else:
                # 검색 키워드 입력
                keyword = st.text_input("검색 키워드", placeholder="예: AI, 기술, 뉴스, 게임...", key="oauth_keyword_input")
                
                # 시간 필터 선택
                time_filter = st.selectbox(
                    "시간 범위 선택",
                    options=[
                        ("latest", "최신 (6시간 이내)"),
                        ("1d", "1일 이내"),
                        ("1w", "1주일 이내"),
                        ("1m", "1개월 이내")
                    ],
                    format_func=lambda x: x[1],
                    key="keyword_time_filter"
                )[0]
                
                # 최대 결과 수 선택
                max_results = st.slider("최대 동영상 수", 10, 100, 50, key="keyword_max_results")
                
                if st.button("키워드로 검색", key="oauth_keyword_search") and keyword:
                    videos = auto_oauth_setup.search_videos_by_keyword(
                        keyword=keyword,
                        time_filter=time_filter,
                        max_results=max_results
                    )
                    
                    if videos:
                        st.success(f"✅ '{keyword}' 키워드로 {len(videos)}개의 동영상을 찾았습니다!")
                        
                        # 동영상 목록 표시
                        for i, video in enumerate(videos):
                            with st.container():
                                col1, col2 = st.columns([1, 3])
                                
                                with col1:
                                    st.image(video['thumbnail_url'], width=120)
                                
                                with col2:
                                    st.markdown(f"**{video['title']}**")
                                    st.markdown(f"**채널**: {video['channel_title']}")
                                    st.markdown(f"**업로드**: {video['published_at'][:10]}")
                                    
                                    if st.button(f"분석하기", key=f"analyze_keyword_{i}"):
                                        st.session_state.selected_video_url = video['url']
                                        st.rerun()
                                
                                st.markdown("---")
                    else:
                        st.warning(f"'{keyword}' 키워드로 조건에 맞는 동영상을 찾을 수 없습니다.")
        
        with tab4:
            st.subheader("⚙️ 간단 검색 (API 키만)")
            st.info("이 탭은 API 키만으로 동작하는 간단한 검색 기능입니다.")
            
            # 검색 키워드 입력
            simple_keyword = st.text_input("검색 키워드", placeholder="예: AI, 기술, 뉴스...", key="simple_keyword_input")
            
            # 최대 결과 수 선택
            simple_max_results = st.slider("최대 동영상 수", 10, 50, 20, key="simple_max_results")
            
            if st.button("간단 검색", key="simple_search") and simple_keyword:
                st.info("간단 검색 기능은 현재 개발 중입니다.")
                st.info("구글 로그인 후 '키워드 검색' 탭을 사용해보세요!")
    
    # 선택된 동영상이 있으면 분석 페이지로 이동
    if hasattr(st.session_state, 'selected_video_url') and st.session_state.selected_video_url:
        st.markdown("---")
        st.subheader("🎬 선택된 동영상 분석")
        st.info(f"선택된 동영상: {st.session_state.selected_video_url}")
        
        if st.button("자막 분석 페이지로 이동", key="go_to_analysis"):
            # URL 처리 페이지로 이동하고 URL 입력
            st.session_state.page = "URL 처리"
            st.session_state.prefill_url = st.session_state.selected_video_url
            st.rerun()
        
        if st.button("선택 해제", key="clear_selection"):
            del st.session_state.selected_video_url
            st.rerun()

if __name__ == "__main__":
    main() 