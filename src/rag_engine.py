import os
import sqlite3
import re

# 📂 로컬 SQLite 데이터베이스 파일 저장 경로
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../chroma_db"))
os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, "rag_documents.db")

def init_db():
    """
    RAG용 SQLite 데이터베이스 테이블을 1회 초기화합니다.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            chunk_index INTEGER,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()

# 임포트 시점 초기화 실행
init_db()

def split_text(text, chunk_size=800, overlap=150):
    """
    문서의 맥락이 깨지지 않도록 슬라이딩 윈도우 방식으로 텍스트를 쪼갭니다.
    """
    chunks = []
    text = text.strip()
    if not text:
        return chunks
        
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += (chunk_size - overlap)
        
    return chunks

def index_document(filename, text):
    """
    추출된 본문 텍스트를 문맥 조각(Chunk)으로 쪼개고 SQLite 테이블에 적재합니다.
    중복 등록을 방지하기 위해 기존 해당 파일명의 조각들은 1차 제거합니다.
    """
    chunks = split_text(text)
    if not chunks:
        return 0
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. 중복 제거
    cursor.execute("DELETE FROM document_chunks WHERE filename = ?", (filename,))
    
    # 2. 청크 적재
    for i, chunk in enumerate(chunks):
        cursor.execute(
            "INSERT INTO document_chunks (filename, chunk_index, content) VALUES (?, ?, ?)",
            (filename, i, chunk)
        )
        
    conn.commit()
    conn.close()
    return len(chunks)

def search_relevant_contexts(query, n_results=3):
    """
    자연어 질문(Query)에서 주요 형태소/키워드를 추출하고, 
    각 청크의 본문 텍스트 내 키워드 매칭 개수(빈도)를 스코어링하여 가장 유사한 Top-K 청크를 골라 반환합니다.
    """
    # 질문에서 조사, 특수문자를 제외한 2글자 이상의 검색 키워드 단어 필터링
    keywords = [w for w in re.split(r'[^a-zA-Z0-9가-힣]+', query) if len(w) > 1]
    if not keywords:
        keywords = [query] if query.strip() else []
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 전체 지식베이스 로드
    cursor.execute("SELECT filename, chunk_index, content FROM document_chunks")
    rows = cursor.fetchall()
    
    scored_chunks = []
    if keywords:
        for filename, chunk_index, content in rows:
            score = 0
            # 키워드 매칭 점수 집계 (빈도 누적)
            for kw in keywords:
                score += content.count(kw)
                
            if score > 0:
                scored_chunks.append((score, content, filename, chunk_index))
                
    # 🌟 [Fallback] 요약 요구나 키워드 매칭 실패 시, 빈손으로 돌아가지 않고 
    # 문서의 가장 앞부분(chunk_index가 작은 상위 3개 문단)을 기본 참고 문맥으로 매칭해 줍니다.
    if not scored_chunks and rows:
        # chunk_index 순으로 정렬하여 상위 n_results 개를 기본으로 태워 보냅니다.
        rows.sort(key=lambda x: x[1])
        for filename, chunk_index, content in rows[:n_results]:
            scored_chunks.append((1, content, filename, chunk_index))
            
    conn.close()
    
    # 매칭 점수가 높은 순으로 정렬
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    contexts = []
    for score, content, filename, chunk_index in scored_chunks[:n_results]:
        contexts.append({
            "text": content,
            "filename": filename,
            "chunk_index": chunk_index
        })
        
    return contexts

def get_indexed_files():
    """
    현재 데이터베이스에 누적 기입되어 서비스 중인 한글/PDF 파일명 목록을 조회합니다.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT filename FROM document_chunks")
    rows = cursor.fetchall()
    conn.close()
    return sorted([row[0] for row in rows])

def delete_all_documents():
    """
    지식베이스 전체를 포맷합니다.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM document_chunks")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to clear SQLite DB: {e}")
        return False
