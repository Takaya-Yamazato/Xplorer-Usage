"""
IEEE Xplore APIレスポンス構造確認スクリプト
===========================================
本番実行前にこのスクリプトを実行し、APIのレスポンス構造を
JSONファイルとして保存して確認できます。

実行方法:
  # 通常モード: ジャーナルの最新3件のUsageを取得
  python debug_api.py

  # DOI指定モード: 指定したDOIの文献のUsageを取得
  python debug_api.py --doi 10.23919/comex.2023XBL0092
  python debug_api.py --doi 10.23919/comex.2023XBL0092 10.23919/comex.2023XBL0098
出力:
  debug_search.json   - 検索APIのレスポンス例
                        各論文にUsage情報(Total Usage / Abstract Views /
                        Full Text Views / PDF Downloads)を付加済み
  debug_metrics.json  - 個別論文メトリクスAPIの生レスポンス例
"""

import argparse
import json
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://ieeexplore.ieee.org"
SEARCH_API = BASE_URL + "/rest/search"
ARTICLE_METRICS_API = BASE_URL + "/rest/document/{article_id}/metrics"
ARTICLE_AUTHORS_API = BASE_URL + "/rest/document/{article_id}/authors"

# IEICE Trans. Commun.
PUNUMBER = "10400553"


def parse_args():
    p = argparse.ArgumentParser(
        description="IEEE Xplore Usage デバッグツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 通常モード（ジャーナルの最新3件）
  python debug_api.py

  # DOI指定モード（1件）
  python debug_api.py --doi 10.23919/comex.2024.0001

  # DOI指定モード（複数件）
  python debug_api.py --doi 10.23919/comex.2024.0001 10.23919/comex.2024.0002
        """,
    )
    p.add_argument(
        "--doi",
        nargs="+",
        metavar="DOI",
        help="Usage を調べたい文献の DOI（複数指定可）",
    )
    return p.parse_args()


def fetch_json(page, url: str, params: dict = None) -> dict:
    method = "POST" if params else "GET"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = page.evaluate(
                """async ([url, method, params]) => {
                    try {
                        const options = {
                            method: method,
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'X-Requested-With': 'XMLHttpRequest',
                            }
                        };
                        if (method === 'POST' && params) {
                            options.headers['Content-Type'] = 'application/json';
                            options.body = JSON.stringify(params);
                        }
                        const resp = await fetch(url, options);
                        if (!resp.ok) return {error: resp.status, url};
                        return await resp.json();
                    } catch (e) {
                        return {error: "fetch_failed", message: e.toString()};
                    }
                }""",
                [url, method, params],
            )
            if isinstance(result, dict) and result.get("error") == "fetch_failed":
                raise Exception(result.get("message", "Fetch failed"))
            return result or {}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"\n  [ERROR] API request failed after {max_retries} retries: {url} - {e}")
                return {"error": str(e)}


def extract_usage(metrics: dict, art: dict = None) -> dict:
    """メトリクスAPIのレスポンスからTotal Usageを抽出して返す。"""
    art = art or {}
    inner_metrics = metrics.get("metrics", {})
    total_usage = (
        metrics.get("usageCount")
        or metrics.get("totalUsageCount")
        or inner_metrics.get("totalDownloads")
        or art.get("usageCount")
        or art.get("downloadCount")
        or 0
    )
    return {
        "usage_total":            total_usage,
        "_metrics_raw_keys":      list(metrics.keys()),  # キー名確認用
    }


def print_usage_table(articles: list[dict]):
    """Usage情報をコンソールに表形式で表示する。"""
    print()
    print(f"  {'DOI':<45} {'Total':>7}  Title")
    print(f"  {'-'*45} {'-'*7}  {'-'*40}")
    for art in articles:
        u = art.get("_usage", {})
        doi   = art.get("doi", "")[:45]
        title = art.get("articleTitle", art.get("documentTitle", art.get("title", "")))[:40]
        total_usage = u.get('usage_total')
        if total_usage is None:
            total_usage = 0
        print(
            f"  {doi:<45} "
            f"{total_usage:>7}  "
            f"{title}"
        )
    print()


def fetch_articles_by_doi(page, dois: list[str]) -> tuple[list[dict], list[dict]]:
    """
    DOIリストで文献を1件ずつ検索して返す。
    Returns: (articles, all_metrics_raw)
    """
    articles = []
    all_metrics_raw = []

    for i, doi in enumerate(dois):
        doi = doi.strip()
        print(f"\n[{i+1}/{len(dois)}] DOI検索中: {doi}")

        # DOIで検索
        search_result = fetch_json(page, SEARCH_API, {
            "newsearch": "true",
            "queryText": f"doi:{doi}",
            "pageNumber": 1,
            "rowsPerPage": 5,
        })

        found = search_result.get("records", [])

        # DOIの完全一致で絞り込む（検索が複数件返す場合に備えて）
        matched = [
            a for a in found
            if a.get("doi", "").lower().strip() == doi.lower().strip()
        ]
        if not matched and found:
            # 完全一致がなければ検索結果の先頭を使う
            matched = [found[0]]
            print(f"  [WARN] DOI完全一致なし。先頭の結果を使用: {found[0].get('doi', '')}")

        if not matched:
            print(f"  [ERROR] 文献が見つかりませんでした: {doi}")
            articles.append({
                "doi": doi,
                "title": "(not found)",
                "articleNumber": "",
                "_usage": {
                    "usage_total": 0,
                    "_metrics_raw_keys": [],
                },
            })
            continue

        art = matched[0]
        article_id = str(art.get("articleNumber", art.get("arnumber", "")))
        print(f"  論文ID : {article_id}")
        title = art.get("articleTitle", art.get("documentTitle", art.get("title", "")))
        print(f"  タイトル: {title[:80]}")
        print(f"  DOI    : {art.get('doi', '')}")

        # 著者情報（所属含む）を取得
        time.sleep(1)
        authors_data = fetch_json(page, ARTICLE_AUTHORS_API.format(article_id=article_id))
        # 個別APIから取得できない場合は検索APIのフォールバックを使用
        authors_list = authors_data.get("authors", art.get("authors", []))

        if authors_list:
            print("  著者・所属:")
            for a in authors_list:
                name = a.get("name", a.get("preferredName", "Unknown"))
                affil = a.get("affiliation") or a.get("affiliations") or a.get("authorAffiliations") or ""
                if isinstance(affil, list):
                    affil = ", ".join(str(x) for x in affil)
                print(f"    - {name}: {affil if affil else '所属情報なし'}")

        # メトリクス取得
        time.sleep(1)
        metrics = fetch_json(page, ARTICLE_METRICS_API.format(article_id=article_id))
        all_metrics_raw.append({
            "doi": doi,
            "article_id": article_id,
            "title": title,
            "metrics_response": metrics,
        })

        usage = extract_usage(metrics, art)
        art["_usage"] = usage
        articles.append(art)

        print(
            f"  Usage  → Total={usage['usage_total']:>6}"
        )

    return articles, all_metrics_raw


def fetch_articles_default(page) -> tuple[dict, list[dict], list[dict]]:
    """
    通常モード: ジャーナルの最新3件を取得して返す。
    Returns: (search_result, articles, all_metrics_raw)
    """
    print("検索APIをテスト中（最新3件）...")
    search_result = fetch_json(page, SEARCH_API, {
        "newsearch": "true",
        "queryText": "",
        "punumber": PUNUMBER,
        "pageNumber": 1,
        "rowsPerPage": 3,
        "sortType": "newest",
    })

    articles = search_result.get("records", [])
    if not articles:
        print("  [WARN] 論文が見つかりませんでした")
        print(f"  レスポンスのキー: {list(search_result.keys())}")
        return search_result, [], []

    print(f"  {len(articles)} 件取得")

    all_metrics_raw = []
    for i, art in enumerate(articles):
        article_id = str(art.get("articleNumber", art.get("arnumber", "")))
        title = art.get("articleTitle", art.get("documentTitle", art.get("title", "")))
        title_short = title[:60]
        print(f"  [{i+1}/{len(articles)}] ID={article_id}  {title_short}...")

        # 著者情報（所属含む）を取得
        time.sleep(1)
        authors_data = fetch_json(page, ARTICLE_AUTHORS_API.format(article_id=article_id))
        # 個別APIから取得できない場合は検索APIのフォールバックを使用
        authors_list = authors_data.get("authors", art.get("authors", []))

        if authors_list:
            print("       著者・所属:")
            for a in authors_list:
                name = a.get("name", a.get("preferredName", "Unknown"))
                affil = a.get("affiliation") or a.get("affiliations") or a.get("authorAffiliations") or ""
                if isinstance(affil, list):
                    affil = ", ".join(str(x) for x in affil)
                print(f"         - {name}: {affil if affil else '所属情報なし'}")

        time.sleep(1)
        metrics = fetch_json(page, ARTICLE_METRICS_API.format(article_id=article_id))
        all_metrics_raw.append({
            "article_id": article_id,
            "title": title,
            "metrics_response": metrics,
        })

        usage = extract_usage(metrics, art)
        art["_usage"] = usage

        print(
            f"       Total={usage['usage_total']:>6}"
        )

    return search_result, articles, all_metrics_raw


def main():
    args = parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print("IEEE Xplore を開いています...")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ---- モード分岐 ----
        if args.doi:
            # DOI指定モード
            print(f"\n=== DOI指定モード ({len(args.doi)} 件) ===")
            articles, all_metrics_raw = fetch_articles_by_doi(page, args.doi)

            # debug_search.json: articlesリストとして保存
            search_result = {"articles": articles, "_mode": "doi_lookup", "_dois": args.doi}

        else:
            # 通常モード
            print("\n=== 通常モード（ジャーナル最新3件） ===")
            search_result, articles, all_metrics_raw = fetch_articles_default(page)

        # ---- ファイル保存 ----
        with open("debug_search.json", "w", encoding="utf-8") as f:
            json.dump(search_result, f, ensure_ascii=False, indent=2)
        print("\n→ debug_search.json に保存（各articleに '_usage' フィールド付き）")

        with open("debug_metrics.json", "w", encoding="utf-8") as f:
            json.dump(all_metrics_raw, f, ensure_ascii=False, indent=2)
        print("→ debug_metrics.json に保存（メトリクスAPIの生レスポンス）")

        # ---- Usage サマリー表示 ----
        if articles:
            print("\n=== Usage サマリー ===")
            print_usage_table(articles)

            if not args.doi:
                # 通常モードのみ：APIキー構造も表示
                print("--- 検索結果の全キー ---")
                print(json.dumps(list(search_result.keys()), ensure_ascii=False, indent=2))
                print("\n--- 最初の論文のキー（_usage付加後） ---")
                print(json.dumps(list(articles[0].keys()), ensure_ascii=False, indent=2))
                print("\n--- _usage フィールドの内容 ---")
                print(json.dumps(articles[0].get("_usage", {}), ensure_ascii=False, indent=2))

        input("内容を確認したらEnterを押してブラウザを閉じます...")
        browser.close()

    print("\nデバッグ完了。debug_search.json と debug_metrics.json を確認してください。")


if __name__ == "__main__":
    main()
