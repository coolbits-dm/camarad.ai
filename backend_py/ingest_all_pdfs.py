#!/usr/bin/env python3
"""
Procesează TOATE PDF-urile din knowledge_base/pdfs/ automat
Extrage → curăță → chunk → title/summary → JSONL per fișier + SQLite comun
"""

import os
import json
import datetime
import re
import sqlite3
from pathlib import Path
from typing import List

try:
    import pdfplumber
except ImportError:
    print("Instalează pdfplumber: pip install pdfplumber")
    exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Instalează tqdm: pip install tqdm")
    tqdm = lambda x: x

# ── Config ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path("C:/grok/camarad/knowledge_base")
PDF_DIR = BASE_DIR / "pdfs"
EXTRACTED_DIR = BASE_DIR / "extracted"
DB_PATH = BASE_DIR / "knowledge.db"

CHUNK_SIZE_MIN = 800
CHUNK_SIZE_MAX = 1200

EXTRACTED_DIR.mkdir(exist_ok=True)

def clean_text(text: str) -> str:
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('• ', '- ').replace('▪ ', '- ')
    return text.strip()

def split_into_chunks(text: str) -> List[str]:
    chunks = []
    current = ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sent in sentences:
        if len(current) + len(sent) <= CHUNK_SIZE_MAX:
            current += " " + sent if current else sent
        else:
            if len(current) >= CHUNK_SIZE_MIN:
                chunks.append(current.strip())
            current = sent
    
    if current and len(current) >= CHUNK_SIZE_MIN // 2:
        chunks.append(current.strip())
    
    return chunks

def generate_title(chunk: str) -> str:
    prefix = chunk[:150].strip()
    words = prefix.split()[:12]
    title = " ".join(words)
    return (title[:77] + "...") if len(title) > 80 else title.capitalize()

def generate_summary(chunk: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', chunk)
    summary = " ".join(sentences[:3])
    return (summary[:147] + "...") if len(summary) > 150 else summary

def process_pdf(pdf_path: Path):
    print(f"\nProcesez: {pdf_path.name}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        print(f"Eroare la deschidere {pdf_path.name}: {e}")
        return 0
    
    cleaned_text = clean_text(full_text)
    chunks = split_into_chunks(cleaned_text)
    
    print(f"  Text curat: {len(cleaned_text):,} caractere")
    print(f"  Chunks generate: {len(chunks)}")
    
    # JSONL per fișier
    jsonl_path = EXTRACTED_DIR / f"{pdf_path.stem}-chunks.jsonl"
    chunk_count = 0
    
    # SQLite
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
            timestamp TEXT
        )
    """)
    
    with open(jsonl_path, "w", encoding="utf-8") as jsonl_file:
        for i, chunk in enumerate(chunks, 1):
            title = generate_title(chunk)
            summary = generate_summary(chunk)
            chunk_id = f"{pdf_path.name}-{i:04d}"
            now = datetime.datetime.utcnow().isoformat()
            
            entry = {
                "chunk_id": chunk_id,
                "title": title,
                "summary": summary,
                "content": chunk,
                "metadata": {
                    "source_file": pdf_path.name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "timestamp": now
                }
            }
            jsonl_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            chunk_count += 1
            
            # Insert DB
            cursor.execute("""
                INSERT OR IGNORE INTO chunks 
                (chunk_id, title, summary, content, source, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chunk_id, title, summary, chunk, pdf_path.name, now))
    
    conn.commit()
    conn.close()
    
    print(f"  Salvat: {jsonl_path}")
    print(f"  Adăugat {chunk_count} chunks în DB")
    return chunk_count

def main():
    if not PDF_DIR.exists():
        print(f"Eroare: Directorul {PDF_DIR} nu există!")
        return
    
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print("Niciun PDF găsit în folder!")
        return
    
    print(f"Găsite {len(pdf_files)} PDF-uri:")
    for p in pdf_files:
        print(f"  - {p.name}")
    
    total_chunks = 0
    for pdf_path in tqdm(pdf_files, desc="Procesare PDF-uri"):
        total_chunks += process_pdf(pdf_path)
    
    print(f"\nFINISH!")
    print(f"Total chunks generate și salvate: {total_chunks}")
    print(f"Bază de date actualizată: {DB_PATH}")

if __name__ == "__main__":
    main()