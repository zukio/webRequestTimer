#!/usr/bin/env python3
"""
UDP通知を受信して内容を表示するテストスクリプト
"""

import socket
import json
import threading
from datetime import datetime
from pathlib import Path


class UDPNotificationReceiver:
    """UDP通知を受信するクラス"""

    def __init__(self, host='localhost', port=12345):
        """
        コンストラクタ

        Args:
            host: 受信するホスト
            port: 受信するポート
        """
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.received_count = 0

    def start_listening(self):
        """UDP通知の受信を開始する"""
        try:
            # UDPソケットを作成
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.running = True

            print(f"🎧 UDP通知受信を開始しました: {self.host}:{self.port}")
            print("=" * 60)
            print("Ctrl+C で停止できます")
            print("=" * 60)

            while self.running:
                try:
                    # データを受信（最大8192バイト）
                    data, addr = self.socket.recvfrom(8192)
                    self.received_count += 1

                    # データをパース（pickleまたはJSON）
                    try:
                        # まずpickleで試行
                        import pickle
                        message = pickle.loads(data)
                        print(f"📦 Pickleデータを受信")
                        self._display_notification(message, addr)
                    except (pickle.UnpicklingError, pickle.PickleError):
                        try:
                            # pickleでダメならJSONで試行
                            message = json.loads(data.decode('utf-8'))
                            print(f"📄 JSONデータを受信")
                            self._display_notification(message, addr)
                        except json.JSONDecodeError as e:
                            print(f"⚠️  データ解析エラー: Pickle/JSON両方で失敗")
                            print(f"Pickleエラー: データがpickle形式ではありません")
                            print(f"JSONエラー: {e}")
                            print(f"生データ (最初の100バイト): {data[:100]}")
                    except Exception as e:
                        print(f"⚠️  予期しないエラー: {e}")
                        print(f"データ長: {len(data)} bytes")

                except socket.error as e:
                    if self.running:
                        print(f"❌ ソケットエラー: {e}")
                        break

        except Exception as e:
            print(f"❌ 受信開始エラー: {e}")

    def _display_notification(self, message, addr):
        """受信した通知を表示する"""
        print(
            f"\n📨 受信 #{self.received_count} - {datetime.now().strftime('%H:%M:%S')}")
        print(f"送信元: {addr[0]}:{addr[1]}")
        print("-" * 40)

        # 基本情報
        print(f"アプリケーション: {message.get('application', 'N/A')}")
        print(f"バージョン: {message.get('version', 'N/A')}")
        print(f"通知タイプ: {message.get('notification_type', 'N/A')}")
        print(f"タイムスタンプ: {message.get('timestamp', 'N/A')}")

        # スケジュール情報
        schedule = message.get('schedule', {})
        if schedule:
            print(f"\n📅 スケジュール情報:")
            print(f"  ID: {schedule.get('id', 'N/A')}")
            print(f"  名前: {schedule.get('name', 'N/A')}")
            print(f"  URL: {schedule.get('url', 'N/A')}")
            print(f"  メソッド: {schedule.get('method', 'N/A')}")

        # リクエスト結果
        request_result = message.get('request_result', {})
        if request_result:
            print(f"\n🔄 リクエスト結果:")
            print(
                f"  成功: {'✅ Yes' if request_result.get('success') else '❌ No'}")
            print(f"  ステータスコード: {request_result.get('status_code', 'N/A')}")
            print(f"  応答時間: {request_result.get('response_time_ms', 'N/A')}ms")
            print(f"  試行回数: {request_result.get('attempt', 'N/A')}")

        # 追加データ（変更検知情報など）
        additional_data = message.get('additional_data', {})
        if additional_data:
            print(f"\n📊 追加データ:")
            for key, value in additional_data.items():
                if key in ['response_hash', 'previous_hash']:
                    # ハッシュ値は先頭8文字のみ表示
                    short_hash = str(value)[
                        :8] + '...' if len(str(value)) > 8 else str(value)
                    print(f"  {key}: {short_hash}")
                else:
                    print(f"  {key}: {value}")

        # 🌟 HTTPレスポンス内容（重要！）
        if 'response_body' in message:
            print(f"\n🌟 HTTPレスポンス内容:")
            response_body = message['response_body']
            if isinstance(response_body, dict):
                print(json.dumps(response_body, indent=2, ensure_ascii=False))
            else:
                print(f"  {response_body}")
        elif message.get('response_body_truncated'):
            print(f"\n📏 レスポンス内容（切り詰められました）:")
            print(
                f"  実際のサイズ: {message.get('response_size_bytes', 'N/A')} bytes")

        # エラー情報
        if 'error' in message:
            print(f"\n❌ エラー: {message['error']}")

        print("-" * 40)

    def stop_listening(self):
        """UDP通知の受信を停止する"""
        self.running = False
        if self.socket:
            self.socket.close()
        print(f"\n🛑 UDP通知受信を停止しました。総受信数: {self.received_count}")


def main():
    """メイン関数"""
    print("WebRequestTimer UDP通知受信テスト")
    print("=" * 60)

    # 設定読み込み
    try:
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        config_path = project_root / "config.json"

        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            udp_config = config.get('udp_notification', {})
            host = udp_config.get('server_address', 'localhost')
            port = udp_config.get('port', 12345)

            print(f"設定ファイルから読み込み:")
            print(f"  ホスト: {host}")
            print(f"  ポート: {port}")
            print(f"  通知有効: {udp_config.get('enabled', False)}")
        else:
            host = 'localhost'
            port = 12345
            print(f"デフォルト設定を使用:")
            print(f"  ホスト: {host}")
            print(f"  ポート: {port}")

    except Exception as e:
        print(f"⚠️  設定読み込みエラー: {e}")
        host = 'localhost'
        port = 12345

    # UDP受信開始
    receiver = UDPNotificationReceiver(host, port)

    try:
        receiver.start_listening()
    except KeyboardInterrupt:
        print("\n中断されました")
    finally:
        receiver.stop_listening()


if __name__ == "__main__":
    main()
