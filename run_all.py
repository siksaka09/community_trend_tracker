"""รันทั้ง pipeline ในคำสั่งเดียว: ดึงข้อมูลจากทุกแหล่ง (X + Reddit) -> ให้ AI วิเคราะห์ -> สรุปเทรนด์"""
import scrape_x
import scrape_reddit
import ai_analyze
import analyze

if __name__ == "__main__":
    print("### STEP 1/4: ดึงทวีตจาก X (Twitter) ###")
    scrape_x.main()

    print("\n### STEP 2/4: ดึงโพสต์จาก Reddit ###")
    scrape_reddit.main()  # ข้ามแบบไม่ error อัตโนมัติถ้าปิดไว้หรือยังไม่ได้ตั้งค่า

    print("\n### STEP 3/4: ให้ AI วิเคราะห์ relevance/sentiment/หัวข้อ ###")
    ai_analyze.main()

    print("\n### STEP 4/4: สรุปเทรนด์ ###")
    analyze.main()
