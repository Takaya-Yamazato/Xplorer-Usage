# IEEE Xplore IEICE Usage Scraper

IEEE Xploreに掲載されている以下のジャーナルの論文Usage（利用統計）を取得し、集計・分析するためのツール群です。

| ジャーナル | punumber |
|---|---|
| IEICE Transactions on Communications | 10400553 |
| IEICE Communications Express | 10250155 |

---

## 必要環境

- Python 3.10 以上
- Playwright および必要なPythonパッケージ

### セットアップ

```bash
# 仮想環境の作成と有効化を推奨します
python3 -m venv venv
source venv/bin/activate

# 依存パッケージのインストール
pip install playwright pandas openpyxl tqdm matplotlib japanize-matplotlib setuptools
# Playwrightのブラウザ（Chromium）をインストール
playwright install chromium
```

---

## ファイル構成

```
ieice_usage_scraper/
├── scraper.py       # メインスクリプト（本番用）
├── debug_api.py     # APIレスポンス構造確認用（初回確認推奨）
└── README.md        # このファイル
```

---

## 使い方

### ステップ 1：APIレスポンス構造の確認（初回のみ推奨）

```bash
python debug_api.py --doi 10.23919/comex.2023XBL0092 10.23919/comex.2023XBL0098　　# DOI指定モード 2 件
python debug_api.py　# 全て
```

ブラウザが開き、IEEE XploreのAPIを叩いて `debug_search.json` と  
`debug_metrics.json` を保存します。  
内容を確認し、`scraper.py` の Usage フィールド抽出部分が  
実際のキー名と合っているか確認してください。

### ステップ 2：本番実行

```bash
# 基本実行（ブラウザ表示あり）
python scraper.py

詳細は以下のとおり．

IEEE Xplore Usage Statistics Scraper
=====================================
対象ジャーナル:
  - IEICE Transactions on Communications (punumber=10400553)
  - IEICE Communications Express      (punumber=10250155)

各論文のUsage（Abstract Views + Full Text Views + PDF Downloads など）を
年・月ごとに集計してExcelファイルに出力します。

依存パッケージのインストール:
  python3 -m venv venv
  source venv/bin/activate
  pip install playwright pandas openpyxl tqdm matplotlib japanize-matplotlib setuptools
  playwright install chromium

実行方法:
  python scraper.py

オプション:
  --headed         ブラウザを表示して実行（デフォルト: 非表示）
  --output FILE    出力Excelファイル名（デフォルト: ieice_usage.xlsx）
  --delay FLOAT    リクエスト間の待機秒数（デフォルト: 2.0）
  --max-pages INT  各ジャーナルの最大ページ数（0=全ページ、デフォルト: 0）
  --doi DOI        特定のDOIのUsageを取得する（複数指定可）
  --pub-year INT   特定の出版年の論文のみを取得する（例: 2024）
  --usage-year INT 月別Usageシートで特定の利用年のみを出力する（例: 2024）
    python scraper.py --doi 10.23919/comex.2023XBL0092 10.23919/comex.2023XBL0098
    python scraper.py --pub-year 2024
    python scraper.py --usage-year 2024
```

---

## 出力Excelファイルの構成

| シート名 | 内容 |
|---|---|
| `Usage集計` | 年×月のピボットテーブル（ジャーナル別・指標別） |
| `論文詳細` | 全論文の raw データ（1行1論文） |
| `年別合計` | 年ごとの合計（ジャーナル横並び） |

### Usage集計シートに含まれる指標

| 指標 | 説明 |
|---|---|
| Total Usage | 総利用数（Abstract + Full Text + PDF） |
| Abstract Views | アブストラクト閲覧数 |
| Full Text Views | 全文HTML閲覧数 |
| PDF Downloads | PDF取得数 |

---

## 注意事項

1. **IEEE Xploreへのログイン不要**ですが、機関アクセスがある場合は  
   ブラウザで事前にログイン状態にしておくとより正確なデータが取れる場合があります。

2. **レート制限**に注意してください。`--delay` オプションで調整できます。  
   デフォルトの 2.0 秒程度が推奨されます。

3. 論文数が多い場合（数百〜数千件）は**数時間かかる**場合があります。  
   `--max-pages` で小さな値を指定して動作確認してから本番実行してください。

4. IEEE Xplore の APIレスポンスの構造が変わっている場合は、  
   `debug_api.py` で確認し、`scraper.py` の抽出ロジックを修正してください。

---

## メトリクスAPIのレスポンス例

`debug_metrics.json` で確認できる主なフィールド:

```json
{
  "articleNumber": "...",
  "usageCount": 1234,
  "abstractViewCount": 500,
  "htmlViewCount": 300,
  "pdfDownloadCount": 434
}
```

IEEE XploreのAPIバージョンによってキー名が異なる場合は  
`scraper.py` の `get_article_metrics()` 関数を修正してください。
