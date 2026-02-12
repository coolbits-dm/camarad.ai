#!/usr/bin/env python3
"""
Procesare PDF McKinsey AI-powered marketing & sales
Extrage text → curăță → chunk → generează title/summary → salvează JSONL + SQLite
"""

import os
import json
import datetime
import re
import sqlite3
from pathlib import Path
from typing import List, Dict

try:
    import pdfplumber
except ImportError:
    print("pdfplumber nu este instalat. Rulează: pip install pdfplumber")
    exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm nu este instalat. Rulează: pip install tqdm")
    tqdm = lambda x: x  # fallback no bar

# ── Config ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path("C:/grok/camarad/knowledge_base")
PDF_DIR = BASE_DIR / "pdfs"
EXTRACTED_DIR = BASE_DIR / "extracted"
DB_PATH = BASE_DIR / "knowledge.db"

PDF_NAME = "ai-powered-marketing-and-sales-reach-new-heights-with-generative-ai.pdf"
PDF_PATH = PDF_DIR / PDF_NAME

CHUNK_SIZE_MIN = 800
CHUNK_SIZE_MAX = 1200

EXTRACTED_JSONL = EXTRACTED_DIR / "ai-powered-marketing-chunks.jsonl"

# Creează foldere dacă nu există
EXTRACTED_DIR.mkdir(exist_ok=True)

def clean_text(text: str) -> str:
    """Curăță text extras din PDF"""
    text = re.sub(r'\n{2,}', '\n', text)           # multiple newlines → una
    text = re.sub(r'\s+', ' ', text)               # multiple spaces → unul
    text = text.replace('• ', '- ').replace('▪ ', '- ')  # bullets comune
    text = text.strip()
    return text

def split_into_chunks(text: str, min_size=CHUNK_SIZE_MIN, max_size=CHUNK_SIZE_MAX) -> List[str]:
    """Split inteligent în chunks respectând propoziții"""
    chunks = []
    current = ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sent in sentences:
        if len(current) + len(sent) <= max_size:
            current += " " + sent if current else sent
        else:
            if len(current) >= min_size:
                chunks.append(current.strip())
            current = sent
    
    if current and len(current) >= min_size // 2:
        chunks.append(current.strip())
    
    return chunks

def generate_title(chunk: str) -> str:
    """Titlu scurt auto-generat din primele 100-150 caractere"""
    prefix = chunk[:150].strip()
    words = prefix.split()[:12]
    title = " ".join(words)
    if len(title) > 80:
        title = title[:77] + "..."
    return title.capitalize()

def generate_summary(chunk: str) -> str:
    """Sumar scurt 1-3 propoziții, max 150 caractere"""
    sentences = re.split(r'(?<=[.!?])\s+', chunk)
    summary = " ".join(sentences[:3])
    if len(summary) > 150:
        summary = summary[:147] + "..."
    return summary

def main():
    if not PDF_PATH.exists():
        print(f"EROARE: Fișierul {PDF_PATH} nu există!")
        print("Verifică dacă l-ai descărcat corect în pdfs/")
        return

    print(f"Procesez: {PDF_NAME}")

    with pdfplumber.open(PDF_PATH) as pdf:
        full_text = ""
        for page in tqdm(pdf.pages, desc="Extrage pagini"):
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    cleaned_text = clean_text(full_text)
    chunks = split_into_chunks(cleaned_text)

    print(f"Text curat extras: {len(cleaned_text):,} caractere")
    print(f"Număr chunks generate: {len(chunks)}")

    # Pregătește SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT UNIQUE,
            title TEXT,
            summary TEXT,
            content TEXT,
            source TEXT,
            page_start INTEGER,
            page_end INTEGER,
            timestamp TEXT,
            embedding_placeholder TEXT DEFAULT ''
        )
    """)
    conn.commit()

    # Salvează JSONL + DB
    processed_chunks = []
    with open(EXTRACTED_JSONL, "w", encoding="utf-8") as jsonl_file:
        for i, chunk in enumerate(chunks, 1):
            title = generate_title(chunk)
            summary = generate_summary(chunk)
            chunk_id = f"{PDF_NAME}-{i:04d}"
            now = datetime.datetime.utcnow().isoformat()

            entry = {
                "chunk_id": chunk_id,
                "title": title,
                "summary": summary,
                "content": chunk,
                "metadata": {
                    "source_file": PDF_NAME,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "timestamp": now
                }
            }

            jsonl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            processed_chunks.append(entry)

            # Insert în SQLite (page_start/end aproximative – poți îmbunătăți)
            cursor.execute("""
                INSERT OR REPLACE INTO chunks 
                (chunk_id, title, summary, content, source, page_start, page_end, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, title, summary, chunk,
                PDF_NAME, 1, len(pdf.pages), now   # placeholder pages – îmbunătățește dacă vrei
            ))

    conn.commit()
    conn.close()

    print(f"\nGATA! Salvat:")
    print(f"  JSONL: {EXTRACTED_JSONL}")
    print(f"  DB:    {DB_PATH}")

    if processed_chunks:
        print("\nPrimul chunk:")
        print(f"Title: {processed_chunks[0]['title']}")
        print(f"Summary: {processed_chunks[0]['summary']}")
        print(f"Content preview: {processed_chunks[0]['content'][:200]}...")

        print("\nUltimul chunk:")
        print(f"Title: {processed_chunks[-1]['title']}")
        print(f"Summary: {processed_chunks[-1]['summary']}")
        print(f"Content preview: {processed_chunks[-1]['content'][:200]}...")

if __name__ == "__main__":
    main()