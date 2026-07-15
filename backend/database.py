import os
import sqlite3
import json
from contextvars import ContextVar
from datetime import datetime
from typing import List, Dict, Any, Optional


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'flower_dance.db')
LEGACY_USER_ID = 'legacy'
active_user_id: ContextVar[str] = ContextVar('active_user_id', default=LEGACY_USER_ID)


def set_active_user(user_id: str):
    return active_user_id.set(user_id)


def reset_active_user(token):
    active_user_id.reset(token)


def get_active_user_id() -> str:
    return active_user_id.get()


def add_user_column(cursor, table: str):
    columns = {row[1] for row in cursor.execute(f'PRAGMA table_info({table})')}
    if 'user_id' not in columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT '{LEGACY_USER_ID}'"
        )


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            content_type TEXT NOT NULL,
            content TEXT NOT NULL,
            filename TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'legacy',
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profile_rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'legacy',
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
            user_id TEXT NOT NULL DEFAULT 'legacy',
            data TEXT NOT NULL,
            generated_at TEXT NOT NULL
        )
    ''')

    for table in ('uploads', 'cards', 'profile_rejections', 'global_profile'):
        add_user_column(cursor, table)

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_user_category ON cards(user_id, category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploads_user_created_at ON uploads(user_id, created_at)')
    
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
            INSERT OR REPLACE INTO uploads (id, user_id, content_type, content, filename, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (upload_id, get_active_user_id(), content_type, content, filename, now_str()))
        conn.commit()
    finally:
        conn.close()


def get_uploads() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, content_type, content, filename, created_at FROM uploads '
            'WHERE user_id = ? ORDER BY created_at DESC',
            (get_active_user_id(),),
        )
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
            INSERT OR REPLACE INTO cards (id, user_id, category, title, content, evidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card['id'],
            get_active_user_id(),
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
                INSERT OR REPLACE INTO cards (id, user_id, category, title, content, evidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card['id'],
                get_active_user_id(),
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
        cursor.execute(
            'SELECT id, category, title, content, evidence, created_at, updated_at FROM cards '
            'WHERE user_id = ? ORDER BY category, created_at DESC',
            (get_active_user_id(),),
        )
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
        cursor.execute(
            'SELECT id, category, title, content, evidence, created_at, updated_at FROM cards '
            'WHERE user_id = ? AND category = ? ORDER BY created_at DESC',
            (get_active_user_id(), category),
        )
        rows = cursor.fetchall()
        return [dict(zip(['id', 'category', 'title', 'content', 'evidence', 'created_at', 'updated_at'], row)) for row in rows]
    finally:
        conn.close()


def delete_card(card_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM cards WHERE id = ? AND user_id = ?', (card_id, get_active_user_id()))
        conn.commit()
    finally:
        conn.close()


def update_card(card_id: str, updates: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [now_str(), card_id, get_active_user_id()]
        cursor.execute(f'UPDATE cards SET {set_clause}, updated_at = ? WHERE id = ? AND user_id = ?', params)
        conn.commit()
    finally:
        conn.close()


# ==================== Profile Rejections ====================

def add_rejection(line_id: str, text: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO profile_rejections (user_id, line_id, text, count, created_at)
            VALUES (?, ?, ?, 1, ?)
        ''', (get_active_user_id(), line_id, text, now_str()))
        
        cursor.execute('''
            UPDATE profile_rejections SET count = count + 1, created_at = ?
            WHERE user_id = ? AND line_id = ? AND text = ?
        ''', (now_str(), get_active_user_id(), line_id, text))
        
        conn.commit()
    finally:
        conn.close()


def get_rejections() -> Dict[str, int]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT line_id, count FROM profile_rejections WHERE user_id = ?',
            (get_active_user_id(),),
        )
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


# ==================== Global Profile ====================

def save_global_profile(data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM global_profile WHERE user_id = ?', (get_active_user_id(),))
        cursor.execute('''
            INSERT INTO global_profile (user_id, data, generated_at)
            VALUES (?, ?, ?)
        ''', (get_active_user_id(), json.dumps(data), data.get('generated_at', now_str())))
        conn.commit()
    finally:
        conn.close()


def get_global_profile() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT data FROM global_profile WHERE user_id = ? ORDER BY generated_at DESC LIMIT 1',
            (get_active_user_id(),),
        )
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
        cursor.execute('DELETE FROM global_profile WHERE user_id = ?', (get_active_user_id(),))
        conn.commit()
    finally:
        conn.close()


# ==================== Init ====================

init_db()
