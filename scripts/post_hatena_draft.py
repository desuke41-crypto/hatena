#!/usr/bin/env python3
"""はてなブログに記事を「下書き」として投稿するスクリプト（AtomPub API）。

必要な環境変数:
  HATENA_ID       はてなID（省略時: desuke41）
  HATENA_BLOG_ID  ブログのドメイン（省略時: desuke41.hatenablog.jp ＝オイル交換プロジェクト）
  HATENA_API_KEY  はてなブログの設定 > 詳細設定 > AtomPub の APIキー

使い方:
  python3 scripts/post_hatena_draft.py articles/oil-change-project/xxx.md
  python3 scripts/post_hatena_draft.py --dry-run articles/...   # 送信せずXMLを表示
  python3 scripts/post_hatena_draft.py --blog desuke41.hateblo.jp articles/...  # メインブログへ
  python3 scripts/post_hatena_draft.py --replace articles/...  # 同じタイトルの下書きを上書き
  python3 scripts/post_hatena_draft.py --replace --match-title "旧タイトル" articles/...  # タイトル変更時

記事ファイル冒頭の <!-- --> コメント内「タイトル案:」または「タイトル:」をタイトルに使い、
コメント部分は本文から取り除く。
"""
import argparse
import base64
import os
import re
import sys
import urllib.request
from xml.sax.saxutils import escape, unescape


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


def request(url, auth, method="GET", data=None):
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/xml"},
    )
    with urllib.request.urlopen(req) as res:
        return res.status, res.read().decode("utf-8")


def find_draft(collection_url, auth, title, max_pages=10):
    """同じタイトルの下書きを探して、その編集用URLを返す（なければ None）。"""
    url = collection_url
    for _ in range(max_pages):
        _, feed = request(url, auth)
        for entry in re.findall(r"<entry\b[^>]*>(.*?)</entry>", feed, re.S):
            t = re.search(r"<title>(.*?)</title>", entry, re.S)
            draft = re.search(r"<app:draft>yes</app:draft>", entry)
            edit = re.search(r'<link rel="edit" href="([^"]+)"', entry)
            if t and draft and edit and unescape(t.group(1)) == title:
                return edit.group(1)
        nxt = re.search(r'<link rel="next" href="([^"]+)"', feed)
        if not nxt:
            return None
        url = unescape(nxt.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--category", action="append", default=[])
    ap.add_argument("--blog", help="投稿先ブログのドメイン（HATENA_BLOG_ID より優先）")
    ap.add_argument("--replace", action="store_true", help="同じタイトルの下書きがあれば上書きする（公開済み記事は対象外）")
    ap.add_argument("--match-title", help="--replace で探す下書きのタイトル（タイトルを変えるときに旧タイトルを指定）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    title, body = parse_article(args.path)
    xml = build_entry(title, body, args.category)
    if args.dry_run:
        print(xml)
        return

    hatena_id = os.environ.get("HATENA_ID", "desuke41")
    blog_id = args.blog or os.environ.get("HATENA_BLOG_ID", "desuke41.hatenablog.jp")
    api_key = os.environ["HATENA_API_KEY"]
    url = f"https://blog.hatena.ne.jp/{hatena_id}/{blog_id}/atom/entry"
    auth = base64.b64encode(f"{hatena_id}:{api_key}".encode()).decode()
    method = "POST"
    if args.replace:
        edit_url = find_draft(url, auth, args.match_title or title)
        if edit_url:
            url, method = edit_url, "PUT"
        else:
            print("同じタイトルの下書きが見つからないので、新しく下書きを作ります。")
    status, resp = request(url, auth, method, xml.encode("utf-8"))
    action = "上書き" if method == "PUT" else "保存"
    print(f"下書きを{action}しました（HTTP {status}）: {title}")
    alt = re.search(r'<link rel="alternate" type="text/html" href="([^"]+)"', resp)
    if alt:
        print(alt.group(1))


if __name__ == "__main__":
    main()
