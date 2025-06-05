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
    get_video_transcript
)
from db_handler import (
    initialize_db,
    save_video_data,
    analyze_video,
    generate_report,
    is_video_in_db,
    generate_economic_news_from_recent_videos
)
from llm_handler import summarize_transcript, analyze_transcript, analyze_transcript_with_type

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

def process_video(video_id, analysis_types=None):
    """비디오를 처리하고 데이터베이스에 저장합니다."""
    if analysis_types is None:
        analysis_types = ["summary"]  # 기본 분석 유형
        
    try:
        # 비디오 정보 가져오기
        video_info = get_info_by_url(f"https://www.youtube.com/watch?v={video_id}")
        if not video_info or not video_info.get("id"):
            print(f"비디오 ID {video_id}에서 정보를 가져오지 못했습니다.")
            return False
            
        # 자막 추출
        transcript, lang = get_video_transcript(video_id)
        
        # 저장
        success = save_video_data(video_info, transcript)
        
        # 자막 요약 (있는 경우에만)
        if success and transcript:
            try:
                print(f"비디오 ID {video_id}에 대한 분석 수행 중... 분석 유형: {', '.join(analysis_types)}")
                
                # 각 분석 유형별로 처리
                for analysis_type in analysis_types:
                    try:
                        start_time = time.time()
                        
                        if analysis_type == "summary":
                            # 자막 길이에 상관없이 청크로 나누어 처리
                            result = summarize_transcript(transcript, max_length=500, analysis_type=analysis_type)
                        else:
                            # 다른 분석 유형 처리
                            result = analyze_transcript_with_type(transcript, analysis_type)
                        
                        # 결과 출력 (일부만)
                        process_time = time.time() - start_time
                        if len(result) > 100:
                            print(f"비디오 '{video_info.get('title')}' {analysis_type} 결과: {result[:100]}... (처리 시간: {process_time:.2f}초)")
                        else:
                            print(f"비디오 '{video_info.get('title')}' {analysis_type} 결과: {result} (처리 시간: {process_time:.2f}초)")
                        
                        # 데이터베이스에 결과 저장
                        from db_handler import save_summary_to_db
                        save_summary_to_db(video_id, analysis_type, result)
                        
                    except Exception as e:
                        print(f"{analysis_type} 생성 중 오류 발생: {e}")
                        
            except Exception as e:
                print(f"요약/분석 생성 중 오류 발생: {e}")
        
        return success
    except Exception as e:
        print(f"비디오 처리 중 오류 발생: {e}")
        return False

def collect_data(analysis_types=None):
    """채널 및 키워드에서 데이터를 수집합니다."""
    if analysis_types is None:
        analysis_types = ["summary"]  # 기본 분석 유형
        
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
            channel_info = get_info_by_url(channel_url)
            if not channel_info:
                print(f"채널 URL {channel_url}에서 정보를 가져오지 못했습니다.")
                continue
                
            channel_id = channel_info.get("id")
            channel_title = channel_info.get("title")
            
            # 채널에서 비디오 검색
            videos = search_videos_by_keyword("", channel_id=channel_id, max_results=15)
            if not videos:
                print(f"채널 '{channel_title}'에서 비디오를 찾지 못했습니다.")
                continue
                
            # 비디오 처리
            for video in videos:
                video_id = video.get("id")
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
                
                # 1주일 전 시간 계산 (timezone-aware)
                one_week_ago = now - timedelta(days=7)
                
                # 발행일이 1주일 이전인지 확인
                if published_date < one_week_ago:
                    print(f"비디오 '{video_title}'은(는) 1주일 이상 지난 영상이므로 건너뜁니다.")
                    continue
                
                print(f"\n비디오 처리 중: {video_title} (ID: {video_id})")
                
                # 비디오 정보 가져오기
                video_info = get_video_info(video_id)
                if not video_info:
                    print(f"비디오 ID {video_id}에 대한 정보를 가져오지 못했습니다.")
                    continue
                
                # 자막 추출
                transcript = get_video_transcript(video_id)
                if not transcript:
                    print(f"비디오 ID {video_id}에 대해 자막을 찾을 수 없습니다.")
                
                # 비디오 정보 저장
                video_info["transcript"] = transcript
                save_video_data(video_info, transcript)
                
                # 자막이 있는 경우에만 분석 수행
                if transcript:
                    for analysis_type in analysis_types:
                        analyze_video(video_id, analysis_type)
                
        except Exception as e:
            print(f"채널 {channel_url} 처리 중 오류 발생: {str(e)}")
            traceback.print_exc()
    
    # 키워드 검색
    for keyword in config["keywords"]:
        try:
            print(f"\n>> 키워드 검색 중: '{keyword}'")
            videos = search_videos_by_keyword(keyword)
            if not videos:
                print(f"키워드 '{keyword}'로 비디오를 찾지 못했습니다.")
                continue
                
            # 비디오 처리
            for video in videos:
                video_id = video.get("id")
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
                
                # 1주일 전 시간 계산 (timezone-aware)
                one_week_ago = now - timedelta(days=7)
                
                # 발행일이 1주일 이전인지 확인
                if published_date < one_week_ago:
                    print(f"비디오 '{video_title}'은(는) 1주일 이상 지난 영상이므로 건너뜁니다.")
                    continue
                
                print(f"\n비디오 처리 중: {video_title} (ID: {video_id})")
                
                # 비디오 정보 가져오기
                video_info = get_video_info(video_id)
                if not video_info:
                    print(f"비디오 ID {video_id}에 대한 정보를 가져오지 못했습니다.")
                    continue
                
                # 자막 추출
                transcript = get_video_transcript(video_id)
                if not transcript:
                    print(f"비디오 ID {video_id}에 대해 자막을 찾을 수 없습니다.")
                
                # 비디오 정보 저장
                video_info["transcript"] = transcript
                save_video_data(video_info, transcript)
                
                # 자막이 있는 경우에만 분석 수행
                if transcript:
                    for analysis_type in analysis_types:
                        analyze_video(video_id, analysis_type)
                
        except Exception as e:
            print(f"키워드 {keyword} 처리 중 오류 발생: {str(e)}")
            traceback.print_exc()
    
    # 종료 시간 기록
    end_time = datetime.now().isoformat()
    print(f"\n=== 데이터 수집 완료: {end_time} ===")
    
    # 리포트 생성
    print("\n=== 리포트 생성 시작 ===")
    report_data = generate_report(hours=12)  # 최근 12시간 내 데이터로 리포트 생성
    
    # 리포트 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON 형식으로 저장
    json_path = os.path.join("reports", f"report_{timestamp}.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    # 마크다운 형식으로 저장
    md_path = os.path.join("reports", f"report_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 신규 콘텐츠 리포트 ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n")
        f.write(f"## 개요\n")
        f.write(f"- 생성 시간: {report_data['generated_at']}\n")
        f.write(f"- 기간: {report_data['since']} 이후\n")
        f.write(f"- 총 비디오 수: {report_data['total_videos']}개\n\n")
        
        if report_data['total_videos'] > 0:
            f.write(f"## 채널별 신규 콘텐츠\n\n")
            
            for channel, videos in report_data['channels'].items():
                f.write(f"### {channel} ({len(videos)}개)\n\n")
                
                for video in videos:
                    f.write(f"#### {video['title']}\n")
                    f.write(f"- 게시일: {video['published_at']}\n")
                    f.write(f"- 조회수: {video['view_count']}\n")
                    f.write(f"- 링크: https://www.youtube.com/watch?v={video['id']}\n\n")
    
    print(f"리포트가 생성되었습니다:")
    print(f"- JSON: {os.path.abspath(json_path)}")
    print(f"- 마크다운: {os.path.abspath(md_path)}")
    print(f"총 {report_data['total_videos']}개의 새 비디오가 수집되었습니다.")
    print("=== 리포트 생성 완료 ===")
    
    return {
        "start_time": start_time,
        "end_time": end_time,
        "videos_count": report_data['total_videos']
    }

def run_scheduler(analysis_types=None):
    """스케줄러를 설정하고 실행합니다."""
    if analysis_types is None:
        analysis_types = ["summary", "analysis_economic"]  # 기본 분석 유형
    
    print(f"스케줄러 설정 중... 기본 분석 유형: {', '.join(analysis_types)}")
    
    # 구성 파일에서 간격 설정 읽기
    config = load_config()
    interval_hours = config.get("schedule_interval", 24)
    
    # 분석 유형을 클로저에 전달
    def scheduled_job():
        """정해진 시간에 실행될 작업"""
        print(f"\n=== 스케줄러 작업 시작: {datetime.now().isoformat()} ===")
        
        # 데이터 수집 및 분석
        collect_data(analysis_types)
        
        # 리포트 생성
        report = generate_report(hours=interval_hours)
        if report:
            print(f"신규 콘텐츠 리포트 생성 완료: {len(report.get('videos', []))}개의 비디오 처리됨.")
        else:
            print("신규 콘텐츠 리포트 생성 실패 또는 처리할 데이터 없음.")
        
        # 경제 뉴스 사설 생성
        news_article = generate_economic_news_from_recent_videos(
            hours=interval_hours,
            style="editorial",  # 기본 스타일: 사설
            word_count=1200,    # 기본 글자수: 1200자
            language="ko"       # 기본 언어: 한국어
        )
        if news_article:
            print(f"경제 뉴스 사설 생성 완료: {news_article['title']}")
        else:
            print("경제 뉴스 사설 생성 실패 또는 처리할 데이터 없음.")
        
        print(f"=== 스케줄러 작업 완료: {datetime.now().isoformat()} ===\n")
    
    # 스케줄 설정 (매일 특정 시간에 실행)
    schedule.every(interval_hours).hours.do(scheduled_job)
    print(f"스케줄러가 {interval_hours}시간마다 실행되도록 설정되었습니다.")
    
    # 처음 한 번 실행
    scheduled_job()
    
    # 스케줄러 계속 실행
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 확인

def test():
    """테스트 기능을 실행합니다."""
    print("YouTube 뉴스 자막 수집 및 요약 시스템 테스트")
    
    # 테스트 URL 목록
    test_urls = [
        "https://www.youtube.com/watch?v=irFqOYrdHy0",  # 일반 비디오 URL
        "https://youtu.be/irFqOYrdHy0",                # 단축 URL
        "https://www.youtube.com/shorts/FYgMrwVY2Q4"   # 쇼츠 URL
    ]
    
    print("\n=== URL 테스트 ===")
    for url in test_urls:
        print(f"\n▶ 테스트 URL: {url}")
        
        try:
            # URL에서 비디오 ID 추출
            video_id = extract_video_id(url)
            print(f"추출된 비디오 ID: {video_id}")
            
            # URL로 비디오 정보 가져오기
            video_info = get_info_by_url(url)
            if not video_info or not video_info.get("id"):
                print(f"URL {url}에서 비디오 정보를 가져오지 못했습니다.")
                continue
                
            print(f"비디오 제목: {video_info.get('title')}")
            print(f"채널명: {video_info.get('channel_title')}")
            
            # 자막 추출
            transcript, lang = get_video_transcript(video_id)
            transcript_preview = transcript[:100] + "..." if transcript else "자막 없음"
            print(f"자막 (언어: {lang}): {transcript_preview}")
            
            # 자막 요약 (있는 경우에만)
            if transcript:
                print("\n=== GPT-4o-mini 자막 요약 ===")
                summary = summarize_transcript(transcript, max_length=500)
                print(f"요약: {summary}")
                
                print("\n=== GPT-4o-mini 자막 분석 ===")
                analysis = analyze_transcript(transcript, "이 내용의 주요 주제와 객관성을 평가해주세요.")
                print(f"분석: {analysis}")
            
            # DB에 저장
            save_result = save_video_data(video_info, transcript)
            if save_result:
                print(f"비디오 ID {video_id} 저장 완료!")
            else:
                print(f"비디오 ID {video_id} 저장 실패 또는 이미 존재함")
                
        except Exception as e:
            print(f"오류 발생: {e}")
    
    print("\n테스트 완료!")

def main():
    """메인 함수를 실행합니다."""
    parser = argparse.ArgumentParser(description="YouTube 뉴스 자막 수집 및 요약 시스템")
    parser.add_argument("--add-channel", help="모니터링할 채널 URL 추가")
    parser.add_argument("--add-keyword", help="모니터링할 키워드 추가")
    parser.add_argument("--process-url", help="특정 URL 처리")
    parser.add_argument("--collect", action="store_true", help="데이터 수집 실행")
    parser.add_argument("--schedule", action="store_true", help="스케줄러 실행")
    parser.add_argument("--test", action="store_true", help="테스트 실행")
    parser.add_argument("--analysis-types", help="수행할 분석 유형 (쉼표로 구분, 예: summary,analysis_economic)")
    parser.add_argument("--interval", type=int, help="스케줄러 실행 간격 (시간)")
    
    args = parser.parse_args()
    
    # 분석 유형 처리
    analysis_types = ["summary"]  # 기본값
    if args.analysis_types:
        analysis_types = args.analysis_types.split(",")
    
    if args.add_channel:
        add_channel(args.add_channel)
    elif args.add_keyword:
        add_keyword(args.add_keyword)
    elif args.interval:
        config = load_config()
        config["schedule_interval"] = args.interval
        save_config(config)
        print(f"스케줄러 간격이 {args.interval}시간으로 설정되었습니다.")
    elif args.process_url:
        video_id = extract_video_id(args.process_url)
        if video_id:
            print(f"URL에서 추출한 비디오 ID: {video_id}")
            process_video(video_id, analysis_types)
        else:
            print(f"유효한 YouTube URL이 아닙니다: {args.process_url}")
    elif args.collect:
        collect_data(analysis_types)
    elif args.schedule:
        run_scheduler(analysis_types)
    elif args.test:
        test()
    else:
        # 인자가 없으면 명령행 모드 실행
        run_command_line_mode()

if __name__ == "__main__":
    main() 