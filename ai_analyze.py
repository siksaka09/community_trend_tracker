"""
ใช้ Claude API วิเคราะห์โพสต์จาก community ทั้ง 3 แหล่ง (X/Twitter, Reddit, Facebook Pages)

=== ส่วนที่ 1: relevance / sentiment / topic (ทุกแพลตฟอร์ม) ===
โดยดึงข้อมูล 4 อย่างต่อโพสต์:
  1. is_relevant  — โพสต์นี้เกี่ยวกับ EA FC 27 จริงไหม (กรองโพสต์อื่นที่หลุดเข้ามา)
  2. sentiment    — โทนของโพสต์ (positive / negative / neutral / mixed)
  3. topics       — หัวข้อที่พูดถึง เช่น gameplay, pricing, release_date, bug, hype, beta, microtransactions
  4. summary      — สรุปสั้นๆ ว่าโพสต์นี้พูดถึงอะไร

=== ส่วนที่ 2: ราคา/โปรโมชั่น (facebook_page เท่านั้น) ===
สำหรับโพสต์จากเพจร้านค้า (platform = facebook_page) จะมีอีกขั้นตอนแยกต่างหาก อ่านข้อความ+รูปภาพ
เพื่อดึงราคา/โปรโมชั่นออกมา เหมาะกับกรณีเทียบราคาขายเหรียญเกมระหว่างสองเพจ ถ้าข้อความไม่มีราคา
แต่โพสต์มีรูป จะส่งรูปให้ Claude อ่านเพิ่ม (ทำเฉพาะเท่าที่จำเป็น ประหยัด request) โพสต์จาก x/reddit
จะไม่ผ่านขั้นตอนนี้เลย (ไม่มีคอลัมน์ราคาให้ใช้)

=== เรื่องโมเดลและค่าใช้จ่าย ===
ใช้ Claude Haiku 4.5 (claude-haiku-4-5-20251001) เป็นค่าเริ่มต้นสำหรับงาน relevance/sentiment/topic
เพราะงานจำแนกประเภท/สรุปสั้นๆ แบบนี้ไม่จำเป็นต้องใช้โมเดลที่แพงกว่า (ราคาปัจจุบัน ณ ปี 2026 อยู่ที่
$1/$5 ต่อล้าน token เทียบกับ Sonnet 5 ที่ $2/$10) รวมกับการวิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request
ทำให้ต้นทุนโดยรวมต่ำมาก ส่วนการอ่านรูปภาพ (vision) ใช้โมเดลเดียวกัน เพราะ Haiku 4.5 อ่านรูปได้
ถ้าอยากได้คุณภาพสูงขึ้น ปรับ MODEL_NAME เป็น "claude-sonnet-5" ได้ที่ตัวแปรด้านล่าง

วิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request (ลด request ลง 5 เท่า ลดโอกาสโดน rate limit)
มี fallback ไปทีละโพสต์ถ้า batch มีปัญหา และ retry อัตโนมัติเมื่อเจอ rate limit / server error
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import os
import io
import json
import time
import requests
from dotenv import load_dotenv
import anthropic


from db import (
    init_db, get_unanalyzed_posts, save_ai_analysis,
    get_unpriced_facebook_posts, save_price_analysis,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL_NAME = "claude-haiku-4-5-20251001"  # ปรับเป็น "claude-sonnet-5" ได้ถ้าอยากได้คุณภาพสูงขึ้น (แพงขึ้น ~4 เท่า)
BATCH_SIZE = 5
MAX_TOKENS = 4000
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # ไม่โหลดรูปที่ใหญ่เกิน 8MB กันเปลืองเวลา/แบนด์วิดท์

EMPTY_RESULT = {
    "is_relevant": False, "sentiment": "neutral", "topics": [], "summary": None,
}
EMPTY_PRICE_RESULT = {
    "has_price": False, "prices": [], "has_promotion": False, "promotion_summary": None,
}

TOPIC_LIST = (
    "gameplay (เกมเพลย์/ระบบเกม), pricing (ราคา/ค่าใช้จ่ายในเกม), release_date (วันวางจำหน่าย/เปิดตัว), "
    "beta (ช่วงทดลองเล่น), bug (บั๊ก/ปัญหาทางเทคนิค), hype (ความตื่นเต้น/รอคอย), "
    "microtransactions (ไมโครทรานแซคชั่น/ซื้อของในเกม), graphics (กราฟิก/ภาพ), "
    "career_mode (โหมดอาชีพ), ultimate_team (โหมด Ultimate Team), rumor (ข่าวลือ/เดา), "
    "comparison (เทียบกับเกมเก่า/เกมอื่น), complaint (ข้อร้องเรียนทั่วไป), other (อื่นๆ)"
)

SYSTEM_PROMPT_SINGLE = f"""คุณเป็นนักวิเคราะห์กระแส/เทรนด์ community เกี่ยวกับวิดีโอเกม EA FC 27
(เกมฟุตบอลจาก EA Sports) จากโพสต์ community (X/Twitter, Reddit, หรือ Facebook)

ให้วิเคราะห์โพสต์แล้วตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON ห้ามมี markdown code fence

โครงสร้างที่ต้องการ:
{{
  "is_relevant": true/false,
  "sentiment": "positive" | "negative" | "neutral" | "mixed",
  "topics": ["gameplay", "pricing"],
  "summary": "สรุปสั้นๆ 1 ประโยคว่าโพสต์นี้พูดถึงอะไร (ภาษาไทย)"
}}

กติกา:
- is_relevant = true ถ้าโพสต์นี้พูดถึงเกม EA FC 27 หรือ EA Sports FC ภาคใหม่จริงๆ
  ถ้าเป็นโพสต์อื่นที่ไม่เกี่ยว (เช่นเกมฟุตบอลอื่น, หัวข้ออื่นที่บังเอิญมีคำคล้ายกัน) ให้ is_relevant = false
- sentiment ให้ประเมินจากน้ำเสียงโดยรวมของโพสต์ ไม่ใช่แค่หัวข้อ
- topics เลือกจากรายการนี้เท่านั้น (เลือกได้หลายอันถ้าเกี่ยวข้องจริง): {TOPIC_LIST}
- ถ้า is_relevant = false ให้ topics = [] และ sentiment = "neutral"
"""

SYSTEM_PROMPT_BATCH = f"""คุณเป็นนักวิเคราะห์กระแส/เทรนด์ community เกี่ยวกับวิดีโอเกม EA FC 27
(เกมฟุตบอลจาก EA Sports) จากโพสต์ community (X/Twitter, Reddit, หรือ Facebook)
ผู้ใช้จะส่งโพสต์มาหลายรายการพร้อมกัน แต่ละรายการมี "uid" กำกับไว้ชัดเจน

กติกาสำคัญที่สุด: ห้ามเอาข้อมูลข้ามโพสต์กันเด็ดขาด แต่ละโพสต์ต้องวิเคราะห์แยกจากกันโดยอิสระ

ให้ตอบกลับเป็น JSON array เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON ห้ามมี markdown code fence
โดยแต่ละ element มีโครงสร้าง:
{{
  "uid": "<คัดลอก uid มาจากโพสต์นั้นเป๊ะๆ>",
  "is_relevant": true/false,
  "sentiment": "positive" | "negative" | "neutral" | "mixed",
  "topics": ["gameplay", "pricing"],
  "summary": "สรุปสั้นๆ 1 ประโยคว่าโพสต์นี้พูดถึงอะไร (ภาษาไทย)"
}}

กติกาอื่นๆ:
- is_relevant = true ถ้าโพสต์นี้พูดถึงเกม EA FC 27 หรือ EA Sports FC ภาคใหม่จริงๆ
  ถ้าเป็นโพสต์อื่นที่ไม่เกี่ยว ให้ is_relevant = false
- sentiment ให้ประเมินจากน้ำเสียงโดยรวมของโพสต์ ไม่ใช่แค่หัวข้อ
- topics เลือกจากรายการนี้เท่านั้น (เลือกได้หลายอันถ้าเกี่ยวข้องจริง): {TOPIC_LIST}
- ถ้า is_relevant = false ให้ topics = [] และ sentiment = "neutral"
- ต้องมี element ครบทุก uid ที่ส่งมา ห้ามขาดหรือเกิน
- ตอบเป็น JSON array เดียวเท่านั้น (ขึ้นต้นด้วย [ และจบด้วย ]) ไม่มีข้อความอื่นใดๆ ทั้งก่อนและหลัง
"""

# ============================================================
# System prompts สำหรับส่วนที่ 2: วิเคราะห์ราคา/โปรโมชั่น (facebook_page เท่านั้น)
# ============================================================

SYSTEM_PROMPT_PRICE_SINGLE = """คุณเป็นผู้ช่วยวิเคราะห์โพสต์ขายเหรียญเกม EA FC (game coins) จาก Facebook
ให้ดึงข้อมูลราคาและโปรโมชั่นออกมาเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON

โครงสร้างที่ต้องการ:
{
  "has_price": true/false,
  "prices": [
    {"quantity": "1M", "price": 25, "currency": "THB", "unit_note": "ต่อ 1 ล้านเหรียญ"}
  ],
  "has_promotion": true/false,
  "promotion_summary": "สรุปสั้นๆ ว่าโปรโมชั่นคืออะไร เช่น ลดราคา 10%, ซื้อ 5 แถม 1 หรือ null ถ้าไม่มี"
}

กติกา:
- ถ้าไม่มีราคาในโพสต์เลย ให้ has_price = false และ prices = []
- แปลงหน่วยเงินให้เป็นตัวเลข ไม่ต้องมีจุลภาคหรือสัญลักษณ์สกุลเงินปนอยู่ในตัวเลข
- ถ้าราคาไม่ชัดเจนหรือกำกวม ให้ข้ามรายการนั้นไป อย่าเดา
- ตอบเป็น JSON object เดียวเท่านั้น ไม่มี markdown code fence ไม่มีคำอธิบายเพิ่ม
"""

SYSTEM_PROMPT_PRICE_BATCH = """คุณเป็นผู้ช่วยวิเคราะห์โพสต์ขายเหรียญเกม EA FC (game coins) จาก Facebook
ผู้ใช้จะส่งโพสต์มาหลายรายการพร้อมกัน แต่ละรายการมี "uid" กำกับไว้ชัดเจน

กติกาสำคัญที่สุด: ห้ามเอาข้อมูลข้ามโพสต์กันเด็ดขาด แต่ละโพสต์ต้องวิเคราะห์แยกจากกันโดยอิสระ
ราคาหรือโปรโมชั่นที่พบในโพสต์หนึ่ง ห้ามนำไปใส่ในผลลัพธ์ของอีกโพสต์หนึ่งเป็นอันขาด

ให้ตอบกลับเป็น JSON array เท่านั้น โดยแต่ละ element มีโครงสร้าง:
{
  "uid": "<คัดลอก uid มาจากโพสต์นั้นเป๊ะๆ>",
  "has_price": true/false,
  "prices": [
    {"quantity": "1M", "price": 25, "currency": "THB", "unit_note": "ต่อ 1 ล้านเหรียญ"}
  ],
  "has_promotion": true/false,
  "promotion_summary": "สรุปสั้นๆ หรือ null ถ้าไม่มี"
}

กติกาอื่นๆ:
- ต้องมี element ครบทุก uid ที่ส่งมา ห้ามขาดหรือเกิน
- ถ้าไม่มีราคาในโพสต์นั้นเลย ให้ has_price = false และ prices = []
- แปลงหน่วยเงินให้เป็นตัวเลข ไม่ต้องมีจุลภาคหรือสัญลักษณ์สกุลเงินปนอยู่ในตัวเลข
- ถ้าราคาไม่ชัดเจนหรือกำกวม ให้ข้ามรายการนั้นไป อย่าเดา
- ตอบเป็น JSON array เดียวเท่านั้น (ขึ้นต้นด้วย [ และจบด้วย ]) ไม่มีข้อความอื่นใดๆ ทั้งก่อนและหลัง
"""

SYSTEM_PROMPT_PRICE_IMAGE = """คุณเป็นผู้ช่วยอ่านรูปภาพโปรโมชั่น/ป้ายราคาของร้านขายเหรียญเกม EA FC
ดูรูปภาพที่แนบมา แล้วดึงราคาและโปรโมชั่นที่ปรากฏอยู่ในรูป (ถ้ามี) ออกมาเป็น JSON เท่านั้น

โครงสร้างที่ต้องการ:
{
  "has_price": true/false,
  "prices": [
    {"quantity": "1M", "price": 25, "currency": "THB", "unit_note": "ต่อ 1 ล้านเหรียญ"}
  ],
  "has_promotion": true/false,
  "promotion_summary": "สรุปสั้นๆ หรือ null ถ้าไม่มี"
}

กติกา:
- ถ้าในรูปไม่มีราคาหรือตัวเลขที่อ่านได้ชัดเจน ให้ has_price = false และ prices = []
- ถ้าตัวเลขในรูปเบลอ/อ่านไม่ออกชัดเจน อย่าเดา ให้ข้ามรายการนั้นไป
- ตอบเป็น JSON object เดียวเท่านั้น ไม่มี markdown code fence ไม่มีคำอธิบายเพิ่ม
"""


def _extract_json(raw: str) -> str:
    """เผื่อ Claude ใส่ markdown fence หรือคำนำมาด้วยแม้จะสั่งห้ามแล้ว ตัดออกให้เหลือแต่ JSON"""
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return raw


def _call_claude(system_prompt: str, user_content: str, max_retries: int = 5) -> str | None:
    """เรียก Claude พร้อม retry เมื่อเจอ rate limit (429) หรือ server error ชั่วคราว (500/503/529)"""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            return _extract_json(response.content[0].text)

        except anthropic.RateLimitError as e:
            wait = min(90, 15 * attempt)
            print(f"    [claude] โดน rate limit (attempt {attempt}/{max_retries}) รอ {wait} วิ แล้วลองใหม่... ({e})")
            time.sleep(wait)
        except (anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            wait = min(60, 5 * attempt)
            print(f"    [claude] เซิร์ฟเวอร์มีปัญหาชั่วคราว (attempt {attempt}/{max_retries}) "
                  f"รอ {wait} วิ แล้วลองใหม่... ({e})")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            print(f"    [claude] เจอ error ที่ retry ไม่ได้ ({e}) ข้ามรายการนี้ไป")
            return None
    return None


def analyze_post_text(text: str) -> dict | None:
    """วิเคราะห์ทีละโพสต์ (ใช้เป็น fallback เวลา batch มีปัญหา)"""
    if not text or not text.strip():
        return dict(EMPTY_RESULT)

    raw = _call_claude(SYSTEM_PROMPT_SINGLE, text)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"    [ai_analyze] parse JSON เดี่ยวไม่ได้: {raw[:100]}")
        return dict(EMPTY_RESULT)


def analyze_batch(posts: list[dict]) -> dict[str, dict] | None:
    payload = [{"uid": p["uid"], "text": (p["text"] or "")[:2000]} for p in posts]
    contents = json.dumps(payload, ensure_ascii=False)

    raw = _call_claude(SYSTEM_PROMPT_BATCH, contents)
    if raw is None:
        return None

    try:
        results = json.loads(raw)
        if not isinstance(results, list):
            raise ValueError("ผลลัพธ์ไม่ใช่ array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    [ai_analyze] parse JSON แบบ batch ไม่ได้ ({e}) จะ fallback ไปทีละโพสต์แทน")
        return None

    result_map = {item["uid"]: item for item in results if item.get("uid")}

    sent_ids = {p["uid"] for p in posts}
    if set(result_map.keys()) != sent_ids:
        missing = sent_ids - set(result_map.keys())
        print(f"    [ai_analyze] batch คืนผลลัพธ์ไม่ครบ (ขาด {len(missing)} รายการ) จะ fallback ไปทีละโพสต์แทน")
        return None

    return result_map


def process_in_batches(posts: list[dict]):
    total_batches = (len(posts) + BATCH_SIZE - 1) // BATCH_SIZE
    done_count = 0

    for b in range(total_batches):
        batch = posts[b * BATCH_SIZE: (b + 1) * BATCH_SIZE]
        print(f"[ai_analyze] แบท {b + 1}/{total_batches} ({len(batch)} โพสต์)")

        result_map = analyze_batch(batch)

        if result_map is not None:
            print(f"  -> วิเคราะห์สำเร็จทั้งแบท ({len(batch)} โพสต์)")
            for post in batch:
                result = result_map.get(post["uid"], EMPTY_RESULT)
                _save(post, result)
                done_count += 1
        else:
            print(f"  -> fallback: วิเคราะห์ทีละโพสต์แทนสำหรับแบทนี้")
            for post in batch:
                result = analyze_post_text(post["text"])
                if result is None:
                    print(f"    [{post['uid']}] ยังไม่สำเร็จ ข้ามไปก่อน จะลองใหม่รอบหน้า")
                    continue
                _save(post, result)
                done_count += 1
                time.sleep(1)  # Claude API มี rate limit สูงกว่า Gemini free tier มาก แต่เว้นนิดหน่อยกันชน

        time.sleep(0.5)

    print(f"[ai_analyze] วิเคราะห์สำเร็จทั้งหมด {done_count}/{len(posts)} โพสต์")


def _save(post: dict, result: dict):
    save_ai_analysis(
        uid=post["uid"],
        is_relevant=result.get("is_relevant", False),
        sentiment=result.get("sentiment", "neutral"),
        topics=json.dumps(result.get("topics", []), ensure_ascii=False),
        summary=result.get("summary"),
    )


# ============================================================
# ส่วนที่ 2: วิเคราะห์ราคา/โปรโมชั่น (facebook_page เท่านั้น)
# ============================================================

def analyze_price_text(text: str) -> dict | None:
    """วิเคราะห์ราคาทีละโพสต์จากข้อความ (ใช้เป็น fallback เวลา batch มีปัญหา)"""
    if not text or not text.strip():
        return dict(EMPTY_PRICE_RESULT)

    raw = _call_claude(SYSTEM_PROMPT_PRICE_SINGLE, text)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"    [ai_analyze] parse JSON ราคาเดี่ยวไม่ได้: {raw[:100]}")
        return dict(EMPTY_PRICE_RESULT)


def analyze_price_batch(posts: list[dict]) -> dict[str, dict] | None:
    payload = [{"uid": p["uid"], "text": (p["text"] or "")[:2000]} for p in posts]
    contents = json.dumps(payload, ensure_ascii=False)

    raw = _call_claude(SYSTEM_PROMPT_PRICE_BATCH, contents)
    if raw is None:
        return None
    try:
        results = json.loads(raw)
        if not isinstance(results, list):
            raise ValueError("ผลลัพธ์ไม่ใช่ array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    [ai_analyze] parse JSON ราคาแบบ batch ไม่ได้ ({e}) จะ fallback ไปทีละโพสต์แทน")
        return None

    result_map = {item["uid"]: item for item in results if item.get("uid")}
    sent_ids = {p["uid"] for p in posts}
    if set(result_map.keys()) != sent_ids:
        missing = sent_ids - set(result_map.keys())
        print(f"    [ai_analyze] batch ราคาคืนผลลัพธ์ไม่ครบ (ขาด {len(missing)} รายการ) จะ fallback ไปทีละโพสต์แทน")
        return None
    return result_map


def _download_image(url: str) -> tuple[bytes, str] | None:
    """โหลดรูปภาพจาก URL คืน (bytes, mime_type) หรือ None ถ้าโหลดไม่สำเร็จ"""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        if not content_type.startswith("image/"):
            content_type = "image/jpeg"
        if len(resp.content) > MAX_IMAGE_BYTES:
            print(f"    [ai_analyze] รูปใหญ่เกิน {MAX_IMAGE_BYTES // (1024*1024)}MB ข้ามไป: {url}")
            return None
        return resp.content, content_type
    except requests.RequestException as e:
        print(f"    [ai_analyze] โหลดรูปไม่สำเร็จ ({url}): {e}")
        return None


def _looks_like_image(data: bytes) -> bool:
    """เช็ค magic bytes คร่าวๆ ว่าเป็นไฟล์รูปภาพจริง กัน HTML/error page หลุดเข้ามา
    (Facebook CDN บางลิงก์หมดอายุหรือต้อง login แล้วจะได้ HTML แทนรูปจริง)"""
    if len(data) < 12:
        return False
    if data[:3] == b"\xff\xd8\xff":  # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WEBP
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):  # GIF
        return True
    return False


def analyze_price_image(image_url: str) -> dict | None:
    """ส่งรูปภาพเดี่ยวให้ Claude อ่านราคา/โปรโมชั่นจากภาพ"""
    downloaded = _download_image(image_url)
    if downloaded is None:
        return None
    image_bytes, mime_type = downloaded

    if not _looks_like_image(image_bytes):
        print(f"    [ai_analyze] ไฟล์ที่โหลดมาไม่ใช่รูปภาพจริง (อาจเป็นหน้า error/login ของ Facebook) "
              f"ข้ามไป: {image_url}")
        return None

    import base64
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            },
        },
        {"type": "text", "text": "อ่านราคาและโปรโมชั่นจากรูปภาพนี้"},
    ]

    try:
        raw = _call_claude(SYSTEM_PROMPT_PRICE_IMAGE, content)
    except anthropic.BadRequestError as e:
        # Claude อาจปฏิเสธรูปที่เสียหาย/ฟอร์แมตแปลกๆ ไม่ใช่บั๊ก แค่รูปนี้อ่านไม่ได้
        print(f"    [ai_analyze] Claude อ่านรูปภาพนี้ไม่ได้ (จะข้ามไป): {e}")
        return None

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"    [ai_analyze] parse JSON จากรูปไม่ได้: {raw[:100]}")
        return None


def _maybe_check_price_image(post: dict, result: dict) -> dict:
    """ถ้าข้อความไม่มีราคาแต่โพสต์มีรูป ลองอ่านราคาจากรูปเพิ่ม (ทำเฉพาะเท่าที่จำเป็น)"""
    if result.get("has_price"):
        result["_price_source"] = "text"
        return result

    try:
        image_urls = json.loads(post.get("image_urls") or "[]")
    except json.JSONDecodeError:
        image_urls = []

    if not image_urls:
        result["_price_source"] = "text"
        return result

    print(f"    [{post['uid']}] ข้อความไม่มีราคา แต่มีรูป {len(image_urls)} รูป ลองอ่านราคาจากรูป...")
    for url in image_urls[:2]:  # ลองสูงสุด 2 รูปแรก กันเปลือง request ถ้ามีรูปเยอะ
        img_result = analyze_price_image(url)
        if img_result and img_result.get("has_price"):
            print(f"    [{post['uid']}] เจอราคาจากรูป!")
            img_result["_price_source"] = "image"
            return img_result
        time.sleep(1)

    result["_price_source"] = "text"
    return result


def _save_price(post: dict, result: dict):
    save_price_analysis(
        uid=post["uid"],
        has_price=result.get("has_price", False),
        price_info=json.dumps(result.get("prices", []), ensure_ascii=False),
        promo_info=json.dumps({
            "has_promotion": result.get("has_promotion", False),
            "summary": result.get("promotion_summary"),
        }, ensure_ascii=False),
        price_source=result.get("_price_source", "text"),
    )


def process_price_in_batches(posts: list[dict]):
    total_batches = (len(posts) + BATCH_SIZE - 1) // BATCH_SIZE
    done_count = 0
    image_checked_count = 0

    for b in range(total_batches):
        batch = posts[b * BATCH_SIZE: (b + 1) * BATCH_SIZE]
        print(f"[ai_analyze:price] แบท {b + 1}/{total_batches} ({len(batch)} โพสต์)")

        result_map = analyze_price_batch(batch)

        if result_map is not None:
            print(f"  -> วิเคราะห์ราคาข้อความสำเร็จทั้งแบท ({len(batch)} โพสต์)")
            for post in batch:
                result = result_map.get(post["uid"], EMPTY_PRICE_RESULT)
                result = _maybe_check_price_image(post, result)
                _save_price(post, result)
                done_count += 1
                if result.get("_price_source") == "image":
                    image_checked_count += 1
        else:
            print(f"  -> fallback: วิเคราะห์ราคาทีละโพสต์แทนสำหรับแบทนี้")
            for post in batch:
                result = analyze_price_text(post["text"])
                if result is None:
                    print(f"    [{post['uid']}] ยังไม่สำเร็จ ข้ามไปก่อน จะลองใหม่รอบหน้า")
                    continue
                result = _maybe_check_price_image(post, result)
                _save_price(post, result)
                done_count += 1
                if result.get("_price_source") == "image":
                    image_checked_count += 1
                time.sleep(1)

        time.sleep(0.5)

    print(f"[ai_analyze:price] วิเคราะห์ราคาสำเร็จทั้งหมด {done_count}/{len(posts)} โพสต์ "
          f"(ในนั้นดึงราคาจากรูปภาพ {image_checked_count} โพสต์)")


def main():
    init_db()

    print("=== ส่วนที่ 1: relevance / sentiment / topic (ทุกแพลตฟอร์ม) ===")
    posts = get_unanalyzed_posts(limit=300)
    print(f"[ai_analyze] มี {len(posts)} โพสต์ที่ยังไม่วิเคราะห์ (batch size = {BATCH_SIZE}, model = {MODEL_NAME})")
    if posts:
        process_in_batches(posts)
    else:
        print("[ai_analyze] ไม่มีโพสต์ที่ต้องวิเคราะห์")

    print("\n=== ส่วนที่ 2: ราคา/โปรโมชั่น (เฉพาะ facebook_page) ===")
    price_posts = get_unpriced_facebook_posts(limit=200)
    print(f"[ai_analyze:price] มี {len(price_posts)} โพสต์ Facebook ที่ยังไม่วิเคราะห์ราคา")
    if price_posts:
        process_price_in_batches(price_posts)
    else:
        print("[ai_analyze:price] ไม่มีโพสต์ Facebook ที่ต้องวิเคราะห์ราคา")


if __name__ == "__main__":
    main()
