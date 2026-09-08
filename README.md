# Community & Competitor Tracker — EA FC 27

โปรเจกต์นี้รวม 2 มุมมองเข้าด้วยกันในฐานข้อมูลเดียว:

1. **ตามกระแส community** — จาก **X (Twitter)** และ **Reddit** วิเคราะห์ sentiment/หัวข้อที่คนพูดถึง
   เกม EA FC 27 โดยรวม (ตื่นเต้น/บ่น/ข่าวลือ ฯลฯ)
2. **เทียบราคาคู่แข่ง** — จาก **Facebook Pages** ที่ระบุตายตัว (เช่น เพจเราเอง + เพจคู่แข่ง)
   เทียบราคา/โปรโมชั่น/engagement ระหว่างเพจร้านค้าที่ขายเหรียญเกม

ทั้งสามแหล่งข้อมูลเก็บอยู่ในตารางเดียว (`community_posts`) แยกด้วยคอลัมน์ `platform`
(`x` / `reddit` / `facebook_page`) — เปิด/ปิดแต่ละแหล่งแยกกันได้อิสระ

ใช้ **Claude API** วิเคราะห์:
- **ทุกแพลตฟอร์ม**: เกี่ยวกับเกม EA FC 27 จริงไหม, โทนของโพสต์ (sentiment), พูดถึงหัวข้ออะไร
- **เฉพาะ Facebook Pages**: ราคา/โปรโมชั่นที่ปรากฏในโพสต์ (อ่านทั้งข้อความและรูปภาพด้วย vision)

แล้วสรุปเป็นรายงาน: ปริมาณโพสต์ตามเวลา, สัดส่วน sentiment, หัวข้อฮิต, โพสต์ไวรัล,
**เทียบราคา/โปรโมชั่น/engagement ระหว่างเพจ Facebook**, และ**คาดการณ์แนวโน้ม**

มี **Local Web Interface** (Streamlit, หลายหน้า) ให้ดูกราฟ/รันสคริปต์/แก้ตั้งค่าผ่านเบราว์เซอร์ได้เลย
ไม่ต้องเปิด terminal พิมพ์คำสั่งเอง — ดูวิธีใช้ที่ `DASHBOARD_README.md`
(อยาก deploy ขึ้น Streamlit Community Cloud ฟรี ดู `CLOUD_DEPLOY.md`)

## โครงสร้างไฟล์
```
community_trend_tracker/
├── .env.example        # แม่แบบไฟล์ config (คัดลอกเป็น .env)
├── requirements.txt     # รายชื่อ library ที่ต้องติดตั้ง
├── db.py                # จัดการฐานข้อมูล SQLite (เก็บที่ data/community_trends.db)
├── scrape_x.py          # ดึงทวีตจากบัญชี X ที่ระบุ ผ่าน Apify
├── scrape_reddit.py     # ดึงโพสต์จาก Reddit (คีย์เวิร์ด + subreddit) ผ่าน Apify
├── scrape_facebook.py   # ดึงโพสต์จากเพจ Facebook ที่ระบุ ผ่าน Apify
├── ai_analyze.py         # ให้ Claude เช็ค relevance/sentiment/หัวข้อ (ทุกแพลตฟอร์ม)
│                         # + วิเคราะห์ราคา/โปรโมชั่น (เฉพาะ facebook_page)
├── analyze.py            # สรุปเทรนด์ + เทียบราคา Facebook + คาดการณ์แนวโน้ม + export CSV
├── app.py                # หน้าแรกของ Web Dashboard (Streamlit)
├── pages/                # หน้าอื่นๆ ของ Web Dashboard (Forecast, Pipeline, Settings, Raw Data)
├── secrets_sync.py       # ให้ dashboard ใช้ .env (ในเครื่อง) หรือ st.secrets (บน cloud) ได้
├── run_all.py            # รันทั้ง 5 ขั้นตอนในคำสั่งเดียว
├── DASHBOARD_README.md   # วิธีติดตั้ง/ใช้งาน Web Dashboard แบบละเอียด
└── CLOUD_DEPLOY.md       # วิธี deploy ขึ้น Streamlit Community Cloud (ฟรี)
```

## ขั้นตอนติดตั้ง (ทำครั้งเดียว)

### 1. ติดตั้ง library
```bash
cd community_trend_tracker
pip install -r requirements.txt
```

### 2. เอา Apify token
สมัครที่ https://console.apify.com/sign-up (มี free tier ให้ credit ทดลองใช้) แล้วไปที่
https://console.apify.com/account/integrations คัดลอก API token

### 3. เอา Claude API key
1. สมัคร/เข้า https://console.anthropic.com/settings/keys คัดลอก key
2. เติมเครดิตที่ https://console.anthropic.com/settings/billing (ขั้นต่ำ ~$5)
   **งบ $5 เพียงพอมากสำหรับทดสอบและใช้งานจริง** เพราะระบบวิเคราะห์เป็นแบทละ 5 โพสต์ต่อ 1 request
   และใช้โมเดล Haiku 4.5 (ถูกสุด) เป็นค่าเริ่มต้น

### 4. ตั้งค่าไฟล์ .env
```bash
cp .env.example .env
```
แล้วเปิดไฟล์ `.env` ใส่ค่าตามที่ต้องการ (ดูรายละเอียดคอมเมนต์ในไฟล์ `.env.example`):
- `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY` — จากขั้นตอนที่ 2-3
- `TWITTER_HANDLES` — บัญชี X ที่ต้องการติดตาม
- `REDDIT_SEARCH_TERMS` / `REDDIT_SUBREDDITS` — คีย์เวิร์ด/ชุมชนที่ต้องการติดตามบน Reddit
- `FB_PAGE_URLS` — URL เพจ Facebook ที่ต้องการเทียบ (เช่น เพจเราเอง + เพจคู่แข่ง)

แต่ละแหล่งข้อมูลมี toggle เปิด/ปิดแยกกัน (`FILTER_BY_KEYWORD` แบบ X, `ENABLE_REDDIT_SOURCE`,
`ENABLE_FACEBOOK_SOURCE`) ถ้าไม่ได้ตั้งค่าหรือปิดไว้ ระบบจะข้ามแหล่งนั้นไปแบบไม่ error

## วิธีรัน

รันทีเดียวครบทุกขั้นตอน:
```bash
python run_all.py
```

หรือรันแยกทีละขั้น:
```bash
python scrape_x.py         # ดึงทวีตจากบัญชีที่ระบุ
python scrape_reddit.py    # ดึงโพสต์จาก Reddit
python scrape_facebook.py  # ดึงโพสต์จากเพจ Facebook
python ai_analyze.py       # ให้ Claude เช็ค relevance/sentiment/หัวข้อ + ราคา (Facebook)
python analyze.py          # พิมพ์สรุปเทรนด์ + export CSV
```

หรือเปิด **Web Dashboard** แทน (แนะนำ — ไม่ต้องจำคำสั่ง มีปุ่มกดรันทุกขั้นตอน):
```bash
streamlit run app.py
```
ดูรายละเอียดเต็มที่ `DASHBOARD_README.md`

ผลลัพธ์ CSV จะอยู่ที่:
- `data/report_volume_over_time.csv` — ปริมาณโพสต์ตามวัน แยกตามแพลตฟอร์ม
- `data/report_sentiment.csv` — สัดส่วน positive/negative/neutral/mixed
- `data/report_top_topics.csv` — หัวข้อที่พูดถึงบ่อยที่สุด
- `data/report_top_posts.csv` — โพสต์ engagement สูงสุด 20 อันดับ
- `data/report_facebook_price_trend.csv` — แนวโน้มราคาเทียบข้ามเพจ Facebook (มีคอลัมน์ `price_source`
  บอกว่าดึงมาจาก `text` หรือ `image`)
- `data/report_facebook_promotions.csv` — โปรโมชั่นที่พบในเพจ Facebook
- `data/report_facebook_engagement.csv` — เปรียบเทียบ engagement เฉลี่ยระหว่างเพจ Facebook
- `data/report_trend_forecast.md` — รายงานคาดการณ์แนวโน้ม (ต้องมีข้อมูลครอบคลุมอย่างน้อย 2-3 วันขึ้นไป)

## ข้อควรระวัง

1. **Terms of Service** — การดึงข้อมูลอัตโนมัติจากทุกแพลตฟอร์มอาจขัดกับ ToS ของแพลตฟอร์มนั้นๆ
   ควรดึงเฉพาะเนื้อหา public, เว้นระยะเวลาที่เหมาะสม ไม่ดึงถี่เกินจำเป็น
2. **Apify credit** — actor แต่ละตัวคิดค่าใช้จ่ายต่างกัน (event-based หรือ pay-per-result) ปรับ
   `TWITTER_RESULTS_LIMIT`, `REDDIT_RESULTS_LIMIT`, `FB_POSTS_PER_PAGE` ให้พอดีกับที่ใช้จริง
3. **Reddit/Facebook actor เป็นของ community** — ถ้า field ไม่ตรงหรือ error ให้เช็ค input schema
   ล่าสุดของ actor นั้นๆ ใน Apify Console แล้วปรับ `run_input` ในสคริปต์ที่เกี่ยวข้อง —
   ทุกสคริปต์จะพิมพ์ชื่อ field ทั้งหมดของโพสต์แรกที่ดึงมาให้ดู ("ตัวอย่าง field ที่มีในผลลัพธ์ดิบ")
4. **โมเดล Claude และค่าใช้จ่าย** — `ai_analyze.py` ใช้ `claude-haiku-4-5-20251001` เป็นค่าเริ่มต้น
   ทั้งงานจำแนก relevance/sentiment/หัวข้อ และงานอ่านราคา/รูปภาพของ Facebook (Haiku อ่านรูปได้)
   `analyze.py` (ส่วนคาดการณ์แนวโน้ม) ใช้ `claude-sonnet-5` เพราะเรียกแค่ครั้งเดียวต่อการรัน
   ต้นทุนต่ำอยู่แล้ว ปรับโมเดลได้ที่ตัวแปร `MODEL_NAME` / `FORECAST_MODEL` ในแต่ละไฟล์
   ระบบมี retry อัตโนมัติสำหรับ rate limit (429) และ server error ชั่วคราว (500/503/529) ทุกจุด
5. **ความแม่นยำของ AI** — ทั้ง relevance filter และการดึงราคาจากข้อความ/รูปภาพไม่แม่นยำ 100% เสมอ
   ควรสุ่มเช็คหน้า **Raw Data** ของ dashboard หรือไฟล์ CSV เทียบกับโพสต์จริงเป็นระยะ
6. **คาดการณ์แนวโน้มเป็นการอนุมาน ไม่ใช่การพยากรณ์ที่แม่นยำ** — AI มองรูปแบบตัวเลขแล้วให้เหตุผล
   แบบมีเงื่อนไข ไม่ใช่การทำนายอนาคตที่แน่นอน ควรใช้ประกอบการตัดสินใจร่วมกับข้อมูลอื่น

## ขั้นตอนถัดไปที่ต่อยอดได้
- เพิ่มแหล่งข้อมูลอื่น (Twitter/X เพิ่มบัญชี, YouTube comments ฯลฯ) — เพิ่มไฟล์ `scrape_<platform>.py`
  ใหม่แล้ว normalize เข้าตาราง `community_posts` เดียวกันได้เลย (ดูตัวอย่างจาก `scrape_facebook.py`)
- เชื่อมโยงสอง insight เข้าด้วยกัน เช่น ดูว่าช่วงที่กระแสเกม EA FC 27 พุ่ง (จาก X/Reddit) เพจขายเหรียญ
  ปรับราคา/โพสต์ถี่ขึ้นตามไหม (มีข้อมูลพร้อมอยู่แล้วในตารางเดียวกัน แค่ join ข้าม platform ใน pandas)
- เพิ่มการแจ้งเตือน (เช่น ผ่าน LINE Notify) เมื่อคู่แข่งลดราคาต่ำกว่าราคาเรา
