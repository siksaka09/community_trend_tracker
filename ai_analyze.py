"""
ใช้ Claude API วิเคราะห์โพสต์จาก community (X/Twitter) เพื่อจับกระแส/เทรนด์เกี่ยวกับเกม EA FC 27
โดยดึงข้อมูล 3 อย่างต่อโพสต์:
  1. is_relevant  — โพสต์นี้เกี่ยวกับ EA FC 27 จริงไหม (กรองทวีตอื่นที่หลุดเข้ามา)
  2. sentiment    — โทนของโพสต์ (positive / negative / neutral / mixed)
  3. topics       — หัวข้อที่พูดถึง เช่น gameplay, pricing, release_date, bug, hype, beta, microtransactions
  4. summary      — สรุปสั้นๆ ว่าโพสต์นี้พูดถึงอะไร

=== เรื่องโมเดลและค่าใช้จ่าย ===
ใช้ Claude Haiku 4.5 (claude-haiku-4-5-20251001) เป็นค่าเริ่มต้น เพราะงานจำแนกประเภท/สรุปสั้นๆ
แบบนี้ไม่จำเป็นต้องใช้โมเดลที่แพงกว่า และ Haiku เร็ว+ถูกกว่ามาก (ราคาปัจจุบัน ณ ปี 2026 อยู่ที่
$1/$5 ต่อล้าน token เทียบกับ Sonnet 5 ที่ $2/$10) รวมกับการวิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request
ทำให้ต้นทุนโดยรวมต่ำมาก (วิเคราะห์ 200 โพสต์ ~ $0.20-0.30) ถ้าอยากได้คุณภาพสูงขึ้น ปรับ MODEL_NAME
เป็น "claude-sonnet-5" ได้ที่ตัวแปรด้านล่าง

วิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request (ลด request ลง 5 เท่า ลดโอกาสโดน rate limit)
มี fallback ไปทีละโพสต์ถ้า batch มีปัญหา และ retry อัตโนมัติเมื่อเจอ rate limit / server error
"""
import os
import json
import time
from dotenv import load_dotenv
import anthropic

from db import init_db, get_unanalyzed_posts, save_ai_analysis

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL_NAME = "claude-haiku-4-5-20251001"  # ปรับเป็น "claude-sonnet-5" ได้ถ้าอยากได้คุณภาพสูงขึ้น (แพงขึ้น ~4 เท่า)
BATCH_SIZE = 5
MAX_TOKENS = 4000

EMPTY_RESULT = {
    "is_relevant": False, "sentiment": "neutral", "topics": [], "summary": None,
}

TOPIC_LIST = (
    "gameplay (เกมเพลย์/ระบบเกม), pricing (ราคา/ค่าใช้จ่ายในเกม), release_date (วันวางจำหน่าย/เปิดตัว), "
    "beta (ช่วงทดลองเล่น), bug (บั๊ก/ปัญหาทางเทคนิค), hype (ความตื่นเต้น/รอคอย), "
    "microtransactions (ไมโครทรานแซคชั่น/ซื้อของในเกม), graphics (กราฟิก/ภาพ), "
    "career_mode (โหมดอาชีพ), ultimate_team (โหมด Ultimate Team), rumor (ข่าวลือ/เดา), "
    "comparison (เทียบกับเกมเก่า/เกมอื่น), complaint (ข้อร้องเรียนทั่วไป), other (อื่นๆ)"
)

SYSTEM_PROMPT_SINGLE = f"""คุณเป็นนักวิเคราะห์กระแส/เทรนด์ community เกี่ยวกับวิดีโอเกม EA FC 27
(เกมฟุตบอลจาก EA Sports) จากทวีต X (Twitter)

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
(เกมฟุตบอลจาก EA Sports) จากทวีต X (Twitter)
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


def main():
    init_db()
    posts = get_unanalyzed_posts(limit=300)
    print(f"[ai_analyze] มี {len(posts)} โพสต์ที่ยังไม่วิเคราะห์ (batch size = {BATCH_SIZE}, model = {MODEL_NAME})")

    if not posts:
        print("[ai_analyze] ไม่มีโพสต์ที่ต้องวิเคราะห์")
        return

    process_in_batches(posts)


if __name__ == "__main__":
    main()
