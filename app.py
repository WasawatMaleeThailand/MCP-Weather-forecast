# requirements:
#   pip install fastapi uvicorn httpx pydantic
# หมายเหตุ: นี่คือ bridge แบบเรียบง่ายที่ทำหน้าที่เป็น "MCP host" ระดับพื้นฐาน:
# - ทำ session ต่อครั้ง: ส่งข้อความ handshake + callTool ผ่าน Streamable HTTP
# - รับผลลัพธ์ tool แล้วคืนเป็น JSON REST ให้ n8n
# - เหมาะสำหรับใช้กับ MCP server ที่เปิดโหมด streamable-http (ปลายทาง …/mcp)

import json
import uuid
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# === ตั้งค่า MCP server ปลายทางของคุณ ===
MCP_URL = "https://server.smithery.ai/@myrve/weather-forecast-mcp-mevy/mcp"

app = FastAPI(title="MCP REST Bridge")

class CallBody(BaseModel):
    tool: str = Field(..., description="ชื่อ tool ที่จะเรียก เช่น get_forecast")
    args: Dict[str, Any] = Field(default_factory=dict, description="พารามิเตอร์ของ tool (dict)")
    # option เสริม: บังคับ model ให้ LLM plan เอง แต่ที่นี่เราเรียก tool ตรง ๆ ไม่ใช้ LLM
    metadata: Optional[Dict[str, Any]] = None


async def mcp_streamable_http_call(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    ทำ 'session สั้น' กับ MCP streamable-http:
      1) ส่ง 'initialize' กำหนดโปรโตคอลเวอร์ชัน
      2) ขอ listTools (เพื่อความถูกต้อง/ตรวจสอบชื่อเครื่องมือ - optional)
      3) callTool(tool, args)
      4) ปิด session

    หมายเหตุ: โค้ดนี้สร้าง 'ข้อความเฟรม' ตามสเปก Streamable HTTP พื้นฐาน (message-based).
    MCP implementations บางตัวอาจเคร่งรูปแบบมากกว่านี้—หากปลายทางไม่ยอมรับ ให้ดูเอกสารสเปกของเซิร์ฟเวอร์นั้น ๆ
    """
    rid_init = str(uuid.uuid4())
    rid_list = str(uuid.uuid4())
    rid_call = str(uuid.uuid4())
    rid_close = str(uuid.uuid4())

    # ข้อความตามลำดับ (ข้อความแต่ละอันเป็น JSON line)
    frames = [
        # 1) initialize
        {
            "type": "initialize",
            "id": rid_init,
            "protocolVersion": "2024-11-07",  # ใช้เวอร์ชันล่าสุดที่เซิร์ฟเวอร์รองรับได้
            "capabilities": {"tools": True, "resources": True}
        },
        # 2) list tools (optional แต่ช่วย fail-fast ถ้าไม่มีเครื่องมือ)
        {"type": "listTools", "id": rid_list},
        # 3) call tool
        {
            "type": "callTool",
            "id": rid_call,
            "name": tool,
            "arguments": args
        },
        # 4) shutdown (optional)
        {"type": "shutdown", "id": rid_close}
    ]

    # streamable-http: ส่งเป็น NDJSON หรือ JSON array (แล้วแต่เซิร์ฟเวอร์)
    # เซิร์ฟเวอร์ Smithery รองรับการส่งเป็นบอดี้ JSON array (ตามตัวอย่าง public)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(MCP_URL, json=frames)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, f"MCP upstream error: {resp.text}")

        data = resp.json()
        # data มักเป็น array ของ "frames ตอบกลับ" เราต้องหาคำตอบของ callTool (id = rid_call)
        call_result: Optional[Dict[str, Any]] = None
        tools_list: Optional[Dict[str, Any]] = None

        for f in data if isinstance(data, list) else [data]:
            if not isinstance(f, dict):
                continue
            if f.get("inReplyTo") == rid_list:
                tools_list = f
            if f.get("inReplyTo") == rid_call:
                call_result = f

        if tools_list and "error" in tools_list:
            raise HTTPException(400, f"MCP listTools error: {tools_list.get('error')}")

        if not call_result:
            # บาง server อาจส่งรูปแบบต่างไป ลองเดางานคืน (fallback)
            # หาค่าที่เป็นผลลัพธ์ tool ตัวแรก
            for f in data if isinstance(data, list) else [data]:
                if f.get("type") in ("toolResult", "result", "response"):
                    call_result = f
                    break

        if not call_result:
            raise HTTPException(502, f"No tool result found in MCP response: {data}")

        # โครงสร้างผลลัพธ์ MCP มักให้ payload อยู่ใน field เช่น 'content' หรือ 'result'
        payload = call_result.get("result") or call_result.get("content") or call_result
        return {"frames": data, "payload": payload}

@app.post("/mcp/call")
async def call_tool(body: CallBody):
    try:
        result = await mcp_streamable_http_call(body.tool, body.args)
        return {"ok": True, "tool": body.tool, "args": body.args, "data": result["payload"]}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(500, f"Bridge error: {e}")
