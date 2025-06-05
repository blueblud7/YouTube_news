#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os

def main():
    """데이터베이스에서 자막이 가장 긴 비디오를 조회합니다."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_news.db")
    
    try:
        # 데이터베이스 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 자막 길이 기준으로 정렬하여 상위 5개 비디오 조회
        cursor.execute('''
            SELECT id, title, channel_title, length(transcript) as transcript_length, published_at 
            FROM videos 
            WHERE transcript IS NOT NULL
            ORDER BY transcript_length DESC 
            LIMIT 5
        ''')
        
        rows = cursor.fetchall()
        
        if not rows:
            print("자막이 있는 비디오를 찾을 수 없습니다.")
            return
        
        print("\n=== 자막이 가장 긴 비디오 목록 ===")
        for i, row in enumerate(rows, 1):
            video_id, title, channel, transcript_length, published_at = row
            print(f"{i}. 비디오 ID: {video_id}")
            print(f"   제목: {title}")
            print(f"   채널: {channel}")
            print(f"   게시일: {published_at}")
            print(f"   자막 길이: {transcript_length:,}자")
            print(f"   URL: https://www.youtube.com/watch?v={video_id}")
            print()
            
        # 총 비디오 수와 자막이 있는 비디오 수 출력
        cursor.execute("SELECT COUNT(*) FROM videos")
        total_videos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos WHERE transcript IS NOT NULL")
        videos_with_transcript = cursor.fetchone()[0]
        
        print(f"총 비디오 수: {total_videos}")
        print(f"자막이 있는 비디오 수: {videos_with_transcript} ({videos_with_transcript/total_videos*100:.1f}%)")
        
    except sqlite3.Error as e:
        print(f"데이터베이스 오류: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 