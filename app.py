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
from db_handler import save_video_data, get_summaries_for_video, generate_report, get_all_channels, add_channel, delete_channel, search_channels_by_keyword, get_all_keywords, add_keyword, delete_keyword, search_videos_by_keyword, get_all_editorials, save_editorial, get_editorials_by_date_range, delete_editorial

# 프로젝트 모듈 임포트
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
            
            video_info = get_info_by_url(f"https://www.youtube.com/watch?v={video_id}")
            if not video_info or not video_info.get("id"):
                st.error(f"비디오 ID {video_id}에서 정보를 가져오지 못했습니다.")
                return
            
            # 비디오 정보 표시
            progress_bar.progress(30)
            status_text.text("자막 추출 중...")
            
            # 자막 추출
            transcript, lang = get_video_transcript(video_id)
            
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
            st.success("모든 처리가 완료되었습니다!")
            
        except Exception as e:
            st.error(f"처리 중 오류가 발생했습니다: {str(e)}")

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
    st.title("채널 및 키워드 관리")
    
    # 채널 및 키워드 정보 로드
    from config import load_config, save_config
    config = load_config()
    
    tabs = st.tabs(["채널 관리", "키워드 관리"])
    
    # 채널 관리 탭
    with tabs[0]:
        st.header("채널 관리")
        
        # 키워드로 채널 검색
        st.subheader("채널 검색")
        channel_search_keyword = st.text_input("키워드로 채널 검색", placeholder="채널명 또는 키워드 입력", key="channel_search")
        
        # 현재 등록된 채널 목록
        if config["channels"]:
            st.subheader("등록된 채널 목록")
            
            # 검색어가 있으면 필터링
            filtered_channels = config["channels"]
            if channel_search_keyword:
                filtered_channels = [channel for channel in config["channels"] if channel_search_keyword.lower() in channel.lower()]
                
            if filtered_channels:
                for i, channel_url in enumerate(filtered_channels):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.write(f"{i+1}. {channel_url}")
                    with col2:
                        if st.button("삭제", key=f"del_channel_{i}"):
                            # config.json에서 채널 삭제
                            config["channels"].remove(channel_url)
                            save_config(config)
                            
                            # 데이터베이스에서도 삭제
                            from youtube_handler import extract_channel_handle, get_channel_info
                            handle = extract_channel_handle(channel_url)
                            channel_identifier = handle if handle else channel_url
                            channel_info = get_channel_info(channel_identifier)
                            if channel_info and channel_info.get("id"):
                                from db_handler import delete_channel
                                delete_channel(channel_info.get("id"))
                            
                            st.success(f"채널 '{channel_url}'이(가) 삭제되었습니다.")
                            st.rerun()
            else:
                st.info(f"검색어 '{channel_search_keyword}'와 일치하는 채널이 없습니다.")
        else:
            st.info("등록된 채널이 없습니다.")
        
        # 새 채널 추가
        st.subheader("새 채널 추가")
        with st.form("add_channel_form"):
            new_channel = st.text_input("YouTube 채널 URL", placeholder="https://www.youtube.com/@channel_name")
            channel_submit = st.form_submit_button("채널 추가")
            
            if channel_submit and new_channel:
                if new_channel in config["channels"]:
                    st.warning(f"채널 '{new_channel}'은(는) 이미 등록되어 있습니다.")
                else:
                    from youtube_handler import extract_channel_handle, get_channel_info_by_handle
                    handle = extract_channel_handle(new_channel)
                    if not handle and not new_channel.startswith('@') and not new_channel.startswith('UC'):
                        st.error("유효한 YouTube 채널 URL, 핸들 또는 ID가 아닙니다.")
                    else:
                        # 채널 정보 가져오기
                        from youtube_handler import get_channel_info
                        channel_identifier = handle if handle else new_channel
                        channel_info = get_channel_info(channel_identifier)
                        if channel_info and channel_info.get("id"):
                            # config.json에 채널 추가
                            from main import add_channel
                            add_channel(new_channel)
                            
                            # 데이터베이스의 channels 테이블에도 추가
                            from db_handler import add_channel as db_add_channel
                            
                            # 채널 ID 형식 확인
                            channel_id = channel_info.get("id")
                            handle = channel_info.get("custom_url", handle)
                            
                            # 직접 매핑된 경우 채널 ID를 데이터베이스에 적합한 형식으로 변환
                            if channel_info.get("is_direct_mapping"):
                                st.info(f"유튜브 API 할당량 제한으로 인해 '{channel_identifier}'를 직접 채널로 등록합니다.")
                            
                            db_add_channel(
                                channel_id=channel_id,
                                title=channel_info.get("title"),
                                handle=handle,
                                description=channel_info.get("description")
                            )
                            
                            st.success(f"채널 '{new_channel}'이(가) 추가되었습니다.")
                            st.rerun()
                        else:
                            st.error(f"채널 '{handle}'의 정보를 가져오지 못했습니다.")
    
    # 키워드 관리 탭
    with tabs[1]:
        st.header("키워드 관리")
        
        # 특정 채널 내에서 키워드 검색 옵션
        st.subheader("채널 내 키워드 검색")
        
        # 채널 선택 드롭다운
        channel_options = ["모든 채널"] + config["channels"]
        selected_channel = st.selectbox("검색할 채널 선택", channel_options, key="keyword_channel_select")
        
        # 현재 등록된 키워드 목록
        if config["keywords"]:
            st.subheader("등록된 키워드 목록")
            
            # 특정 채널을 선택한 경우 해당 정보 표시
            if selected_channel != "모든 채널":
                st.info(f"선택한 채널: {selected_channel}")
                
                # 선택한 채널에서 키워드 검색 버튼
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("채널에서 키워드 검색", key="search_in_channel"):
                        with st.spinner("채널에서 키워드 검색 중..."):
                            # 채널 ID 추출
                            channel_handle = extract_channel_handle(selected_channel)
                            if channel_handle:
                                channel_info = get_channel_info_by_handle(channel_handle)
                                if channel_info:
                                    channel_id = channel_info.get("id")
                                    st.session_state.channel_id_for_search = channel_id
                                    st.session_state.channel_name_for_search = channel_info.get("title")
                                    st.success(f"채널 ID: {channel_id} ({channel_info.get('title')}) 검색 준비 완료")
                                else:
                                    st.error("채널 정보를 가져오지 못했습니다.")
                            else:
                                st.error("채널 핸들을 추출하지 못했습니다.")
            
            for i, keyword in enumerate(config["keywords"]):
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"{i+1}. {keyword}")
                with col2:
                    # 채널 ID가 세션에 있으면 해당 채널에서 키워드 검색 버튼 추가
                    if st.session_state.get("channel_id_for_search") and selected_channel != "모든 채널":
                        if st.button(f"검색", key=f"search_keyword_{i}"):
                            from youtube_handler import search_videos_by_keyword
                            channel_id = st.session_state.channel_id_for_search
                            channel_name = st.session_state.channel_name_for_search
                            with st.spinner(f"'{channel_name}' 채널에서 '{keyword}' 검색 중..."):
                                videos = search_videos_by_keyword(keyword, channel_id=channel_id, max_results=5)
                                if videos:
                                    st.success(f"'{channel_name}' 채널에서 '{keyword}' 키워드로 {len(videos)}개의 동영상을 찾았습니다.")
                                    for video in videos:
                                        st.markdown(f"**{video['title']}**")
                                        st.markdown(f"[YouTube에서 보기](https://www.youtube.com/watch?v={video['video_id']})")
                                else:
                                    st.warning(f"'{channel_name}' 채널에서 '{keyword}' 키워드에 해당하는 동영상을 찾지 못했습니다.")
                with col3:
                    if st.button("삭제", key=f"del_keyword_{i}"):
                        config["keywords"].remove(keyword)
                        save_config(config)
                        st.success(f"키워드 '{keyword}'이(가) 삭제되었습니다.")
                        st.rerun()
        else:
            st.info("등록된 키워드가 없습니다.")
        
        # 새 키워드 추가
        st.subheader("새 키워드 추가")
        with st.form("add_keyword_form"):
            new_keyword = st.text_input("검색 키워드", placeholder="검색할 키워드 입력")
            
            # 선택한 채널에서 키워드 검색 옵션 추가
            if selected_channel != "모든 채널":
                search_in_selected_channel = st.checkbox(f"'{selected_channel}' 채널에서 검색")
            else:
                search_in_selected_channel = False
                
            keyword_submit = st.form_submit_button("키워드 추가")
            
            if keyword_submit and new_keyword:
                if new_keyword in config["keywords"]:
                    st.warning(f"키워드 '{new_keyword}'은(는) 이미 등록되어 있습니다.")
                else:
                    # 키워드 추가
                    from main import add_keyword
                    add_keyword(new_keyword)
                    st.success(f"키워드 '{new_keyword}'이(가) 추가되었습니다.")
                    
                    # 선택한 채널에서 키워드 검색
                    if search_in_selected_channel:
                        from youtube_handler import extract_channel_handle, get_channel_info_by_handle, search_videos_by_keyword
                        channel_handle = extract_channel_handle(selected_channel)
                        if channel_handle:
                            channel_info = get_channel_info_by_handle(channel_handle)
                            if channel_info:
                                channel_id = channel_info.get("id")
                                channel_name = channel_info.get("title")
                                with st.spinner(f"'{channel_name}' 채널에서 '{new_keyword}' 검색 중..."):
                                    videos = search_videos_by_keyword(new_keyword, channel_id=channel_id, max_results=5)
                                    if videos:
                                        st.success(f"'{channel_name}' 채널에서 '{new_keyword}' 키워드로 {len(videos)}개의 동영상을 찾았습니다.")
                                        for video in videos:
                                            st.markdown(f"**{video['title']}**")
                                            st.markdown(f"[YouTube에서 보기](https://www.youtube.com/watch?v={video['video_id']})")
                                    else:
                                        st.warning(f"'{channel_name}' 채널에서 '{new_keyword}' 키워드에 해당하는 동영상을 찾지 못했습니다.")
                            else:
                                st.error("채널 정보를 가져오지 못했습니다.")
                        else:
                            st.error("채널 핸들을 추출하지 못했습니다.")
                    
                    st.rerun()
    
    # 데이터 수집 실행
    st.header("데이터 수집 실행")
    
    with st.form("collect_data_form"):
        st.subheader("등록된 채널과 키워드로 데이터 수집")
        
        analysis_types = st.multiselect(
            "분석 유형 선택",
            options=[t["code"] for t in get_available_analysis_types()],
            default=["summary"],
            format_func=lambda x: next((t["description"] for t in get_available_analysis_types() if t["code"] == x), x)
        )
        
        collect_submit = st.form_submit_button("데이터 수집 시작")
        
        if collect_submit:
            if not config["channels"] and not config["keywords"]:
                st.error("데이터 수집을 시작하려면 최소 하나의 채널 또는 키워드를 등록해야 합니다.")
            else:
                try:
                    with st.spinner("데이터 수집 중... 이 작업은 몇 분 정도 소요될 수 있습니다."):
                        # 데이터 수집 실행
                        from main import collect_data
                        collect_data(analysis_types)
                        st.success("데이터 수집이 완료되었습니다.")
                        
                        # 홈으로 리디렉션
                        st.experimental_set_query_params()  # URL 파라미터 제거
                        time.sleep(2)  # 2초 대기
                        st.experimental_rerun()  # 페이지 새로고침
                        
                except Exception as e:
                    st.error(f"데이터 수집 중 오류가 발생했습니다: {str(e)}")

# 키워드 분석 페이지
def keyword_analysis_page():
    st.title("키워드 및 기간 분석")
    
    # 데이터베이스에서 모든 비디오 정보 로드
    conn = sqlite3.connect(DB_PATH)
    all_videos_query = """
        SELECT v.id, v.title, v.channel_title, v.published_at, v.view_count,
               length(v.transcript) as transcript_length,
               (SELECT COUNT(*) FROM summaries s WHERE s.video_id = v.id) as analysis_count
        FROM videos v
        WHERE v.transcript IS NOT NULL
        ORDER BY v.published_at DESC
    """
    all_videos_df = pd.read_sql_query(all_videos_query, conn)
    conn.close()
    
    if all_videos_df.empty:
        st.warning("분석할 비디오 데이터가 없습니다.")
        return
    
    # 날짜 포맷 변환
    all_videos_df['published_at'] = pd.to_datetime(all_videos_df['published_at'])
    all_videos_df['year_month'] = all_videos_df['published_at'].dt.strftime('%Y-%m')
    
    # 필터링 옵션
    st.subheader("필터 옵션")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 채널 필터
        channels = ["모든 채널"] + all_videos_df['channel_title'].unique().tolist()
        selected_channel = st.selectbox("채널 선택", channels)
    
    with col2:
        # 날짜 범위 필터
        date_range = st.date_input(
            "기간 선택",
            value=(
                all_videos_df['published_at'].min().date(),
                all_videos_df['published_at'].max().date()
            ),
            min_value=all_videos_df['published_at'].min().date(),
            max_value=all_videos_df['published_at'].max().date()
        )
    
    # 키워드 검색
    keyword_search = st.text_input("제목에서 키워드 검색", placeholder="검색어 입력")
    
    # 필터링 적용
    filtered_df = all_videos_df.copy()
    
    # 채널 필터 적용
    if selected_channel != "모든 채널":
        filtered_df = filtered_df[filtered_df['channel_title'] == selected_channel]
    
    # 날짜 필터 적용
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['published_at'].dt.date >= start_date) & 
            (filtered_df['published_at'].dt.date <= end_date)
        ]
    
    # 키워드 필터 적용
    if keyword_search:
        filtered_df = filtered_df[filtered_df['title'].str.contains(keyword_search, case=False, na=False)]
    
    # 결과 표시
    st.subheader("검색 결과")
    st.write(f"총 {len(filtered_df)} 개의 비디오가 검색되었습니다.")
    
    if not filtered_df.empty:
        # 데이터 테이블로 표시
        st.dataframe(
            filtered_df[['title', 'channel_title', 'published_at', 'view_count', 'transcript_length', 'analysis_count']],
            column_config={
                "title": "제목",
                "channel_title": "채널",
                "published_at": "게시일",
                "view_count": st.column_config.NumberColumn("조회수", format="%d"),
                "transcript_length": st.column_config.NumberColumn("자막 길이", format="%d자"),
                "analysis_count": st.column_config.NumberColumn("분석 수", format="%d개")
            },
            hide_index=True
        )
        
        # 선택된 비디오 분석
        if len(filtered_df) > 0:
            st.subheader("비디오 분석")
            selected_video_id = st.selectbox(
                "분석할 비디오 선택",
                options=filtered_df["id"].tolist(),
                format_func=lambda x: filtered_df[filtered_df['id'] == x]['title'].iloc[0]
            )
            
            if selected_video_id:
                # 기존 분석 표시
                summaries = get_summaries_for_video(selected_video_id)
                
                if summaries:
                    summary_type = st.selectbox(
                        "분석 유형 선택",
                        options=list(summaries.keys()),
                        format_func=lambda x: next((t["description"] for t in get_available_analysis_types() if t["code"] == x), x)
                    )
                    
                    if summary_type:
                        st.subheader(f"{summary_type} 결과")
                        st.markdown(summaries[summary_type])
                        
                        # YouTube로 이동 링크
                        st.markdown(f"[YouTube에서 보기](https://www.youtube.com/watch?v={selected_video_id})")
                else:
                    st.warning("이 비디오에 대한 분석 결과가 없습니다.")
                    
                    # 새 분석 옵션
                    if st.button("분석 생성"):
                        st.session_state.analyze_video_id = selected_video_id
                        # URL 파라미터를 통해 페이지 전환
                        st.experimental_set_query_params(menu="analyze", video_id=selected_video_id)
                        st.rerun()
    else:
        st.info("검색 결과가 없습니다. 다른 필터 옵션을 선택해 보세요.")
    
    # 기간별 통계
    if not all_videos_df.empty:
        st.subheader("기간별 통계")
        
        # 월별 비디오 수
        monthly_videos = filtered_df.groupby('year_month').size().reset_index(name='count')
        
        if not monthly_videos.empty:
            st.bar_chart(monthly_videos.set_index('year_month'))
            
            # 채널별 비디오 수
            st.subheader("채널별 비디오 수")
            channel_counts = filtered_df['channel_title'].value_counts().reset_index()
            channel_counts.columns = ['channel', 'count']
            st.bar_chart(channel_counts.set_index('channel'))

# 신규 콘텐츠 리포트 페이지
def new_content_report_page():
    st.title("신규 콘텐츠 리포트")
    
    # 기간 선택
    st.subheader("리포트 기간 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        hours_options = [1, 3, 6, 12, 24, 48, 72]
        selected_hours = st.selectbox(
            "기간 선택", 
            options=hours_options, 
            index=3,  # 기본값 12시간
            format_func=lambda x: f"최근 {x}시간"
        )
    
    with col2:
        custom_date = st.checkbox("직접 날짜 선택")
        if custom_date:
            selected_date = st.date_input(
                "특정 날짜 이후",
                value=datetime.now().date() - timedelta(days=1),
                max_value=datetime.now().date()
            )
            selected_time = st.time_input(
                "시간",
                value=datetime.now().time()
            )
            # 날짜와 시간을 결합하여 timezone-aware한 datetime 객체 생성
            selected_datetime = datetime.combine(selected_date, selected_time).replace(tzinfo=timezone.utc)
            since_timestamp = selected_datetime.isoformat()
        else:
            # 시간 기준으로 계산 (timezone-aware)
            since_timestamp = None
    
    # 비디오 검색 필터
    st.subheader("비디오 필터")
    search_query = st.text_input("제목으로 검색", "")
    
    # 리포트 생성 버튼
    if st.button("리포트 생성", type="primary"):
        with st.spinner("리포트를 생성하는 중..."):
            if custom_date:
                report_data = generate_report(since_timestamp=since_timestamp)
            else:
                report_data = generate_report(hours=selected_hours)
            
            # 리포트 데이터 표시
            st.success(f"리포트가 생성되었습니다. 총 {report_data['total_videos']}개의 비디오가 발견되었습니다.")
            
            if report_data['total_videos'] == 0:
                st.info("선택한 기간 내에 새로운 비디오가 없습니다.")
            else:
                # 채널별로 비디오 표시
                for channel, videos in report_data['channels'].items():
                    # 검색 필터 적용
                    if search_query:
                        filtered_videos = [v for v in videos if search_query.lower() in v['title'].lower()]
                        if not filtered_videos:
                            continue
                    else:
                        filtered_videos = videos
                    
                    st.subheader(f"{channel} ({len(filtered_videos)}개)")
                    
                    # 각 비디오를 확장 가능한 카드로 표시
                    for video in filtered_videos:
                        with st.expander(f"{video['title']}"):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"**게시일:** {video['published_at']}")
                                st.write(f"**조회수:** {video.get('view_count', 'N/A')}")
                                
                                # 유튜브 링크 추가
                                video_url = f"https://www.youtube.com/watch?v={video['id']}"
                                st.markdown(f"[YouTube에서 보기]({video_url})")
                            
                            # 요약 정보 표시 (탭으로 구성)
                            if video.get('summaries'):
                                tabs = st.tabs(list(video['summaries'].keys()))
                                for i, (analysis_type, content) in enumerate(video['summaries'].items()):
                                    with tabs[i]:
                                        st.markdown(content)
                            else:
                                st.info("이 비디오에 대한 요약 정보가 없습니다.")
    
    # 저장된 리포트 목록
    st.subheader("저장된 리포트")
    reports_dir = "reports"
    if os.path.exists(reports_dir):
        report_files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
        report_files.sort(reverse=True)  # 최신 순으로 정렬
        
        if report_files:
            selected_report = st.selectbox(
                "저장된 리포트 선택",
                options=report_files,
                format_func=lambda x: x.replace('report_', '').replace('.md', '').replace('_', ' ')
            )
            
            if selected_report:
                with open(os.path.join(reports_dir, selected_report), 'r', encoding='utf-8') as f:
                    report_content = f.read()
                st.markdown(report_content)
        else:
            st.info("저장된 리포트가 없습니다.")
    else:
        st.info("리포트 디렉토리가 존재하지 않습니다.")

# 저장된 리포트 페이지
def saved_reports_page():
    st.title("저장된 리포트")
    
    # 리포트 디렉토리 경로
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    
    # 디렉토리가 없으면 생성
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        st.info("아직 저장된 리포트가 없습니다.")
        return
    
    # 마크다운 리포트 파일 목록
    md_reports = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
    
    if not md_reports:
        st.info("아직 저장된 리포트가 없습니다.")
        return
    
    # 날짜순으로 정렬 (최신순)
    md_reports.sort(reverse=True)
    
    # 리포트 선택
    selected_report = st.selectbox(
        "리포트 선택",
        options=md_reports,
        format_func=lambda x: x.replace('report_', '').replace('.md', '').replace('_', ' ') + ' 리포트'
    )
    
    if selected_report:
        report_path = os.path.join(reports_dir, selected_report)
        
        # 리포트 파일 읽기
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            # 리포트 표시
            st.markdown(report_content)
            
            # 리포트 다운로드 버튼
            st.download_button(
                label="리포트 다운로드",
                data=report_content,
                file_name=selected_report,
                mime="text/markdown"
            )
        except Exception as e:
            st.error(f"리포트를 읽는 중 오류가 발생했습니다: {str(e)}")

# 뉴스 페이지
def news_page():
    st.title("경제/주식 전망 뉴스")
    
    st.markdown("""
    이 페이지에서는 수집된 YouTube 자막을 기반으로 경제 전문가가 작성한 것 같은 경제 및 주식 시장 전망 사설을 제공합니다.
    키워드를 추출하여 선택한 키워드에 초점을 맞춘 뉴스를 생성할 수 있습니다.
    """)
    
    # 키워드 추출 및 뉴스 생성 옵션
    with st.expander("키워드 추출 및 뉴스 생성", expanded=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            hours = st.slider("몇 시간 이내의 비디오를 분석할지 선택", 1, 72, 24)
            
        with col2:
            extract_button = st.button("키워드 추출")
        
        # 키워드 추출 버튼 클릭 시
        if extract_button:
            with st.spinner("최근 영상의 자막을 분석하여 경제/주식 관련 키워드를 추출하는 중..."):
                from db_handler import extract_keywords_from_recent_videos
                keywords = extract_keywords_from_recent_videos(hours=hours)
                
                if keywords:
                    st.session_state.extracted_keywords = keywords
                    st.success(f"{len(keywords)}개의 키워드가 추출되었습니다!")
                else:
                    st.error("키워드 추출에 실패했습니다. 충분한 자막 데이터가 없거나 처리 중 오류가 발생했습니다.")
        
        # 직접 키워드 입력 영역
        st.subheader("키워드 직접 입력")
        custom_keyword = st.text_input("관심 있는 키워드를 직접 입력하세요 (쉼표로 구분)", placeholder="예: 금리, 인플레이션, 부동산")
        
        # 직접 입력한 키워드가 있으면 처리
        if custom_keyword:
            # 쉼표로 구분된 키워드를 리스트로 변환
            custom_keywords = [k.strip() for k in custom_keyword.split(',') if k.strip()]
            
            # 직접 입력한 키워드가 있으면 세션에 저장
            if custom_keywords:
                if 'custom_keywords' not in st.session_state:
                    st.session_state.custom_keywords = custom_keywords
                else:
                    # 기존 키워드와 병합 (중복 제거)
                    st.session_state.custom_keywords = list(set(st.session_state.custom_keywords + custom_keywords))
                
                # 선택된 키워드 목록에도 추가
                if 'selected_keywords' not in st.session_state:
                    st.session_state.selected_keywords = custom_keywords
                else:
                    # 기존 선택된 키워드와 병합 (중복 제거)
                    st.session_state.selected_keywords = list(set(st.session_state.selected_keywords + custom_keywords))
        
        # 직접 입력한 키워드 목록 표시
        if 'custom_keywords' in st.session_state and st.session_state.custom_keywords:
            st.write("직접 입력한 키워드:")
            custom_keyword_cols = st.columns(3)
            for i, keyword in enumerate(st.session_state.custom_keywords):
                col_index = i % 3
                with custom_keyword_cols[col_index]:
                    is_selected = keyword in st.session_state.selected_keywords if 'selected_keywords' in st.session_state else False
                    if st.checkbox(keyword, value=is_selected, key=f"custom_keyword_{i}"):
                        if 'selected_keywords' not in st.session_state:
                            st.session_state.selected_keywords = [keyword]
                        elif keyword not in st.session_state.selected_keywords:
                            st.session_state.selected_keywords.append(keyword)
                    else:
                        if 'selected_keywords' in st.session_state and keyword in st.session_state.selected_keywords:
                            st.session_state.selected_keywords.remove(keyword)
        
        # 세션에 저장된 키워드가 있으면 표시
        if 'extracted_keywords' in st.session_state and st.session_state.extracted_keywords:
            keywords = st.session_state.extracted_keywords
            
            st.subheader("추출된 키워드")
            
            # 선택한 키워드 상태 관리
            if 'selected_keywords' not in st.session_state:
                st.session_state.selected_keywords = []
            
            # 키워드 선택 UI (멀티셀렉트 대신 체크박스 목록 사용)
            keyword_cols = st.columns(3)  # 3개의 열로 키워드 표시
            for i, keyword in enumerate(keywords):
                col_index = i % 3
                with keyword_cols[col_index]:
                    is_selected = keyword in st.session_state.selected_keywords
                    if st.checkbox(keyword, value=is_selected, key=f"keyword_{i}"):
                        if keyword not in st.session_state.selected_keywords:
                            st.session_state.selected_keywords.append(keyword)
                    else:
                        if keyword in st.session_state.selected_keywords:
                            st.session_state.selected_keywords.remove(keyword)
            
        # 선택된 키워드가 있으면 뉴스 생성 옵션 표시
        if 'selected_keywords' in st.session_state and st.session_state.selected_keywords:
            st.subheader("뉴스 생성 옵션")
            
            # 선택된 키워드 표시
            selected_keywords_str = ", ".join(st.session_state.selected_keywords)
            st.write(f"**선택된 키워드:** {selected_keywords_str}")
            
            col1, col2 = st.columns(2)
            with col1:
                style = st.selectbox(
                    "리포트 스타일", 
                    ["basic", "concise", "editorial", "news", "research"],
                    format_func=lambda x: {
                        "basic": "기본", 
                        "concise": "간결", 
                        "editorial": "사설", 
                        "news": "신문기사", 
                        "research": "딥리서치"
                    }.get(x, x)
                )
                
                word_count = st.number_input(
                    "글자수 (자)", 
                    min_value=500, 
                    max_value=3000, 
                    value=1000, 
                    step=100
                )
            
            with col2:
                language = st.selectbox(
                    "언어", 
                    ["ko", "en"],
                    format_func=lambda x: {"ko": "한국어", "en": "영어"}.get(x, x)
                )
                
                generate_button = st.button("뉴스 생성", key="generate_by_keywords")
            
            if generate_button:
                with st.spinner(f"선택한 키워드 '{', '.join(st.session_state.selected_keywords)}'에 대한 뉴스를 생성하는 중..."):
                    from db_handler import generate_news_by_keywords
                    news_article = generate_news_by_keywords(
                        keywords=st.session_state.selected_keywords,
                        hours=hours,
                        style=style,
                        word_count=word_count,
                        language=language
                    )
                    
                    if news_article:
                        st.success("새로운 경제/주식 전망 뉴스가 생성되었습니다!")
                        # 새로 생성된 뉴스를 세션에 저장하여 바로 표시
                        st.session_state.current_news = news_article
                    else:
                        st.error("뉴스 생성에 실패했습니다. 충분한 자막 데이터가 없거나 처리 중 오류가 발생했습니다.")
    
    # 최신 뉴스 목록 또는 현재 뉴스 표시
    if 'current_news' in st.session_state and st.session_state.current_news:
        # 현재 선택된 뉴스 표시
        display_news(st.session_state.current_news)
    else:
        # 최신 뉴스 목록 표시
        display_latest_news()

def display_news(news_article):
    """뉴스 사설을 표시합니다."""
    st.subheader("현재 뉴스")
    
    # 뉴스 제목 및 정보
    st.markdown(f"## {news_article['title']}")
    st.markdown(f"*생성일: {news_article['created_at'][:10]}*")
    
    # 키워드 표시
    if 'keywords' in news_article and news_article['keywords']:
        keywords_str = ", ".join(news_article['keywords'])
        st.markdown(f"**키워드:** {keywords_str}")
    
    # 내용 표시 (마크다운 형식 지원)
    st.markdown(news_article['content'])
    
    # 다른 뉴스 보기 버튼
    if st.button("다른 뉴스 보기"):
        st.session_state.current_news = None
        st.rerun()
    
    # 출처 비디오 정보
    if 'video_ids' in news_article and news_article['video_ids']:
        with st.expander("분석에 사용된 영상"):
            # 비디오 정보 가져오기
            conn = sqlite3.connect(DB_PATH)
            for video_id in news_article['video_ids']:
                cursor = conn.cursor()
                cursor.execute("SELECT title, channel_title, url FROM videos WHERE id = ?", (video_id,))
                video_info = cursor.fetchone()
                
                if video_info:
                    st.markdown(f"- [{video_info[0]} - {video_info[1]}]({video_info[2]})")
            conn.close()

def display_latest_news():
    """최신 뉴스 목록을 표시합니다."""
    st.subheader("최신 경제/주식 전망 뉴스")
    
    from db_handler import get_latest_news
    news_articles = get_latest_news(news_type="economic", limit=10)
    
    if not news_articles:
        st.info("아직 생성된 뉴스 사설이 없습니다. 키워드를 추출하고 뉴스를 생성해 보세요.")
    else:
        # 뉴스 선택 탭
        if len(news_articles) > 1:
            news_titles = [f"{article['title']} ({article['created_at'][:10]})" for article in news_articles]
            selected_news_index = st.selectbox("뉴스 선택", range(len(news_titles)), format_func=lambda i: news_titles[i])
            selected_news = news_articles[selected_news_index]
        else:
            selected_news = news_articles[0]
        
        # 선택된 뉴스를 세션에 저장하고 표시
        st.session_state.current_news = selected_news
        display_news(selected_news)

# 최신 영상 분석 페이지
def latest_videos_analysis_page():
    st.title("채널/키워드별 최신 영상 분석")
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["채널별 분석", "키워드별 분석", "주식 종목별 분석"])
    
    with tab1:
        st.subheader("채널별 최신 영상 분석")
        
        # 채널 목록 가져오기
        channels = get_all_channels()
        
        if not channels:
            st.warning("등록된 채널이 없습니다. '채널 및 키워드 관리' 메뉴에서 채널을 추가해주세요.")
        else:
            # 채널 선택
            selected_channel = st.selectbox(
                "분석할 채널 선택",
                options=[c["channel_id"] for c in channels],
                format_func=lambda x: next((c["title"] for c in channels if c["channel_id"] == x), x)
            )
            
            # 시간 범위 선택
            hours = st.slider("최근 몇 시간 이내의 영상을 분석할까요?", 24, 168, 72, 24)
            
            # 최대 결과 수 선택
            limit = st.slider("최대 몇 개의 영상을 분석할까요?", 5, 20, 10, 1)
            
            if st.button("채널 영상 분석 실행"):
                with st.spinner("채널의 최신 영상 분석 중..."):
                    # 최신 영상 분석 정보 가져오기
                    from db_handler import get_latest_videos_analysis_by_channel
                    videos = get_latest_videos_analysis_by_channel(selected_channel, hours=hours, limit=limit)
                    
                    if not videos:
                        st.info(f"최근 {hours}시간 이내에 등록된 영상이 없습니다.")
                    else:
                        st.success(f"{len(videos)}개의 영상이 분석되었습니다.")
                        
                        # 각 영상 정보 표시
                        for i, video in enumerate(videos):
                            st.markdown(f"### {i+1}. {video['title']}")
                            st.markdown(f"**채널:** {video['channel_title']} | **게시일:** {video['published_at']}")
                            st.markdown(f"**영상 링크:** [YouTube에서 보기]({video['url']})")
                            
                            # 요약 정보가 있으면 표시
                            if 'summaries' in video and video['summaries']:
                                with st.expander("영상 요약"):
                                    for summary_type, content in video['summaries'].items():
                                        st.markdown(f"**{summary_type}:**")
                                        st.markdown(content)
                            else:
                                st.warning("이 영상에 대한 요약 정보가 없습니다.")
                                # 분석 수행 버튼
                                if st.button(f"영상 요약 생성", key=f"analyze_summary_{video['id']}"):
                                    with st.spinner(f"'{video['title']}' 영상 요약 생성 중..."):
                                        from db_handler import analyze_video
                                        success = analyze_video(video['id'], "summary")
                                        if success:
                                            st.success(f"영상 요약이 생성되었습니다.")
                                            st.rerun()
                                        else:
                                            st.error("영상 요약 생성 중 오류가 발생했습니다.")
                            
                            # 주식 종목 정보가 있으면 표시
                            if 'stock_info' in video and video['stock_info']:
                                with st.expander("언급된 주식 종목 정보", expanded=True):
                                    for stock in video['stock_info']:
                                        st.markdown(f"**회사명:** {stock.get('회사명', 'N/A')}")
                                        if '티커' in stock:
                                            st.markdown(f"**티커:** {stock.get('티커', 'N/A')}")
                                        if '언급된_내용' in stock:
                                            st.markdown(f"**언급된 내용:**")
                                            st.markdown(stock.get('언급된_내용', 'N/A'))
                                        st.markdown("---")
                            
                            # 상세 분석 정보가 있으면 표시
                            if 'detailed_analysis' in video and video['detailed_analysis'] and 'analysis_data' in video['detailed_analysis']:
                                with st.expander("상세 분석 결과"):
                                    analysis_data = video['detailed_analysis']['analysis_data']
                                    
                                    # 경제 및 주식 시장 관련 주요 내용 요약
                                    if '영상_내용_종합_요약' in analysis_data:
                                        st.markdown("**종합 요약:**")
                                        st.markdown(analysis_data['영상_내용_종합_요약'])
                                    
                                    # 언급된 경제 지표나 이벤트
                                    if '언급된_경제_지표_및_이벤트' in analysis_data:
                                        st.markdown("**언급된 경제 지표 및 이벤트:**")
                                        st.markdown(analysis_data['언급된_경제_지표_및_이벤트'])
                                    
                                    # 시장 전망이나 예측 정보
                                    if '시장_전망_및_예측' in analysis_data:
                                        st.markdown("**시장 전망 및 예측:**")
                                        st.markdown(analysis_data['시장_전망_및_예측'])
                                    
                                    # 투자 전략이나 조언
                                    if '투자_전략_및_조언' in analysis_data:
                                        st.markdown("**투자 전략 및 조언:**")
                                        st.markdown(analysis_data['투자_전략_및_조언'])
                            else:
                                st.warning("이 영상에 대한 상세 분석 정보가 없습니다.")
                                # 경제 분석 수행 버튼
                                if st.button(f"경제 분석 생성", key=f"analyze_economic_{video['id']}"):
                                    with st.spinner(f"'{video['title']}' 영상 경제 분석 중..."):
                                        from db_handler import analyze_video
                                        success = analyze_video(video['id'], "economic")
                                        if success:
                                            st.success(f"영상 경제 분석이 생성되었습니다.")
                                            st.rerun()
                                        else:
                                            st.error("영상 경제 분석 생성 중 오류가 발생했습니다.")
                            
                            st.markdown("---")
    
    with tab2:
        st.subheader("키워드별 최신 영상 분석")
        
        # 키워드 목록 가져오기
        keywords = get_all_keywords()
        
        if not keywords:
            st.warning("등록된 키워드가 없습니다. '채널 및 키워드 관리' 메뉴에서 키워드를 추가해주세요.")
            
            # 키워드가 없어도 직접 입력 가능
            custom_keyword = st.text_input("분석할 키워드 직접 입력")
            if custom_keyword:
                # 시간 범위 선택
                hours = st.slider("최근 몇 시간 이내의 영상을 분석할까요? (키워드)", 24, 168, 72, 24)
                
                # 최대 결과 수 선택
                limit = st.slider("최대 몇 개의 영상을 분석할까요? (키워드)", 5, 20, 10, 1)
                
                if st.button("키워드 영상 분석 실행"):
                    with st.spinner(f"'{custom_keyword}' 키워드 관련 최신 영상 분석 중..."):
                        # 최신 영상 분석 정보 가져오기
                        from db_handler import get_latest_videos_analysis_by_keyword
                        videos = get_latest_videos_analysis_by_keyword(custom_keyword, hours=hours, limit=limit)
                        
                        display_keyword_videos_analysis(videos, custom_keyword, hours)
        else:
            # 키워드 선택
            selected_keyword = st.selectbox(
                "분석할 키워드 선택",
                options=[k["keyword"] for k in keywords],
                format_func=lambda x: x
            )
            
            # 시간 범위 선택
            hours = st.slider("최근 몇 시간 이내의 영상을 분석할까요? (키워드)", 24, 168, 72, 24)
            
            # 최대 결과 수 선택
            limit = st.slider("최대 몇 개의 영상을 분석할까요? (키워드)", 5, 20, 10, 1)
            
            if st.button("키워드 영상 분석 실행"):
                with st.spinner(f"'{selected_keyword}' 키워드 관련 최신 영상 분석 중..."):
                    # 최신 영상 분석 정보 가져오기
                    from db_handler import get_latest_videos_analysis_by_keyword
                    videos = get_latest_videos_analysis_by_keyword(selected_keyword, hours=hours, limit=limit)
                    
                    display_keyword_videos_analysis(videos, selected_keyword, hours)
    
    with tab3:
        st.subheader("주식 종목별 최신 영상 분석")
        
        # 주식 종목명 직접 입력
        stock_name = st.text_input("분석할 주식 종목명 또는 티커 입력 (예: 삼성전자, AAPL)")
        
        if stock_name:
            # 시간 범위 선택
            hours = st.slider("최근 몇 시간 이내의 영상을 분석할까요? (주식)", 24, 336, 168, 24)
            
            # 최대 결과 수 선택
            limit = st.slider("최대 몇 개의 영상을 분석할까요? (주식)", 5, 20, 10, 1)
            
            if st.button("주식 종목 영상 분석 실행"):
                with st.spinner(f"'{stock_name}' 주식 종목 관련 최신 영상 분석 중..."):
                    # 최신 영상 분석 정보 가져오기
                    from db_handler import get_latest_videos_by_stock
                    videos = get_latest_videos_by_stock(stock_name, hours=hours, limit=limit)
                    
                    if not videos:
                        st.info(f"최근 {hours}시간 이내에 '{stock_name}' 주식 종목이 언급된 영상이 없습니다.")
                    else:
                        st.success(f"{len(videos)}개의 영상에서 '{stock_name}' 주식 종목이 언급되었습니다.")
                        
                        # 각 영상 정보 표시
                        for i, video in enumerate(videos):
                            st.markdown(f"### {i+1}. {video['title']}")
                            st.markdown(f"**영상 링크:** [YouTube에서 보기]({video['url']})")
                            st.markdown(f"**분석 시간:** {video['created_at']}")
                            
                            # 주식 종목 정보 표시 (항상 있음)
                            st.markdown("#### 주식 종목 정보")
                            for stock in video['stock_info']:
                                col1, col2 = st.columns([1, 3])
                                with col1:
                                    st.markdown(f"**회사명:** {stock.get('회사명', 'N/A')}")
                                    if '티커' in stock:
                                        st.markdown(f"**티커:** {stock.get('티커', 'N/A')}")
                                with col2:
                                    if '언급된_내용' in stock:
                                        st.markdown(f"**언급된 내용:**")
                                        st.markdown(stock.get('언급된_내용', 'N/A'))
                            
                            # 추가 분석 정보
                            with st.expander("영상 상세 분석"):
                                analysis_data = video['analysis_data']
                                
                                # 경제 및 주식 시장 관련 주요 내용 요약
                                if '영상_내용_종합_요약' in analysis_data:
                                    st.markdown("**종합 요약:**")
                                    st.markdown(analysis_data['영상_내용_종합_요약'])
                                
                                # 시장 전망이나 예측 정보
                                if '시장_전망_및_예측' in analysis_data:
                                    st.markdown("**시장 전망 및 예측:**")
                                    st.markdown(analysis_data['시장_전망_및_예측'])
                                
                                # 투자 전략이나 조언
                                if '투자_전략_및_조언' in analysis_data:
                                    st.markdown("**투자 전략 및 조언:**")
                                    st.markdown(analysis_data['투자_전략_및_조언'])
                            
                            st.markdown("---")

# 키워드 영상 분석 결과 표시 헬퍼 함수
def display_keyword_videos_analysis(videos, keyword, hours):
    if not videos:
        st.info(f"최근 {hours}시간 이내에 '{keyword}' 키워드가 포함된 영상이 없습니다.")
    else:
        st.success(f"{len(videos)}개의 영상에서 '{keyword}' 키워드가 발견되었습니다.")
        
        # 각 영상 정보 표시
        for i, video in enumerate(videos):
            st.markdown(f"### {i+1}. {video['title']}")
            st.markdown(f"**채널:** {video['channel_title']} | **게시일:** {video['published_at']}")
            st.markdown(f"**영상 링크:** [YouTube에서 보기]({video['url']})")
            
            # 요약 정보가 있으면 표시
            if 'summaries' in video and video['summaries']:
                with st.expander("영상 요약"):
                    for summary_type, content in video['summaries'].items():
                        st.markdown(f"**{summary_type}:**")
                        st.markdown(content)
            else:
                st.warning("이 영상에 대한 요약 정보가 없습니다.")
                # 분석 수행 버튼
                if st.button(f"영상 요약 생성", key=f"kw_analyze_summary_{video['id']}"):
                    with st.spinner(f"'{video['title']}' 영상 요약 생성 중..."):
                        from db_handler import analyze_video
                        success = analyze_video(video['id'], "summary")
                        if success:
                            st.success(f"영상 요약이 생성되었습니다.")
                            st.rerun()
                        else:
                            st.error("영상 요약 생성 중 오류가 발생했습니다.")
            
            # 주식 종목 정보가 있으면 표시
            if 'stock_info' in video and video['stock_info']:
                with st.expander("언급된 주식 종목 정보", expanded=True):
                    for stock in video['stock_info']:
                        st.markdown(f"**회사명:** {stock.get('회사명', 'N/A')}")
                        if '티커' in stock:
                            st.markdown(f"**티커:** {stock.get('티커', 'N/A')}")
                        if '언급된_내용' in stock:
                            st.markdown(f"**언급된 내용:**")
                            st.markdown(stock.get('언급된_내용', 'N/A'))
                        st.markdown("---")
            
            # 상세 분석 정보가 있으면 표시
            if 'detailed_analysis' in video and video['detailed_analysis'] and 'analysis_data' in video['detailed_analysis']:
                with st.expander("상세 분석 결과"):
                    analysis_data = video['detailed_analysis']['analysis_data']
                    
                    # 경제 및 주식 시장 관련 주요 내용 요약
                    if '영상_내용_종합_요약' in analysis_data:
                        st.markdown("**종합 요약:**")
                        st.markdown(analysis_data['영상_내용_종합_요약'])
                    
                    # 언급된 경제 지표나 이벤트
                    if '언급된_경제_지표_및_이벤트' in analysis_data:
                        st.markdown("**언급된 경제 지표 및 이벤트:**")
                        st.markdown(analysis_data['언급된_경제_지표_및_이벤트'])
                    
                    # 시장 전망이나 예측 정보
                    if '시장_전망_및_예측' in analysis_data:
                        st.markdown("**시장 전망 및 예측:**")
                        st.markdown(analysis_data['시장_전망_및_예측'])
                    
                    # 투자 전략이나 조언
                    if '투자_전략_및_조언' in analysis_data:
                        st.markdown("**투자 전략 및 조언:**")
                        st.markdown(analysis_data['투자_전략_및_조언'])
            else:
                st.warning("이 영상에 대한 상세 분석 정보가 없습니다.")
                # 경제 분석 수행 버튼
                if st.button(f"경제 분석 생성", key=f"kw_analyze_economic_{video['id']}"):
                    with st.spinner(f"'{video['title']}' 영상 경제 분석 중..."):
                        from db_handler import analyze_video
                        success = analyze_video(video['id'], "economic")
                        if success:
                            st.success(f"영상 경제 분석이 생성되었습니다.")
                            st.rerun()
                        else:
                            st.error("영상 경제 분석 생성 중 오류가 발생했습니다.")
            
            st.markdown("---")

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
    if "page" not in st.session_state:
        st.session_state.page = "home"
    
    if "channel_id_for_search" not in st.session_state:
        st.session_state.channel_id_for_search = None
        
    if "channel_name_for_search" not in st.session_state:
        st.session_state.channel_name_for_search = None
    
    # 기존에 config.json에 저장된 채널을 DB에 동기화
    from config import load_config
    from youtube_handler import extract_channel_handle, get_channel_info_by_handle
    from db_handler import get_all_channels, add_channel
    
    config = load_config()
    db_channels = get_all_channels()
    db_channel_ids = [channel.get("channel_id") for channel in db_channels]
    
    # config.json에 있는 채널들을 DB에 추가
    for channel_url in config["channels"]:
        handle = extract_channel_handle(channel_url)
        if handle:
            channel_info = get_channel_info_by_handle(handle)
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
    """구글 로그인을 통한 최신 동영상 검색 페이지"""
    st.title("🔐 구글 로그인 및 최신 동영상")
    
    # 구글 인증 핸들러 임포트
    from google_auth_handler import auth_handler
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["🔑 구글 로그인", "📺 구독 채널 동영상", "🔍 키워드 검색", "⚙️ 간단 검색 (API 키만)"])
    
    with tab1:
        st.subheader("구글 계정 로그인")
        st.markdown("""
        YouTube API를 사용하여 다음 기능들을 이용하려면 구글 계정으로 로그인이 필요합니다:
        
        - 📺 **구독 채널 목록 확인**
        - 🎬 **구독 채널의 최신 동영상 가져오기**
        - 🔍 **키워드 기반 동영상 검색**
        """)
        
        # 로그인 상태 확인
        if auth_handler.youtube_service:
            st.success("✅ 이미 로그인되어 있습니다!")
            
            # 로그아웃 버튼
            if st.button("로그아웃"):
                import os
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                auth_handler.creds = None
                auth_handler.youtube_service = None
                st.success("로그아웃되었습니다.")
                st.rerun()
        else:
            st.info("구글 계정으로 로그인하세요.")
            
            # 자동 설정 도구
            with st.expander("🔧 자동 설정 도구"):
                st.markdown("### 1단계: credentials.json 템플릿 생성")
                if st.button("템플릿 파일 생성"):
                    template_file = auth_handler.create_credentials_template()
                    st.success(f"✅ {template_file} 파일이 생성되었습니다!")
                    st.info("이제 이 파일을 참고하여 실제 credentials.json을 만들어주세요.")
                
                st.markdown("### 2단계: Google Cloud Console 설정")
                st.markdown("""
                1. **[Google Cloud Console](https://console.cloud.google.com/)**에 접속
                2. 새 프로젝트 생성 또는 기존 프로젝트 선택
                3. **YouTube Data API v3** 활성화
                4. **사용자 인증 정보** 메뉴로 이동
                5. **OAuth 2.0 클라이언트 ID** 생성 (데스크톱 앱)
                6. 다운로드한 JSON 파일을 `credentials.json`으로 이름 변경
                7. 프로젝트 루트 디렉토리에 업로드
                """)
            
            # 로그인 버튼
            if st.button("구글 로그인"):
                with st.spinner("구글 로그인 중..."):
                    if auth_handler.authenticate():
                        st.success("✅ 로그인 성공!")
                        st.rerun()
                    else:
                        st.error("❌ 로그인 실패. credentials.json 파일을 확인하세요.")
        
        # 설정 안내
        with st.expander("📋 상세 설정 방법"):
            st.markdown("""
            ### 1. Google Cloud Console 설정
            1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
            2. 새 프로젝트 생성 또는 기존 프로젝트 선택
            3. YouTube Data API v3 활성화
            
            ### 2. OAuth 2.0 클라이언트 ID 생성
            1. "API 및 서비스" > "사용자 인증 정보" 메뉴로 이동
            2. "사용자 인증 정보 만들기" > "OAuth 2.0 클라이언트 ID" 선택
            3. 애플리케이션 유형: "데스크톱 앱" 선택
            4. 클라이언트 ID 생성 후 JSON 파일 다운로드
            
            ### 3. credentials.json 파일 업로드
            1. 다운로드한 JSON 파일을 `credentials.json`으로 이름 변경
            2. 프로젝트 루트 디렉토리에 업로드
            """)
    
    with tab2:
        st.subheader("구독 채널 최신 동영상")
        
        if not auth_handler.youtube_service:
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
                format_func=lambda x: x[1]
            )[0]
            
            # 최대 결과 수 선택
            max_results = st.slider("최대 동영상 수", 10, 100, 50)
            
            if st.button("구독 채널 동영상 가져오기"):
                with st.spinner("구독 채널 동영상을 가져오는 중..."):
                    videos = auth_handler.get_subscription_videos(
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
                                    st.markdown(f"📺 {video['channel_title']}")
                                    if 'subscription' in video:
                                        st.markdown(f"🔔 구독 채널: {video['subscription']}")
                                    
                                    # 발행일 포맷팅
                                    published_date = datetime.fromisoformat(
                                        video['published_at'].replace('Z', '+00:00')
                                    ).strftime("%Y-%m-%d %H:%M")
                                    st.markdown(f"📅 {published_date}")
                                    
                                    # 링크 버튼
                                    if st.button(f"보기 {i+1}", key=f"watch_{i}"):
                                        st.markdown(f"[YouTube에서 보기]({video['url']})")
                                    
                                    # 분석 버튼
                                    if st.button(f"분석 {i+1}", key=f"analyze_{i}"):
                                        st.session_state.selected_video_url = video['url']
                                        st.rerun()
                        
                        st.markdown("---")
                        st.markdown("💡 **팁**: 동영상을 분석하려면 '분석' 버튼을 클릭하세요.")
                    else:
                        st.warning("해당 기간에 업로드된 구독 채널 동영상이 없습니다.")
    
    with tab3:
        st.subheader("키워드 기반 동영상 검색")
        
        if not auth_handler.youtube_service:
            st.warning("먼저 구글 로그인을 해주세요.")
            st.info("💡 또는 '간단 검색 (API 키만)' 탭을 사용해보세요!")
        else:
            # 검색 키워드 입력
            keyword = st.text_input("검색 키워드", placeholder="예: AI, 기술, 뉴스, 게임...")
            
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
            
            if st.button("키워드로 검색") and keyword:
                with st.spinner(f"'{keyword}' 키워드로 동영상을 검색하는 중..."):
                    videos = auth_handler.search_videos_by_keyword(
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
                                    st.markdown(f"📺 {video['channel_title']}")
                                    
                                    # 발행일 포맷팅
                                    published_date = datetime.fromisoformat(
                                        video['published_at'].replace('Z', '+00:00')
                                    ).strftime("%Y-%m-%d %H:%M")
                                    st.markdown(f"📅 {published_date}")
                                    
                                    # 설명 미리보기
                                    if video['description']:
                                        desc_preview = video['description'][:100] + "..." if len(video['description']) > 100 else video['description']
                                        st.markdown(f"📝 {desc_preview}")
                                    
                                    # 링크 버튼
                                    if st.button(f"보기 {i+1}", key=f"keyword_watch_{i}"):
                                        st.markdown(f"[YouTube에서 보기]({video['url']})")
                                    
                                    # 분석 버튼
                                    if st.button(f"분석 {i+1}", key=f"keyword_analyze_{i}"):
                                        st.session_state.selected_video_url = video['url']
                                        st.rerun()
                        
                        st.markdown("---")
                        st.markdown("💡 **팁**: 동영상을 분석하려면 '분석' 버튼을 클릭하세요.")
                    else:
                        st.warning(f"'{keyword}' 키워드로 해당 기간에 업로드된 동영상을 찾을 수 없습니다.")
    
    with tab4:
        st.subheader("간단 검색 (API 키만)")
        st.markdown("""
        💡 **구글 로그인 없이도 사용 가능합니다!**
        
        YouTube API 키만 있으면 키워드 검색이 가능합니다.
        구독 채널 기능은 사용할 수 없지만, 키워드 검색은 정상 작동합니다.
        """)
        
        # 검색 키워드 입력
        keyword = st.text_input("검색 키워드", placeholder="예: AI, 기술, 뉴스, 게임...", key="simple_keyword")
        
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
            key="simple_time_filter"
        )[0]
        
        # 최대 결과 수 선택
        max_results = st.slider("최대 동영상 수", 10, 100, 50, key="simple_max_results")
        
        if st.button("간단 검색") and keyword:
            with st.spinner(f"'{keyword}' 키워드로 동영상을 검색하는 중..."):
                videos = auth_handler.search_videos_by_keyword_simple(
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
                                st.markdown(f"📺 {video['channel_title']}")
                                
                                # 발행일 포맷팅
                                published_date = datetime.fromisoformat(
                                    video['published_at'].replace('Z', '+00:00')
                                ).strftime("%Y-%m-%d %H:%M")
                                st.markdown(f"📅 {published_date}")
                                
                                # 설명 미리보기
                                if video['description']:
                                    desc_preview = video['description'][:100] + "..." if len(video['description']) > 100 else video['description']
                                    st.markdown(f"📝 {desc_preview}")
                                
                                # 링크 버튼
                                if st.button(f"보기 {i+1}", key=f"simple_watch_{i}"):
                                    st.markdown(f"[YouTube에서 보기]({video['url']})")
                                
                                # 분석 버튼
                                if st.button(f"분석 {i+1}", key=f"simple_analyze_{i}"):
                                    st.session_state.selected_video_url = video['url']
                                    st.rerun()
                    
                    st.markdown("---")
                    st.markdown("💡 **팁**: 동영상을 분석하려면 '분석' 버튼을 클릭하세요.")
                else:
                    st.warning(f"'{keyword}' 키워드로 해당 기간에 업로드된 동영상을 찾을 수 없습니다.")
    
    # 선택된 동영상이 있으면 분석 페이지로 이동
    if hasattr(st.session_state, 'selected_video_url') and st.session_state.selected_video_url:
        st.markdown("---")
        st.subheader("🎬 선택된 동영상 분석")
        st.info(f"선택된 동영상: {st.session_state.selected_video_url}")
        
        if st.button("자막 분석 페이지로 이동"):
            # URL 처리 페이지로 이동하고 URL 입력
            st.session_state.page = "URL 처리"
            st.session_state.prefill_url = st.session_state.selected_video_url
            st.rerun()
        
        if st.button("선택 해제"):
            del st.session_state.selected_video_url
            st.rerun()

if __name__ == "__main__":
    main() 