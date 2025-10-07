"""
Enhanced Logging Module for WebRequestTimer

このモジュールはWebRequestTimerアプリケーション用の包括的なログ機能を提供します。
リクエスト履歴、成功/失敗ログ、レスポンス内容の記録、ログローテーション機能を含みます。
"""

import logging
import logging.handlers
import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import threading


class RequestLogger:
    """WebRequestTimer専用のログ管理クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        コンストラクタ

        Args:
            config: アプリケーション設定
        """
        self.config = config
        self.logger = logging.getLogger('WebRequestTimer')
        self.db_lock = threading.Lock()

        # ログディレクトリの作成
        self.log_dir = Path(os.path.dirname(config.get(
            'log_file', 'logs/web_request_timer.log')))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # データベース初期化
        self.db_path = self.log_dir / 'request_history.db'
        self._init_database()

        # ファイルログの設定
        self._setup_file_logging()

        self.logger.info("RequestLogger initialized")

    def _setup_file_logging(self):
        """ファイルログの設定を行う"""
        log_file = self.config.get('log_file', 'logs/web_request_timer.log')
        log_level = getattr(logging, self.config.get(
            'log_level', 'INFO').upper())
        max_size_mb = self.config.get('max_log_size_mb', 10)
        backup_count = self.config.get('backup_log_count', 5)

        # 既存のハンドラーをクリア
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # ローテーションファイルハンドラーの設定
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )

        # コンソールハンドラーの設定
        console_handler = logging.StreamHandler()

        # フォーマッターの設定
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # ハンドラーをロガーに追加
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.setLevel(log_level)

    def _init_database(self):
        """SQLiteデータベースの初期化"""
        with sqlite3.connect(self.db_path) as conn:
            # リクエスト履歴テーブル
            conn.execute('''
                CREATE TABLE IF NOT EXISTS request_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    schedule_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL,
                    headers TEXT,
                    request_body TEXT,
                    success BOOLEAN NOT NULL,
                    status_code INTEGER,
                    response_time_ms INTEGER,
                    response_headers TEXT,
                    response_body TEXT,
                    error_message TEXT,
                    attempt_count INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # スケジュール統計テーブル
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schedule_stats (
                    schedule_id TEXT PRIMARY KEY,
                    schedule_name TEXT NOT NULL,
                    total_requests INTEGER DEFAULT 0,
                    successful_requests INTEGER DEFAULT 0,
                    failed_requests INTEGER DEFAULT 0,
                    last_request_time TEXT,
                    last_success_time TEXT,
                    last_failure_time TEXT,
                    average_response_time_ms REAL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # インデックスの作成
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_request_history_timestamp ON request_history(timestamp)')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_request_history_request_id ON request_history(request_id)')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_request_history_success ON request_history(success)')

            conn.commit()

    def log_request_result(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """
        リクエスト結果をログに記録する

        Args:
            request_result: リクエスト実行結果
            schedule_config: スケジュール設定
        """
        try:
            # ログメッセージの作成
            request_id = request_result.get('request_id', 'unknown')
            success = request_result.get('success', False)
            status_code = request_result.get('status_code')
            response_time = request_result.get('response_time_ms', 0)
            error_message = request_result.get('error', '')

            # ログ出力
            if success:
                self.logger.info(
                    f"Request {request_id} SUCCESS - Status: {status_code}, "
                    f"Time: {response_time}ms, URL: {schedule_config.get('url', 'unknown')}"
                )
            else:
                self.logger.error(
                    f"Request {request_id} FAILED - Error: {error_message}, "
                    f"URL: {schedule_config.get('url', 'unknown')}"
                )

            # データベースに記録
            self._save_to_database(request_result, schedule_config)

        except Exception as e:
            self.logger.error(f"Failed to log request result: {e}")

    def _save_to_database(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """データベースにリクエスト結果を保存する"""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # データ型の検証と変換
                    status_code = request_result.get('status_code')
                    if status_code is not None:
                        try:
                            status_code = int(status_code)
                        except (ValueError, TypeError):
                            status_code = None

                    response_time_ms = request_result.get('response_time_ms')
                    if response_time_ms is not None:
                        try:
                            response_time_ms = int(float(response_time_ms))
                        except (ValueError, TypeError):
                            response_time_ms = None

                    attempt_count = request_result.get('attempt', 1)
                    try:
                        attempt_count = int(attempt_count)
                    except (ValueError, TypeError):
                        attempt_count = 1

                    # リクエスト履歴の保存
                    conn.execute('''
                        INSERT INTO request_history (
                            request_id, schedule_name, timestamp, url, method, headers,
                            request_body, success, status_code, response_time_ms,
                            response_headers, response_body, error_message, attempt_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        str(request_result.get('request_id', '')),
                        str(schedule_config.get(
                            'name', schedule_config.get('id', ''))),
                        str(request_result.get('timestamp', '')),
                        str(schedule_config.get('url', '')),
                        str(schedule_config.get('method', '')),
                        json.dumps(schedule_config.get(
                            'headers', {}), ensure_ascii=False),
                        json.dumps(schedule_config.get(
                            'body'), ensure_ascii=False) if schedule_config.get('body') else None,
                        bool(request_result.get('success', False)),
                        status_code,
                        response_time_ms,
                        json.dumps(request_result.get(
                            'response_headers', {}), ensure_ascii=False),
                        json.dumps(request_result.get('response_body'), ensure_ascii=False) if request_result.get(
                            'response_body') else None,
                        str(request_result.get('error', '')
                            ) if request_result.get('error') else None,
                        attempt_count
                    ))

                    # 統計情報の更新
                    self._update_schedule_stats(
                        conn, request_result, schedule_config)

                    conn.commit()

            except Exception as e:
                self.logger.error(f"Database save error: {e}")

    def _update_schedule_stats(self, conn: sqlite3.Connection, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """スケジュール統計情報を更新する"""
        schedule_id = schedule_config.get('id')
        schedule_name = schedule_config.get('name', schedule_id)
        success = request_result.get('success', False)
        response_time = request_result.get('response_time_ms', 0)
        timestamp = request_result.get('timestamp')

        # 既存の統計を取得
        cursor = conn.execute(
            'SELECT * FROM schedule_stats WHERE schedule_id = ?', (schedule_id,))
        existing_stats = cursor.fetchone()

        if existing_stats:
            # 既存統計の更新
            total_requests = existing_stats[2] + 1
            successful_requests = existing_stats[3] + (1 if success else 0)
            failed_requests = existing_stats[4] + (0 if success else 1)

            # 平均応答時間の計算
            if success and response_time is not None:
                try:
                    response_time_num = float(
                        response_time) if response_time is not None else 0
                    current_avg = float(
                        existing_stats[7]) if existing_stats[7] is not None else 0
                    new_avg = (
                        (current_avg * existing_stats[3]) + response_time_num) / successful_requests
                except (ValueError, TypeError):
                    new_avg = existing_stats[7] or 0
            else:
                new_avg = existing_stats[7] or 0

            conn.execute('''
                UPDATE schedule_stats SET
                    schedule_name = ?, total_requests = ?, successful_requests = ?,
                    failed_requests = ?, last_request_time = ?,
                    last_success_time = CASE WHEN ? THEN ? ELSE last_success_time END,
                    last_failure_time = CASE WHEN NOT ? THEN ? ELSE last_failure_time END,
                    average_response_time_ms = ?, updated_at = CURRENT_TIMESTAMP
                WHERE schedule_id = ?
            ''', (
                schedule_name, total_requests, successful_requests, failed_requests,
                timestamp, success, timestamp, success, timestamp, new_avg, schedule_id
            ))
        else:
            # 新規統計の作成
            try:
                avg_response_time = float(
                    response_time) if success and response_time is not None else 0
            except (ValueError, TypeError):
                avg_response_time = 0

            conn.execute('''
                INSERT INTO schedule_stats (
                    schedule_id, schedule_name, total_requests, successful_requests,
                    failed_requests, last_request_time, last_success_time,
                    last_failure_time, average_response_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                schedule_id, schedule_name, 1, 1 if success else 0, 0 if success else 1,
                timestamp, timestamp if success else None,
                timestamp if not success else None, avg_response_time
            ))

    def get_request_history(self,
                            schedule_id: Optional[str] = None,
                            limit: int = 100,
                            success_filter: Optional[bool] = None,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        リクエスト履歴を取得する

        Args:
            schedule_id: 特定のスケジュールID
            limit: 取得件数の上限
            success_filter: 成功/失敗のフィルター
            start_date: 開始日時（ISO形式）
            end_date: 終了日時（ISO形式）

        Returns:
            List[Dict]: リクエスト履歴のリスト
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    query = 'SELECT * FROM request_history WHERE 1=1'
                    params = []

                    if schedule_id:
                        query += ' AND request_id LIKE ?'
                        params.append(f'{schedule_id}%')

                    if success_filter is not None:
                        query += ' AND success = ?'
                        params.append(success_filter)

                    if start_date:
                        query += ' AND timestamp >= ?'
                        params.append(start_date)

                    if end_date:
                        query += ' AND timestamp <= ?'
                        params.append(end_date)

                    query += ' ORDER BY timestamp DESC LIMIT ?'
                    params.append(limit)

                    cursor = conn.execute(query, params)
                    rows = cursor.fetchall()

                    # 辞書形式に変換
                    columns = [description[0]
                               for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]

            except Exception as e:
                self.logger.error(f"Failed to get request history: {e}")
                return []

    def get_schedule_statistics(self, schedule_id: Optional[str] = None) -> Dict[str, Any]:
        """
        スケジュール統計情報を取得する

        Args:
            schedule_id: 特定のスケジュールID

        Returns:
            Dict: 統計情報
        """
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    if schedule_id:
                        cursor = conn.execute(
                            'SELECT * FROM schedule_stats WHERE schedule_id = ?', (schedule_id,))
                        row = cursor.fetchone()
                        if row:
                            columns = [description[0]
                                       for description in cursor.description]
                            return dict(zip(columns, row))
                        else:
                            return {}
                    else:
                        cursor = conn.execute('SELECT * FROM schedule_stats')
                        rows = cursor.fetchall()
                        columns = [description[0]
                                   for description in cursor.description]
                        return {
                            'schedules': [dict(zip(columns, row)) for row in rows],
                            'summary': self._get_global_statistics(conn)
                        }

            except Exception as e:
                self.logger.error(f"Failed to get schedule statistics: {e}")
                return {}

    def _get_global_statistics(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """グローバル統計情報を取得する"""
        try:
            # 総リクエスト数
            cursor = conn.execute(
                'SELECT SUM(total_requests), SUM(successful_requests), SUM(failed_requests) FROM schedule_stats')
            total_requests, successful_requests, failed_requests = cursor.fetchone()

            # 最近24時間のリクエスト数
            yesterday = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0)
            cursor = conn.execute(
                'SELECT COUNT(*) FROM request_history WHERE timestamp >= ?',
                (yesterday.isoformat(),)
            )
            recent_requests = cursor.fetchone()[0]

            return {
                'total_requests': total_requests or 0,
                'successful_requests': successful_requests or 0,
                'failed_requests': failed_requests or 0,
                'success_rate': (successful_requests / total_requests * 100) if total_requests else 0,
                'recent_24h_requests': recent_requests or 0
            }

        except Exception as e:
            self.logger.error(f"Failed to get global statistics: {e}")
            return {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'success_rate': 0,
                'recent_24h_requests': 0
            }

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """
        古いログデータを削除する

        Args:
            days_to_keep: 保持する日数
        """
        with self.db_lock:
            try:
                cutoff_date = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=days_to_keep)

                with sqlite3.connect(self.db_path) as conn:
                    # 古いリクエスト履歴を削除
                    cursor = conn.execute(
                        'DELETE FROM request_history WHERE timestamp < ?',
                        (cutoff_date.isoformat(),)
                    )
                    deleted_count = cursor.rowcount

                    # 統計情報は削除しない（累計のため）

                    conn.commit()

                self.logger.info(
                    f"Cleaned up {deleted_count} old log entries (older than {days_to_keep} days)")

            except Exception as e:
                self.logger.error(f"Failed to cleanup old logs: {e}")


# 使用例とテスト
def test_request_logger():
    """RequestLoggerのテスト用関数"""
    config = {
        'log_file': 'logs/test_web_request_timer.log',
        'log_level': 'INFO',
        'max_log_size_mb': 5,
        'backup_log_count': 3
    }

    logger = RequestLogger(config)

    # テスト用のリクエスト結果
    test_request_result = {
        'request_id': 'test_request_001',
        'timestamp': datetime.now().isoformat(),
        'success': True,
        'status_code': 200,
        'response_time_ms': 150,
        'response_headers': {'Content-Type': 'application/json'},
        'response_body': {'message': 'Hello World'},
        'attempt': 1
    }

    test_schedule_config = {
        'id': 'test_schedule',
        'name': 'Test Schedule',
        'url': 'https://httpbin.org/get',
        'method': 'GET',
        'headers': {'User-Agent': 'Test-Agent'},
        'body': None
    }

    # ログ記録テスト
    logger.log_request_result(test_request_result, test_schedule_config)

    # 履歴取得テスト
    history = logger.get_request_history(limit=10)
    print(f"取得した履歴件数: {len(history)}")

    # 統計取得テスト
    stats = logger.get_schedule_statistics()
    print("統計情報:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # テスト実行
    from datetime import timedelta
    test_request_logger()
