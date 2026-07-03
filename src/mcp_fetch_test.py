import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 1. 실행할 Fetch MCP 서버의 파라미터 정의 (npx mcp-fetch-server 실행)
    # 이 서버는 Node.js 환경에서 통로 오염 없이 깔끔하게 작동하도록 빌드된 상용 서버입니다.
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y", 
            "mcp-fetch-server"
        ]
    )

    # 2. stdio_client를 사용해 백그라운드에서 Fetch MCP 서버 시작
    print("🔌 웹 Fetch MCP 서버에 연결을 시도하는 중 (npx 가동)...")
    async with stdio_client(server_params) as (read, write):
        
        # 3. 세션 열기 및 초기화
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ MCP 세션이 성공적으로 연결 및 초기화되었습니다.")
            
            # 4. 사용 가능한 도구 목록 조회
            print("🔍 서버가 제공하는 도구 목록을 요청하는 중...")
            tools_response = await session.list_tools()
            
            print("\n==========================================")
            print("🛠️ Fetch MCP 서버에서 제공하는 도구 목록:")
            print("==========================================")
            for tool in tools_response.tools:
                print(f"- 도구 이름: {tool.name}")
                print(f"  설명: {tool.description}")
                print(f"  인자 구조(Schema): {tool.inputSchema}\n")
            
            # 5. 실제로 웹 페이지 가져오기 도구(fetch) 호출 
            # (예시로 https://example.com 의 본문 긁어오기)
            target_url = "https://example.com"
            print(f"🚀 [도구 실행] 'fetch' 도구를 호출하여 '{target_url}' 본문 읽기를 요청하는 중...")
            
            try:
                fetch_result = await session.call_tool(
                    name="fetch",
                    arguments={"url": target_url}
                )
                
                print("\n==========================================")
                print("🌐 웹 페이지 읽기 결과 (마크다운 포맷):")
                print("==========================================")
                for content in fetch_result.content:
                    print(content.text)
                    
            except Exception as e:
                print(f"❌ 도구 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
