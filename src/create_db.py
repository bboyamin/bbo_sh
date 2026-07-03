import sqlite3

def create_welfare_db():
    # 1. welfare.db 라는 데이터베이스 파일에 연결 (없으면 새로 생성됩니다)
    conn = sqlite3.connect("welfare.db")
    cursor = conn.cursor()

    # 2. 복지 정책을 저장할 테이블(표) 만들기
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS welfare_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,          -- 혜택 이름
        min_age INTEGER,             -- 최소 나이 조건
        max_age INTEGER,             -- 최대 나이 조건
        region TEXT,                 -- 거주 지역 조건
        is_employed INTEGER,         -- 직장인 여부 (1: 직장인, 0: 상관없음)
        min_children INTEGER,        -- 최소 자녀 수 조건
        description TEXT             -- 상세 설명
    )
    """)

    # 3. 테스트용 공공 복지 데이터 준비
    policies = [
        ("어르신 무상 교통카드 지원", 65, 150, "서울", 0, 0, "서울시에 거주하는 만 65세 이상 어르신에게 지하철 무임승차가 가능한 우대용 교통카드를 발급합니다."),
        ("청년 희망 저축통장 지원", 19, 34, "전국", 1, 0, "근로 중인 청년의 자산 형성을 돕기 위해, 저축액에 상응하는 정부 지원금을 추가 매칭 적립해 드립니다."),
        ("다자녀 양육 수당 지원", 19, 150, "전국", 0, 2, "자녀가 2명 이상인 다자녀 가구를 대상으로 매월 일정 금액의 보육 및 양육 수당을 지급합니다."),
        ("서울시 청년 수당", 19, 34, "서울", 0, 0, "서울시에 거주하는 미취업 청년들의 활동 지원을 위해 매월 50만 원씩 최대 6개월간 지원합니다.")
    ]

    # 4. 준비된 데이터를 테이블에 삽입하기
    cursor.executemany("""
    INSERT INTO welfare_policies (name, min_age, max_age, region, is_employed, min_children, description)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, policies)

    # 5. 저장 및 연결 종료
    conn.commit()
    conn.close()
    print("✅ welfare.db 복지 데이터베이스 구축 성공!")

if __name__ == "__main__":
    create_welfare_db()
