"""
ดึงโพสต์จากเพจ Facebook (เช่น เพจร้านขายเหรียญเกม EA FC ของเราเองและคู่แข่ง) ผ่าน Apify actor:
apify/facebook-posts-scraper

ต่างจาก X/Reddit ตรงที่นี่คือการติดตามเพจร้านค้าที่รู้จักตายตัว (ไม่ใช่ค้นหากว้างๆ) เหมาะกับ
"เทียบราคา/โปรโมชั่น" ระหว่างเพจของเรากับคู่แข่ง มากกว่าจะใช้ "ตามกระแส community" แบบ X/Reddit

เปิด/ปิดแหล่งข้อมูลนี้ได้ทั้งหมดด้วย ENABLE_FACEBOOK_SOURCE ใน .env (ค่าเริ่มต้น = true)
ถ้าปิดไว้ หรือยังไม่ได้ตั้งค่า FB_PAGE_URLS สคริปต์จะ "ข้ามแบบเงียบๆ" (ไม่ error) เพื่อให้
run_all.py ทำงานต่อได้ปกติแม้ยังไม่ได้ตั้งค่า Facebook ไว้

หมายเหตุสำคัญ: Apify actor บางตัวมีการปรับ input schema เป็นระยะ
ถ้ารันแล้ว error เรื่อง field ไม่ตรง ให้เข้าไปดู "Input" tab ของ actor
ที่หน้า https://console.apify.com > Actors > Facebook Posts Scraper
แล้วปรับ dict ใน run_input ด้านล่างให้ตรงกับ schema ปัจจุบัน
"""

import sys
if sys.platform == "win32":
    # Windows console บางเครื่องใช้ encoding cp1252 เป็นค่าเริ่มต้น ซึ่งพิมพ์ข้อความไทยไม่ได้
    # (จะเจอ UnicodeEncodeError) บังคับให้ stdout/stderr เป็น UTF-8 เสมอกันปัญหานี้
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import os
import json
import datetime as dt
from dotenv import load_dotenv
from apify_client import ApifyClient

from db import init_db, upsert_posts

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
PAGE_URLS = [u.strip() for u in os.getenv("FB_PAGE_URLS", "").split(",") if u.strip()]
POSTS_PER_PAGE = int(os.getenv("FB_POSTS_PER_PAGE", "30"))
ENABLE_FACEBOOK_SOURCE = os.getenv("ENABLE_FACEBOOK_SOURCE", "true").strip().lower() in ("1", "true", "yes")

ACTOR_ID = "apify/facebook-posts-scraper"


def _get_run_dataset_id(run) -> str:
    """apify-client บางเวอร์ชันคืน dict บางเวอร์ชันคืน object ที่ใช้ .attribute เลยรองรับทั้งสองแบบ"""
    if isinstance(run, dict):
        dataset_id = run["defaultDatasetId"]
    else:
        dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)
    if not dataset_id:
        raise RuntimeError(f"ดึง defaultDatasetId จากผลลัพธ์ run ไม่ได้: {run!r}")
    return dataset_id


def fetch_posts_for_pages(page_urls: list[str], results_limit: int) -> list[dict]:
    if not APIFY_TOKEN or APIFY_TOKEN == "your_apify_token_here":
        raise RuntimeError("ยังไม่ได้ตั้งค่า APIFY_API_TOKEN ใน .env กรุณาสมัคร Apify แล้วใส่ token ก่อน")
    if not page_urls:
        raise RuntimeError("ยังไม่ได้ใส่ FB_PAGE_URLS ใน .env")

    client = ApifyClient(APIFY_TOKEN)

    run_input = {
        "startUrls": [{"url": u} for u in page_urls],
        "resultsLimit": results_limit,
    }

    print(f"[scrape_facebook] กำลังเรียก Apify actor '{ACTOR_ID}' สำหรับ {len(page_urls)} เพจ ...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    dataset_id = _get_run_dataset_id(run)
    items = list(client.dataset(dataset_id).iterate_items())
    print(f"[scrape_facebook] ได้ผลลัพธ์ดิบทั้งหมด {len(items)} รายการ")
    return items


def normalize_item(item: dict) -> dict | None:
    """
    แปลงผลลัพธ์ดิบจาก Apify ให้เข้ากับ schema ของตาราง community_posts ร่วม
    โครงสร้าง field ของ actor นี้อาจเปลี่ยนได้ตามเวอร์ชัน จึงลอง key หลายแบบ (fallback)
    """
    post_id = item.get("postId") or item.get("id") or item.get("url")
    if not post_id:
        return None

    text = item.get("text") or item.get("message") or ""
    page_name = item.get("pageName") or item.get("user", {}).get("name") or "unknown"
    page_url = item.get("pageUrl") or item.get("facebookUrl") or ""
    post_url = item.get("url") or item.get("postUrl") or ""

    posted_at = item.get("time") or item.get("timestamp") or item.get("date")

    likes = item.get("likes") or item.get("likesCount") or 0
    comments = item.get("comments") or item.get("commentsCount") or 0
    shares = item.get("shares") or item.get("sharesCount") or 0
    # ยอดวิว มักมีเฉพาะโพสต์วิดีโอ ชื่อ field แตกต่างกันไปตามเวอร์ชัน actor ลองหลายแบบ
    views = (item.get("videoViewCount") or item.get("viewsCount")
             or item.get("views") or item.get("video_view_count") or None)

    # ดึง URL รูปภาพจากโพสต์ (โครงสร้างมักเป็น list ของ dict หรือ list ของ string แล้วแต่ actor)
    image_urls = []
    raw_media = item.get("media") or item.get("photos") or item.get("attachments") or []
    if isinstance(raw_media, list):
        for m in raw_media:
            if isinstance(m, str):
                image_urls.append(m)
            elif isinstance(m, dict):
                url = m.get("url")
                if not url and isinstance(m.get("photo_image"), dict):
                    url = m["photo_image"].get("uri")
                if not url:
                    url = m.get("uri") or m.get("thumbnail")
                if url:
                    image_urls.append(url)
    single_thumb = item.get("thumbnailUrl") or item.get("thumbnail")
    if single_thumb and single_thumb not in image_urls:
        image_urls.append(single_thumb)

    return {
        "uid": f"facebook_page:{post_id}",
        "platform": "facebook_page",
        "source_name": page_name,
        "source_url": page_url,
        "post_id": str(post_id),
        "posted_at": str(posted_at) if posted_at else None,
        "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "title": "",
        "text": text,
        "post_url": post_url,
        # รวม comments+shares เป็นค่าเดียวเก็บในคอลัมน์ comments (เหมือน pattern ที่ใช้กับ X:
        # replies+retweets รวมกัน) เพื่อให้ schema ใช้ร่วมกันได้ทุกแพลตฟอร์ม
        # แยก likes/comments/shares/views ออกจากกันชัดเจน เพื่อให้ดู engagement แบบละเอียดได้
        # (เดิมเคยรวม comments+shares ไว้ด้วยกัน แต่แยกออกมาแล้วเพื่อรองรับหน้า Facebook Prices)
        "score": likes,
        "comments": comments,
        "shares": shares,
        "image_urls": json.dumps(image_urls, ensure_ascii=False),
        "views": views,
    }


def main():
    init_db()

    if not ENABLE_FACEBOOK_SOURCE:
        print("[scrape_facebook] ปิดแหล่งข้อมูล Facebook ไว้ (ENABLE_FACEBOOK_SOURCE=false) ข้ามขั้นตอนนี้")
        return
    if not PAGE_URLS:
        print("[scrape_facebook] ยังไม่ได้ตั้งค่า FB_PAGE_URLS ใน .env ข้ามขั้นตอนนี้ "
              "(ไปตั้งค่าที่หน้า Settings หรือแก้ .env โดยตรง)")
        return

    raw_items = fetch_posts_for_pages(PAGE_URLS, POSTS_PER_PAGE)

    if raw_items:
        print(f"[scrape_facebook] ตัวอย่าง field ที่มีในผลลัพธ์ดิบ: {list(raw_items[0].keys())}")

    normalized = []
    for item in raw_items:
        n = normalize_item(item)
        if n:
            normalized.append(n)

    inserted = upsert_posts(normalized)
    with_image = sum(1 for n in normalized if json.loads(n["image_urls"] or "[]"))
    print(f"[scrape_facebook] บันทึกใหม่ {inserted} โพสต์ (ที่เหลือเป็นโพสต์ซ้ำที่เคยดึงแล้ว), "
          f"มีรูปภาพแนบ {with_image}/{len(normalized)} โพสต์")


if __name__ == "__main__":
    main()
