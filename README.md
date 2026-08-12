# 月相羅針 計算PoC v0.7｜Vue.js画面版

春華プロジェクトの「月相羅針 Web計算サービス」を技術検証するための、小規模な Flask + Vue 3 Web アプリです。

v0.7では、v0.6のPython計算ロジックを維持したまま、利用者が操作する画面部分をVue.js化しています。

```text
ブラウザ
  ↓
Vue.js（入力・画面制御・結果表示）
  ↓ fetch / JSON
Flask API
  ↓
Python（入力検証・天体計算・月相分類）
  ↓ JSON
Vue.js（結果部分だけ更新）
```

## 重要

この PoC は、**月相羅針の正式占術仕様を確定するものではありません。**

現在の P01〜P08 は、360°を45°ずつ8等分し、標準的な月相名称とPoC用説明文章を割り当てた技術確認用の仮仕様です。春華独自の正式な月相羅針の ID・名称・角度範囲・境界条件・説明文・特徴・進み方が確定したら、`phase_classifier.py` の定義を差し替える前提です。

出生時間不明時の `stable` / `ambiguous` 判定も、**PoCの技術検証仕様であり、春華独自の正式ルールではありません。**

## v0.7でVue.js化した範囲

Vue 3側では次を担当します。

- 生年月日・出生時間・出生地の入力状態
- 入力エラーの表示
- `POST /api/calculate` への `fetch()` 送信
- 計算中表示と連続送信防止
- 出生時間ありの結果表示
- 出生時間不明時の `stable` / `ambiguous` と候補一覧表示
- ページ全体を再読み込みせず結果部分だけ更新
- v0.6の現在年月日／現在時刻の入力UI挙動
- v0.5以降のリセット仕様

Vue 3はCDN版のグローバルビルドを読み込みます。Vite、Vue CLI、Node.js開発サーバー、SPA Router、Pinia、TypeScriptは導入していません。

## Python側で維持している範囲

次の処理はJavaScriptへ移植せず、Python側に残しています。

- 出生情報の検証
- 出生日時のUTC変換
- Swiss Ephemeris / pyswissephによる太陽黄経計算
- Swiss Ephemeris / pyswissephによる月黄経計算
- 角度差計算
- 月相8分類
- 出生時間不明時の候補計算
- `stable` / `ambiguous` 判定
- 出生地処理

角度差計算は従来どおり、`astronomy.py` の次の処理を維持しています。

```python
angle_difference = normalize_angle(moon_longitude - sun_longitude)
```

`normalize_angle()` は `% 360.0` で正規化するため、実質的な計算式は次のとおりです。

```python
(moon_longitude - sun_longitude) % 360.0
```

## Flask API

### `POST /api/calculate`

Vue.jsからJSONで出生情報を送信します。

リクエスト例：

```json
{
  "birth_date": "1964-09-03",
  "birth_time": "11:23",
  "birth_place": "兵庫県小野市"
}
```

出生時間が不明な場合は `birth_time` を空文字で送信します。

```json
{
  "birth_date": "1964-09-03",
  "birth_time": "",
  "birth_place": "兵庫県小野市"
}
```

正常時：

```json
{
  "success": true,
  "result": {
    "classification_status": "exact"
  }
}
```

入力エラー時：

```json
{
  "success": false,
  "errors": [
    "生年月日を入力してください。",
    "出生地を入力してください。"
  ]
}
```

HTTPステータスは、正常時 `200`、入力エラー時 `400`、天体計算・予期しないサーバーエラー時 `500` を返します。

## 入力UI仕様（v0.6から維持）

### 入力欄の高さ

- 生年月日
- 出生時間
- 出生地

を同一の高さ `48px` とし、生年月日と出生時間の上端位置をそろえています。

iPad/Safariのネイティブdate/time入力を維持したまま、`block-size` も固定しています。

### 生年月日が空欄の場合

空欄のdate入力を開く時点で、端末ローカルの現在年月日を入力画面の現在値として設定します。

既に値がある場合は現在年月日で上書きしません。

### 出生時間が空欄の場合

空欄のtime入力を開く時点で、端末ローカルの現在時刻（分単位）を入力画面の現在値として設定します。

既に値がある場合は現在時刻で上書きしません。

### リセット

リセット後は前回計算値へ戻さず、次の3項目を空欄にする仕様を維持しています。

- 生年月日
- 出生時間
- 出生地

その後、空欄の生年月日・出生時間入力を改めて開いた場合に、現在年月日／現在時刻を現在値として使います。

## 出生時間が分かる場合

1. 生年月日・出生時間・出生地を入力
2. Vue.jsがFlask APIへJSON送信
3. 日本国内として `Asia/Tokyo` を使用
4. 出生時刻を UTC へ変換
5. pyswisseph で地心・トロピカルの太陽黄経・月黄経を計算
6. `(moon_longitude - sun_longitude) % 360.0` で角度差を算出
7. 技術確認用の標準月相8分類を1つ判定
8. JSONをVue.jsへ返す
9. Vue.jsが結果カードを更新

## 出生時間が分からない場合

出生時間が未入力の場合、特定の仮時刻を使って1分類に決めるのではなく、その出生日の範囲内で月相分類が変化する可能性を確認します。

- 対象時刻：`00:00:00` ～ `23:59:59`（Asia/Tokyo）
- 基本サンプリング：30分刻み＋`23:59:59`
- サンプル間は角度差を連続値として追跡し、45°区分を通過した場合は候補へ含める
- 360°→0°のラップアラウンドも連続角として扱う

一日中同じ分類の場合：

- `classification_status == "stable"`
- 1つの候補を表示

一日の途中で分類境界をまたぐ場合：

- `classification_status == "ambiguous"`
- 複数候補を表示
- 1つに確定しない

## 必要環境

- Python 3.9 以上を推奨
- pip
- ブラウザからVue 3 CDNへアクセスできるネットワーク環境

Node.jsは不要です。

## インストール

```bash
pip install -r requirements.txt
```

## 起動

```bash
python app.py
```

ブラウザで次を開きます。

```text
http://127.0.0.1:5000
```

Flaskは `0.0.0.0:5000` で待ち受けます。

## GitHub Codespaces での起動

Codespaces の Terminal で次を実行します。

```bash
pip install -r requirements.txt
python app.py
```

**PORTS** タブで **5000** 番ポートを見つけ、**Open in Browser** を選択してください。

別のNode開発サーバーを起動する必要はありません。

## 正解確認用テストデータ（出生時間あり）

- 生年月日：1964-09-03
- 出生時間：11:23
- 出生地：兵庫県小野市
- タイムゾーン：Asia/Tokyo

期待値（概算）：

- UTC：1964-09-03 02:23:00 UTC
- 太陽黄経：約 160.60945188°
- 月黄経：約 119.86709682°
- 角度差：約 319.25764494°
- PoC標準月相8分類：P08 / 欠けていく三日月（Waning Crescent）

## 出生時間不明のテスト例

### stable

- 生年月日：1964-09-04
- 出生時間：空欄
- 期待：`stable`、候補 `P08` 1件

### ambiguous

- 生年月日：1964-09-03
- 出生時間：空欄
- 期待：`ambiguous`、候補 `P07` と `P08`

同じ1964-09-03でも、出生時間が11:23と分かっている場合は `P08` と一意判定します。

## テスト

```bash
python -m unittest discover -s tests -v
```

v0.7では、従来の基準計算・境界・出生時間不明テストに加え、次を確認します。

- Flask APIへ正常入力を送ると計算結果が返る
- 出生時間ありで `exact` / `P08`
- 出生時間なしで `stable` / `ambiguous`
- 入力エラーがJSONで返る
- Vue 3と `static/app.js` が画面から読み込まれる
- Vueが `/api/calculate` を呼び出す
- リセット仕様を維持
- 現在年月日／現在時刻の入力UI仕様を維持
- date/time/textの入力欄高さを維持

## ファイル構成

```text
gessou_rashin_poc/
├── app.py
├── astronomy.py
├── phase_classifier.py
├── location_master.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
└── tests/
    └── test_core.py
```

## モジュール分離方針

- `static/app.js`：Vue.jsの画面状態、API呼び出し、結果描画用の表示処理
- `app.py`：HTML配信、JSON API、入力検証、既存Python計算モジュールの呼び出し
- `astronomy.py`：現地時刻→UTC→ユリウス日→太陽・月黄経→角度差、出生時間不明時の日内複数時刻計算
- `phase_classifier.py`：1角度の8分類、複数角度から候補分類を求める処理
- `location_master.py`：出生地→タイムゾーン（将来は緯度・経度・歴史的タイムゾーンへ拡張）

## 天体暦について

コードは `pyswisseph` に対して Swiss Ephemeris モードを要求します。外部の Swiss Ephemeris 天体暦データファイルが環境に存在しない場合、ライブラリが Moshier モードへフォールバックすることがあります。画面には実際に使用されたモードを表示します。

PoCの再現性をより厳密に固定する段階では、使用する天体暦データファイル、バージョン、配置方法まで固定して管理してください。

## ライセンス上の注意

Swiss Ephemeris はライセンス条件を持つソフトウェアです。`pyswisseph` を利用した本PoCを一般公開・配布・商用利用へ進める場合は、**Swiss Ephemeris および pyswisseph の最新の公式ライセンス条件を、実施時点で必ず確認してください。**

また、v0.7ではVue 3をCDNから読み込む構成です。正式サービス化する場合は、依存ライブラリのバージョン固定、配信方法、ライセンス表記、CSP等を含めて再検討してください。

## PoC v0.7 で実装していないもの

会員登録、ログイン、決済、AI機能、AI春華接続、個人鑑定、カード機能、履歴保存、SNS共有、高度デザイン、本格的な出生地検索、地図連携、外国出生地対応、データベース、管理画面、Viteによる本格フロントエンドビルドは対象外です。

## 既知の制約

- 出生地は日本国内として `Asia/Tokyo` に固定しています。
- 出生時間不明時は30分刻みの天体計算を基本とし、サンプル間の連続角度経路から45°区分通過を補足します。
- 正式な春華独自分類、境界条件、説明文、出生時間不明時の正式ルールは未実装です。
- Vue 3はCDN読込のため、初回表示時にブラウザがCDNへ接続できる必要があります。
- iPad Safariのネイティブ日付・時刻ピッカー、リセット挙動、入力欄高さは実機で最終確認が必要です。
- 一般公開・商用利用前に Swiss Ephemeris / pyswisseph およびVue等の依存関係・ライセンス条件を確認する必要があります。
