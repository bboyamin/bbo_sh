import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Add src module to python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from local_issue_collector import collect_all_issues
except Exception as e:
    print("Collector import notice:", e)
    collect_all_issues = None

class DynamicHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/api/collect":
            query_params = urllib.parse.parse_qs(parsed_path.query)
            kw_param = query_params.get("keywords", ["용인시,처인구,용인특례시"])[0]
            keywords = [k.strip() for k in kw_param.split(",") if k.strip()]
            
            print(f"🔄 [/api/collect] 동적 키워드 수집 요청: {keywords}")
            if collect_all_issues:
                issues = collect_all_issues(keywords=keywords)
            else:
                issues = []
            
            output_path = os.path.join(os.path.dirname(__file__), "data", "issues.json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(issues, ensure_ascii=False).encode('utf-8'))
            return

        super().do_GET()

if __name__ == "__main__":
    port = 8080
    print(f"🚀 Custom Server running on http://localhost:{port}")
    server = HTTPServer(('0.0.0.0', port), DynamicHTTPHandler)
    server.serve_forever()
