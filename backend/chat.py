#!/usr/bin/env python3
"""Interactive command-line chat over the legal vector database.

Retrieves the most relevant legal chunks for each user question and asks
Gemini to answer strictly from that context, citing the source document.

Usage:
    python chat.py
"""

import os
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
K = 6  # chunks to retrieve per question

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
    return "\n\n---\n\n".join(f"[ที่มา: {d.metadata.get('source', 'unknown')}]\n{d.page_content}" for d in docs)


def _invoke_with_retry(llm, messages, attempts: int = 4):
    """Invoke the LLM, backing off on 429 rate limits."""
    for attempt in range(1, attempts + 1):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            rate_limited = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)
            if not rate_limited or attempt == attempts:
                raise
            wait = 20 * attempt
            print(f"  ติด rate limit, รอ {wait} วินาทีแล้วลองใหม่ ({attempt}/{attempts - 1})...")
            time.sleep(wait)


def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit("Error: set GOOGLE_API_KEY in .env")
    if not DB_PATH.exists():
        sys.exit("Error: vector DB not found. Run `python ingest.py` first.")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBED_MODEL,
        output_dimensionality=EMBED_DIM,
        task_type="RETRIEVAL_QUERY",
    )
    db = SQLiteVec(
        table="law_chunks",
        connection=None,
        db_file=str(DB_PATH),
        embedding=embeddings,
    )
    llm = ChatGoogleGenerativeAI(model=CHAT_MODEL, temperature=0.1)

    print("=== ระบบถามตอบกฎหมาย (พิมพ์คำถาม, /exit เพื่อออก) ===")
    while True:
        try:
            question = input("\nคำถาม: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("/exit", "/quit", "exit", "quit"):
            break

        docs = db.similarity_search(question, k=K)
        if not docs:
            print("ไม่พบข้อมูลในฐานข้อมูล ลองรัน ingest.py ใหม่")
            continue

        print("\n--- กำลังค้นและคิดคำตอบ... ---")
        response = _invoke_with_retry(
            llm,
            [
                SystemMessage(SYSTEM_PROMPT),
                HumanMessage(f"CONTEXT (ข้อความจากเอกสารกฎหมาย):\n{build_context(docs)}\n\nคำถาม: {question}"),
            ],
        )
        print("\nคำตอบ:")
        print(response.text)
        print("\nเอกสารต้นทาง:")
        for d in docs:
            print(f"  - {d.metadata.get('source', 'unknown')}")


if __name__ == "__main__":
    main()
