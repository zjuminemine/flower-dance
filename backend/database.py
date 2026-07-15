import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'flower_dance.db')


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY,
            content_type TEXT NOT NULL,
            content TEXT NOT NULL,
            filename TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cards_category ON cards(category)
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profile_rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT NOT NULL,
            text TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(line_id, text)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            generated_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()


def get_connection():
    return sqlite3.connect(DB_PATH)


def now_str():
    return datetime.now().isoformat()


# ==================== Uploads ====================

def add_upload(upload_id: str, content_type: str, content: str, filename: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO uploads (id, content_type, content, filename, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (upload_id, content_type, content, filename, now_str()))
        conn.commit()
    finally:
        conn.close()


def get_uploads() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM uploads ORDER BY created_at DESC')
        rows = cursor.fetchall()
        return [
            {
                'id': upload_id,
                'source_type': content_type,
                'raw_text': content,
                'filename': filename,
                'created_at': created_at,
            }
            for upload_id, content_type, content, filename, created_at in rows
        ]
    finally:
        conn.close()


# ==================== Cards ====================

def add_card(card: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO cards (id, category, title, content, evidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            card['id'],
            card['category'],
            card['title'],
            card['content'],
            card.get('evidence', ''),
            card.get('created_at', now_str()),
            now_str()
        ))
        conn.commit()
    finally:
        conn.close()


def add_cards(cards_list: List[Dict[str, Any]]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for card in cards_list:
            cursor.execute('''
                INSERT OR REPLACE INTO cards (id, category, title, content, evidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                card['id'],
                card['category'],
                card['title'],
                card['content'],
                card.get('evidence', ''),
                card.get('created_at', now_str()),
                now_str()
            ))
        conn.commit()
    finally:
        conn.close()


def get_cards() -> Dict[str, List[Dict[str, Any]]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM cards ORDER BY category, created_at DESC')
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            card = dict(zip(['id', 'category', 'title', 'content', 'evidence', 'created_at', 'updated_at'], row))
            category = card['category']
            try:
                content_json = json.loads(card['content'])
                card.update(content_json)
            except (json.JSONDecodeError, TypeError):
                pass
            if category not in result:
                result[category] = []
            result[category].append(card)
        return result
    finally:
        conn.close()


def get_cards_by_category(category: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM cards WHERE category = ? ORDER BY created_at DESC', (category,))
        rows = cursor.fetchall()
        return [dict(zip(['id', 'category', 'title', 'content', 'evidence', 'created_at', 'updated_at'], row)) for row in rows]
    finally:
        conn.close()


def delete_card(card_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
        conn.commit()
    finally:
        conn.close()


def update_card(card_id: str, updates: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [now_str(), card_id]
        cursor.execute(f'UPDATE cards SET {set_clause}, updated_at = ? WHERE id = ?', params)
        conn.commit()
    finally:
        conn.close()


# ==================== Profile Rejections ====================

def add_rejection(line_id: str, text: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO profile_rejections (line_id, text, count, created_at)
            VALUES (?, ?, 1, ?)
        ''', (line_id, text, now_str()))
        
        cursor.execute('''
            UPDATE profile_rejections SET count = count + 1, created_at = ?
            WHERE line_id = ? AND text = ?
        ''', (now_str(), line_id, text))
        
        conn.commit()
    finally:
        conn.close()


def get_rejections() -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT line_id, count FROM profile_rejections')
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


# ==================== Global Profile ====================

def save_global_profile(data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM global_profile')
        cursor.execute('''
            INSERT INTO global_profile (data, generated_at)
            VALUES (?, ?)
        ''', (json.dumps(data), data.get('generated_at', now_str())))
        conn.commit()
    finally:
        conn.close()


def get_global_profile() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT data FROM global_profile ORDER BY generated_at DESC LIMIT 1')
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    finally:
        conn.close()


def clear_global_profile():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM global_profile')
        conn.commit()
    finally:
        conn.close()


# ==================== Init ====================

init_db()
