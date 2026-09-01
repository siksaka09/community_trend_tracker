"""
จัดการฐานข้อมูล SQLite สำหรับเก็บโพสต์จาก community ต่างๆ (Reddit, Facebook Groups, ฯลฯ)
ใช้ตารางเดียวรวมทุกแพลตฟอร์ม โดยมีคอลัมน์ "platform" กำกับ เพื่อให้เทียบข้ามแพลตฟอร์มง่าย
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "community_trends.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS community_posts (
            uid TEXT PRIMARY KEY,        -- "<platform>:<post_id>" กันชนกันข้ามแพลตฟอร์ม
            platform TEXT NOT NULL,      -- "reddit" หรือ "facebook_group"
            source_name TEXT,            -- ชื่อ subreddit หรือชื่อกลุ่ม
            source_url TEXT,
            post_id TEXT NOT NULL,
            posted_at TEXT,
            scraped_at TEXT NOT NULL,
            title TEXT,                  -- มีเฉพาะ Reddit ส่วน Facebook มักไม่มี title แยก
            text TEXT,
            post_url TEXT,
            score INTEGER,               -- upvotes (reddit) หรือ likes/reactions (facebook)
            comments INTEGER,
            -- ฟิลด์ที่ AI วิเคราะห์แล้วเติมให้ทีหลัง
            is_relevant INTEGER,         -- 1 = เกี่ยวกับ EA FC 27 จริง, 0 = ไม่เกี่ยว, NULL = ยังไม่เช็ค
            sentiment TEXT,              -- "positive" / "negative" / "neutral" / "mixed"
            topics TEXT,                 -- JSON list เช่น ["gameplay","pricing","release_date","bug"]
            summary TEXT,                -- สรุปสั้นๆ ว่าโพสต์นี้พูดถึงอะไร
            ai_analyzed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def upsert_posts(posts: list[dict]) -> int:
    """บันทึกโพสต์ลง DB โดยข้ามโพสต์ที่มี uid ซ้ำอยู่แล้ว (กันดึงซ้ำเวลารันทุกวัน)"""
    conn = get_connection()
    cur = conn.cursor()
    inserted = 0
    for p in posts:
        try:
            cur.execute("""
                INSERT INTO community_posts (uid, platform, source_name, source_url, post_id,
                                              posted_at, scraped_at, title, text, post_url,
                                              score, comments)
                VALUES (:uid, :platform, :source_name, :source_url, :post_id,
                        :posted_at, :scraped_at, :title, :text, :post_url,
                        :score, :comments)
                ON CONFLICT(uid) DO NOTHING
            """, p)
            if cur.rowcount > 0:
                inserted += 1
        except sqlite3.Error as e:
            print(f"  [db] ข้าม post {p.get('uid')}: {e}")
    conn.commit()
    conn.close()
    return inserted


def get_unanalyzed_posts(limit: int = 300) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM community_posts WHERE ai_analyzed = 0 ORDER BY posted_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_ai_analysis(uid: str, is_relevant: bool, sentiment: str, topics: str, summary: str):
    conn = get_connection()
    conn.execute("""
        UPDATE community_posts
        SET is_relevant = ?, sentiment = ?, topics = ?, summary = ?, ai_analyzed = 1
        WHERE uid = ?
    """, (int(is_relevant), sentiment, topics, summary, uid))
    conn.commit()
    conn.close()


def get_all_posts_df():
    import pandas as pd
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM community_posts", conn)
    conn.close()
    return df


# ============================================================
# ฟังก์ชันเพิ่มเติมสำหรับ Web Dashboard (Streamlit)
# ============================================================

def get_summary_stats() -> dict:
    """สรุปตัวเลขภาพรวมไว้ใช้แสดงเป็น metric card บนหน้า dashboard"""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN ai_analyzed = 1 THEN 1 ELSE 0 END) AS analyzed,
               SUM(CASE WHEN is_relevant = 1 THEN 1 ELSE 0 END) AS relevant,
               COUNT(DISTINCT source_name) AS accounts
        FROM community_posts
    """).fetchone()
    conn.close()
    if row is None:
        return {"total": 0, "analyzed": 0, "relevant": 0, "accounts": 0}
    result = dict(row)
    for key in ("total", "analyzed", "relevant", "accounts"):
        result[key] = result[key] or 0
    return result


def update_post_relevance(uid: str, is_relevant: bool):
    """แก้ค่า is_relevant ของโพสต์เดียวด้วยมือ (ใช้ตอนพบว่า AI จำแนกผิดพลาด)"""
    conn = get_connection()
    conn.execute(
        "UPDATE community_posts SET is_relevant = ? WHERE uid = ?",
        (int(is_relevant), uid),
    )
    conn.commit()
    conn.close()
