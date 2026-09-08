"""รันทั้ง pipeline ในคำสั่งเดียว: ดึงข้อมูลจากทุกแหล่ง (X + Reddit + Facebook Pages) -> AI วิเคราะห์ -> สรุป"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import scrape_x
import scrape_reddit
import scrape_facebook
import ai_analyze
import analyze


if __name__ == "__main__":
    print("### STEP 1/5: ดึงทวีตจาก X (Twitter) ###")
    scrape_x.main()

    print("\n### STEP 2/5: ดึงโพสต์จาก Reddit ###")
    scrape_reddit.main()  # ข้ามแบบไม่ error อัตโนมัติถ้าปิดไว้หรือยังไม่ได้ตั้งค่า

    print("\n### STEP 3/5: ดึงโพสต์จากเพจ Facebook ###")
    scrape_facebook.main()  # ข้ามแบบไม่ error อัตโนมัติถ้าปิดไว้หรือยังไม่ได้ตั้งค่า

    print("\n### STEP 4/5: ให้ AI วิเคราะห์ relevance/sentiment/หัวข้อ + ราคา/โปรโมชั่น (Facebook) ###")
    ai_analyze.main()

    print("\n### STEP 5/5: สรุปเทรนด์ ###")
    analyze.main()
