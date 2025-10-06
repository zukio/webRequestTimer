# WebRequestTimer

指定された時刻・間隔でWebリクエストを送信するシステムトレイ常駐アプリケーションです。

## 主な機能

### 1. Webリクエスト送信
- **GET/POST対応**: HTTPメソッドGET、POSTをサポート
- **認証ヘッダー**: Authorization等のカスタムヘッダーに対応
- **リトライ機能**: 失敗時の自動リトライ（回数・遅延設定可能）
- **タイムアウト設定**: リクエストごとのタイムアウト設定

### 2. スケジュール管理
- **間隔指定**: 秒単位での定期実行
- **Cron式対応**: 複雑なスケジューリング（毎時、毎日等）
- **複数スケジュール**: 異なるURLに対する複数の定期実行設定
- **有効/無効切り替え**: 個別スケジュールの一時停止・再開

### 3. UDP通知機能 ⭐ NEW!
- **レスポンス変更検知**: 前回のレスポンスと比較し、変更があった場合に通知
- **成功/失敗通知**: リクエストの成功・失敗状態の通知
- **外部アプリ連携**: UDP経由で別のアプリケーションに通知を送信
- **通知設定**: 送信先アドレス・ポート、通知条件の詳細設定

### 4. システムトレイ常駐
- **バックグラウンド動作**: Windowsのシステムトレイに常駐
- **GUI操作**: トレイメニューからの直感的な操作
- **設定管理**: スケジュールの追加・編集・削除
- **リアルタイム状態表示**: 実行中ジョブ数や次回実行時刻の表示

### 5. ログ・統計機能
- **リクエスト履歴**: 全てのリクエスト結果をSQLiteに記録
- **成功率統計**: スケジュールごとの成功率・平均応答時間
- **ログローテーション**: 指定サイズでのログファイル自動切り替え
- **履歴検索**: 成功/失敗フィルタ、期間指定検索

## 起動方法

### トレイモード（通常）
```batch
run.bat
```

### コンソールモード（開発/デバッグ用）
```batch
run.bat --console
```

### コマンドライン操作
```batch
# 設定変更
run.bat --set key value

# 設定確認
run.bat --console
```

## 設定ファイル（config.json）

### 基本設定
```json
{
  "app_name": "WebRequestTimer",
  "enable_tray": true,
  "log_level": "INFO",
  "log_file": "logs/web_request_timer.log"
}
```

### リクエストスケジュール
```json
{
  "request_schedules": [
    {
      "id": "api_check",
      "name": "API状態確認",
      "enabled": true,
      "url": "https://api.example.com/status",
      "method": "GET",
      "headers": {
        "Authorization": "Bearer your_token_here",
        "User-Agent": "WebRequestTimer/1.0"
      },
      "body": null,
      "schedule_type": "interval",
      "interval_seconds": 300,
      "timeout_seconds": 30,
      "retry_count": 3
    }
  ]
}
```

### UDP通知設定
```json
{
  "udp_notification": {
    "enabled": true,
    "server_address": "localhost",
    "port": 12345,
    "delay_seconds": 1,
    "notify_on_success": true,
    "notify_on_failure": true,
    "notify_on_response_change": true,
    "max_response_size_bytes": 1024
  }
}
```

## UDP通知メッセージ形式

外部アプリケーションが受信するUDP通知メッセージの形式：

```json
{
  "application": "WebRequestTimer",
  "version": "1.0",
  "timestamp": "2025-10-06T15:30:00",
  "notification_type": "response_changed",
  "schedule": {
    "id": "api_check",
    "name": "API状態確認",
    "url": "https://api.example.com/status",
    "method": "GET"
  },
  "request_result": {
    "request_id": "api_check",
    "success": true,
    "status_code": 200,
    "response_time_ms": 150,
    "timestamp": "2025-10-06T15:30:00",
    "attempt": 1
  },
  "additional_data": {
    "is_response_changed": true,
    "response_hash": "abc123...",
    "previous_hash": "def456..."
  },
  "response_body": {
    "status": "ok",
    "version": "2.1.0"
  }
}
```

### 通知タイプ
- `first_success`: 初回成功時
- `response_changed`: レスポンス内容変更時
- `success_no_change`: 成功（変更なし）
- `failure`: 失敗時
- `recovery`: エラー状態からの回復時

## トレイメニュー操作

### スケジュール管理
- **新しいスケジュールを追加**: GUIでスケジュール作成
- **スケジュール一覧を表示**: 登録済みスケジュールの管理
- **スケジューラーを開始/停止**: 全体の実行制御

### 設定・監視
- **ログ・統計表示**: リクエスト履歴と統計情報
- **UDP通知設定**: 送信先・通知条件の設定
- **設定ファイル編集**: config.jsonの直接編集

## コンソールモードコマンド

```
webrt> status    # スケジューラー状態表示
webrt> start     # スケジューラー開始
webrt> stop      # スケジューラー停止
webrt> history   # 最近のリクエスト履歴
webrt> stats     # 統計情報表示
webrt> quit      # アプリケーション終了
```

## 使用例

### 1. API監視
定期的にAPI エンドポイントの状態をチェックし、レスポンスが変更された際に外部システムに通知

### 2. Webhook送信
定期的に外部システムに状態情報をPOST送信

### 3. サービス死活監視
重要なWebサービスの生存確認を定期実行し、障害時に通知

### 4. データ取得
外部APIから定期的にデータを取得し、更新があった場合に処理を起動

## 技術仕様

- **開発言語**: Python 3.8+
- **GUI**: pystray (システムトレイ), tkinter (設定ダイアログ)
- **HTTP通信**: aiohttp (非同期処理)
- **スケジューリング**: croniter (Cron式解析)
- **データベース**: SQLite (リクエスト履歴)
- **設定形式**: JSON

## ファイル構成

```
webRequestTimer/
├── main.py                    # メインアプリケーション
├── config.json               # 設定ファイル
├── requirements.txt          # 依存関係
├── run.bat                   # 実行スクリプト
├── logs/                     # ログディレクトリ
│   ├── web_request_timer.log # アプリケーションログ
│   └── request_history.db    # リクエスト履歴データベース
├── assets/
│   └── icon.ico             # トレイアイコン
└── modules/
    ├── web_request_client.py      # HTTPクライアント
    ├── request_scheduler.py       # スケジューラー
    ├── request_logger.py          # ログ管理
    ├── udp_notifier.py           # UDP通知
    ├── tray_app.py               # トレイアプリケーション
    ├── lock.py                   # 重複起動防止
    └── communication/
        └── udp_client.py         # UDP送信クライアント
```

## セットアップ手順

1. **仮想環境の作成**（既に作成済み）
2. **依存関係のインストール**
   ```batch
   venv\Scripts\pip install -r requirements.txt
   ```
3. **設定ファイルの編集** - config.jsonでスケジュールとUDP通知を設定
4. **実行**
   ```batch
   run.bat
   ```

## 今後の拡張案

- **認証方式の拡張**: OAuth 2.0、Basic認証等
- **レスポンス形式対応**: XML、CSV等
- **通知方式の追加**: メール、Slack、Teams等
- **GUI設定画面**: より詳細な設定画面
- **プラグインシステム**: カスタム処理の追加
- **クラスター対応**: 複数インスタンスでの分散実行

---

WebRequestTimerは軽量かつ高機能なWebリクエスト自動化ツールとして、API監視、定期データ取得、外部システム連携など幅広い用途でご活用いただけます。