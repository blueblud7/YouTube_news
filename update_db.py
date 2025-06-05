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
                video_ids TEXT,
                style TEXT DEFAULT 'basic',
                word_count INTEGER DEFAULT 1000,
                language TEXT DEFAULT 'ko',
                keywords TEXT
            )
        """)
        conn.commit()
        print("news 테이블이 성공적으로 추가되었습니다.")
    
    conn.close()

def update_news_table():
    """뉴스 테이블에 새로운 필드를 추가합니다."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 뉴스 테이블이 있는지 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='news'")
    if not cursor.fetchone():
        print("news 테이블이 존재하지 않습니다. 먼저 add_news_table()을 실행하세요.")
        conn.close()
        return
    
    # 현재 컬럼 구조 확인
    cursor.execute("PRAGMA table_info(news)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 필요한 필드 추가
    for field, field_type, default in [
        ('style', 'TEXT', "'basic'"), 
        ('word_count', 'INTEGER', "1000"), 
        ('language', 'TEXT', "'ko'"),
        ('keywords', 'TEXT', "NULL")
    ]:
        if field not in columns:
            try:
                cursor.execute(f"ALTER TABLE news ADD COLUMN {field} {field_type} DEFAULT {default}")
                print(f"news 테이블에 {field} 필드가 추가되었습니다.")
            except sqlite3.OperationalError as e:
                print(f"필드 {field} 추가 중 오류 발생: {e}")
        else:
            print(f"news 테이블에 {field} 필드가 이미 존재합니다.")
    
    conn.commit()
    conn.close()

def add_extracted_keywords_table():
    """추출된 키워드를 저장하는 테이블을 추가합니다."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 키워드 테이블이 있는지 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_keywords'")
    if cursor.fetchone():
        print("extracted_keywords 테이블이 이미 존재합니다.")
    else:
        # 추출된 키워드 테이블 추가
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (keyword)
            )
        """)
        conn.commit()
        print("extracted_keywords 테이블이 성공적으로 추가되었습니다.")
    
    conn.close()

if __name__ == "__main__":
    add_news_table()
    update_news_table()
    add_extracted_keywords_table() 