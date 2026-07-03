import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 1. 실행할 상용 MCP 서버의 파라미터 정의 
    # (npx @modelcontextprotocol/server-sqlite --db welfare.db 명령어를 서브프로세스로 실행하게 설정)
    db_path = os.path.abspath("welfare.db")
    
    # 가상환경의 bin 폴더 아래에 있는 mcp-server-sqlite 실행파일 경로를 자동으로 조합
    bin_dir = os.path.dirname(sys.executable)
    mcp_sqlite_bin = os.path.join(bin_dir, "mcp-server-sqlite")
    
    server_params = StdioServerParameters(
        command=mcp_sqlite_bin,  # 자동 감지된 스크립트 실행파일 주소
        args=[
            "--db-path", 
            db_path
        ]
    )



    # 2. stdio_client를 사용해 백그라운드에서 SQLite MCP 서버 시작
    print("🔌 SQLite MCP 서버에 연결을 시도하는 중...")
    async with stdio_client(server_params) as (read, write):
        
        # 3. 세션 열기 및 초기화
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ MCP 세션이 성공적으로 연결 및 초기화되었습니다.")
            
            # 4. MCP 서버가 기본 제공하는 도구 목록 조회
            print("🔍 서버가 제공하는 도구 목록을 요청하는 중...")
            tools_response = await session.list_tools()
            
            print("\n==========================================")
            print("🛠️ SQLite MCP 서버에서 제공하는 도구 목록:")
            print("==========================================")
            for tool in tools_response.tools:
                print(f"- 도구 이름: {tool.name}")
                print(f"  설명: {tool.description}")
                print(f"  인자 구조(Schema): {tool.inputSchema}\n")

            # 5. 실제로 MCP 도구(read_query)를 사용하여 데이터베이스 직접 조회하기
            print("\n🚀 [도구 실행] read_query 도구를 사용하여 DB 조회를 요청하는 중...")
            query_result = await session.call_tool(
                name="read_query",
                arguments={"query": "SELECT name, min_age, region, description FROM welfare_policies"}
            )
            
            print("\n==========================================")
            print("📊 MCP 도구 실행 결과 (DB 데이터):")
            print("==========================================")
            for content in query_result.content:
                print(content.text)

if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(main())
