"""
ดึงทวีตจากบัญชี X (Twitter) ที่ระบุไว้ (เช่น เพจข่าวเกม, บัญชีทางการของ EA Sports FC,
บัญชีผู้มีอิทธิพลในวงการ) ผ่าน Apify actor: xquik/x-tweet-scraper

=== ทำไมเปลี่ยนจาก apidojo/twitter-scraper-lite มาเป็นตัวนี้ ===
actor ของค่าย apidojo (ทั้ง twitter-scraper-lite และ tweet-scraper) มีเงื่อนไขที่ตัว actor
ตั้งเอง (ไม่เกี่ยวกับเครดิต Apify ที่เหลือ) ว่าบัญชีที่อยู่ Apify Free Plan จะถูกจำกัดผลลัพธ์
ไว้ที่ 10 รายการเสมอ ต้องสมัครแพลนเสียเงินของ Apify (Starter ขึ้นไป) ถึงจะปลดล็อค
ส่วน xquik/x-tweet-scraper เป็น pay-per-result เต็มรูปแบบ คิดเงินจากเครดิตตรงๆ
"$0.15 ต่อ 1,000 แถวที่ส่งมอบ บนทุกแพลนของ Apify" (ตามหน้า actor) จึงใช้ได้เต็มที่บน Free Plan
ไม่ต้องอัพเกรดบัญชี Apify

=== 2 โหมดการดึงข้อมูล (ตั้งค่าได้ที่ FILTER_BY_KEYWORD ใน .env) ===
1. FILTER_BY_KEYWORD=false (ค่าเริ่มต้น) — ดึงทุกทวีตจากบัญชีที่ระบุ ใช้ "startUrls" เป็น
   URL โปรไฟล์ตรงๆ (เอกสารของ actor บอกว่าทางนี้เป็น fast user-timeline path)
   การกรองว่าเกี่ยวกับ FC27 หรือไม่จะเกิดขึ้นทีหลังตอน ai_analyze.py
2. FILTER_BY_KEYWORD=true — กรองตั้งแต่ตอนดึงเลย โดยใช้ Twitter advanced search query
   รูปแบบ "from:<handle> (keyword1 OR keyword2 OR ...)" ผ่าน field "searchTerms"
   ประหยัด credit/token กว่า แต่เสี่ยงพลาดทวีตที่พูดถึงเกมแบบอ้อมๆ ไม่ตรงคีย์เวิร์ดเป๊ะ

สำคัญ: สคริปต์นี้เรียก actor แยกทีละบัญชี (ไม่ส่งหลายบัญชีรวมในการรันเดียว) เพื่อให้เห็นชัดเจนว่า
บัญชีไหนได้ผลลัพธ์เท่าไหร่ และบัญชีที่มีปัญหาจะไม่ทำให้บัญชีอื่นพังไปด้วย

หมายเหตุสำคัญเรื่อง schema: xquik/x-tweet-scraper เป็น actor คนละค่ายกับ apidojo เดิม ชื่อ field
ในผลลัพธ์อาจไม่เหมือนกันเป๊ะ (ตั้ง fieldStyle="camelCase" ไว้เพื่อให้เดา field ง่ายขึ้น) โค้ดด้านล่าง
เขียน normalize_item() แบบ fallback หลายชื่อ field ไว้กันเหนียว แต่ **แนะนำให้รันครั้งแรกแล้วดู
log บรรทัด "ตัวอย่าง field ที่มีในผลลัพธ์ดิบ" ก่อน** ถ้าพบว่า field ไม่ตรงกับที่เดาไว้ ให้ปรับ
normalize_item() ตามชื่อ field จริงที่เห็น
"""
import os
import datetime as dt
from dotenv import load_dotenv
from apify_client import ApifyClient

from db import init_db, upsert_posts

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
TWITTER_HANDLES = [h.strip().lstrip("@") for h in os.getenv("TWITTER_HANDLES", "").split(",") if h.strip()]
TWITTER_KEYWORDS = [k.strip() for k in os.getenv("TWITTER_KEYWORDS", "").split(",") if k.strip()]
FILTER_BY_KEYWORD = os.getenv("FILTER_BY_KEYWORD", "false").strip().lower() in ("1", "true", "yes")
RESULTS_LIMIT = int(os.getenv("TWITTER_RESULTS_LIMIT", "40"))

ACTOR_ID = "xquik/x-tweet-scraper"


def _get_run_dataset_id(run) -> str:
    """apify-client บางเวอร์ชันคืน dict บางเวอร์ชันคืน object ที่ใช้ .attribute เลยรองรับทั้งสองแบบ"""
    if isinstance(run, dict):
        dataset_id = run["defaultDatasetId"]
    else:
        dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    if not dataset_id:
        raise RuntimeError(f"ดึง defaultDatasetId จากผลลัพธ์ run ไม่ได้: {run!r}")
    return dataset_id


def _build_search_term_for_handle(handle: str) -> str:
    """สร้าง query แบบ 'from:<handle> (keyword1 OR keyword2)' สำหรับบัญชีเดียว"""
    if not TWITTER_KEYWORDS:
        raise RuntimeError(
            "เปิด FILTER_BY_KEYWORD=true ไว้ แต่ยังไม่ได้ใส่ TWITTER_KEYWORDS ใน .env "
            "กรุณาใส่คีย์เวิร์ด เช่น TWITTER_KEYWORDS=FC27,FC 27,EAFC27,EA FC 27"
        )
    keyword_clause = " OR ".join(
        f'"{kw}"' if " " in kw else kw for kw in TWITTER_KEYWORDS
    )
    return f"from:{handle} ({keyword_clause})"


def fetch_tweets() -> list[dict]:
    if not APIFY_TOKEN or APIFY_TOKEN == "your_apify_token_here":
        raise RuntimeError("ยังไม่ได้ตั้งค่า APIFY_API_TOKEN ใน .env กรุณาสมัคร Apify แล้วใส่ token ก่อน")
    if not TWITTER_HANDLES:
        raise RuntimeError(
            "ยังไม่ได้ใส่ TWITTER_HANDLES ใน .env กรุณาระบุบัญชี X ที่ต้องการติดตาม "
            "เช่น TWITTER_HANDLES=EASPORTSFC,eafootball_news"
        )

    client = ApifyClient(APIFY_TOKEN)
    all_items = []

    for handle in TWITTER_HANDLES:
        if FILTER_BY_KEYWORD:
            search_term = _build_search_term_for_handle(handle)
            run_input = {
                "searchTerms": [search_term],
                "maxItems": RESULTS_LIMIT,
                "queryType": "Latest",
                "outputVariant": "rich",
                "fieldStyle": "camelCase",
            }
            print(f"[scrape_x] ค้นหา @{handle} ด้วย query: {search_term}")
        else:
            # ใช้ startUrls กับ URL โปรไฟล์ตรงๆ = fast user-timeline path ตามเอกสารของ actor
            run_input = {
                "startUrls": [f"https://x.com/{handle}"],
                "maxItems": RESULTS_LIMIT,
                "outputVariant": "rich",
                "fieldStyle": "camelCase",
            }
            print(f"[scrape_x] ดึงทุกทวีตจาก @{handle} ...")

        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input)
            dataset_id = _get_run_dataset_id(run)
            items = list(client.dataset(dataset_id).iterate_items())

            # actor นี้อาจแทรก diagnostic row (สรุปสถานะ run) ปนมาในผลลัพธ์ ให้กรองออกก่อนนับ/ใช้งาน
            before = len(items)
            items = [it for it in items if it.get("resultType") != "diagnostic"]
            if len(items) != before:
                print(f"  [scrape_x] กรอง diagnostic row ออก {before - len(items)} รายการ")

            print(f"  -> ได้ {len(items)} ทวีตจาก @{handle}")
            if len(items) == 0:
                print(f"  [scrape_x] หมายเหตุ: @{handle} ไม่มีผลลัพธ์เลย ถ้าเปิด FILTER_BY_KEYWORD=true อยู่ "
                      f"อาจเป็นเพราะบัญชีนี้ไม่ได้ใช้คำในลิสต์ TWITTER_KEYWORDS ตรงเป๊ะ "
                      f"(ลองปิด filter ชั่วคราวเพื่อดูว่าบัญชีนี้ทวีตอะไรบ้าง)")
            all_items.extend(items)
        except Exception as e:
            print(f"  [scrape_x] ดึงจาก @{handle} ล้มเหลว: {e}")

    print(f"[scrape_x] รวมทั้งหมด {len(all_items)} ทวีต จาก {len(TWITTER_HANDLES)} บัญชี")
    return all_items


def normalize_item(item: dict) -> dict | None:
    """
    แปลงผลลัพธ์ดิบจาก Apify ให้เข้ากับ schema ของเรา
    เขียนแบบ fallback หลายชื่อ field เพราะ xquik/x-tweet-scraper เป็น actor คนละค่ายกับตัวเดิม
    (apidojo) ชื่อ field อาจไม่ตรงกับที่เดาไว้ทั้งหมด — เช็ค log "ตัวอย่าง field ที่มีในผลลัพธ์ดิบ"
    ตอนรันจริงแล้วปรับตรงนี้ถ้าจำเป็น
    """
    tweet_id = item.get("id") or item.get("tweetId") or item.get("id_str") or item.get("url")
    if not tweet_id:
        return None

    text = item.get("text") or item.get("fullText") or item.get("full_text") or ""

    author = item.get("author") or item.get("user") or {}
    handle = (
        (author.get("userName") if isinstance(author, dict) else None)
        or (author.get("screenName") if isinstance(author, dict) else None)
        or item.get("username")
        or item.get("screenName")
        or item.get("authorUsername")
        or "unknown"
    )

    tweet_url = item.get("url") or item.get("twitterUrl") or item.get("tweetUrl") or ""
    posted_at = item.get("createdAt") or item.get("created_at") or item.get("timestamp") or item.get("date")

    likes = (
        item.get("likeCount") or item.get("favoriteCount") or item.get("likes")
        or item.get("like_count") or 0
    )
    replies = item.get("replyCount") or item.get("comments") or item.get("reply_count") or 0
    retweets = item.get("retweetCount") or item.get("retweets") or item.get("retweet_count") or 0
    # engagement รวม ใช้เป็นตัวชี้วัดว่าทวีตนี้ "ไวรัล" แค่ไหน (เก็บไว้ในคอลัมน์ comments เดิมของ db
    # เพื่อไม่ต้อง migrate schema ใหม่ — comments ในที่นี้หมายถึง reply+retweet รวมกัน)
    engagement_comments = replies + retweets

    return {
        "uid": f"x:{tweet_id}",
        "platform": "x",
        "source_name": f"@{handle}",
        "source_url": f"https://x.com/{handle}",
        "post_id": str(tweet_id),
        "posted_at": str(posted_at) if posted_at else None,
        "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "title": "",
        "text": text,
        "post_url": tweet_url,
        "score": likes,
        "comments": engagement_comments,
    }


def main():
    init_db()
    raw_items = fetch_tweets()

    if raw_items:
        print(f"[scrape_x] ตัวอย่าง field ที่มีในผลลัพธ์ดิบ: {list(raw_items[0].keys())}")

    normalized = []
    for item in raw_items:
        n = normalize_item(item)
        if n:
            normalized.append(n)

    # สรุปจำนวนทวีตต่อบัญชี เอาไว้เช็คว่าบัญชีไหนได้ผลลัพธ์เยอะ/น้อยผิดปกติ
    from collections import Counter
    per_handle = Counter(n["source_name"] for n in normalized)
    print("[scrape_x] จำนวนทวีตต่อบัญชี:")
    for handle, count in per_handle.most_common():
        print(f"    {handle}: {count} ทวีต")

    inserted = upsert_posts(normalized)
    print(f"[scrape_x] บันทึกใหม่ {inserted} ทวีต (ที่เหลือเป็นทวีตซ้ำที่เคยดึงแล้ว)")


if __name__ == "__main__":
    main()