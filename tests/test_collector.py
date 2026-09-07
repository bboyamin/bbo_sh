import unittest
import sys
import os
import re

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.local_issue_collector import clean_base_url, is_duplicate_issue, deduplicate_issues, collect_all_issues

class TestLocalIssueCollector(unittest.TestCase):

    def test_clean_base_url(self):
        url1 = "https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions"
        self.assertEqual(clean_base_url(url1), "https://factchat-cloud.mindlogic.ai/v1/gateway")

        url2 = "https://factchat-cloud.mindlogic.ai/v1/gateway/"
        self.assertEqual(clean_base_url(url2), "https://factchat-cloud.mindlogic.ai/v1/gateway")

        url3 = ""
        self.assertEqual(clean_base_url(url3), "https://factchat-cloud.mindlogic.ai/v1/gateway")

    def test_title_dot_cleaning(self):
        title_with_dots = "용인 처인구 반도체 클러스터 우회도로 확장 공사 승인........"
        cleaned = re.sub(r'\.\.\.+$', '', title_with_dots).strip()
        self.assertEqual(cleaned, "용인 처인구 반도체 클러스터 우회도로 확장 공사 승인")
        self.assertTrue(len(cleaned) > 20)

    def test_similarity_deduplication(self):
        item_a = {"title": "용인 처인구 반도체 클러스터 연계 도로망 대폭 확충 확정"}
        item_b = {"title": "용인 처인구 반도체 클러스터 연계 도로망 대폭 확충 승인"}
        item_c = {"title": "용인시 경전철 신규 연장선 타당성 조사 결과 발표"}

        self.assertTrue(is_duplicate_issue(item_a, item_b))
        self.assertFalse(is_duplicate_issue(item_a, item_c))

    def test_collect_all_issues_keyword_parameter(self):
        keywords = ["용인시", "처인구"]
        issues = collect_all_issues(keywords=keywords)
        self.assertIsInstance(issues, list)
        self.assertTrue(len(issues) > 0)
        
        # Verify title does not end with trailing dots
        for item in issues:
            self.assertFalse(item["title"].endswith("..."))

if __name__ == '__main__':
    unittest.main()
