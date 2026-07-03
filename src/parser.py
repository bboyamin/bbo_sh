import os
import zipfile
import xml.etree.ElementTree as ET
import fitz  # PyMuPDF

def parse_hwpx(file_path):
    """
    HWPX 파일의 압축을 풀어 section0.xml 내부의 단락(<hp:p>) 및 텍스트(<hp:t>) 데이터를 
    순수 파이썬 기본 xml 엔진으로 정밀 파싱해 가져옵니다. (한글 프로그램 불필요)
    """
    text_content = []
    try:
        with zipfile.ZipFile(file_path) as z:
            sec_file = None
            # HWPX의 실제 본문 내용 XML 파일명 탐색
            for name in z.namelist():
                if "section0.xml" in name:
                    sec_file = name
                    break
            
            if not sec_file:
                return "[오류] HWPX 본문 XML 데이터를 찾을 수 없습니다."
                
            xml_data = z.read(sec_file)
            root = ET.fromstring(xml_data)
            
            # HWPML 2011 파라그래프/섹션 네임스페이스 사전 정의
            ns = {
                'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
                'hs': 'http://www.hancom.co.kr/hwpml/2011/section'
            }
            
            # hp:p 태그를 돌며 문장 획득
            for p in root.findall('.//hp:p', ns):
                p_text = []
                # hp:t(텍스트 노드) 파싱
                for t in p.findall('.//hp:t', ns):
                    if t.text:
                        p_text.append(t.text)
                if p_text:
                    text_content.append("".join(p_text))
                    
        return "\n".join(text_content)
    except Exception as e:
        return f"[오류] HWPX 파싱 실패: {str(e)}"

def parse_pdf(file_path):
    """
    PyMuPDF(fitz) 라이브러리를 가동해 PDF 문서를 페이지별로 순회하며 
    텍스트 레이아웃을 고속 추출합니다.
    """
    text_content = []
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            if text:
                text_content.append(f"--- [페이지 {page_num + 1}] ---\n" + text)
        return "\n".join(text_content)
    except Exception as e:
        return f"[오류] PDF 파싱 실패: {str(e)}"

def extract_text_from_file(file_path):
    """
    전달된 파일의 확장자를 감별하여 HWPX / PDF 파서로 분기해 텍스트를 추출합니다.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".hwpx":
        return parse_hwpx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    else:
        return f"[오류] 지원하지 않는 파일 형식입니다: {ext}"
