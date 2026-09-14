# Web Dashboard — วิธีติดตั้งและใช้งาน

ไฟล์ในนี้เป็นส่วนเสริมที่เพิ่มหน้าเว็บ (Streamlit) ให้กับโปรเจกต์ `community_trend_tracker` เดิม
**ไม่ได้แก้ตรรกะของ `scrape_x.py` / `ai_analyze.py` / `analyze.py` เลย** — หน้าเว็บแค่เรียกใช้ฟังก์ชัน
เดิมหรือรันสคริปต์เดิมเป็น subprocess เท่านั้น

## ไฟล์ที่เพิ่มเข้ามา

```
community_trend_tracker/
├── app.py                  # หน้าแรก: Dashboard ภาพรวมเทรนด์
├── pages/
│   ├── 1_Facebook_Prices.py # เทียบราคา/โปรโมชั่น/engagement (ไลค์/คอมเมนต์/แชร์/ยอดวิว) ระหว่างเพจ Facebook
│   ├── 2_Forecast.py       # ดู/สร้างรายงานคาดการณ์แนวโน้ม
│   ├── 3_Pipeline.py       # ปุ่มรัน scrape/analyze/summarize + ดู log real-time
│   ├── 4_Settings.py       # แก้ handles/keywords/limit ได้จากหน้าเว็บ (ในเครื่อง=ถาวร, cloud=session-only)
│   └── 5_Raw_Data.py       # ดู/แก้ไข is_relevant ของโพสต์ดิบทีละรายการ
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

- **หน้า Pipeline** รันสคริปต์เดิม (`scrape_x.py`, `scrape_reddit.py`, `scrape_facebook.py`,
  `ai_analyze.py`, `analyze.py`, `run_all.py`) เป็น subprocess แยก แล้วสตรีม log ที่สคริปต์ print
  ออกมาให้ดูแบบ real-time — ระหว่างที่กำลังรันอยู่ หน้าเว็บจะค้าง (บล็อก) จนกว่าจะเสร็จ ซึ่งเหมาะกับ
  การใช้งานคนเดียวบนเครื่องตัวเองอยู่แล้ว **อย่ากดปุ่มซ้ำระหว่างที่กำลังรัน**
- **หน้า Settings** แก้ค่าที่ไม่ใช่ความลับได้ทั้งหมด:
  - X (Twitter): `TWITTER_HANDLES`, `TWITTER_KEYWORDS`, `FILTER_BY_KEYWORD`, `TWITTER_RESULTS_LIMIT`
  - Reddit: `ENABLE_REDDIT_SOURCE` (ปุ่มเปิด/ปิดทั้งแหล่งข้อมูล), `REDDIT_SEARCH_TERMS` (คีย์เวิร์ดค้นหา
    ข้ามทั้ง Reddit), `REDDIT_SUBREDDITS` (community ที่รู้จักอยู่แล้ว), `REDDIT_RESULTS_LIMIT`
    (จำนวนโพสต์สูงสุดต่อรอบ)
  - Facebook Pages: `ENABLE_FACEBOOK_SOURCE` (ปุ่มเปิด/ปิดทั้งแหล่งข้อมูล), `FB_PAGE_URLS` (URL เพจ
    ที่ติดตาม เช่น เพจเราเอง+เพจคู่แข่ง), `FB_POSTS_PER_PAGE` (จำนวนโพสต์สูงสุดต่อเพจต่อรอบ)
    — ต่างจาก X/Reddit ตรงที่แหล่งนี้ใช้เทียบราคา/โปรโมชั่น/engagement ระหว่างเพจร้านค้าที่รู้จัก
    ตายตัว ไม่ใช่ตามกระแส community กว้างๆ

  ส่วน `APIFY_API_TOKEN` และ `ANTHROPIC_API_KEY` ต้องแก้ในไฟล์ `.env` โดยตรง (ตั้งใจไม่ให้แก้ผ่าน
  หน้าเว็บ เพื่อไม่ให้ค่า key/token หลุดไปแสดงบนหน้าจอ)

  **พฤติกรรมต่างกันตามที่รัน:**
  - **ในเครื่อง** (มีไฟล์ `.env`) — บันทึกแล้วเขียนกลับลงไฟล์ `.env` จริง **ถาวร** มีผลทุกครั้งที่รันใหม่
  - **บน Streamlit Cloud** (ไม่มี `.env` ใช้ Secrets แทน) — บันทึกแล้วมีผล**เฉพาะ session ปัจจุบัน**
    เท่านั้น (เขียนเข้า `os.environ` ของโปรเซสที่รันอยู่ ซึ่ง subprocess ที่ปุ่มในหน้า Pipeline เรียก
    จะสืบทอดค่านี้ไปด้วย เลยมีผลจริงตอนกดรัน) ถ้าแอป **reboot/restart** ค่าจะกลับไปเป็นของเดิมใน
    Secrets ทันที เพราะ Streamlit Cloud ไม่มี API ให้แอปเขียนกลับเข้าไฟล์ secrets ถาวรได้ ถ้าอยากให้
    ค่าอยู่ถาวรต้องไปแก้ที่หน้า "Manage app" > "Secrets" ของ Cloud โดยตรง — และถ้ามีคนอื่นเข้าใช้แอป
    เดียวกันพร้อมกัน การแก้ค่าจะมีผลกับทุกคนที่ใช้อยู่ในตอนนั้นด้วย (เพราะ `os.environ` เป็นของทั้ง
    โปรเซส ไม่ได้แยกตามคนใช้)
- **หน้า Pipeline** มีปุ่มแยกสำหรับ `scrape_x.py`, `scrape_reddit.py`, และ `scrape_facebook.py`
  — ปุ่ม Reddit/Facebook จะรันแล้วข้ามแบบไม่ error อัตโนมัติถ้าปิด toggle ที่เกี่ยวข้องไว้ หรือยังไม่ได้
  ตั้งค่าที่จำเป็น (คีย์เวิร์ด/subreddit สำหรับ Reddit, URL เพจสำหรับ Facebook)
- **หน้า Raw Data** ใช้เช็คว่า AI จำแนก `is_relevant` ผิดพลาดหรือไม่ (ตามที่ README เดิมแนะนำให้สุ่มเช็ค)
  แก้ค่าในตารางแล้วกด "บันทึกการแก้ไข" เพื่อเขียนกลับเข้า SQLite
- **หน้า Facebook Prices** แยกออกจากหน้า Dashboard หลักโดยเฉพาะ เพราะเป็นคนละโฟกัส (หน้าแรกดูกระแส
  community, หน้านี้เจาะจงเทียบเพจร้านค้า) แสดง engagement แบบละเอียด — ไลค์/คอมเมนต์/แชร์/ยอดวิว
  ทั้งค่าเฉลี่ยต่อโพสต์และยอดรวม แยกกราฟตามช่วงเวลาให้เลือกดูทีละตัวชี้วัด (ไลค์/คอมเมนต์/แชร์/ยอดวิว)
  พร้อมกราฟราคา, ตารางโปรโมชั่น, และตารางโพสต์ engagement สูงสุด — มีตัวกรองเลือกเพจที่จะดูในแถบซ้าย
  **หมายเหตุ:** คอลัมน์ `shares` เป็นฟีเจอร์ใหม่ ถ้ามีโพสต์ Facebook ที่ดึงมาก่อนหน้านี้ (ก่อนอัปเดต)
  ค่า `shares` ของโพสต์เก่าจะเป็นค่าว่าง (NULL) ไม่ error แต่จะไม่มีข้อมูลแชร์ให้ดูจนกว่าจะดึงใหม่
- ข้อมูลบนหน้า Dashboard/Raw Data ถูก cache ไว้ 30-60 วินาที (`st.cache_data`) ถ้าเพิ่งรัน pipeline เสร็จ
  แล้วตัวเลขยังไม่อัปเดต ให้รอสักครู่หรือกด refresh หน้าเว็บ
