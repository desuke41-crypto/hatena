#!/usr/bin/env python3
"""はてなブログに記事を「下書き」として投稿するスクリプト（AtomPub API）。

必要な環境変数:
  HATENA_ID       はてなID
  HATENA_BLOG_ID  ブログのドメイン（例: oil-change.hatenablog.com）
  HATENA_API_KEY  はてなブログの設定 > 詳細設定 > AtomPub の APIキー

使い方:
  python3 scripts/post_hatena_draft.py articles/oil-change-project/xxx.md
  python3 scripts/post_hatena_draft.py --dry-run articles/...   # 送信せずXMLを表示

記事ファイル冒頭の <!-- --> コメント内「タイトル案:」または「タイトル:」をタイトルに使い、
コメント部分は本文から取り除く。
"""
import argparse
import base64
import os
import re
import sys
import urllib.request
from xml.sax.saxutils import escape


def parse_article(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    title = None
    m = re.match(r"\s*<!--(.*?)-->\s*", text, re.S)
    if m:
        t = re.search(r"^タイトル(?:案)?[:：]\s*(.+)$", m.group(1), re.M)
        if t:
            title = t.group(1).strip()
        text = text[m.end():]
    if title is None:
        h = re.match(r"\s*#\s+(.+)\n", text)
        if h:
            title = h.group(1).strip()
            text = text[h.end():]
    if not title:
        sys.exit("タイトルが見つかりません")
    return title, text.strip() + "\n"


def build_entry(title, body, categories):
    cats = "".join(f'  <category term="{escape(c)}" />\n' for c in categories)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<entry xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app">\n'
        f"  <title>{escape(title)}</title>\n"
        f'  <content type="text/x-markdown">{escape(body)}</content>\n'
        f"{cats}"
        "  <app:control><app:draft>yes</app:draft></app:control>\n"
        "</entry>\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--category", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    title, body = parse_article(args.path)
    xml = build_entry(title, body, args.category)
    if args.dry_run:
        print(xml)
        return

    hatena_id = os.environ["HATENA_ID"]
    blog_id = os.environ["HATENA_BLOG_ID"]
    api_key = os.environ["HATENA_API_KEY"]
    url = f"https://blog.hatena.ne.jp/{hatena_id}/{blog_id}/atom/entry"
    auth = base64.b64encode(f"{hatena_id}:{api_key}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=xml.encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/xml"},
    )
    with urllib.request.urlopen(req) as res:
        resp = res.read().decode("utf-8")
    edit = re.search(r'<link rel="alternate" type="text/html" href="([^"]+)"', resp)
    print(f"下書きを保存しました（HTTP {res.status}）: {title}")
    if edit:
        print(edit.group(1))


if __name__ == "__main__":
    main()
