# 1. เลือก Base Image: ใช้ Python เวอร์ชัน 3.11 แบบ slim ซึ่งมีขนาดเล็ก
FROM python:3.11-slim

# 2. ตั้งค่า Working Directory: กำหนดโฟลเดอร์ทำงานหลักภายใน container เป็น /app
WORKDIR /app

# 3. คัดลอกไฟล์ Dependencies: คัดลอกไฟล์ requirements.txt เข้าไปก่อน
#    เพื่อใช้ประโยชน์จาก Docker cache ทำให้ build ครั้งถัดไปเร็วขึ้นถ้าไม่มีการแก้ dependency
COPY requirements.txt .

# 4. ติดตั้ง Dependencies: รันคำสั่ง pip install จากไฟล์ requirements.txt
#    --no-cache-dir ช่วยให้ image มีขนาดเล็กลง
RUN pip install --no-cache-dir -r requirements.txt

# 5. คัดลอกโค้ดทั้งหมด: คัดลอกไฟล์ที่เหลือทั้งหมดในโปรเจกต์ (เช่น mcp_client.py) เข้าไปใน /app
COPY . .
#COPY server.py .

ENV PORT=8017
EXPOSE 8017
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8017"]
