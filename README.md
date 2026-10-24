# Legal RAG (LangChain + SQLite Vector)

ระบบถามตอบกฎหมายไทย จากไฟล์ Markdown ใน `data/`
ใช้ Google AI Studio (Gemini) เป็นทั้ง embedding และ LLM, เก็บเวกเตอร์ใน SQLite ผ่าน `sqlite-vec`

## Setup

```powershell
pip install -r requirements.txt
Copy-Item .env.example .env
# แล้วแก้ .env ใส่ GOOGLE_API_KEY ของคุณ (ขอได้ที่ https://aistudio.google.com/apikey)
```

> ห้าม commit ไฟล์ `.env` — ถูก ignore ไว้แล้วใน `.gitignore`

## Build index

```powershell
python backend/ingest.py
```

- อ่านทุก `data/*.md`
- แบ่ง chunk 1200 ตัวอักษร (overlap 200)
- embed ด้วย `gemini-embedding-001` (768 มิติ)
- สร้าง/ต่อ `legal_rag.db` (ที่ root)
- ถ้าไฟล์ DB มีอยู่แล้ว จะ **resume** ต่อจาก chunk ที่ embed ไปแล้ว (ไม่ต้องเริ่มใหม่) และรออัตโนมัติเมื่อเจอ rate limit
- ถ้าแก้ไฟล์ใน `data/` แล้วอยากสร้างใหม่ทั้งหมด ให้ลบ `legal_rag.db` ก่อน

## Chat

```powershell
python backend/chat.py
```

- ค้น 6 chunks ที่เกี่ยวข้อง (cosine)
- ตอบด้วย `gemini-3.8-flash` โดยอ้างอิงเฉพาะ context
- แสดงเอกสารต้นทางท้ายคำตอบ
- พิมพ์ `/exit` เพื่อออก

## Web UI

```powershell
pip install -r requirements.txt   # ถ้ายังไม่ได้ติดตั้ง fastapi/uvicorn
python backend/server.py            # http://127.0.0.1:8000
python backend/server.py 8080       # port กำหนดเอง
```

เปิดเบราว์เซอร์ไปที่ `http://127.0.0.1:8000` — หน้า chat จะเรียก `POST /api/chat` ที่ backend โดยอัตโนมัติ

| ไฟล์ | หน้าที่ |
|---|---|
| `backend/ingest.py` | โหลด → chunk → embed → เก็บ SQLite |
| `backend/chat.py` | CLI ถามตอบ RAG |
| `.env.example` | ตัวอย่างไฟล์ตั้งค่า environment (คัดลอกเป็น `.env`) |
| `data/*.md` | แหล่งข้อมูลกฎหมาย |
| `data/pdf2md.py` | แปลง PDF → Markdown (ใช้ตอนเตรียมข้อมูล) |
| `frontend/` | หน้าเว็บ (login, chat) |
| `docs/` | เอกสารประกอบโปรเจกต์ |
