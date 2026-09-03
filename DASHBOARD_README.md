# Web Dashboard — วิธีติดตั้งและใช้งาน

ไฟล์ในนี้เป็นส่วนเสริมที่เพิ่มหน้าเว็บ (Streamlit) ให้กับโปรเจกต์ `community_trend_tracker` เดิม
**ไม่ได้แก้ตรรกะของ `scrape_x.py` / `ai_analyze.py` / `analyze.py` เลย** — หน้าเว็บแค่เรียกใช้ฟังก์ชัน
เดิมหรือรันสคริปต์เดิมเป็น subprocess เท่านั้น

## ไฟล์ที่เพิ่มเข้ามา

```
community_trend_tracker/
├── app.py                  # หน้าแรก: Dashboard ภาพรวมเทรนด์
├── pages/
│   ├── 1_Forecast.py       # ดู/สร้างรายงานคาดการณ์แนวโน้ม
│   ├── 2_Pipeline.py       # ปุ่มรัน scrape/analyze/summarize + ดู log real-time
│   ├── 3_Settings.py       # แก้ handles/keywords/limit ใน .env ผ่านหน้าเว็บ
│   └── 4_Raw_Data.py       # ดู/แก้ไข is_relevant ของโพสต์ดิบทีละรายการ
├── db.py                   # ไฟล์เดิม + เพิ่ม 2 ฟังก์ชัน: get_summary_stats(), update_post_relevance()
├── secrets_sync.py         # ให้ใช้ .env (ในเครื่อง) หรือ st.secrets (บน cloud) ได้โดยไม่ต้องแก้สคริปต์เดิม
├── requirements.txt        # รวมแพ็กเกจเดิม + streamlit/plotly ไว้ไฟล์เดียว (ใช้แทนไฟล์เดิมได้เลย)
├── .gitignore              # กัน .env / ไฟล์ฐานข้อมูล หลุดขึ้น git โดยไม่ตั้งใจ
├── secrets.toml.example    # ตัวอย่างค่าที่ต้องตั้งตอน deploy บน Streamlit Community Cloud
└── CLOUD_DEPLOY.md         # ขั้นตอน deploy ขึ้น Streamlit Community Cloud (ฟรี) แบบละเอียด
```

## ขั้นตอนติดตั้ง (รันในเครื่อง)

1. คัดลอกไฟล์ทั้งหมดในนี้ไปวางไว้ที่โฟลเดอร์ `community_trend_tracker/` เดิมของคุณ
   (ระดับเดียวกับ `analyze.py`, `scrape_x.py` ฯลฯ)
2. **แทนที่ `db.py` และ `requirements.txt` เดิมด้วยไฟล์ที่แนบมานี้**
   (`db.py` เพิ่มแค่ 2 ฟังก์ชันต่อท้าย ไม่ได้ลบ/แก้อะไรเดิม, `requirements.txt` รวม streamlit/plotly ไว้แล้ว)
3. ติดตั้งแพ็กเกจ:
   ```bash
   pip install -r requirements.txt
   ```
4. ตรวจสอบว่ามีไฟล์ `.env` ที่ตั้งค่าไว้แล้ว (ถ้ายังไม่มี ทำตามขั้นตอนใน README เดิมก่อน)

ถ้าต้องการ deploy ขึ้น Streamlit Community Cloud (ฟรี) แทนการรันในเครื่อง ดูขั้นตอนละเอียดใน
`CLOUD_DEPLOY.md`

## วิธีรัน

```bash
cd community_trend_tracker
streamlit run app.py
```

จะเปิดเบราว์เซอร์อัตโนมัติที่ `http://localhost:8501` — เมนูแต่ละหน้าอยู่แถบด้านซ้าย

## หมายเหตุการใช้งาน

- **หน้า Pipeline** รันสคริปต์เดิม (`scrape_x.py`, `ai_analyze.py`, `analyze.py`, `run_all.py`) เป็น
  subprocess แยก แล้วสตรีม log ที่สคริปต์ print ออกมาให้ดูแบบ real-time — ระหว่างที่กำลังรันอยู่
  หน้าเว็บจะค้าง (บล็อก) จนกว่าจะเสร็จ ซึ่งเหมาะกับการใช้งานคนเดียวบนเครื่องตัวเองอยู่แล้ว
  **อย่ากดปุ่มซ้ำระหว่างที่กำลังรัน**
- **หน้า Settings** แก้ค่าที่ไม่ใช่ความลับได้ทั้งหมด:
  - X (Twitter): `TWITTER_HANDLES`, `TWITTER_KEYWORDS`, `FILTER_BY_KEYWORD`, `TWITTER_RESULTS_LIMIT`
  - Reddit: `ENABLE_REDDIT_SOURCE` (ปุ่มเปิด/ปิดทั้งแหล่งข้อมูล), `REDDIT_SEARCH_TERMS` (คีย์เวิร์ดค้นหา
    ข้ามทั้ง Reddit), `REDDIT_SUBREDDITS` (community ที่รู้จักอยู่แล้ว), `REDDIT_RESULTS_LIMIT`
    (จำนวนโพสต์สูงสุดต่อรอบ)

  ส่วน `APIFY_API_TOKEN` และ `ANTHROPIC_API_KEY` ต้องแก้ในไฟล์ `.env` โดยตรง (ตั้งใจไม่ให้แก้ผ่าน
  หน้าเว็บ เพื่อไม่ให้ค่า key/token หลุดไปแสดงบนหน้าจอ)
- **หน้า Pipeline** มีปุ่มแยกสำหรับ `scrape_x.py` และ `scrape_reddit.py` — ปุ่ม Reddit จะรันแล้วข้าม
  แบบไม่ error อัตโนมัติถ้าปิด `ENABLE_REDDIT_SOURCE` ไว้ หรือยังไม่ได้ตั้งค่าคีย์เวิร์ด/subreddit เลย
- **หน้า Raw Data** ใช้เช็คว่า AI จำแนก `is_relevant` ผิดพลาดหรือไม่ (ตามที่ README เดิมแนะนำให้สุ่มเช็ค)
  แก้ค่าในตารางแล้วกด "บันทึกการแก้ไข" เพื่อเขียนกลับเข้า SQLite
- ข้อมูลบนหน้า Dashboard/Raw Data ถูก cache ไว้ 30-60 วินาที (`st.cache_data`) ถ้าเพิ่งรัน pipeline เสร็จ
  แล้วตัวเลขยังไม่อัปเดต ให้รอสักครู่หรือกด refresh หน้าเว็บ
