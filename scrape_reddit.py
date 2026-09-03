"""
ดึงโพสต์จาก Reddit ผ่าน Apify actor: trudax/reddit-scraper-lite
ค้นหาได้ทั้งแบบคีย์เวิร์ด (REDDIT_SEARCH_TERMS) และแบบระบุ subreddit ตรงๆ (REDDIT_SUBREDDITS)

ต่างจาก X (Twitter) ตรงที่ Reddit ค้นหาข้ามทั้งแพลตฟอร์มด้วยคีย์เวิร์ดได้เลย ไม่ต้องรู้ล่วงหน้าว่า
โพสต์อยู่ใน subreddit ไหน เหมาะกับการจับกระแสที่กระจายอยู่หลาย community

เปิด/ปิดแหล่งข้อมูลนี้ได้ทั้งหมดด้วย ENABLE_REDDIT_SOURCE ใน .env (ค่าเริ่มต้น = true)
ถ้าปิดไว้ หรือยังไม่ได้ตั้งค่า REDDIT_SEARCH_TERMS/REDDIT_SUBREDDITS เลย สคริปต์จะ "ข้ามแบบเงียบๆ"
(ไม่ error) เพื่อให้ run_all.py ทำงานต่อได้ปกติแม้ยังไม่ได้ตั้งค่า Reddit ไว้

หมายเหตุสำคัญ: actor นี้เป็นของ community (ไม่ใช่ Apify ทำเอง) input schema อาจเปลี่ยนได้
ถ้ารันแล้ว error เรื่อง field ไม่ตรง ให้เข้าไปดู "Input" tab ที่หน้า
https://apify.com/trudax/reddit-scraper-lite/input-schema แล้วปรับ dict ใน run_input ด้านล่าง
"""
import os
import datetime as dt
from dotenv import load_dotenv
from apify_client import ApifyClient

from db import init_db, upsert_posts

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
SEARCH_TERMS = [t.strip() for t in os.getenv("REDDIT_SEARCH_TERMS", "").split(",") if t.strip()]
SUBREDDITS = [s.strip() for s in os.getenv("REDDIT_SUBREDDITS", "").split(",") if s.strip()]
RESULTS_LIMIT = int(os.getenv("REDDIT_RESULTS_LIMIT", "40"))
ENABLE_REDDIT_SOURCE = os.getenv("ENABLE_REDDIT_SOURCE", "true").strip().lower() in ("1", "true", "yes")

ACTOR_ID = "trudax/reddit-scraper-lite"


def _get_run_dataset_id(run) -> str:
    """apify-client บางเวอร์ชันคืน dict บางเวอร์ชันคืน object ที่ใช้ .attribute เลยรองรับทั้งสองแบบ"""
    if isinstance(run, dict):
        dataset_id = run["defaultDatasetId"]
    else:
        dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    if not dataset_id:
        raise RuntimeError(f"ดึง defaultDatasetId จากผลลัพธ์ run ไม่ได้: {run!r}")
    return dataset_id


def fetch_reddit_posts() -> list[dict]:
    if not APIFY_TOKEN or APIFY_TOKEN == "your_apify_token_here":
        raise RuntimeError("ยังไม่ได้ตั้งค่า APIFY_API_TOKEN ใน .env กรุณาสมัคร Apify แล้วใส่ token ก่อน")

    client = ApifyClient(APIFY_TOKEN)
    all_items = []

    # แยกเรียก actor ทีละคีย์เวิร์ด/ทีละ subreddit (ไม่รวมหลายอย่างในการรันเดียว)
    # เพื่อให้เห็นชัดเจนว่าคำค้น/ชุมชนไหนได้ผลลัพธ์เท่าไหร่ และตัวไหนมีปัญหาจะไม่ทำให้ตัวอื่นพังตาม

    # รอบที่ 1: ค้นหาด้วยคีย์เวิร์ด (จับกระแสจากทั่วทั้ง Reddit ไม่จำกัด subreddit)
    for term in SEARCH_TERMS:
        run_input = {
            "searches": [term],
            "type": "posts",
            "sort": "new",
            "maxItems": RESULTS_LIMIT,
        }
        print(f"[scrape_reddit] ค้นหาคีย์เวิร์ด: '{term}' ...")
        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input)
            dataset_id = _get_run_dataset_id(run)
            items = list(client.dataset(dataset_id).iterate_items())
            print(f"  -> ได้ {len(items)} โพสต์")
            all_items.extend(items)
        except Exception as e:
            print(f"  [scrape_reddit] ค้นหาคีย์เวิร์ด '{term}' ล้มเหลว: {e}")

    # รอบที่ 2: ดึงจาก subreddit ที่ระบุตรงๆ (จับโพสต์ล่าสุดจากชุมชนที่รู้จักอยู่แล้ว)
    for sub in SUBREDDITS:
        run_input = {
            "startUrls": [{"url": f"https://www.reddit.com/r/{sub}/new/"}],
            "type": "posts",
            "maxItems": RESULTS_LIMIT,
        }
        print(f"[scrape_reddit] ดึงจาก subreddit: r/{sub} ...")
        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input)
            dataset_id = _get_run_dataset_id(run)
            items = list(client.dataset(dataset_id).iterate_items())
            print(f"  -> ได้ {len(items)} โพสต์")
            all_items.extend(items)
        except Exception as e:
            print(f"  [scrape_reddit] ดึงจาก r/{sub} ล้มเหลว: {e}")

    return all_items


def normalize_item(item: dict) -> dict | None:
    """
    แปลงผลลัพธ์ดิบจาก Apify ให้เข้ากับ schema ของเรา
    โครงสร้าง field ของ actor นี้อาจเปลี่ยนได้ตามเวอร์ชัน จึงลอง key หลายแบบ (fallback)
    """
    post_id = item.get("id") or item.get("postId") or item.get("url")
    if not post_id:
        return None

    title = item.get("title") or ""
    text = item.get("body") or item.get("selftext") or item.get("text") or ""
    # รวม title กับ text เข้าด้วยกัน เพราะบางโพสต์ข้อมูลสำคัญอยู่ใน title (เช่นหัวข้อคำถาม/ข่าว)
    combined_text = f"{title}\n{text}".strip()

    source_name = item.get("communityName") or item.get("subreddit") or item.get("community") or "unknown"
    source_url = f"https://www.reddit.com/r/{source_name}" if source_name != "unknown" else ""
    post_url = item.get("url") or item.get("permalink") or ""
    if post_url and not post_url.startswith("http"):
        post_url = f"https://www.reddit.com{post_url}"

    posted_at = item.get("createdAt") or item.get("created") or item.get("date")
    score = item.get("upVotes") or item.get("score") or item.get("upvotes") or 0
    comments = item.get("numberOfComments") or item.get("numComments") or item.get("commentsCount") or 0

    return {
        "uid": f"reddit:{post_id}",
        "platform": "reddit",
        "source_name": f"r/{source_name}",
        "source_url": source_url,
        "post_id": str(post_id),
        "posted_at": str(posted_at) if posted_at else None,
        "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "title": title,
        "text": combined_text,
        "post_url": post_url,
        "score": score,
        "comments": comments,
    }


def main():
    init_db()

    if not ENABLE_REDDIT_SOURCE:
        print("[scrape_reddit] ปิดแหล่งข้อมูล Reddit ไว้ (ENABLE_REDDIT_SOURCE=false) ข้ามขั้นตอนนี้")
        return
    if not SEARCH_TERMS and not SUBREDDITS:
        print("[scrape_reddit] ยังไม่ได้ตั้งค่า REDDIT_SEARCH_TERMS หรือ REDDIT_SUBREDDITS ใน .env "
              "เลยแม้แต่อย่างเดียว ข้ามขั้นตอนนี้ (ไปตั้งค่าที่หน้า Settings หรือแก้ .env โดยตรง)")
        return

    raw_items = fetch_reddit_posts()

    if raw_items:
        print(f"[scrape_reddit] ตัวอย่าง field ที่มีในผลลัพธ์ดิบ: {list(raw_items[0].keys())}")

    normalized = []
    seen_ids = set()
    for item in raw_items:
        n = normalize_item(item)
        if n and n["uid"] not in seen_ids:  # กันโพสต์ซ้ำที่มาจากหลายคีย์เวิร์ด/subreddit
            normalized.append(n)
            seen_ids.add(n["uid"])

    inserted = upsert_posts(normalized)
    print(f"[scrape_reddit] ดึงมาทั้งหมด {len(normalized)} โพสต์ (หลังตัดซ้ำ), "
          f"บันทึกใหม่ {inserted} โพสต์")


if __name__ == "__main__":
    main()
