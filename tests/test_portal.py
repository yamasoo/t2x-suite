# -*- coding: utf-8 -*-
"""t2x-suite Portal 單元測試（純標準函式庫）。"""
import sys
import unittest
from pathlib import Path
from unittest import mock

PORTAL_DIR = Path(__file__).resolve().parents[1] / "portal"
if str(PORTAL_DIR) not in sys.path:
    sys.path.insert(0, str(PORTAL_DIR))

import server as portal_server  # noqa: E402


class TestPortalOverview(unittest.TestCase):
    def test_build_overview_merges_ns_t2vn_and_comics(self):
        def fake_get_json(url: str, timeout: float = 2.0):
            if url.endswith(":8765/api/config"):
                return True, {"version": "3.2.0"}
            if url.endswith(":8765/api/books"):
                return True, {
                    "books": [
                        {
                            "id": "book_alpha",
                            "name": "範例作品甲",
                            "is_book": True,
                            "lang": "zh-TW",
                            "chapters_written": 12,
                            "chapters_planned": 20,
                            "pending_candidates": 1,
                            "chars": 36000,
                            "unit": "字",
                        },
                        {
                            "id": "book_beta",
                            "name": "範例作品乙",
                            "is_book": True,
                            "lang": "zh-TW",
                            "chapters_written": 3,
                            "chapters_planned": 10,
                            "pending_candidates": 0,
                            "chars": 9000,
                            "unit": "字",
                        },
                    ]
                }
            if url.endswith(":7866/api/settings"):
                return True, {"comfyui": {"base_url": "http://127.0.0.1:8188"}}
            if url.endswith(":7866/api/books"):
                return True, {
                    "books": [
                        {
                            "book_id": "alpha",
                            "display_name": "範例作品甲",
                            "lang": "zh-TW",
                            "source_kind": "library",
                            "source_dir": "book_alpha",
                            "chapters": 10,
                            "annotated": 8,
                            "reviewed": 5,
                        },
                        {
                            "book_id": "ext_only",
                            "display_name": "外部匯入作品",
                            "lang": "zh-TW",
                            "source_kind": "import",
                            "source_dir": "",
                            "chapters": 4,
                            "annotated": 2,
                            "reviewed": 1,
                        },
                    ],
                    "library": [
                        {"dir_name": "book_beta", "visual_cards": 6},
                    ],
                }
            if url.endswith("/api/books/alpha/comic"):
                return True, {"projects": [{"project_id": "main", "title": "主線漫畫", "broken": False}]}
            if url.endswith("/api/books/ext_only/comic"):
                return True, {"projects": []}
            return False, None

        with mock.patch.object(portal_server, "_http_get_json", side_effect=fake_get_json), mock.patch.object(
            portal_server, "_http_ping", return_value=True
        ):
            res = portal_server.build_overview("http://127.0.0.1:8765", "http://127.0.0.1:7866")

        self.assertTrue(res["services"]["novel_studio"]["online"])
        self.assertEqual(res["services"]["novel_studio"]["version"], "3.2.0")
        self.assertTrue(res["services"]["t2vn"]["online"])
        self.assertTrue(res["services"]["comfyui"]["online"])

        by_key = {b["key"]: b for b in res["books"]}
        self.assertEqual(set(by_key.keys()), {"book_alpha", "book_beta", "ext_only"})

        alpha = by_key["book_alpha"]
        self.assertTrue(alpha["t2vn"]["imported"])
        self.assertEqual(alpha["t2vn"]["book_id"], "alpha")
        self.assertEqual(alpha["t2vn"]["reviewed"], 5)
        self.assertEqual(alpha["comic"]["count"], 1)

        beta = by_key["book_beta"]
        self.assertFalse(beta["t2vn"]["imported"])
        self.assertEqual(beta["ns"]["visual_cards"], 6)

        ext = by_key["ext_only"]
        self.assertIsNone(ext["ns"])
        self.assertTrue(ext["t2vn"]["imported"])

    def test_build_overview_offline_graceful(self):
        with mock.patch.object(portal_server, "_http_get_json", return_value=(False, None)), mock.patch.object(
            portal_server, "_http_ping", return_value=False
        ):
            res = portal_server.build_overview("http://127.0.0.1:1", "http://127.0.0.1:2")
        self.assertFalse(res["services"]["novel_studio"]["online"])
        self.assertFalse(res["services"]["t2vn"]["online"])
        self.assertEqual(res["books"], [])

    def test_themes_catalog_valid(self):
        import json
        import re

        themes_path = PORTAL_DIR / "themes.json"
        self.assertTrue(themes_path.is_file())
        themes = json.loads(themes_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(themes), 10)
        required_tokens = {
            "bg", "bg-elev", "bg-sunken", "fg", "fg-muted", "fg-faint",
            "line", "line-strong", "accent", "accent-hover", "accent-soft", "on-accent",
            "info", "info-soft", "ok", "ok-soft", "warn", "warn-soft", "err", "err-soft",
        }
        ids = set()
        for t in themes:
            self.assertNotIn(t["id"], ids)
            ids.add(t["id"])
            self.assertIn(t["scheme"], ("light", "dark"))
            self.assertEqual(len(t["swatches"]), 4)
            self.assertTrue(required_tokens.issubset(set(t["tokens"].keys())))
            for val in t["tokens"].values():
                self.assertRegex(val, r"^#[0-9a-fA-F]{6}$")


if __name__ == "__main__":
    unittest.main()
