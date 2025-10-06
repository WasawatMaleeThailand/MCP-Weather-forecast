# MCP REST Bridge

Bridge นี้แปลง REST ⇄ MCP (Streamable HTTP) เพื่อให้ระบบอย่าง n8n เรียกใช้ MCP Server ได้ง่าย ๆ

## วิธีใช้งาน (Local)
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
