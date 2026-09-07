from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import sys
import os

# Add project root to sys.path so we can import src.local_issue_collector
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.local_issue_collector import collect_all_issues
except ImportError:
    def collect_all_issues(keywords=None):
        return []

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        kw_str = params.get('keywords', ['용인시,처인구'])[0]
        keywords = [k.strip() for k in kw_str.split(',') if k.strip()]
        
        # Try loading static dataset for fallback
        static_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "data", "issues.json"))
        if not os.path.exists(static_file):
            static_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "LocalIssueNotifier", "data", "issues.json"))

        static_issues = []
        if os.path.exists(static_file):
            try:
                with open(static_file, 'r', encoding='utf-8') as f:
                    static_issues = json.load(f)
            except Exception:
                pass

        try:
            live_issues = collect_all_issues(keywords=keywords)
            if len(live_issues) >= 10:
                issues = live_issues
            else:
                issues = static_issues if len(static_issues) > len(live_issues) else live_issues
        except Exception as e:
            print("Vercel collect error:", e)
            issues = static_issues

        body = json.dumps(issues, ensure_ascii=False).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
