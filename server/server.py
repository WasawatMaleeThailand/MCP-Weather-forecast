import os
import uuid
from typing import Dict, Any, List, Tuple
from fastapi import FastAPI, HTTPException, Request
import httpx

app = FastAPI(title="MCP Weather Forecast Server")

# ====== Configs ======
# เลือก provider สาธารณะ (ฟรี) สำหรับ geocoding+forecast
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# รายการเครื่องมือของเซิร์ฟเวอร์นี้
TOOLS = [
    {
        "name": "get_forecast",
        "description": "Get simple daily weather forecast by city name",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7}
            },
            "required": ["city"],
            "additionalProperties": False
        }
    },
]

def frame_reply(in_reply_to: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """ตอบเฟรมมาตรฐาน พร้อม inReplyTo"""
    out = {"inReplyTo": in_reply_to}
    out.update(payload)
    return out

async def geocode_city(city: str) -> Tuple[float, float, str]:
    params = {"name": city, "count": 1, "language": "en"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(GEO_URL, params=params)
        r.raise_for_status()
        data = r.json()
    results = data.get("results") or []
    if not results:
        raise HTTPException(404, f"City '{city}' not found")
    top = results[0]
    return float(top["latitude"]), float(top["longitude"]), f"{top['name']}, {top.get('country','')}"

async def fetch_forecast(city: str, days: int) -> Dict[str, Any]:
    lat, lon, label = await geocode_city(city)
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ["temperature_2m_max","temperature_2m_min","precipitation_sum"],
        "timezone": "auto"
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(FORECAST_URL, params=params)
        r.raise_for_status()
        data = r.json()
    daily = data.get("daily", {})
    # ตัดเหลือ N วันแรก (days) แบบปลอดภัย
    out = []
    for i, date in enumerate(daily.get("time", [])):
        if i >= max(1, min(days or 3, 7)):
            break
        out.append({
            "date": date,
            "t_max": daily.get("temperature_2m_max", [None]*len(daily.get("time",[])))[i],
            "t_min": daily.get("temperature_2m_min", [None]*len(daily.get("time",[])))[i],
            "precip_mm": daily.get("precipitation_sum", [None]*len(daily.get("time",[])))[i],
        })
    return {"city": label, "lat": lat, "lon": lon, "days": len(out), "daily": out}

@app.post("/mcp")
async def mcp_endpoint(req: Request):
    """
    รับ array ของ frames:
      - { "type": "initialize", "id": "...", "protocolVersion": "...", "capabilities": {...} }
      - { "type": "listTools",  "id": "..." }
      - { "type": "callTool",   "id": "...", "name": "get_forecast", "arguments": {...} }
      - { "type": "shutdown",   "id": "..." }
    ตอบกลับเป็น array ของ frames ที่มี "inReplyTo"
    """
    try:
        frames = await req.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(frames, list):
        raise HTTPException(400, "Payload must be a JSON array of frames")

    replies: List[Dict[str, Any]] = []

    for f in frames:
        ftype = f.get("type")
        fid = f.get("id") or str(uuid.uuid4())

        # 1) initialize
        if ftype == "initialize":
            replies.append(frame_reply(fid, {
                "type": "initialized",
                "serverInfo": {
                    "name": "mcp-weather-forecast",
                    "version": "0.1.0"
                },
                "protocolVersion": f.get("protocolVersion") or "2024-11-07",
                "capabilities": {"tools": True, "resources": False}
            }))

        # 2) listTools
        elif ftype == "listTools":
            replies.append(frame_reply(fid, {
                "type": "tools",
                "tools": TOOLS
            }))

        # 3) callTool
        elif ftype == "callTool":
            name = f.get("name")
            args = f.get("arguments") or {}
            if name != "get_forecast":
                replies.append(frame_reply(fid, {
                    "type": "error", "error": f"Unknown tool: {name}"
                }))
                continue

            city = str(args.get("city") or "").strip()
            days = int(args.get("days") or 3)
            if not city:
                replies.append(frame_reply(fid, {
                    "type": "error", "error": "Missing required argument: city"
                }))
                continue
            if days < 1 or days > 7:
                replies.append(frame_reply(fid, {
                    "type": "error", "error": "days must be between 1 and 7"
                }))
                continue

            try:
                data = await fetch_forecast(city, days)
                replies.append(frame_reply(fid, {
                    "type": "toolResult",
                    "result": data
                }))
            except HTTPException as e:
                replies.append(frame_reply(fid, {"type": "error", "error": str(e.detail)}))
            except Exception as e:
                replies.append(frame_reply(fid, {"type": "error", "error": f"internal error: {e}"}))

        # 4) shutdown (optional)
        elif ftype == "shutdown":
            replies.append(frame_reply(fid, {"type": "ok"}))

        # อื่น ๆ
        else:
            replies.append(frame_reply(fid, {"type": "error", "error": f"Unknown frame type: {ftype}"}))

    return replies
