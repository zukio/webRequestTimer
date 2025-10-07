"""
WebRequestTimer - Web Request Scheduler with System Tray

指定された時刻・間隔でWebリクエストを送信するシステムトレイ常駐アプリケーション
GET/POSTリクエスト、認証ヘッダー、Cron式・間隔指定をサポート
"""

import os
import sys
import signal
import argparse
import asyncio
import threading
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 自作モジュールのインポート
from modules.lock import SingleInstance
from modules.tray_app import start_tray_app
from modules.web_request_client import WebRequestClient
from modules.request_scheduler import RequestScheduler
from modules.request_logger import RequestLogger
from modules.udp_notifier import ResponseChangeDetector

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


class WebRequestTimerApp:
    """WebRequestTimerメインアプリケーション"""

    def __init__(self, config: Dict[str, Any]):
        """
        コンストラクタ

        Args:
            config: アプリケーション設定
        """
        self.config = config
        self.logger = None
        self.request_logger = None
        self.scheduler = None
        self.web_client = None
        self.tray_app = None
        self.udp_notifier = None
        self.running = False

        # ログ設定
        self._setup_logging()

        # コンポーネントの初期化
        self._initialize_components()

    def _setup_logging(self):
        """ログ設定を初期化する"""
        try:
            # RequestLoggerを使用してログ設定
            self.request_logger = RequestLogger(self.config)
            self.logger = logging.getLogger('WebRequestTimer.Main')
            self.logger.info("WebRequestTimer application initialized")
        except Exception as e:
            # フォールバック用の基本ログ設定
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(
                        'web_request_timer.log', encoding='utf-8')
                ]
            )
            self.logger = logging.getLogger('WebRequestTimer.Main')
            self.logger.error(f"Failed to initialize RequestLogger: {e}")

    def _initialize_components(self):
        """アプリケーションコンポーネントを初期化する"""
        try:
            # UDP通知機能の初期化
            udp_config = self.config.get('udp_notification', {})
            if udp_config.get('enabled', True):
                self.udp_notifier = ResponseChangeDetector(udp_config)

            # スケジューラーの初期化
            self.scheduler = RequestScheduler(self._request_callback)

            # トレイアプリの初期化
            self.tray_app = start_tray_app(
                self.config, self._scheduler_callback)

            self.logger.info("Application components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    async def _request_callback(self, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        リクエスト実行のコールバック

        Args:
            schedule_config: スケジュール設定

        Returns:
            Dict: リクエスト実行結果
        """
        try:
            # WebRequestClientを使用してリクエスト実行
            global_settings = self.config.get('global_settings', {})

            async with WebRequestClient(global_settings) as client:
                result = await client.send_request(schedule_config)

                # ログに記録
                if self.request_logger:
                    self.request_logger.log_request_result(
                        result, schedule_config)

                # UDP通知
                if self.udp_notifier:
                    self.udp_notifier.process_request_result(
                        result, schedule_config)

                return result

        except Exception as e:
            self.logger.error(f"Request callback error: {e}")
            error_result = {
                'request_id': schedule_config.get('id', 'unknown'),
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'error': str(e),
                'status_code': None,
                'response_body': None,
                'response_headers': None,
                'response_time_ms': None
            }

            # エラーもログに記録
            if self.request_logger:
                self.request_logger.log_request_result(
                    error_result, schedule_config)

            # UDP通知（エラー時）
            if self.udp_notifier:
                self.udp_notifier.process_request_result(
                    error_result, schedule_config)

            return error_result

    def _scheduler_callback(self, action: str, data: Dict[str, Any]) -> Any:
        """
        スケジューラー操作のコールバック

        Args:
            action: 操作タイプ
            data: 操作データ

        Returns:
            Any: 操作結果
        """
        try:
            if action == 'add_schedule':
                return self.scheduler.add_schedule(data)

            elif action == 'remove_schedule':
                schedule_id = data.get('schedule_id')
                return self.scheduler.remove_schedule(schedule_id)

            elif action == 'update_schedule':
                return self.scheduler.update_schedule(data)

            elif action == 'get_status':
                status = self.scheduler.get_schedule_status()
                # トレイアプリの状態を更新
                if self.tray_app:
                    self.tray_app.update_status(status)
                return status

            elif action == 'start':
                try:
                    loop = asyncio.get_running_loop()
                    return asyncio.create_task(self._start_scheduler_async())
                except RuntimeError:
                    # イベントループが実行されていない場合は新しいループで実行
                    try:
                        asyncio.run(self._start_scheduler_async())
                        return True
                    except Exception as e:
                        self.logger.error(f"Failed to start scheduler: {e}")
                        return False

            elif action == 'stop':
                try:
                    loop = asyncio.get_running_loop()
                    return asyncio.create_task(self._stop_scheduler_async())
                except RuntimeError:
                    # イベントループが実行されていない場合は、スレッドセーフな停止処理を実行
                    try:
                        # スケジューラーに停止フラグを設定（同期的に実行可能）
                        if self.scheduler:
                            self.scheduler.stop_sync()
                            self.logger.info(
                                "Scheduler stop flag set successfully")

                        # トレイアプリの状態を更新
                        if self.tray_app:
                            status = {'scheduler_running': False,
                                      'total_jobs': 0, 'running_jobs': 0}
                            self.tray_app.update_status(status)

                        return True
                    except Exception as e:
                        self.logger.error(f"Failed to stop scheduler: {e}")
                        return False

            elif action == 'get_history':
                if self.request_logger:
                    return self.request_logger.get_request_history(limit=100)
                return []

            elif action == 'get_statistics':
                stats = {}
                if self.request_logger:
                    stats.update(self.request_logger.get_schedule_statistics())
                if self.udp_notifier:
                    stats['udp_notification'] = self.udp_notifier.get_statistics()
                return stats

            elif action == 'update_udp_config':
                if self.udp_notifier:
                    self.udp_notifier.update_config(data)
                    # 設定も更新
                    self.config['udp_notification'] = data
                    return True
                return False

            elif action == 'test_request':
                # 最初の有効なスケジュールでテスト実行
                schedules = self.config.get('request_schedules', [])
                for schedule in schedules:
                    if schedule.get('enabled', True):
                        try:
                            loop = asyncio.get_running_loop()
                            return asyncio.create_task(self._request_callback(schedule))
                        except RuntimeError:
                            # イベントループが実行されていない場合は新しいループで実行
                            try:
                                result = asyncio.run(
                                    self._request_callback(schedule))
                                return result
                            except Exception as e:
                                self.logger.error(
                                    f"Failed to run test request: {e}")
                                return None
                return None

            else:
                self.logger.warning(
                    f"Unknown scheduler callback action: {action}")
                return None

        except Exception as e:
            self.logger.error(
                f"Scheduler callback error for action '{action}': {e}")
            return None

    async def _start_scheduler_async(self):
        """スケジューラーを非同期で開始する"""
        try:
            # 設定からスケジュールを読み込み
            schedules = self.config.get('request_schedules', [])
            for schedule in schedules:
                if schedule.get('enabled', True):
                    self.scheduler.add_schedule(schedule)

            await self.scheduler.start()
            self.logger.info("Scheduler started successfully")

            # トレイアプリの状態を更新
            if self.tray_app:
                status = self.scheduler.get_schedule_status()
                self.tray_app.update_status(status)

        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")

    async def _stop_scheduler_async(self):
        """スケジューラーを非同期で停止する"""
        try:
            if self.scheduler:
                await self.scheduler.stop()
                self.logger.info("Scheduler stopped successfully")
            else:
                self.logger.warning("Scheduler is not initialized")

            # トレイアプリの状態を更新
            if self.tray_app:
                status = self.scheduler.get_schedule_status() if self.scheduler else {
                    'scheduler_running': False}
                self.tray_app.update_status(status)

        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {e}")

    async def start(self):
        """アプリケーションを開始する"""
        try:
            self.running = True
            self.logger.info("WebRequestTimer application starting...")

            # 自動開始が有効な場合、スケジューラーを開始
            if self.config.get('auto_start_scheduler', True):
                await self._start_scheduler_async()

            # メインループ
            await self._main_loop()

        except Exception as e:
            self.logger.error(f"Application start error: {e}")
            raise

    async def stop(self):
        """アプリケーションを停止する"""
        try:
            self.running = False
            self.logger.info("WebRequestTimer application stopping...")

            # スケジューラーを停止
            if self.scheduler:
                await self.scheduler.stop()

            # トレイアプリを停止
            if self.tray_app:
                self.tray_app.running = False

            self.logger.info("WebRequestTimer application stopped")

        except Exception as e:
            self.logger.error(f"Application stop error: {e}")

    async def _main_loop(self):
        """アプリケーションのメインループ"""
        try:
            while self.running:
                # スケジューラーの状態をトレイアプリに更新
                if self.scheduler and self.tray_app:
                    status = self.scheduler.get_schedule_status()
                    self.tray_app.update_status(status)

                # 1秒間隔で状態更新
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Main loop cancelled")
        except Exception as e:
            self.logger.error(f"Main loop error: {e}")


def load_config() -> Dict[str, Any]:
    """設定ファイルを読み込む"""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # デフォルト設定を作成
            default_config = {
                "app_name": "WebRequestTimer",
                "enable_tray": True,
                "auto_start_scheduler": False,
                "log_level": "INFO",
                "log_file": "logs/web_request_timer.log",
                "max_log_size_mb": 10,
                "backup_log_count": 5,
                "request_schedules": [],
                "global_settings": {
                    "user_agent": "WebRequestTimer/1.0",
                    "default_timeout": 30,
                    "default_retry_count": 3,
                    "default_retry_delay": 5,
                    "verify_ssl": True,
                    "follow_redirects": True,
                    "max_concurrent_requests": 5
                },
                "udp_notification": {
                    "enabled": False,
                    "server_address": "localhost",
                    "port": 12345,
                    "delay_seconds": 1,
                    "notify_on_success": True,
                    "notify_on_failure": True,
                    "notify_on_response_change": True,
                    "max_response_size_bytes": 1024,
                    "response_change_threshold": 0.1
                }
            }

            # ディレクトリを作成
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

            # デフォルト設定を保存
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)

            return default_config

    except Exception as e:
        print(f"Failed to load config: {e}")
        return {}


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description='WebRequestTimer - Web Request Scheduler')
    parser.add_argument('--console', action='store_true',
                        help='コンソールモードで起動（トレイアイコンなし）')
    parser.add_argument('--config', type=str, default=CONFIG_PATH,
                        help='設定ファイルのパス')
    parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'),
                        help='設定を変更（--set key value）')
    parser.add_argument('--test', action='store_true',
                        help='設定のテスト実行')
    parser.add_argument('--no-auto-start', action='store_true',
                        help='スケジューラーの自動開始を無効化')

    return parser.parse_args()


async def console_mode(app: WebRequestTimerApp):
    """コンソールモードでアプリケーションを実行する"""
    print("WebRequestTimer - Console Mode")
    print("Commands: status, start, stop, history, stats, quit")

    try:
        from aioconsole import ainput

        while app.running:
            try:
                command = await ainput("webrt> ")
                command = command.strip().lower()

                if command == 'quit' or command == 'exit':
                    break
                elif command == 'status':
                    status = app.scheduler.get_schedule_status()
                    print(json.dumps(status, indent=2, ensure_ascii=False))
                elif command == 'start':
                    await app._start_scheduler_async()
                    print("Scheduler started")
                elif command == 'stop':
                    await app._stop_scheduler_async()
                    print("Scheduler stopped")
                elif command == 'history':
                    if app.request_logger:
                        history = app.request_logger.get_request_history(
                            limit=10)
                        print(f"Recent {len(history)} requests:")
                        for record in history:
                            print(
                                f"  {record.get('timestamp')} - {record.get('request_id')} - {'SUCCESS' if record.get('success') else 'FAILED'}")
                elif command == 'stats':
                    if app.request_logger:
                        stats = app.request_logger.get_schedule_statistics()
                        print(json.dumps(stats, indent=2, ensure_ascii=False))
                elif command == 'help':
                    print("Available commands:")
                    print("  status  - Show scheduler status")
                    print("  start   - Start scheduler")
                    print("  stop    - Stop scheduler")
                    print("  history - Show request history")
                    print("  stats   - Show statistics")
                    print("  quit    - Exit application")
                else:
                    print(f"Unknown command: {command}")

            except EOFError:
                break
            except Exception as e:
                print(f"Command error: {e}")

    except ImportError:
        print("aioconsole not available, running without interactive console")
        # 無限ループで待機
        while app.running:
            await asyncio.sleep(1)


def main():
    """メイン関数"""
    args = parse_args()

    # 設定ファイルのパスを設定
    global CONFIG_PATH
    CONFIG_PATH = args.config

    # 設定読み込み
    config = load_config()

    # 設定変更モード
    if args.set:
        key, value = args.set
        # 値の型推論
        if value.lower() in ['true', 'false']:
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass  # 文字列のまま

        config[key] = value
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f'設定 {key} を {value} に変更しました')
        return

    # 自動開始の無効化
    if args.no_auto_start:
        config['auto_start_scheduler'] = False

    # 重複起動防止
    lock = SingleInstance('WebRequestTimer')
    try:
        lock.acquire()

        # アプリケーション初期化
        app = WebRequestTimerApp(config)

        # 終了処理のセットアップ
        def signal_handler(signum, frame):
            print(f"\nSignal {signum} received, shutting down...")
            asyncio.create_task(app.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 実行モードの選択
        if args.console:
            # コンソールモード
            print("Starting WebRequestTimer in console mode...")
            asyncio.run(console_mode(app))
        else:
            # トレイモード
            if not config.get('enable_tray', True):
                print("Tray mode disabled in config, falling back to console mode")
                asyncio.run(console_mode(app))
            else:
                print("Starting WebRequestTimer in tray mode...")
                asyncio.run(app.start())

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Application error: {e}")
        return 1
    finally:
        lock.release()

    return 0


if __name__ == '__main__':
    sys.exit(main())
