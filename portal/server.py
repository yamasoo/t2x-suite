#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""t2x-suite Portal: 唯讀跨管線總覽伺服器（純 Python 標準函式庫，僅綁 127.0.0.1）。"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
INDEX_HTML = HERE / "index.html"
DEFAULT_NS_URL = "http://127.0.0.1:8765"
DEFAULT_T2VN_URL = "http://127.0.0.1:7866"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _env_url(name: str, fallback: str) -> str:
    return (os.environ.get(name) or fallback).strip().rstrip("/")


def _http_get_json(url: str, timeout: float = 2.0) -> tuple[bool, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False, None
            raw = resp.read().decode("utf-8", errors="replace")
            return True, json.loads(raw)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False, None


def _http_ping(url: str, timeout: float = 1.2) -> bool:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def build_overview(ns_url: str, t2vn_url: str, comfy_hint: str = "") -> dict[str, Any]:
    """唯讀聚合 Novel Studio 與 T2VN / T2C 的書本與服務狀態。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        f_ns_cfg = pool.submit(_http_get_json, f"{ns_url}/api/config")
        f_ns_books = pool.submit(_http_get_json, f"{ns_url}/api/books")
        f_t2_cfg = pool.submit(_http_get_json, f"{t2vn_url}/api/settings")
        f_t2_books = pool.submit(_http_get_json, f"{t2vn_url}/api/books")

        ns_cfg_ok, ns_cfg = f_ns_cfg.result()
        ns_books_ok, ns_books_data = f_ns_books.result()
        t2_cfg_ok, t2_cfg = f_t2_cfg.result()
        t2_books_ok, t2_books_data = f_t2_books.result()

        comfy_url = (comfy_hint or "").strip().rstrip("/")
        if not comfy_url and t2_cfg_ok and isinstance(t2_cfg, dict):
            comfy_url = str(((t2_cfg.get("comfyui") or {}).get("base_url")) or "").strip().rstrip("/")
        f_comfy = pool.submit(_http_ping, f"{comfy_url}/system_stats") if comfy_url else None

        t2_books = list((t2_books_data or {}).get("books") or []) if t2_books_ok and isinstance(t2_books_data, dict) else []
        t2_library = list((t2_books_data or {}).get("library") or []) if t2_books_ok and isinstance(t2_books_data, dict) else []

        comic_futures: dict[str, concurrent.futures.Future] = {}
        if t2_books_ok:
            for b in t2_books:
                bid = str(b.get("book_id") or "")
                if bid:
                    comic_futures[bid] = pool.submit(
                        _http_get_json,
                        f"{t2vn_url}/api/books/{urllib.parse.quote(bid)}/comic",
                        1.5,
                    )

        comic_by_book: dict[str, list[dict[str, Any]]] = {}
        for bid, fut in comic_futures.items():
            ok, payload = fut.result()
            if ok and isinstance(payload, dict):
                comic_by_book[bid] = list(payload.get("projects") or [])
            else:
                comic_by_book[bid] = []

        comfy_online = f_comfy.result() if f_comfy is not None else False

    ns_books = list((ns_books_data or {}).get("books") or []) if ns_books_ok and isinstance(ns_books_data, dict) else []
    lib_by_dir = {str(item.get("dir_name") or ""): item for item in t2_library if item.get("dir_name")}
    t2_by_source: dict[str, dict[str, Any]] = {}
    t2_unmatched: list[dict[str, Any]] = []
    for b in t2_books:
        src = str(b.get("source_dir") or "").strip()
        if src:
            t2_by_source[src] = b
        else:
            t2_unmatched.append(b)

    merged: list[dict[str, Any]] = []
    seen_sources: set[str] = set()

    for nb in ns_books:
        if not nb.get("is_book"):
            continue
        ns_id = str(nb.get("id") or "")
        seen_sources.add(ns_id)
        tb = t2_by_source.get(ns_id)
        lib_info = lib_by_dir.get(ns_id) or {}
        bid = str(tb.get("book_id") or "") if tb else ""
        comics = comic_by_book.get(bid, []) if bid else []
        merged.append({
            "key": ns_id,
            "title": str(nb.get("name") or ns_id),
            "lang": str(nb.get("lang") or (tb or {}).get("lang") or "zh-TW"),
            "needs_migration": bool(nb.get("needs_migration")),
            "ns": {
                "id": ns_id,
                "chapters_written": int(nb.get("chapters_written") or 0),
                "chapters_planned": int(nb.get("chapters_planned") or 0),
                "pending_candidates": int(nb.get("pending_candidates") or 0),
                "chars": int(nb.get("chars") or 0),
                "unit": str(nb.get("unit") or "字"),
                "visual_cards": int(lib_info.get("visual_cards") or 0),
            },
            "t2vn": {
                "imported": tb is not None,
                "book_id": bid,
                "chapters": int(tb.get("chapters") or 0) if tb else 0,
                "annotated": int(tb.get("annotated") or 0) if tb else 0,
                "reviewed": int(tb.get("reviewed") or 0) if tb else 0,
                "source_kind": str(tb.get("source_kind") or "") if tb else "",
            },
            "comic": {
                "count": len([p for p in comics if not p.get("broken")]),
                "projects": [
                    {"project_id": p.get("project_id"), "title": p.get("title")}
                    for p in comics
                    if not p.get("broken")
                ],
            },
        })

    # T2VN 裡有、但 NS 未啟動或非書庫來源的書
    for src, tb in t2_by_source.items():
        if src in seen_sources:
            continue
        bid = str(tb.get("book_id") or "")
        comics = comic_by_book.get(bid, [])
        merged.append({
            "key": bid or src,
            "title": str(tb.get("display_name") or bid or src),
            "lang": str(tb.get("lang") or "zh-TW"),
            "needs_migration": False,
            "ns": None,
            "t2vn": {
                "imported": True,
                "book_id": bid,
                "chapters": int(tb.get("chapters") or 0),
                "annotated": int(tb.get("annotated") or 0),
                "reviewed": int(tb.get("reviewed") or 0),
                "source_kind": str(tb.get("source_kind") or "library"),
            },
            "comic": {
                "count": len([p for p in comics if not p.get("broken")]),
                "projects": [
                    {"project_id": p.get("project_id"), "title": p.get("title")}
                    for p in comics
                    if not p.get("broken")
                ],
            },
        })

    for tb in t2_unmatched:
        bid = str(tb.get("book_id") or "")
        comics = comic_by_book.get(bid, [])
        merged.append({
            "key": bid,
            "title": str(tb.get("display_name") or bid),
            "lang": str(tb.get("lang") or "zh-TW"),
            "needs_migration": False,
            "ns": None,
            "t2vn": {
                "imported": True,
                "book_id": bid,
                "chapters": int(tb.get("chapters") or 0),
                "annotated": int(tb.get("annotated") or 0),
                "reviewed": int(tb.get("reviewed") or 0),
                "source_kind": str(tb.get("source_kind") or "import"),
            },
            "comic": {
                "count": len([p for p in comics if not p.get("broken")]),
                "projects": [
                    {"project_id": p.get("project_id"), "title": p.get("title")}
                    for p in comics
                    if not p.get("broken")
                ],
            },
        })

    return {
        "services": {
            "novel_studio": {
                "url": ns_url,
                "online": ns_cfg_ok or ns_books_ok,
                "version": str((ns_cfg or {}).get("version") or "") if isinstance(ns_cfg, dict) else "",
            },
            "t2vn": {
                "url": t2vn_url,
                "online": t2_cfg_ok or t2_books_ok,
            },
            "comfyui": {
                "url": comfy_url,
                "online": bool(comfy_online),
            },
        },
        "books": merged,
    }


def make_handler(ns_url: str, t2vn_url: str, comfy_hint: str) -> type[BaseHTTPRequestHandler]:
    class PortalHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _is_local_host(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0].strip("[]").lower()
            return not host or host in LOCAL_HOSTS

        def _send_bytes(self, code: int, content_type: str, data: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if not self._is_local_host():
                self._send_bytes(403, "text/plain; charset=utf-8", b"Forbidden: localhost only")
                return
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/index.html"):
                if not INDEX_HTML.is_file():
                    self._send_bytes(404, "text/plain; charset=utf-8", b"index.html not found")
                    return
                self._send_bytes(200, "text/html; charset=utf-8", INDEX_HTML.read_bytes())
                return
            if path == "/api/overview":
                payload = build_overview(ns_url, t2vn_url, comfy_hint)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send_bytes(200, "application/json; charset=utf-8", body)
                return
            self._send_bytes(404, "application/json; charset=utf-8", b'{"error":"not_found"}')

    return PortalHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="t2x-suite read-only Portal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8700)
    args = parser.parse_args()

    if args.host not in LOCAL_HOSTS:
        raise SystemExit(f"Portal only binds to localhost ({', '.join(sorted(LOCAL_HOSTS))})")

    ns_url = _env_url("NS_URL", DEFAULT_NS_URL)
    t2vn_url = _env_url("T2VN_URL", DEFAULT_T2VN_URL)
    comfy_hint = (os.environ.get("T2X_COMFYUI_URL") or "").strip().rstrip("/")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(ns_url, t2vn_url, comfy_hint))
    print(f"[portal] listening on http://{args.host}:{args.port} (NS={ns_url}, T2VN={t2vn_url})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
