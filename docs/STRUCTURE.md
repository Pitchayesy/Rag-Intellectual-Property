# โครงสร้างโปรเจกต์

```
Rag-Intellectual-Property/
├── backend/          # โค้ด Python (RAG pipeline)
│   ├── ingest.py     # โหลด → chunk → embed → เก็บ SQLite
│   └── chat.py       # CLI ถามตอบ RAG
├── frontend/         # หน้าเว็บ (login.html, chat.html)
├── data/             # แหล่งข้อมูลกฎหมาย (.md, .pdf, pdf2md.py)
├── docs/             # เอกสารประกอบ
├── .env.example      # ตัวอย่างตั้งค่า (คัดลอกเป็น .env)
├── .gitignore
├── README.md
├── requirements.txt
└── legal_rag.db      # vector DB (สร้างโดย ingest.py, ถูก ignore)
```

## การรัน

```powershell
# ที่ root ของโปรเจกต์
pip install -r requirements.txt
Copy-Item .env.example .env   # แล้วใส่ GOOGLE_API_KEY
python backend/ingest.py      # สร้าง legal_rag.db
python backend/chat.py         # เริ่มแชท
```
