"""
สรุปกระแส/เทรนด์เกี่ยวกับเกม EA FC 27 จากข้อมูลที่เก็บไว้ (ดึงมาจาก X/Twitter):
1. ปริมาณโพสต์ตามเวลา (วันไหนพูดถึงเยอะ) แยกตามบัญชี/แพลตฟอร์ม
2. สัดส่วน sentiment (positive/negative/neutral/mixed) โดยรวม
3. หัวข้อที่พูดถึงบ่อยที่สุด (topics)
4. โพสต์ที่มี engagement สูงสุด (พร้อมสรุปว่าพูดถึงอะไร) — เอาไว้ดูว่าอะไรกำลัง "ไวรัล"
5. คาดการณ์แนวโน้ม (ให้ Claude ช่วยตีความ) — เทียบสถิติครึ่งแรกกับครึ่งหลังของข้อมูลที่มี
   แล้วให้ AI อนุมานว่าถ้าแนวโน้มนี้ดำเนินต่อไป มีสัญญาณอะไรที่ควรจับตา
   **หมายเหตุสำคัญ: นี่คือการอนุมานจากรูปแบบข้อมูล ไม่ใช่การพยากรณ์ที่แม่นยำ** AI ไม่สามารถ
   ทำนายอนาคตได้จริง เป็นเพียงการมองรูปแบบแล้วให้เหตุผลแบบมีตรรกะเท่านั้น ควรใช้ประกอบการตัดสินใจ
   ร่วมกับข้อมูลอื่นๆ ไม่ควรเชื่อเป็นข้อเท็จจริง

ผลลัพธ์จะพิมพ์ออกหน้าจอ และ export เป็น CSV/Markdown ไว้ที่ data/report_*
"""
import os
import json
import time
from pathlib import Path
from collections import Counter
import pandas as pd
from dotenv import load_dotenv
import anthropic

from db import get_all_posts_df

load_dotenv()

OUT_DIR = Path(__file__).parent / "data"

# ใช้ Sonnet 5 สำหรับส่วนนี้ (ต่างจาก ai_analyze.py ที่ใช้ Haiku) เพราะเป็นการเรียก API แค่ครั้งเดียว
# ต่อการรัน (ไม่ใช่ต่อโพสต์) ต้นทุนจึงต่ำมากอยู่แล้ว การใช้โมเดลที่คุณภาพการเขียน/ให้เหตุผลดีกว่า
# จึงคุ้มกว่าในจุดนี้ ปรับเป็น "claude-haiku-4-5-20251001" ได้ถ้าอยากประหยัดสุด
FORECAST_MODEL = "claude-sonnet-5"


def load_data() -> pd.DataFrame:
    df = get_all_posts_df()
    if df.empty:
        return df
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["posted_at"])
    return df


def filter_relevant(df: pd.DataFrame) -> pd.DataFrame:
    """เอาเฉพาะโพสต์ที่ AI ระบุว่าเกี่ยวกับ EA FC 27 (is_relevant = 1)
    โพสต์ที่ยังไม่วิเคราะห์ (NULL) จะถูกเตือนไว้แยกต่างหาก ไม่รวมในรายงานสรุป เพราะไม่รู้ว่าเกี่ยวจริงไหม"""
    unanalyzed = df["is_relevant"].isna().sum()
    if unanalyzed > 0:
        print(f"[analyze] หมายเหตุ: มี {unanalyzed} โพสต์ที่ยังไม่ได้วิเคราะห์ (รัน ai_analyze.py ก่อนเพื่อรวมเข้ารายงาน)")
    return df[df["is_relevant"] == 1]


def volume_over_time(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["posted_at"].dt.date
    return df.groupby(["date", "platform"]).size().reset_index(name="post_count").sort_values("date")


def sentiment_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    counts = df.groupby(["platform", "sentiment"]).size().reset_index(name="count")
    totals = df.groupby("platform").size().rename("total")
    counts = counts.merge(totals, on="platform")
    counts["percent"] = (counts["count"] / counts["total"] * 100).round(1)
    return counts.sort_values(["platform", "count"], ascending=[True, False])


def top_topics(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    counter = Counter()
    for _, row in df.iterrows():
        try:
            topics = json.loads(row["topics"]) if row["topics"] else []
        except json.JSONDecodeError:
            continue
        counter.update(topics)
    rows = [{"topic": t, "mentions": c} for t, c in counter.most_common(top_n)]
    return pd.DataFrame(rows)


def top_engagement_posts(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["engagement"] = pd.to_numeric(df["score"], errors="coerce").fillna(0) + \
                        pd.to_numeric(df["comments"], errors="coerce").fillna(0)
    cols = ["platform", "source_name", "posted_at", "summary", "sentiment", "engagement", "post_url"]
    return df.sort_values("engagement", ascending=False)[cols].head(top_n)


# ============================================================
# ส่วนที่ 5: คาดการณ์แนวโน้ม
# ============================================================

def split_time_windows(df: pd.DataFrame):
    """
    แบ่งข้อมูลเป็น 2 ช่วงเวลา (ครึ่งแรก vs ครึ่งหลัง) โดยใช้จุดกึ่งกลางของช่วงเวลาที่มีข้อมูลจริง
    คืนค่า (older_df, recent_df, span_days) หรือ (None, None, span_days) ถ้าข้อมูลครอบคลุมเวลาน้อยเกินไป
    (ต้องการอย่างน้อย ~2 วันเพื่อให้การเทียบมีความหมาย)
    """
    min_date = df["posted_at"].min()
    max_date = df["posted_at"].max()
    span_days = (max_date - min_date).days

    if span_days < 2:
        return None, None, span_days

    midpoint = min_date + (max_date - min_date) / 2
    older_df = df[df["posted_at"] < midpoint]
    recent_df = df[df["posted_at"] >= midpoint]
    return older_df, recent_df, span_days


def compute_trend_stats(older_df: pd.DataFrame, recent_df: pd.DataFrame) -> dict:
    """คำนวณสถิติเปรียบเทียบ 2 ช่วงเวลา: ปริมาณ, sentiment, หัวข้อที่มา/หัวข้อที่ซาลง"""

    def sentiment_pct(d: pd.DataFrame) -> dict:
        if len(d) == 0:
            return {}
        counts = d["sentiment"].value_counts(normalize=True) * 100
        return counts.round(1).to_dict()

    def topic_counts(d: pd.DataFrame) -> Counter:
        counter = Counter()
        for _, row in d.iterrows():
            try:
                topics = json.loads(row["topics"]) if row["topics"] else []
            except json.JSONDecodeError:
                continue
            counter.update(topics)
        return counter

    older_n, recent_n = len(older_df), len(recent_df)
    volume_change_pct = round((recent_n - older_n) / older_n * 100, 1) if older_n > 0 else None

    older_sentiment = sentiment_pct(older_df)
    recent_sentiment = sentiment_pct(recent_df)
    sentiment_shift = {
        s: round(recent_sentiment.get(s, 0) - older_sentiment.get(s, 0), 1)
        for s in set(older_sentiment) | set(recent_sentiment)
    }

    older_topics = topic_counts(older_df)
    recent_topics = topic_counts(recent_df)
    # normalize เป็นสัดส่วนต่อโพสต์ในช่วงนั้นๆ กันเอนเอียงจากจำนวนโพสต์ที่ไม่เท่ากัน
    all_topics = set(older_topics) | set(recent_topics)
    topic_momentum = []
    for t in all_topics:
        older_pct = (older_topics.get(t, 0) / older_n * 100) if older_n > 0 else 0
        recent_pct = (recent_topics.get(t, 0) / recent_n * 100) if recent_n > 0 else 0
        topic_momentum.append({"topic": t, "older_pct": round(older_pct, 1),
                                "recent_pct": round(recent_pct, 1),
                                "change": round(recent_pct - older_pct, 1)})
    topic_momentum.sort(key=lambda x: x["change"], reverse=True)

    return {
        "older_post_count": older_n,
        "recent_post_count": recent_n,
        "volume_change_pct": volume_change_pct,
        "older_sentiment_pct": older_sentiment,
        "recent_sentiment_pct": recent_sentiment,
        "sentiment_shift": sentiment_shift,
        "topic_momentum": topic_momentum[:10],  # เอาแค่ 10 อันดับที่เปลี่ยนแปลงมากสุด (ทั้งขึ้นและลง)
    }


FORECAST_SYSTEM_PROMPT = """คุณเป็นนักวิเคราะห์กระแส community เกี่ยวกับวิดีโอเกม EA FC 27
ผู้ใช้จะส่งสถิติเชิงเปรียบเทียบระหว่าง 2 ช่วงเวลา (ช่วงก่อนหน้า vs ช่วงล่าสุด) ที่คำนวณจากทวีตจริงมาให้

หน้าที่ของคุณคือมองรูปแบบ (pattern) ในตัวเลขเหล่านี้ แล้วเขียนรายงานสั้นๆ เป็นภาษาไทย
อธิบายว่า "ถ้าแนวโน้มนี้ดำเนินต่อไป มีสัญญาณอะไรที่ควรจับตา" — เน้นย้ำว่านี่คือการอนุมานจากรูปแบบ
ข้อมูลเชิงสถิติที่มีอยู่จำกัด ไม่ใช่การพยากรณ์ที่แม่นยำหรือข้อเท็จจริง

โครงสร้างรายงาน (ใช้ markdown):
## สรุปแนวโน้มปัจจุบัน
(อธิบายสั้นๆ ว่าตัวเลขบอกอะไร เช่น ปริมาณโพสต์เพิ่ม/ลด, sentiment เปลี่ยนไปทางไหน)

## หัวข้อที่กำลังมาแรง / กำลังซาลง
(อ้างอิงจาก topic_momentum)

## สัญญาณที่ควรจับตา
(ระบุ 2-4 สัญญาณที่น่าสนใจ พร้อมเหตุผลว่าทำไมถึงน่าจับตา)

## ข้อจำกัดของการวิเคราะห์นี้
(ระบุตรงๆ ว่าเป็นการมองรูปแบบจากข้อมูลจำนวนจำกัด ไม่ใช่การพยากรณ์ที่แม่นยำ ต้องระวังปัจจัยภายนอก
ที่ไม่ได้อยู่ในข้อมูล เช่น ข่าวใหม่ที่ยังไม่เกิดขึ้น)

กติกา:
- ห้ามยืนยันว่า "จะเกิด X แน่นอน" ให้ใช้ภาษาแบบมีเงื่อนไข เช่น "ถ้าแนวโน้มนี้ดำเนินต่อ อาจ..."
- ถ้าข้อมูลน้อยเกินไปจนสรุปอะไรไม่ได้ชัดเจน ให้บอกตรงๆ ว่าข้อมูลยังไม่พอสรุป
- ตอบเป็น markdown text ธรรมดา ไม่ต้องมี code fence ครอบ
"""


def generate_forecast(stats: dict, max_retries: int = 3) -> str | None:
    """ส่งสถิติแนวโน้มให้ Claude ช่วยตีความเป็นรายงาน (เรียก API แค่ครั้งเดียวต่อการรัน)"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_key_here":
        print("[analyze] ข้ามส่วนคาดการณ์แนวโน้ม: ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY ใน .env")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    user_content = json.dumps(stats, ensure_ascii=False, indent=2)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.messages.create(
                model=FORECAST_MODEL,
                max_tokens=1500,
                system=FORECAST_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as e:
            wait = min(60, 15 * attempt)
            print(f"    [forecast] โดน rate limit (attempt {attempt}/{max_retries}) รอ {wait} วิ แล้วลองใหม่... ({e})")
            time.sleep(wait)
        except (anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            wait = min(30, 5 * attempt)
            print(f"    [forecast] เซิร์ฟเวอร์มีปัญหาชั่วคราว (attempt {attempt}/{max_retries}) "
                  f"รอ {wait} วิ แล้วลองใหม่... ({e})")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            print(f"    [forecast] เจอ error ที่ retry ไม่ได้ ({e})")
            return None
    return None


def main():
    OUT_DIR.mkdir(exist_ok=True)
    df_all = load_data()

    if df_all.empty:
        print("ยังไม่มีข้อมูลในฐานข้อมูล กรุณารัน scrape_x.py ก่อน")
        return

    df = filter_relevant(df_all)
    excluded = len(df_all) - len(df) - df_all["is_relevant"].isna().sum()
    if excluded > 0:
        print(f"[analyze] กรองโพสต์ที่ไม่เกี่ยวกับ EA FC 27 ออก {excluded} โพสต์")

    if df.empty:
        print("ยังไม่มีโพสต์ที่ผ่านการวิเคราะห์และเกี่ยวข้องกับ EA FC 27 — รัน ai_analyze.py ก่อน")
        return

    print(f"[analyze] ใช้ {len(df)} โพสต์ที่เกี่ยวข้องในการสรุปเทรนด์\n")

    print("=" * 60)
    print("1) ปริมาณโพสต์ตามเวลา (แยกตามแพลตฟอร์ม)")
    print("=" * 60)
    volume = volume_over_time(df)
    print(volume.to_string(index=False))
    volume.to_csv(OUT_DIR / "report_volume_over_time.csv", index=False)

    print("\n" + "=" * 60)
    print("2) สัดส่วน Sentiment (แยกตามแพลตฟอร์ม)")
    print("=" * 60)
    sentiment = sentiment_breakdown(df)
    print(sentiment.to_string(index=False))
    sentiment.to_csv(OUT_DIR / "report_sentiment.csv", index=False)

    print("\n" + "=" * 60)
    print("3) หัวข้อที่พูดถึงบ่อยที่สุด")
    print("=" * 60)
    topics = top_topics(df)
    if topics.empty:
        print("ยังไม่มีข้อมูลหัวข้อ")
    else:
        print(topics.to_string(index=False))
        topics.to_csv(OUT_DIR / "report_top_topics.csv", index=False)

    print("\n" + "=" * 60)
    print("4) โพสต์ที่มี Engagement สูงสุด (กำลังเป็นกระแส)")
    print("=" * 60)
    top_posts = top_engagement_posts(df)
    print(top_posts.to_string(index=False))
    top_posts.to_csv(OUT_DIR / "report_top_posts.csv", index=False)

    print("\n" + "=" * 60)
    print("5) คาดการณ์แนวโน้ม (อนุมานจากรูปแบบข้อมูล ไม่ใช่การพยากรณ์ที่แม่นยำ)")
    print("=" * 60)
    older_df, recent_df, span_days = split_time_windows(df)
    if older_df is None:
        print(f"ข้อมูลครอบคลุมช่วงเวลาแค่ {span_days} วัน สั้นเกินไปที่จะเทียบแนวโน้มได้อย่างมีความหมาย "
              f"— เก็บข้อมูลต่อเนื่องอย่างน้อย 2-3 วันขึ้นไปก่อนแล้วรันใหม่")
    elif len(older_df) == 0 or len(recent_df) == 0:
        print("ช่วงเวลาใดช่วงเวลาหนึ่งไม่มีโพสต์เลย ข้อมูลไม่พอเทียบแนวโน้ม")
    else:
        stats = compute_trend_stats(older_df, recent_df)
        print(f"เทียบช่วง {older_df['posted_at'].min().date()}–{older_df['posted_at'].max().date()} "
              f"({stats['older_post_count']} โพสต์) กับช่วง "
              f"{recent_df['posted_at'].min().date()}–{recent_df['posted_at'].max().date()} "
              f"({stats['recent_post_count']} โพสต์)\n")
        forecast_text = generate_forecast(stats)
        if forecast_text:
            print(forecast_text)
            with open(OUT_DIR / "report_trend_forecast.md", "w", encoding="utf-8") as f:
                f.write(f"# คาดการณ์แนวโน้ม EA FC 27\n\n")
                f.write(f"เทียบช่วง {older_df['posted_at'].min().date()}–{older_df['posted_at'].max().date()} "
                        f"กับ {recent_df['posted_at'].min().date()}–{recent_df['posted_at'].max().date()}\n\n")
                f.write(forecast_text)
            print(f"\n[analyze] บันทึกรายงานคาดการณ์ไว้ที่: {OUT_DIR / 'report_trend_forecast.md'}")
        else:
            print("ไม่สามารถสร้างรายงานคาดการณ์ได้ (เช็ค ANTHROPIC_API_KEY หรือลองรันใหม่)")

    print(f"\n[analyze] บันทึกไฟล์ CSV ไว้ที่โฟลเดอร์: {OUT_DIR}")


if __name__ == "__main__":
    main()
