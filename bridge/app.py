import os
import json
import uuid
from typing import Optional, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field

app = FastAPI(title="MCP REST Bridge")

# MCP Server ปลายทาง (ค่าเริ่มต้นชี้ไปที่เซิร์ฟเวอร์ของเราเอง)
MCP_UPSTREAM_URL = os.environ.get("MCP_UPSTREAM_URL", "http://server:8017/mcp")

API_KEY = os.environ.get("API_KEY")  # ถ้าตั้งค่าไว้ จะบังคับ header X-API-Key

class CallBody(BaseModel):
    tool: str = Field(..., description="ชื่อ tool เช่น get_forecast")
    args: Dict[str, Any] = Field(default_factory=dict, description="อาร์กิวเมนต์ของ tool")

def make_frame(ftype: str, id_: Optional[str] = None, **extra) -> Dict[str, Any]:
    f = {"type": ftype, "id": id_ or str(uuid.uuid4())}
    f.update(extra)
    return f

async def call_mcp(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    rid_init = str(uuid.uuid4())
    rid_list = str(uuid.uuid4())
    rid_call = str(uuid.uuid4())
    rid_close = str(uuid.uuid4())

    frames = [
        make_frame("initialize", rid_init, protocolVersion="2024-11-07",
                   capabilities={"tools": True, "resources": True}),
        make_frame("listTools", rid_list),
        make_frame("callTool", rid_call, name=tool, arguments=args),
        make_frame("shutdown", rid_close),
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(MCP_UPSTREAM_URL, json=frames)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"MCP upstream error: {r.text}")
        data = r.json()

    # หาเฟรมผลลัพธ์ของ callTool
    result = None
    for f in data if isinstance(data, list) else [data]:
        if f.get("inReplyTo") == rid_call:
            result = f
            break
    if not result:
        # fallback: หาเฟรมลักษณะ result/response
        for f in data if isinstance(data, list) else [data]:
            if f.get("type") in ("toolResult", "result", "response"):
                result = f
                break
    if not result:
        raise HTTPException(502, f"No tool result frame in response: {data}")

    if result.get("type") == "error":
        raise HTTPException(400, f"MCP tool error: {result.get('error')}")

    payload = result.get("result") or result.get("content") or result
    return {"frames": data, "payload": payload}

@app.post("/mcp/call")
async def mcp_call(body: CallBody, x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")
    try:
        out = await call_mcp(body.tool, body.args)
        return {"ok": True, "tool": body.tool, "args": body.args, "data": out["payload"]}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(500, f"Bridge error: {e}")
