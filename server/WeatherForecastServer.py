# mcp_client.py
import requests
import json
import uuid

# --- Config ---
# URL ของ MCP Server ที่ได้จากไฟล์แนบ
MCP_URL = "https://server.smithery.ai/@myrve/weather-forecast-mcp-mevy/m"

def send_mcp_frames(frames: list):
    """
    ฟังก์ชันสำหรับส่ง Frames ไปยัง MCP Server และรับการตอบกลับ
    """
    print("-----------------------------------------")
    print(f"REQUEST --> {json.dumps(frames)}")
    
    try:
        # ส่ง POST request พร้อมข้อมูล JSON และตั้งค่า header
        response = requests.post(
            MCP_URL,
            json=frames,
            headers={"Content-Type": "application/json"},
            timeout=60 # รอการตอบกลับสูงสุด 60 วินาที
        )
        # หากเซิร์ฟเวอร์ตอบกลับมาเป็น error (เช่น 404, 500) ให้โปรแกรมหยุด
        response.raise_for_status()
        
        # แปลงข้อมูลตอบกลับจาก JSON เป็น Python object
        replies = response.json()
        print(f"RESPONSE <-- {json.dumps(replies)}")
        return replies

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้: {e}")
        return None

def main():
    """
    ฟังก์ชันหลักในการทำงานของ Client
    """
    print(f"🚀 เริ่มต้นการเชื่อมต่อกับ MCP Server ที่: {MCP_URL}\n")

    # === ขั้นตอนที่ 1: Initialize ===
    # เป็นการ "ทักทาย" เซิร์ฟเวอร์เพื่อเริ่มการสื่อสาร
    print("ขั้นตอนที่ 1: กำลังส่งคำสั่ง 'initialize'...")
    init_frame = [{
        "type": "initialize",
        "id": f"init-{uuid.uuid4()}",
        "protocolVersion": "2024-11-07"
    }]
    send_mcp_frames(init_frame)

    # === ขั้นตอนที่ 2: List Tools ===
    # ถามเซิร์ฟเวอร์ว่ามีความสามารถ (Tools) อะไรบ้าง
    print("\nขั้นตอนที่ 2: กำลังส่งคำสั่ง 'listTools'...")
    list_tools_frame = [{
        "type": "listTools",
        "id": f"list-{uuid.uuid4()}"
    }]
    send_mcp_frames(list_tools_frame)

    # === ขั้นตอนที่ 3: Call Tool "get_forecast" ===
    # เรียกใช้งานเครื่องมือพยากรณ์อากาศ
    print("\nขั้นตอนที่ 3: กำลังเรียกใช้ 'get_forecast' สำหรับกรุงเทพฯ 5 วัน...")
    city_to_forecast = "Bangkok"
    days_to_forecast = 5
    
    call_tool_frame = [{
        "type": "callTool",
        "id": f"call-{uuid.uuid4()}",
        "name": "get_forecast",
        "arguments": {
            "city": city_to_forecast,
            "days": days_to_forecast
        }
    }]
    
    replies = send_mcp_frames(call_tool_frame)

    # === ขั้นตอนที่ 4: แสดงผลลัพธ์ที่สวยงาม ===
    # นำผลลัพธ์ที่ได้จากขั้นตอนที่ 3 มาจัดรูปแบบให้อ่านง่าย
    if replies and isinstance(replies, list) and replies[0].get("type") == "toolResult":
        result = replies[0].get("result", {})
        print("\n✅ ได้รับผลการพยากรณ์อากาศสำเร็จ!")
        print("-----------------------------------------")
        print(f"📍 เมือง: {result.get('city')}")
        print(f"📅 จำนวนวัน: {result.get('days')}")
        print("-----------------------------------------")
        
        for day_data in result.get("daily", []):
            print(f"  - วันที่: {day_data.get('date')}")
            print(f"    - อุณหภูมิสูงสุด: {day_data.get('t_max')} °C")
            print(f"    - อุณหภูมิต่ำสุด: {day_data.get('t_min')} °C")
            print(f"    - ปริมาณฝน: {day_data.get('precip_mm')} mm\n")
    else:
        print("\n❌ ไม่ได้รับผลลัพธ์การพยากรณ์อากาศที่ถูกต้อง")


if __name__ == "__main__":
    main()
