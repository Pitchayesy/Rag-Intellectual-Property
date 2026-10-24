"""Shared RAG helpers used by both the CLI (chat.py) and the web server (server.py)."""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SQLiteVec

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
DB_PATH = BASE_DIR / "legal_rag.db"

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIM = 768
CHAT_MODEL = "gemini-3.8-flash"
K = 6

load_dotenv(BASE_DIR / ".env")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยวิเคราะห์กฎหมายไทย ตอบคำถามโดยอ้างอิงจากเอกสารกฎหมายที่ให้ใน CONTEXT เท่านั้น

กติกา:
1. ตอบเป็นภาษาไทย ชัดเจน อ้างมาตรา/หมวด/บรรพ ที่เกี่ยวข้องเสมอ
2. หาก CONTEXT มีคำตอบ ให้ยกข้อความหรือสรุปบทบัญญัติพร้อมระบุเลขมาตรา
3. หาก CONTEXT ไม่มีข้อมูลเพียงพอ ให้ตอบว่าไม่พบบทบัญญัติที่เกี่ยวข้องในเอกสารที่มี และแนะนำว่าควรศึกษากฎหมายใดต่อ
4. ห้ามเดาหรือใช้ความรู้นอก CONTEXT
5. ปิดท้ายด้วยข้อความสั้น ๆ ว่านี่เป็นข้อมูลเพื่อการศึกษา ไม่ใช่คำแนะนำทางกฎหมายอย่างเป็นทางการ"""


def build_context(docs: list[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[ที่มา: {d.metadata.get('source', 'unknown')}]\\n{d.page_content}" for d in docs
    )


def _invoke_with_retry(llm, messages, attempts: int = 4):
    for attempt in range(1, attempts + 1):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            rate_limited = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if not rate_limited or attempt == attempts:
                raise
            wait = 20 * attempt
            time.sleep(wait)


# แคช instance ที่สร้างหนักและใช้ร่วมกันได้อย่างปลอดภัย (HTTP clients)
_embeddings = None
_llm = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBED_MODEL,
            output_dimensionality=EMBED_DIM,
            task_type="RETRIEVAL_QUERY",
        )
    return _embeddings


def get_vector_db():
    # สร้างต่อ request: SQLiteVec ถือ sqlite3 connection ซึ่งไม่ปลอดภัยหากแชร์ข้าม thread
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"vector DB not found: {DB_PATH}. Run `python backend/ingest.py` first."
        )
    return SQLiteVec(
        table="law_chunks",
        connection=None,
        db_file=str(DB_PATH),
        embedding=get_embeddings(),
    )


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.1)
    return _llm


def answer_question(question: str) -> dict:
    """Return {'answer': str, 'sources': list[str]}."""
    db = get_vector_db()
    docs = db.similarity_search(question, k=K)
    if not docs:
        return {
            "answer": "ไม่พบข้อมูลในฐานข้อมูล ลองรัน ingest.py ใหม่",
            "sources": [],
        }
    llm = get_llm()
    response = _invoke_with_retry(
        llm,
        [
            SystemMessage(SYSTEM_PROMPT),
            HumanMessage(f"CONTEXT (ข้อความจากเอกสารกฎหมาย):\\n{build_context(docs)}\\n\\nคำถาม: {question}"),
        ],
    )
    sources = []
    seen = set()
    for d in docs:
        s = d.metadata.get("source", "unknown")
        if s not in seen:
            seen.add(s)
            sources.append(s)
    return {"answer": response.text, "sources": sources}
