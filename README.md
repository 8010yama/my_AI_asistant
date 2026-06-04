# ALIA - AI音声アシスタント

スマートフォンから話しかけると音声で返答するAIアシスタント。天気・電車・地図・メモ・カレンダーに対応。

## 機能

- **天気** - 現在地の気温・降水予報
- **電車** - 乗り換え案内・次の電車
- **マップ** - Apple Maps / Google Maps ナビ起動
- **メモ** - Notionのメモページに追記
- **TODO** - NotionのTODOページにチェックボックスで追加
- **カレンダー** - Google Calendarへの予定追加・読み上げ・時間変更

## 技術構成

- **バックエンド**: FastAPI + Uvicorn
- **LLM**: Ollama (qwen2.5:3b)
- **音声合成**: VOICEVOX
- **音声認識**: faster-whisper
- **外部公開**: ngrok

## セットアップ

```bash
pip install -r requirements.txt
```

`.env` を作成して以下を設定：

```
API_KEY=             # 任意の文字列（クライアントアプリと合わせる）
NGROK_TOKEN=         # https://dashboard.ngrok.com でサインアップ → Your Authtoken
YAHOO_APP_ID=        # https://developer.yahoo.co.jp でアプリ登録 → クライアントID
NOTION_TOKEN=        # https://www.notion.so/my-integrations でインテグレーション作成 → シークレット
NOTION_MEMO_PAGE_ID= # メモ用NotionページのURL末尾のID（32桁の英数字）
NOTION_TODO_PAGE_ID= # TODO用NotionページのURL末尾のID（32桁の英数字）
GOOGLE_CLIENT_ID=    # https://console.cloud.google.com → APIとサービス → 認証情報 → OAuthクライアントID作成
GOOGLE_CLIENT_SECRET=# 同上（クライアントシークレット）
GOOGLE_REFRESH_TOKEN=# 下記「Googleリフレッシュトークンの取得」を参照
GOOGLE_CALENDAR_ID=primary
```

### Notion ページIDの確認方法

NotionでページをブラウザURLで開いたとき:
```
https://www.notion.so/ページタイトル-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
末尾の32桁英数字部分がページID。

インテグレーションの接続許可：対象ページ右上「…」→「コネクト」→作成したインテグレーションを選択。

### Google リフレッシュトークンの取得

1. [Google Cloud Console](https://console.cloud.google.com) でプロジェクト作成
2. 「APIとサービス」→「ライブラリ」→「Google Calendar API」を有効化
3. 「認証情報」→「OAuthクライアントID」→アプリの種類「デスクトップアプリ」で作成
4. 「OAuth同意画面」→「テストユーザー」に自分のGmailを追加
5. 認証情報の「承認済みリダイレクトURI」に `http://localhost:8080` を追加
6. 以下のURLをブラウザで開いてGoogleログイン・許可（`CLIENT_ID`を置き換え）:
```
https://accounts.google.com/o/oauth2/auth?client_id=CLIENT_ID&redirect_uri=http://localhost:8080&scope=https://www.googleapis.com/auth/calendar&response_type=code&access_type=offline&prompt=consent
```
7. リダイレクト後のURLから `code=` の値をコピーし、以下を実行（各値を置き換え）:
```bash
curl -X POST https://oauth2.googleapis.com/token \
  -d "code=CODE&client_id=CLIENT_ID&client_secret=CLIENT_SECRET&redirect_uri=http://localhost:8080&grant_type=authorization_code"
```
8. レスポンスの `refresh_token` を `.env` に設定

## 起動

```bash
venv\Scripts\activate
python .\ALIA.py
```
