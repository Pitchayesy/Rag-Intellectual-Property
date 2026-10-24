#!/usr/bin/env python3
"""Interactive command-line chat over the legal vector database."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rag import answer_question

BASE_DIR = Path(__file__).resolve().parent.parent


def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        # rag module already loaded dotenv; re-check
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit("Error: set GOOGLE_API_KEY in .env")

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

        print("\n--- กำลังค้นและคิดคำตอบ... ---")
        try:
            result = answer_question(question)
        except Exception as exc:
            print(f"เกิดข้อผิดพลาด: {exc}")
            continue
        print("\nคำตอบ:")
        print(result["answer"])
        print("\nเอกสารต้นทาง:")
        for s in result["sources"]:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
