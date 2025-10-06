"""
UDP Notification Module for WebRequestTimer

レスポンス変更検知とUDP通知機能を提供します。
既存のDelayedUDPSenderを活用して、レスポンス内容が変更された際に外部アプリケーションに通知します。
"""

import json
import hashlib
import logging
import pickle
from datetime import datetime
from typing import Dict, Any, Optional, Set
from modules.communication.udp_client import DelayedUDPSender


class ResponseChangeDetector:
    """レスポンス変更検知とUDP通知を行うクラス"""

    def __init__(self, udp_config: Dict[str, Any]):
        """
        コンストラクタ

        Args:
            udp_config: UDP通知設定
        """
        self.udp_config = udp_config
        self.logger = logging.getLogger(__name__)

        # DelayedUDPSenderの初期化
        delay_seconds = udp_config.get('delay_seconds', 1)
        self.udp_sender = DelayedUDPSender(delay_seconds)

        # レスポンス履歴の保存（schedule_id -> response_hash）
        self.response_hashes: Dict[str, str] = {}

        # 通知済みのエラー状態を追跡（重複通知を防ぐため）
        self.notified_errors: Set[str] = set()

        self.logger.info("ResponseChangeDetector initialized")

    def process_request_result(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """
        リクエスト結果を処理してレスポンス変更を検知し、必要に応じてUDP通知を送信する

        Args:
            request_result: リクエスト実行結果
            schedule_config: スケジュール設定
        """
        if not self.udp_config.get('enabled', True):
            return

        request_id = request_result.get('request_id', 'unknown')
        success = request_result.get('success', False)

        try:
            # 成功時の処理
            if success:
                self._handle_success_response(request_result, schedule_config)
                # エラー状態から回復した場合の通知
                if request_id in self.notified_errors:
                    self.notified_errors.remove(request_id)
                    self._send_recovery_notification(
                        request_result, schedule_config)
            else:
                # 失敗時の処理
                self._handle_failure_response(request_result, schedule_config)

        except Exception as e:
            self.logger.error(
                f"Error processing request result for UDP notification: {e}")

    def _handle_success_response(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """成功したレスポンスを処理する"""
        request_id = request_result.get('request_id')
        response_body = request_result.get('response_body')

        # レスポンス内容のハッシュを計算
        current_hash = self._calculate_response_hash(response_body)
        previous_hash = self.response_hashes.get(request_id)

        # 初回実行またはレスポンス変更の検知
        is_first_run = previous_hash is None
        is_response_changed = previous_hash and previous_hash != current_hash

        # ハッシュを更新
        self.response_hashes[request_id] = current_hash

        # 通知条件の判定
        should_notify = False
        notification_type = None

        if is_first_run and self.udp_config.get('notify_on_success', True):
            should_notify = True
            notification_type = 'first_success'
        elif is_response_changed and self.udp_config.get('notify_on_response_change', True):
            should_notify = True
            notification_type = 'response_changed'
        elif not is_response_changed and self.udp_config.get('notify_on_success', False):
            # 変更なしでも成功時に通知する設定の場合
            should_notify = True
            notification_type = 'success_no_change'

        if should_notify:
            self._send_udp_notification(request_result, schedule_config, notification_type, {
                'is_first_run': is_first_run,
                'is_response_changed': is_response_changed,
                'response_hash': current_hash,
                'previous_hash': previous_hash
            })

    def _handle_failure_response(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """失敗したレスポンスを処理する"""
        if not self.udp_config.get('notify_on_failure', True):
            return

        request_id = request_result.get('request_id')

        # 重複エラー通知を防ぐ
        error_key = f"{request_id}_{request_result.get('error', 'unknown_error')}"
        if error_key in self.notified_errors:
            return

        self.notified_errors.add(error_key)

        self._send_udp_notification(request_result, schedule_config, 'failure', {
            'error_message': request_result.get('error', 'Unknown error'),
            'status_code': request_result.get('status_code'),
            'attempt_count': request_result.get('attempt', 1)
        })

    def _send_recovery_notification(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any]):
        """エラー状態からの回復通知を送信する"""
        self._send_udp_notification(request_result, schedule_config, 'recovery', {
            'message': 'Request recovered from error state'
        })

    def _calculate_response_hash(self, response_body: Any) -> str:
        """
        レスポンス内容のハッシュを計算する

        Args:
            response_body: レスポンス内容

        Returns:
            str: SHA-256ハッシュ値
        """
        try:
            if response_body is None:
                return hashlib.sha256(b'').hexdigest()

            # レスポンス内容を文字列に変換
            if isinstance(response_body, dict):
                # 辞書の場合はJSONでシリアライズ（キー順序を固定）
                content_str = json.dumps(
                    response_body, sort_keys=True, ensure_ascii=False)
            else:
                content_str = str(response_body)

            # SHA-256ハッシュを計算
            return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

        except Exception as e:
            self.logger.error(f"Failed to calculate response hash: {e}")
            return hashlib.sha256(b'error_calculating_hash').hexdigest()

    def _send_udp_notification(self, request_result: Dict[str, Any], schedule_config: Dict[str, Any],
                               notification_type: str, additional_data: Dict[str, Any] = None):
        """
        UDP通知を送信する

        Args:
            request_result: リクエスト実行結果
            schedule_config: スケジュール設定
            notification_type: 通知タイプ
            additional_data: 追加データ
        """
        try:
            # 通知メッセージの構築
            notification_message = {
                'application': 'WebRequestTimer',
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'notification_type': notification_type,
                'schedule': {
                    'id': schedule_config.get('id'),
                    'name': schedule_config.get('name'),
                    'url': schedule_config.get('url'),
                    'method': schedule_config.get('method')
                },
                'request_result': {
                    'request_id': request_result.get('request_id'),
                    'success': request_result.get('success'),
                    'status_code': request_result.get('status_code'),
                    'response_time_ms': request_result.get('response_time_ms'),
                    'timestamp': request_result.get('timestamp'),
                    'attempt': request_result.get('attempt', 1)
                }
            }

            # 追加データがある場合は含める
            if additional_data:
                notification_message['additional_data'] = additional_data

            # 成功時はレスポンス内容も含める（サイズ制限あり）
            if (request_result.get('success') and
                    notification_type in ['first_success', 'response_changed']):

                response_body = request_result.get('response_body')
                if response_body:
                    # レスポンス内容のサイズ制限（デフォルト: 1KB）
                    max_response_size = self.udp_config.get(
                        'max_response_size_bytes', 1024)
                    response_str = json.dumps(response_body, ensure_ascii=False) if isinstance(
                        response_body, dict) else str(response_body)

                    if len(response_str.encode('utf-8')) <= max_response_size:
                        notification_message['response_body'] = response_body
                    else:
                        notification_message['response_body_truncated'] = True
                        notification_message['response_size_bytes'] = len(
                            response_str.encode('utf-8'))

            # エラー時はエラー情報を含める
            if not request_result.get('success'):
                notification_message['error'] = request_result.get('error')

            # UDP送信
            server_address = self.udp_config.get('server_address', 'localhost')
            port = self.udp_config.get('port', 12345)

            self.udp_sender.send_message(
                server_address, port, notification_message)

            self.logger.info(
                f"UDP notification sent: {notification_type} for {request_result.get('request_id')}")

        except Exception as e:
            self.logger.error(f"Failed to send UDP notification: {e}")

    def update_config(self, new_udp_config: Dict[str, Any]):
        """
        UDP設定を更新する

        Args:
            new_udp_config: 新しいUDP設定
        """
        self.udp_config = new_udp_config

        # DelayedUDPSenderの遅延時間を更新
        delay_seconds = new_udp_config.get('delay_seconds', 1)
        self.udp_sender.delay = delay_seconds

        self.logger.info("UDP configuration updated")

    def get_statistics(self) -> Dict[str, Any]:
        """
        UDP通知の統計情報を取得する

        Returns:
            Dict: 統計情報
        """
        return {
            'total_tracked_schedules': len(self.response_hashes),
            'active_error_notifications': len(self.notified_errors),
            'udp_config': self.udp_config,
            'tracked_schedules': list(self.response_hashes.keys())
        }

    def clear_history(self, schedule_id: Optional[str] = None):
        """
        レスポンス履歴をクリアする

        Args:
            schedule_id: 特定のスケジュールID（Noneの場合は全履歴をクリア）
        """
        if schedule_id:
            self.response_hashes.pop(schedule_id, None)
            # エラー通知状態もクリア
            self.notified_errors = {
                err for err in self.notified_errors if not err.startswith(f"{schedule_id}_")}
            self.logger.info(f"Cleared history for schedule {schedule_id}")
        else:
            self.response_hashes.clear()
            self.notified_errors.clear()
            self.logger.info("Cleared all response history")


# テスト用関数
def test_response_change_detector():
    """ResponseChangeDetectorのテスト用関数"""
    udp_config = {
        'enabled': True,
        'server_address': 'localhost',
        'port': 12345,
        'delay_seconds': 1,
        'notify_on_success': True,
        'notify_on_failure': True,
        'notify_on_response_change': True,
        'max_response_size_bytes': 1024
    }

    detector = ResponseChangeDetector(udp_config)

    # テスト用のスケジュール設定
    test_schedule = {
        'id': 'test_schedule',
        'name': 'Test Schedule',
        'url': 'https://httpbin.org/get',
        'method': 'GET'
    }

    # テスト用のリクエスト結果（初回成功）
    result1 = {
        'request_id': 'test_schedule',
        'timestamp': datetime.now().isoformat(),
        'success': True,
        'status_code': 200,
        'response_time_ms': 150,
        'response_body': {'message': 'Hello World', 'version': '1.0'},
        'attempt': 1
    }

    print("Testing first success...")
    detector.process_request_result(result1, test_schedule)

    # テスト用のリクエスト結果（レスポンス変更）
    result2 = {
        'request_id': 'test_schedule',
        'timestamp': datetime.now().isoformat(),
        'success': True,
        'status_code': 200,
        'response_time_ms': 140,
        # バージョンが変更
        'response_body': {'message': 'Hello World', 'version': '2.0'},
        'attempt': 1
    }

    print("Testing response change...")
    detector.process_request_result(result2, test_schedule)

    # テスト用のリクエスト結果（エラー）
    result3 = {
        'request_id': 'test_schedule',
        'timestamp': datetime.now().isoformat(),
        'success': False,
        'error': 'Connection timeout',
        'status_code': None,
        'response_time_ms': None,
        'attempt': 1
    }

    print("Testing failure...")
    detector.process_request_result(result3, test_schedule)

    # 統計情報の表示
    stats = detector.get_statistics()
    print("Statistics:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    test_response_change_detector()
