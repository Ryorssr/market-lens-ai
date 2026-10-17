# Market Lens AI v0.6 — iPhone向け無料ホスティング構成

**個人向け試作品です。公開価格の一部と公式RSS以外はデモです。**

## GitHub Pagesで公開する（PC常時起動・追加課金なし）

1. GitHubアカウントを用意し、新しい **Public** リポジトリ（例 `market-lens-personal`）を作成します。GitHub Pagesの無料利用条件はプラン・リポジトリ公開範囲により変わります。**Publicにするとコードと生成データは誰でも閲覧できます。** 秘密情報や顧客情報は絶対に入れないでください。
2. ZIPを解凍して、フォルダの**中身**（`.github/workflows/update.yml` を含む）をリポジトリのルートにアップロードしてコミットします。Webアップロードで隠しフォルダを落とさないよう注意してください。Gitコマンドでのpushでも構いません。
3. GitHubリポジトリの **Settings → Pages → Build and deployment → Deploy from a branch** で、`main` ブランチの `/ (root)` を選び保存します。
4. **Actions → Refresh public market data → Run workflow** を手動実行します。初回のニュース・為替の取得結果を Actions のログで確認します。失敗時はデモのままです。
5. Pages の公開URL（通常 `https://ユーザー名.github.io/リポジトリ名/`）を iPhone Safari で開きます。**共有 → ホーム画面に追加** でアプリアイコンを置けます。

### 更新頻度
GitHub Actions が原則毎時17分に公式データを取得し、JSONをリポジトリに保存します。**GitHubのスケジュール実行は遅延・スキップされることがあり、1時間ごとの実行は保証されません。** アプリは表示中に15分ごとに保存済みデータを確認します。画面に表示される更新時刻を確認してください。Actions が停止・失敗しても前回データを維持するため、古い情報の可能性があります。

### 通知について
- 開いている間：新着の「重要ニュース候補」を検知し、ブラウザが許可していれば通知を試みます。
- **閉じている間：通知できません。** iPhoneのホーム画面Webアプリにするだけではバックグラウンド通知にはなりません。Web Pushには別途プッシュ購読・サーバー送信が必要です。
- キーワード判定は実際の市場影響を保証しません。FRB/ECBのニュースが中心で、日本・企業決算・地政学などは網羅しません。

### 実データとデモの区別
- `data/fx.json`: ECB参考レートの4つの円クロス（EUR/JPYはECB値、他はEUR基準値から計算）。市場の終値ではありません。
- `data/news.json`: FRB/ECB公式RSSの見出し・出典・日時・リンク。見出しは原文。
- **デモ**：米国株、日本株、原油、金、米国債、すべてのチャート時系列、朝刊内の5つの仮想ニュース、AI質問の定型回答。
- 公開前に各データの利用規約、第三者への再配信条件を確認してください。個人用でも公開GitHub Pagesは外部から閲覧できます。

### PCで動作確認
`python -m http.server 8765` で開けますが、`data/*.json` が未更新ならニュースと為替は表示できません。`python update_data.py` でデータを取得できます（ネットワーク接続が必要）。`start_server.py` は従来版との互換用ローカルAPIサーバーです。

### 出典
- FRB: https://www.federalreserve.gov/feeds/press_all.xml
- ECBニュース: https://www.ecb.europa.eu/rss/press.html
- ECB為替: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml
