"""
จัดการฐานข้อมูล SQLite สำหรับเก็บโพสต์จาก community ต่างๆ (X/Twitter, Reddit, Facebook Pages)
ใช้ตารางเดียวรวมทุกแพลตฟอร์ม โดยมีคอลัมน์ "platform" กำกับ เพื่อให้เทียบข้ามแพลตฟอร์มง่าย

=== เกี่ยวกับคอลัมน์ราคา/โปรโมชั่น (facebook_page เท่านั้น) ===
platform "facebook_page" ใช้สำหรับติดตามเพจร้านค้า (เช่น เทียบราคาขายเหรียญเกมระหว่างสองเพจ)
ซึ่งมีข้อมูลที่ platform อื่น (x, reddit) ไม่มี — คอลัมน์ has_price/price_info/promo_info/
price_source/image_urls/views จึงเป็นแบบ nullable: มีค่าเฉพาะโพสต์จาก facebook_page เท่านั้น
โพสต์จาก x/reddit จะเป็น NULL เสมอ (ไม่ error อะไร แค่ไม่ได้ใช้ฟิลด์พวกนี้)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "community_trends.db"

# คอลัมน์ที่เพิ่มเข้ามาทีหลัง (สำหรับ migrate ฐานข้อมูลเดิมที่มีอยู่แล้วแบบไม่ให้ข้อมูลหาย)
EXTRA_COLUMNS = {
    "has_price": "INTEGER",       # 1/0/NULL — มีราคาปรากฏในโพสต์ไหม (facebook_page เท่านั้น)
    "price_info": "TEXT",         # JSON list: [{"quantity":"1M","price":25,"currency":"THB"}]
    "promo_info": "TEXT",         # JSON: {"has_promotion": true/false, "summary": "..."}
    "price_source": "TEXT",       # "text" หรือ "image" — ราคาดึงมาจากไหน
    "price_analyzed": "INTEGER DEFAULT 0",  # แยกจาก ai_analyzed เพราะเป็นขั้นตอนคนละรอบ
    "image_urls": "TEXT",         # JSON list ของ URL รูปภาพในโพสต์ (facebook_page เท่านั้น)
    "views": "INTEGER",           # ยอดวิว ถ้ามี (เช่นโพสต์วิดีโอ)
    "shares": "INTEGER",          # ยอดแชร์ แยกจาก comments (facebook_page เท่านั้น เดิมรวมไว้ใน
                                   # comments แต่แยกออกมาทีหลังเพื่อให้ดู engagement ละเอียดขึ้นได้)
}


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
            platform TEXT NOT NULL,      -- "x" / "reddit" / "facebook_page"
            source_name TEXT,            -- ชื่อบัญชี X, subreddit, หรือชื่อเพจ Facebook
            source_url TEXT,
            post_id TEXT NOT NULL,
            posted_at TEXT,
            scraped_at TEXT NOT NULL,
            title TEXT,                  -- มีเฉพาะ Reddit ส่วนแพลตฟอร์มอื่นมักไม่มี title แยก
            text TEXT,
            post_url TEXT,
            score INTEGER,               -- upvotes (reddit) / likes (x, facebook)
            comments INTEGER,            -- comments เพียวๆ (facebook_page แยก shares ออกต่างหากแล้ว
                                          -- ส่วน x คือ replies+retweets รวมกัน, reddit คือ comment count)
            -- ฟิลด์ที่ AI วิเคราะห์แล้วเติมให้ทีหลัง (relevance/sentiment/topic — ทุกแพลตฟอร์ม)
            is_relevant INTEGER,         -- 1 = เกี่ยวกับ EA FC 27 จริง, 0 = ไม่เกี่ยว, NULL = ยังไม่เช็ค
            sentiment TEXT,              -- "positive" / "negative" / "neutral" / "mixed"
            topics TEXT,                 -- JSON list เช่น ["gameplay","pricing","release_date","bug"]
            summary TEXT,                -- สรุปสั้นๆ ว่าโพสต์นี้พูดถึงอะไร
            ai_analyzed INTEGER DEFAULT 0
        )
    """)

    # migrate: เติมคอลัมน์ใหม่ให้ฐานข้อมูลเดิมที่เคยสร้างไว้ก่อนหน้านี้ (ไม่กระทบข้อมูลเดิม)
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(community_posts)").fetchall()}
    for col_name, col_type in EXTRA_COLUMNS.items():
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE community_posts ADD COLUMN {col_name} {col_type}")
            print(f"  [db] migrate: เพิ่มคอลัมน์ '{col_name}' เข้าไปในฐานข้อมูลเดิม")

    conn.commit()
    conn.close()


def upsert_posts(posts: list[dict]) -> int:
    """บันทึกโพสต์ลง DB โดยข้ามโพสต์ที่มี uid ซ้ำอยู่แล้ว (กันดึงซ้ำเวลารันทุกวัน)"""
    conn = get_connection()
    cur = conn.cursor()
    inserted = 0
    for p in posts:
        # เติมค่า default ให้ฟิลด์ใหม่เผื่อ scraper บางตัวไม่ได้ส่งมา (เช่น x/reddit ไม่มีเรื่องราคา/แชร์)
        p.setdefault("image_urls", None)
        p.setdefault("views", None)
        p.setdefault("shares", None)
        try:
            cur.execute("""
                INSERT INTO community_posts (uid, platform, source_name, source_url, post_id,
                                              posted_at, scraped_at, title, text, post_url,
                                              score, comments, image_urls, views, shares)
                VALUES (:uid, :platform, :source_name, :source_url, :post_id,
                        :posted_at, :scraped_at, :title, :text, :post_url,
                        :score, :comments, :image_urls, :views, :shares)
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
    """โพสต์ที่ยังไม่เช็ค relevance/sentiment/topic (ใช้ได้กับทุกแพลตฟอร์ม)"""
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


def get_unpriced_facebook_posts(limit: int = 200) -> list[dict]:
    """โพสต์จาก facebook_page ที่ยังไม่เช็คราคา/โปรโมชั่น (ขั้นตอนแยกจาก ai_analyzed)"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM community_posts
        WHERE platform = 'facebook_page' AND price_analyzed = 0
        ORDER BY posted_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_price_analysis(uid: str, has_price: bool, price_info: str, promo_info: str, price_source: str = "text"):
    conn = get_connection()
    conn.execute("""
        UPDATE community_posts
        SET has_price = ?, price_info = ?, promo_info = ?, price_source = ?, price_analyzed = 1
        WHERE uid = ?
    """, (int(has_price), price_info, promo_info, price_source, uid))
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
               COUNT(DISTINCT source_name) AS accounts,
               SUM(CASE WHEN platform = 'facebook_page' THEN 1 ELSE 0 END) AS facebook_posts
        FROM community_posts
    """).fetchone()
    conn.close()
    if row is None:
        return {"total": 0, "analyzed": 0, "relevant": 0, "accounts": 0, "facebook_posts": 0}
    result = dict(row)
    for key in ("total", "analyzed", "relevant", "accounts", "facebook_posts"):
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
