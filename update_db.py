#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
데이터베이스 업데이트 스크립트
"""

import sqlite3
import os

# 데이터베이스 파일 경로
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_news.db")

def add_news_table():
    """뉴스 사설을 저장하는 테이블을 추가합니다."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 뉴스 테이블이 있는지 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news'")
    if cursor.fetchone():
        print("news 테이블이 이미 존재합니다.")
    else:
        # 뉴스 사설을 저장하는 테이블 추가
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                news_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                video_ids TEXT
            )
        """)
        conn.commit()
        print("news 테이블이 성공적으로 추가되었습니다.")
    
    conn.close()

if __name__ == "__main__":
    add_news_table() 