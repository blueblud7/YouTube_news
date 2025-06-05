#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
자막이 있는 비디오를 처리하고 요약 정보를 생성하는 스크립트
"""

import sqlite3
import os
import time
import argparse
from llm_handler import (
    summarize_transcript, 
    analyze_transcript_with_type, 
    get_available_analysis_types
)
from db_handler import save_summary_to_db, get_summaries_for_video

# 데이터베이스 파일 경로
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_news.db")

def get_videos_with_transcript(limit=5):
    """자막이 있는 비디오 목록을 가져옵니다."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, channel_title, transcript 
        FROM videos 
        WHERE transcript IS NOT NULL
        ORDER BY length(transcript) DESC
        LIMIT ?
    ''', (limit,))
    
    videos = cursor.fetchall()
    conn.close()
    
    return videos

def process_and_summarize(analysis_types=None, limit=3, save_to_db=True, force=False):
    """
    자막이 있는 비디오를 처리하고 요약 정보를 생성합니다.
    
    :param analysis_types: 수행할 분석 유형 목록 (지정하지 않으면 'summary'만 실행)
    :param limit: 처리할 비디오 수
    :param save_to_db: 결과를 데이터베이스에 저장할지 여부
    :param force: 이미 있는 분석도 다시 수행할지 여부
    """
    if analysis_types is None:
        analysis_types = ["summary"]
        
    print("\n=== 자막 요약 처리 시작 ===")
    print(f"처리할 분석 유형: {', '.join(analysis_types)}")
    
    # 자막이 있는 비디오 가져오기
    videos = get_videos_with_transcript(limit=limit)
    
    if not videos:
        print("자막이 있는 비디오가 없습니다.")
        return
    
    # 각 비디오 처리
    for i, (video_id, title, channel, transcript) in enumerate(videos, 1):
        print(f"\n처리 중 {i}/{len(videos)}: {title}")
        print(f"채널: {channel}")
        print(f"자막 길이: {len(transcript)}자")
        
        try:
            # 기존 요약 정보 확인
            if not force:
                existing_summaries = get_summaries_for_video(video_id)
            else:
                existing_summaries = {}
            
            # 각 분석 유형별로 처리
            for analysis_type in analysis_types:
                # 이미 있는 분석은 건너뛰기 (강제 옵션이 아닌 경우)
                if not force and analysis_type in existing_summaries:
                    print(f"\n{analysis_type}는 이미 존재합니다. 건너뜁니다. (강제 재생성하려면 --force 옵션 사용)")
                    continue
                    
                print(f"\n{analysis_type} 생성 중...")
                start_time = time.time()
                
                if analysis_type == "summary":
                    result = summarize_transcript(transcript, analysis_type=analysis_type)
                else:
                    result = analyze_transcript_with_type(transcript, analysis_type)
                
                process_time = time.time() - start_time
                print(f"{analysis_type} 완료 (처리 시간: {process_time:.2f}초)")
                print(f"\n{analysis_type} 결과:\n{result[:300]}...(생략)")
                
                # 데이터베이스에 결과 저장
                if save_to_db:
                    success = save_summary_to_db(video_id, analysis_type, result)
                    if success:
                        print(f"결과가 데이터베이스에 저장되었습니다.")
            
        except Exception as e:
            print(f"오류 발생: {e}")
    
    print("\n=== 자막 요약 처리 완료 ===")

def show_video_summaries(video_id):
    """
    특정 비디오의 모든 요약 정보를 표시합니다.
    
    :param video_id: 비디오 ID
    """
    # 비디오 정보 가져오기
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, channel_title FROM videos WHERE id = ?", (video_id,))
    video_info = cursor.fetchone()
    conn.close()
    
    if not video_info:
        print(f"비디오 ID {video_id}을(를) 찾을 수 없습니다.")
        return
    
    title, channel = video_info
    print(f"\n=== '{title}' (채널: {channel}) 요약 정보 ===")
    
    # 요약 정보 가져오기
    summaries = get_summaries_for_video(video_id)
    
    if not summaries:
        print("이 비디오에 대한 요약 정보가 없습니다.")
        return
    
    # 각 유형별 요약 표시
    for summary_type, content in summaries.items():
        print(f"\n--- {summary_type} ---")
        print(content)
    
    print("\n=== 요약 정보 표시 완료 ===")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="YouTube 비디오 자막 요약 및 분석 도구")
    
    # 서브커맨드 설정
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")
    
    # 요약 및 분석 명령
    summarize_parser = subparsers.add_parser("summarize", help="비디오 요약 및 분석")
    summarize_parser.add_argument("--types", nargs="+", help="수행할 분석 유형 (쉼표로 구분)")
    summarize_parser.add_argument("--limit", type=int, default=3, help="처리할 비디오 수 (기본값: 3)")
    summarize_parser.add_argument("--no-save", action="store_true", help="결과를 데이터베이스에 저장하지 않음")
    summarize_parser.add_argument("--force", action="store_true", help="이미 있는 분석도 다시 수행")
    
    # 요약 정보 표시 명령
    show_parser = subparsers.add_parser("show", help="저장된 요약 정보 표시")
    show_parser.add_argument("video_id", help="표시할 비디오 ID")
    
    # 사용 가능한 분석 유형 표시 명령
    types_parser = subparsers.add_parser("types", help="사용 가능한 분석 유형 표시")
    
    args = parser.parse_args()
    
    # 명령에 따라 다른 동작 수행
    if args.command == "summarize":
        # 분석 유형 처리
        analysis_types = args.types if args.types else ["summary"]
        if len(analysis_types) == 1 and "," in analysis_types[0]:
            analysis_types = analysis_types[0].split(",")
        
        process_and_summarize(
            analysis_types=analysis_types,
            limit=args.limit,
            save_to_db=not args.no_save,
            force=args.force
        )
    elif args.command == "show":
        show_video_summaries(args.video_id)
    elif args.command == "types":
        print("\n=== 사용 가능한 분석 유형 ===")
        for type_info in get_available_analysis_types():
            print(f"{type_info['code']}: {type_info['description']}")
    else:
        # 기본 동작: 요약 실행
        process_and_summarize(force=False)

if __name__ == "__main__":
    main() 