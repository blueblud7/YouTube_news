#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
YouTube 뉴스 자막 수집 및 요약 시스템
사용법: python main.py
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime, timedelta, timezone
import schedule
import threading
import argparse

from config import load_config, save_config
from youtube_handler import (
    get_info_by_url,
    search_videos_by_keyword,
    get_video_info,
    get_video_transcript,
    get_latest_videos_from_channel
)
from db_handler import (
    initialize_db,
    save_video_data,
    analyze_video,
    generate_report,
    is_video_in_db,
    generate_economic_news_from_recent_videos,
    is_video_processed
)
from llm_handler import summarize_transcript, analyze_transcript, analyze_transcript_with_type, analyze_transcript_for_economic_insights, create_detailed_video_summary

# 구성 파일 경로
CONFIG_FILE = "youtube_news_config.json"

def load_config():
    """구성 파일을 로드합니다."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 기본 구성 생성
        default_config = {
            "channels": [],
            "keywords": [],
            "schedule_interval": 24,  # 시간 단위
            "last_run": None
        }
        save_config(default_config)
        return default_config

def save_config(config):
    """구성 파일을 저장합니다."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def add_channel(channel_url):
    """모니터링할 채널을 추가합니다."""
    config = load_config()
    if channel_url not in config["channels"]:
        config["channels"].append(channel_url)
        save_config(config)
        print(f"채널 '{channel_url}'이(가) 모니터링 목록에 추가되었습니다.")
    else:
        print(f"채널 '{channel_url}'은(는) 이미 모니터링 중입니다.")

def add_keyword(keyword):
    """모니터링할 키워드를 추가합니다."""
    config = load_config()
    if keyword not in config["keywords"]:
        config["keywords"].append(keyword)
        save_config(config)
        print(f"키워드 '{keyword}'이(가) 모니터링 목록에 추가되었습니다.")
    else:
        print(f"키워드 '{keyword}'은(는) 이미 모니터링 중입니다.")

def process_video(video_id, video_info, transcript, analysis_types=None):
    """비디오 처리 및 분석 함수"""
    from db_handler import save_video_data, save_summary_to_db
    from llm_handler import summarize_transcript, analyze_transcript_with_type, analyze_transcript_for_economic_insights, create_detailed_video_summary
    
    try:
        # 데이터베이스에 저장
        if not save_video_data(video_info, transcript):
            print(f"비디오 ID {video_id}는 이미 데이터베이스에 있습니다.")
        
        # 분석 유형이 없으면 기본값 사용
        if not analysis_types:
            analysis_types = ["summary"]
        
        # 각 분석 유형에 대해 처리
        for analysis_type in analysis_types:
            try:
                # 요약 생성
                if analysis_type == "summary":
                    summary = summarize_transcript(transcript, analysis_type=analysis_type)
                else:
                    summary = analyze_transcript_with_type(transcript, analysis_type)
                
                # 데이터베이스에 저장
                save_summary_to_db(video_id, analysis_type, summary)
                
            except Exception as e:
                print(f"비디오 ID {video_id}의 {analysis_type} 분석 중 오류 발생: {e}")
        
        # 경제 및 주식 관련 상세 분석 수행
        try:
            # 경제 분석
            economic_analysis = analyze_transcript_for_economic_insights(transcript, video_id, video_info.get('title', ''))
            if economic_analysis:
                from db_handler import save_analysis
                save_analysis(video_id, 'analysis_economic', economic_analysis)
                print(f"비디오 ID {video_id}의 경제 분석이 저장되었습니다.")
            
            # 상세 영상 분석
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            detailed_analysis = create_detailed_video_summary(transcript, video_id, video_info.get('title', ''), video_url)
            if detailed_analysis:
                from db_handler import save_detailed_video_analysis
                save_detailed_video_analysis(video_id, video_info.get('title', ''), video_url, detailed_analysis)
                print(f"비디오 ID {video_id}의 상세 분석이 저장되었습니다.")
                
        except Exception as e:
            print(f"비디오 ID {video_id}의 상세 분석 중 오류 발생: {e}")
        
        return True
        
    except Exception as e:
        print(f"비디오 ID {video_id} 처리 중 오류 발생: {e}")
        return False

def collect_data(analysis_types=None, credentials=None):
    """채널 및 키워드에서 데이터를 수집합니다."""
    if analysis_types is None:
        analysis_types = ["summary"]  # 기본 분석 유형
        
    if credentials is None:
        print("오류: OAuth2 인증 정보가 필요합니다.")
        return
        
    print(f"\n=== 데이터 수집 시작: {datetime.now().isoformat()} ===")
    print(f"수행할 분석 유형: {', '.join(analysis_types)}")
    
    # 시작 시간 기록
    start_time = datetime.now().isoformat()
    
    config = load_config()
    
    # 마지막 실행 시간 업데이트
    config["last_run"] = datetime.now().isoformat()
    save_config(config)
    
    # 채널 처리
    for channel_url in config["channels"]:
        try:
            print(f"\n>> 채널 처리 중: {channel_url}")
            # 채널 정보 가져오기
            channel_info = get_info_by_url(channel_url, credentials)
            if not channel_info:
                print(f"채널 URL {channel_url}에서 정보를 가져오지 못했습니다.")
                continue
                
            channel_id = channel_info.get("id")
            channel_title = channel_info.get("title")
            
            # 채널에서 비디오 검색
            videos = search_videos_by_keyword("", credentials, channel_id=channel_id, max_results=15)
            if not videos:
                print(f"채널 '{channel_title}'에서 비디오를 찾지 못했습니다.")
                continue
                
            # 비디오 처리
            for video in videos:
                video_id = video.get("video_id")  # youtube_handler에서 반환하는 키 이름
                video_title = video.get("title")
                
                # 이미 데이터베이스에 있는지 확인
                if is_video_in_db(video_id):
                    print(f"비디오 '{video_title}' (ID: {video_id})는 이미 데이터베이스에 있으므로 건너뜁니다.")
                    continue
                
                # 발행일 확인 (1주일 이내인지)
                published_at = video.get("published_at")
                
                # 발행일을 datetime 객체로 변환 (문자열인 경우)
                if isinstance(published_at, str):
                    # ISO 형식 문자열을 datetime으로 변환
                    if 'Z' in published_at:
                        published_at = published_at.replace('Z', '+00:00')
                    published_date = datetime.fromisoformat(published_at)
                else:
                    # 이미 datetime 객체인 경우
                    published_date = published_at
                
                # 현재 시간을 timezone-aware로 생성 (UTC 기준)
                now = datetime.now(timezone.utc)
                
                # published_date가 timezone-naive인 경우 UTC로 가정하여 timezone-aware로 변환
                if published_date.tzinfo is None:
                    published_date = published_date.replace(tzinfo=timezone.utc)
                
                # 1주일 이내인지 확인
                if (now - published_date).days > 7:
                    print(f"비디오 '{video_title}' (ID: {video_id})는 1주일 이전에 발행되어 건너뜁니다.")
                    continue
                
                print(f"비디오 처리 중: '{video_title}' (ID: {video_id})")
                
                # 비디오 상세 정보 가져오기
                video_info = get_video_info(video_id, credentials)
                if not video_info:
                    print(f"비디오 ID {video_id}에서 상세 정보를 가져오지 못했습니다.")
                    continue
                
                # 자막 가져오기
                transcript, lang = get_video_transcript(video_id, credentials)
                if not transcript:
                    print(f"비디오 ID {video_id}에서 자막을 찾을 수 없습니다.")
                    continue
                
                # 비디오 처리 및 분석
                process_video(video_id, video_info, transcript, analysis_types)
                
        except Exception as e:
            print(f"채널 {channel_url} 처리 중 오류 발생: {e}")
            traceback.print_exc()
    
    # 키워드 처리
    for keyword in config["keywords"]:
        try:
            print(f"\n>> 키워드 처리 중: '{keyword}'")
            
            # 키워드로 비디오 검색
            videos = search_videos_by_keyword(keyword, credentials, max_results=10)
            if not videos:
                print(f"키워드 '{keyword}'로 비디오를 찾지 못했습니다.")
                continue
            
            # 비디오 처리
            for video in videos:
                video_id = video.get("video_id")
                video_title = video.get("title")
                
                # 이미 데이터베이스에 있는지 확인
                if is_video_in_db(video_id):
                    print(f"비디오 '{video_title}' (ID: {video_id})는 이미 데이터베이스에 있으므로 건너뜁니다.")
                    continue
                
                # 발행일 확인 (1주일 이내인지)
                published_at = video.get("published_at")
                
                # 발행일을 datetime 객체로 변환 (문자열인 경우)
                if isinstance(published_at, str):
                    # ISO 형식 문자열을 datetime으로 변환
                    if 'Z' in published_at:
                        published_at = published_at.replace('Z', '+00:00')
                    published_date = datetime.fromisoformat(published_at)
                else:
                    # 이미 datetime 객체인 경우
                    published_date = published_at
                
                # 현재 시간을 timezone-aware로 생성 (UTC 기준)
                now = datetime.now(timezone.utc)
                
                # published_date가 timezone-naive인 경우 UTC로 가정하여 timezone-aware로 변환
                if published_date.tzinfo is None:
                    published_date = published_date.replace(tzinfo=timezone.utc)
                
                # 1주일 이내인지 확인
                if (now - published_date).days > 7:
                    print(f"비디오 '{video_title}' (ID: {video_id})는 1주일 이전에 발행되어 건너뜁니다.")
                    continue
                
                print(f"비디오 처리 중: '{video_title}' (ID: {video_id})")
                
                # 비디오 상세 정보 가져오기
                video_info = get_video_info(video_id, credentials)
                if not video_info:
                    print(f"비디오 ID {video_id}에서 상세 정보를 가져오지 못했습니다.")
                    continue
                
                # 자막 가져오기
                transcript, lang = get_video_transcript(video_id, credentials)
                if not transcript:
                    print(f"비디오 ID {video_id}에서 자막을 찾을 수 없습니다.")
                    continue
                
                # 비디오 처리 및 분석
                process_video(video_id, video_info, transcript, analysis_types)
                
        except Exception as e:
            print(f"키워드 '{keyword}' 처리 중 오류 발생: {e}")
            traceback.print_exc()
    
    print(f"\n=== 데이터 수집 완료: {datetime.now().isoformat()} ===")

def run_scheduler(analysis_types=None, credentials=None):
    """스케줄러를 실행합니다."""
    if credentials is None:
        print("오류: OAuth2 인증 정보가 필요합니다.")
        return
        
    config = load_config()
    interval = config.get("schedule_interval", 24)  # 기본값: 24시간
    
    def scheduled_job():
        try:
            print(f"\n=== 스케줄된 작업 시작: {datetime.now().isoformat()} ===")
            collect_data(analysis_types, credentials)
            print(f"=== 스케줄된 작업 완료: {datetime.now().isoformat()} ===")
        except Exception as e:
            print(f"스케줄된 작업 중 오류 발생: {e}")
            traceback.print_exc()
    
    # 즉시 한 번 실행
    scheduled_job()
    
    # 스케줄 설정
    schedule.every(interval).hours.do(scheduled_job)
    
    print(f"스케줄러가 시작되었습니다. {interval}시간마다 실행됩니다.")
    
    # 스케줄러 실행
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 체크

def test():
    """테스트 함수"""
    print("=== 테스트 시작 ===")
    
    # 데이터베이스 초기화
    initialize_db()
    print("데이터베이스 초기화 완료")
    
    # 구성 파일 테스트
    config = load_config()
    print(f"구성 파일 로드 완료: {config}")
    
    # 채널 추가 테스트
    add_channel("https://www.youtube.com/@understanding")
    print("채널 추가 테스트 완료")
    
    # 키워드 추가 테스트
    add_keyword("경제")
    print("키워드 추가 테스트 완료")
    
    print("=== 테스트 완료 ===")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="YouTube 뉴스 자막 수집 및 요약 시스템")
    parser.add_argument("--test", action="store_true", help="테스트 모드 실행")
    parser.add_argument("--collect", action="store_true", help="데이터 수집 실행")
    parser.add_argument("--schedule", action="store_true", help="스케줄러 실행")
    parser.add_argument("--analysis-types", nargs="+", default=["summary"], help="분석 유형 지정")
    
    args = parser.parse_args()
    
    if args.test:
        test()
    elif args.collect:
        print("OAuth2 인증이 필요합니다. Streamlit 앱에서 로그인 후 사용해주세요.")
    elif args.schedule:
        print("OAuth2 인증이 필요합니다. Streamlit 앱에서 로그인 후 사용해주세요.")
    else:
        print("사용법:")
        print("  python main.py --test     # 테스트 실행")
        print("  python main.py --collect  # 데이터 수집 실행 (OAuth2 필요)")
        print("  python main.py --schedule # 스케줄러 실행 (OAuth2 필요)")

if __name__ == "__main__":
    main() 