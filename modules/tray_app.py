"""
WebRequestTimer Tray Application

システムトレイに常駐するWebRequestTimerのメインアプリケーション
"""

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading
import json
import os
import asyncio
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from datetime import datetime
from typing import Dict, Any, Optional, Callable


CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')


class WebRequestTimerTrayApp:
    """WebRequestTimer専用のトレイアプリケーション"""

    def __init__(self, config: Dict[str, Any], scheduler_callback: Optional[Callable] = None):
        """
        コンストラクタ

        Args:
            config: アプリケーション設定
            scheduler_callback: スケジューラー操作のコールバック
        """
        self.config = config
        self.scheduler_callback = scheduler_callback
        self.icon = None
        self.running = True
        self.logger = logging.getLogger(__name__)

        # ステータス情報
        self.scheduler_status = {'total_jobs': 0,
                                 'running_jobs': 0, 'scheduler_running': False}

    def create_icon_image(self, active: bool = False) -> Image.Image:
        """
        トレイアイコン画像を作成する

        Args:
            active: アクティブ状態（緑色）

        Returns:
            Image: アイコン画像
        """
        # 64x64のアイコンを作成
        image = Image.new('RGB', (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        # 背景円
        if active:
            draw.ellipse([8, 8, 56, 56], fill=(34, 139, 34))  # 緑色（動作中）
        else:
            draw.ellipse([8, 8, 56, 56], fill=(169, 169, 169))  # グレー（停止中）

        # 時計のアイコン
        draw.ellipse([16, 16, 48, 48], fill=(255, 255, 255))
        draw.ellipse([20, 20, 44, 44], outline=(0, 0, 0), width=2)

        # 時計の針
        draw.line([32, 32, 32, 24], fill=(0, 0, 0), width=2)  # 短針
        draw.line([32, 32, 40, 32], fill=(0, 0, 0), width=1)  # 長針

        # 中心点
        draw.ellipse([30, 30, 34, 34], fill=(0, 0, 0))

        return image

    def setup_tray(self):
        """トレイアイコンとメニューを設定する"""
        try:
            # アイコン画像の作成
            active = self.scheduler_status.get('scheduler_running', False)
            image = self.create_icon_image(active)

            # ステータス情報のメニュー項目を作成
            status_items = self._create_status_menu_items()

            # スケジュール管理メニュー項目を作成
            schedule_items = self._create_schedule_menu_items()

            # メインメニューの構築
            menu = pystray.Menu(
                # ステータス情報
                item('WebRequestTimer', None, enabled=False),
                pystray.Menu.SEPARATOR,
                *status_items,
                pystray.Menu.SEPARATOR,

                # スケジュール管理
                item('スケジュール管理', pystray.Menu(*schedule_items)),

                # ログ・統計 #（UIが複雑になるので非表示、CLI等で対処）
                # item('ログ・統計', pystray.Menu(
                #    item('リクエスト履歴を表示', self.show_request_history),
                #    item('統計情報を表示', self.show_statistics),
                #    item('ログファイルを開く', self.open_log_file)
                # )),

                # 設定
                item('設定', pystray.Menu(
                    item('設定ファイルを編集', self.edit_config_file),
                    item('UDP通知設定', self.configure_udp_notification)
                )),

                pystray.Menu.SEPARATOR,
                item('情報・ヘルプ', pystray.Menu(
                    item('バージョン情報', self.show_about),
                    item('使用方法', self.show_help)
                )),

                pystray.Menu.SEPARATOR,
                item('終了', self.on_exit)
            )

            app_name = self.config.get('app_name', 'WebRequestTimer')
            self.icon = pystray.Icon(app_name, image, app_name, menu)

        except Exception as e:
            self.logger.error(f"Failed to setup tray: {e}")
            # フォールバック用のシンプルなアイコン
            image = self.create_icon_image()
            menu = pystray.Menu(item('終了', self.on_exit))
            self.icon = pystray.Icon(
                'WebRequestTimer', image, 'WebRequestTimer', menu)

    def _create_status_menu_items(self) -> list:
        """ステータス表示用のメニュー項目を作成する"""
        total_jobs = self.scheduler_status.get('total_jobs', 0)
        running_jobs = self.scheduler_status.get('running_jobs', 0)
        scheduler_running = self.scheduler_status.get(
            'scheduler_running', False)

        status_text = "稼働中" if scheduler_running else "停止中"

        return [
            item(f'スケジューラー: {status_text}', None, enabled=False),
            item(f'登録スケジュール数: {total_jobs}', None, enabled=False),
            item(f'実行中ジョブ数: {running_jobs}', None, enabled=False)
        ]

    def _create_schedule_menu_items(self) -> list:
        """スケジュール管理メニュー項目を作成する"""
        items = [
            item('新しいスケジュールを追加', self.add_new_schedule),
            item('スケジュール一覧を表示', self.show_schedule_list),
            pystray.Menu.SEPARATOR,
            item('スケジューラーを開始', self.start_scheduler),
            item('スケジューラーを停止', self.stop_scheduler),
            # pystray.Menu.SEPARATOR,
            # item('今すぐテスト実行', self.run_test_request) #（UIが複雑になるので非表示、CLI等で対処）
        ]

        # 個別スケジュールの有効/無効切り替え #（UIが複雑になるので非表示、CLI等で対処）
        # schedules = self.config.get('request_schedules', [])
        # if schedules:
        #    items.append(pystray.Menu.SEPARATOR)
        #    items.append(item('個別スケジュール切り替え',
        #                      pystray.Menu(*[
        #                          item(f"{s.get('name', s.get('id'))}: {'有効' if s.get('enabled', True) else '無効'}",
        #                               self._create_toggle_handler(s.get('id')))
        #                          for s in schedules[:10]  # 最大10件まで表示
        #                      ])))

        return items

    def _create_toggle_handler(self, schedule_id: str):
        """スケジュール切り替えハンドラーを作成する"""
        def handler(icon, item):
            self.toggle_schedule(schedule_id)
        return handler

    def update_status(self, scheduler_status: Dict[str, Any]):
        """
        スケジューラーの状態を更新する

        Args:
            scheduler_status: スケジューラーの状態情報
        """
        self.scheduler_status = scheduler_status
        if self.icon:
            # アイコンの更新
            active = scheduler_status.get('scheduler_running', False)
            new_image = self.create_icon_image(active)
            self.icon.icon = new_image

    # メニューアクションのハンドラー
    def add_new_schedule(self, icon, item):
        """新しいスケジュールを追加する"""
        try:
            self._run_dialog(self._add_schedule_dialog)
        except Exception as e:
            self.logger.error(f"Failed to add new schedule: {e}")
            self._show_error("スケジュール追加エラー", str(e))

    def _add_schedule_dialog(self):
        """スケジュール追加ダイアログ"""
        root = tk.Tk()
        root.title("新しいスケジュールを追加")
        root.geometry("500x600")
        root.transient()
        root.grab_set()

        # フォーム要素
        tk.Label(root, text="スケジュール名:").pack(pady=5)
        name_entry = tk.Entry(root, width=50)
        name_entry.pack(pady=5)

        tk.Label(root, text="URL:").pack(pady=5)
        url_entry = tk.Entry(root, width=50)
        url_entry.pack(pady=5)

        tk.Label(root, text="HTTPメソッド:").pack(pady=5)
        method_var = tk.StringVar(value="GET")
        method_combo = ttk.Combobox(root, textvariable=method_var, values=[
                                    "GET", "POST", "PUT", "DELETE"])
        method_combo.pack(pady=5)

        tk.Label(root, text="スケジュールタイプ:").pack(pady=5)
        schedule_type_var = tk.StringVar(value="interval")
        schedule_type_combo = ttk.Combobox(
            root, textvariable=schedule_type_var, values=["interval", "cron"])
        schedule_type_combo.pack(pady=5)

        tk.Label(root, text="間隔（秒）またはCron式:").pack(pady=5)
        schedule_value_entry = tk.Entry(root, width=50)
        schedule_value_entry.pack(pady=5)

        tk.Label(root, text="ヘッダー (JSON形式):").pack(pady=5)
        headers_text = tk.Text(root, height=4, width=60)
        headers_text.insert(tk.END, '{"User-Agent": "WebRequestTimer/1.0"}')
        headers_text.pack(pady=5)

        tk.Label(root, text="リクエストボディ (JSON形式、GETの場合は空):").pack(pady=5)
        body_text = tk.Text(root, height=4, width=60)
        body_text.pack(pady=5)

        result = {'saved': False}

        def save_schedule():
            try:
                # 入力値の取得と検証
                name = name_entry.get().strip()
                url = url_entry.get().strip()
                method = method_var.get()
                schedule_type = schedule_type_var.get()
                schedule_value = schedule_value_entry.get().strip()

                if not all([name, url, schedule_value]):
                    messagebox.showerror("エラー", "必須項目を入力してください")
                    return

                # ヘッダーの解析
                try:
                    headers = json.loads(headers_text.get(
                        1.0, tk.END).strip() or '{}')
                except json.JSONDecodeError:
                    messagebox.showerror("エラー", "ヘッダーのJSON形式が正しくありません")
                    return

                # ボディの解析
                body_content = body_text.get(1.0, tk.END).strip()
                body = None
                if body_content:
                    try:
                        body = json.loads(body_content)
                    except json.JSONDecodeError:
                        messagebox.showerror("エラー", "リクエストボディのJSON形式が正しくありません")
                        return

                # スケジュール設定の作成
                schedule_id = f"schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                new_schedule = {
                    'id': schedule_id,
                    'name': name,
                    'enabled': True,
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'body': body,
                    'schedule_type': schedule_type,
                    'timeout_seconds': 30,
                    'retry_count': 3,
                    'retry_delay_seconds': 5
                }

                if schedule_type == 'interval':
                    try:
                        new_schedule['interval_seconds'] = int(schedule_value)
                        new_schedule['cron_expression'] = None
                    except ValueError:
                        messagebox.showerror("エラー", "間隔は数値で入力してください")
                        return
                else:  # cron
                    new_schedule['interval_seconds'] = None
                    new_schedule['cron_expression'] = schedule_value

                # 設定に追加
                if 'request_schedules' not in self.config:
                    self.config['request_schedules'] = []

                self.config['request_schedules'].append(new_schedule)
                self.save_config()

                # スケジューラーに追加
                if self.scheduler_callback:
                    self.scheduler_callback('add_schedule', new_schedule)

                result['saved'] = True
                messagebox.showinfo("成功", f"スケジュール '{name}' を追加しました")
                root.destroy()

            except Exception as e:
                messagebox.showerror("エラー", f"スケジュールの保存に失敗しました: {e}")

        # ボタン
        button_frame = tk.Frame(root)
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="保存", command=save_schedule).pack(
            side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="キャンセル", command=root.destroy).pack(
            side=tk.LEFT, padx=10)

        root.mainloop()
        return result['saved']

    def show_schedule_list(self, icon, item):
        """スケジュール一覧を表示する"""
        try:
            self._run_dialog(self._show_schedule_list_dialog)
        except Exception as e:
            self.logger.error(f"Failed to show schedule list: {e}")

    def _show_schedule_list_dialog(self):
        """スケジュール一覧ダイアログ"""
        root = tk.Tk()
        root.title("スケジュール一覧")
        root.geometry("800x500")

        # リストボックス
        frame = tk.Frame(root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        listbox = tk.Listbox(frame, height=15)
        scrollbar = tk.Scrollbar(
            frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        # スケジュール情報の表示
        schedules = self.config.get('request_schedules', [])
        for i, schedule in enumerate(schedules):
            status = "有効" if schedule.get('enabled', True) else "無効"
            schedule_info = f"{schedule.get('name', schedule.get('id'))} ({status}) - {schedule.get('method')} {schedule.get('url')}"
            listbox.insert(tk.END, schedule_info)

        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ボタンフレーム
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)

        def toggle_selected():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                schedule = schedules[idx]
                schedule['enabled'] = not schedule.get('enabled', True)
                self.save_config()

                # 表示を更新
                status = "有効" if schedule['enabled'] else "無効"
                schedule_info = f"{schedule.get('name', schedule.get('id'))} ({status}) - {schedule.get('method')} {schedule.get('url')}"
                listbox.delete(idx)
                listbox.insert(idx, schedule_info)

                messagebox.showinfo(
                    "更新完了", f"スケジュール '{schedule.get('name')}' を{status}にしました")

        def delete_selected():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                schedule = schedules[idx]
                if messagebox.askyesno("確認", f"スケジュール '{schedule.get('name')}' を削除しますか？"):
                    del schedules[idx]
                    self.save_config()
                    listbox.delete(idx)
                    messagebox.showinfo("削除完了", "スケジュールを削除しました")

        tk.Button(button_frame, text="有効/無効切り替え",
                  command=toggle_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="削除", command=delete_selected).pack(
            side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="閉じる", command=root.destroy).pack(
            side=tk.LEFT, padx=5)

        root.mainloop()

    def show_request_history(self, icon, item):
        """リクエスト履歴を表示する"""
        try:
            if self.scheduler_callback:
                history = self.scheduler_callback('get_history', {})
                self._show_info(
                    "リクエスト履歴", f"履歴件数: {len(history) if history else 0}件")
            else:
                self._show_info("情報", "スケジューラーが利用できません")
        except Exception as e:
            self.logger.error(f"Failed to show request history: {e}")

    def show_statistics(self, icon, item):
        """統計情報を表示する"""
        try:
            if self.scheduler_callback:
                stats = self.scheduler_callback('get_statistics', {})
                self._show_info("統計情報", json.dumps(
                    stats, indent=2, ensure_ascii=False))
            else:
                self._show_info("情報", "スケジューラーが利用できません")
        except Exception as e:
            self.logger.error(f"Failed to show statistics: {e}")

    def start_scheduler(self, icon, item):
        """スケジューラーを開始する"""
        try:
            if self.scheduler_callback:
                self.scheduler_callback('start', {})
                self._show_info("情報", "スケジューラーを開始しました")
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")

    def stop_scheduler(self, icon, item):
        """スケジューラーを停止する"""
        try:
            if self.scheduler_callback:
                self.scheduler_callback('stop', {})
                self._show_info("情報", "スケジューラーを停止しました")
        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {e}")

    def run_test_request(self, icon, item):
        """テストリクエストを実行する"""
        try:
            if self.scheduler_callback:
                self.scheduler_callback('test_request', {})
                self._show_info("情報", "テストリクエストを実行しました")
        except Exception as e:
            self.logger.error(f"Failed to run test request: {e}")

    def toggle_schedule(self, schedule_id: str):
        """指定されたスケジュールの有効/無効を切り替える"""
        try:
            schedules = self.config.get('request_schedules', [])
            for schedule in schedules:
                if schedule.get('id') == schedule_id:
                    schedule['enabled'] = not schedule.get('enabled', True)
                    self.save_config()
                    status = "有効" if schedule['enabled'] else "無効"
                    self._show_info(
                        "更新完了", f"スケジュール '{schedule.get('name')}' を{status}にしました")
                    break
        except Exception as e:
            self.logger.error(f"Failed to toggle schedule {schedule_id}: {e}")

    def edit_config_file(self, icon, item):
        """設定ファイルを編集する"""
        try:
            import subprocess

            # 設定ファイルを開く
            subprocess.run(['notepad.exe', CONFIG_PATH])

            # 編集後にリロードするか確認
            def ask_reload():
                root = tk.Tk()
                root.withdraw()
                if messagebox.askyesno("設定リロード", "設定ファイルの編集が完了しました。\n設定をリロードしますか？"):
                    self.reload_config(None, None)
                root.destroy()

            # 別スレッドで確認ダイアログを表示
            threading.Thread(target=ask_reload, daemon=True).start()

        except Exception as e:
            self._show_error("エラー", f"設定ファイルを開けませんでした: {e}")

    def open_log_file(self, icon, item):
        """ログファイルを開く"""
        try:
            log_file = self.config.get(
                'log_file', 'logs/web_request_timer.log')
            if os.path.exists(log_file):
                import subprocess
                subprocess.run(['notepad.exe', log_file])
            else:
                self._show_info("情報", "ログファイルが見つかりません")
        except Exception as e:
            self._show_error("エラー", f"ログファイルを開けませんでした: {e}")

    def configure_logging(self, icon, item):
        """ログ設定を変更する"""
        try:
            current_level = self.config.get('log_level', 'INFO')
            new_level = simpledialog.askstring("ログレベル設定",
                                               f"現在のログレベル: {current_level}\n新しいログレベルを入力してください（DEBUG, INFO, WARNING, ERROR）:")
            if new_level and new_level.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                self.config['log_level'] = new_level.upper()
                self.save_config()
                self._show_info("設定更新", f"ログレベルを {new_level.upper()} に変更しました")
        except Exception as e:
            self._show_error("エラー", f"ログ設定の変更に失敗しました: {e}")

    def configure_udp_notification(self, icon, item):
        """UDP通知設定を変更する"""
        try:
            self._run_dialog(self._configure_udp_dialog)
        except Exception as e:
            self.logger.error(f"Failed to configure UDP notification: {e}")
            self._show_error("エラー", f"UDP設定の変更に失敗しました: {e}")

    def _configure_udp_dialog(self):
        """UDP通知設定ダイアログ"""
        root = tk.Tk()
        root.title("UDP通知設定")
        root.geometry("500x450")
        root.transient()
        root.grab_set()

        # 現在の設定を取得
        udp_config = self.config.get('udp_notification', {})

        # 有効/無効
        tk.Label(root, text="UDP通知を有効にする:").pack(pady=5)
        enabled_var = tk.BooleanVar(value=udp_config.get('enabled', True))
        tk.Checkbutton(root, variable=enabled_var).pack(pady=5)

        # サーバーアドレス
        tk.Label(root, text="送信先アドレス:").pack(pady=5)
        address_entry = tk.Entry(root, width=50)
        address_entry.insert(0, udp_config.get('server_address', 'localhost'))
        address_entry.pack(pady=5)

        # ポート番号
        tk.Label(root, text="ポート番号:").pack(pady=5)
        port_entry = tk.Entry(root, width=20)
        port_entry.insert(0, str(udp_config.get('port', 12345)))
        port_entry.pack(pady=5)

        # 遅延時間
        tk.Label(root, text="送信遅延時間（秒）:").pack(pady=5)
        delay_entry = tk.Entry(root, width=20)
        delay_entry.insert(0, str(udp_config.get('delay_seconds', 1)))
        delay_entry.pack(pady=5)

        # 通知条件
        tk.Label(root, text="通知条件:").pack(pady=10)

        notify_success_var = tk.BooleanVar(
            value=udp_config.get('notify_on_success', True))
        tk.Checkbutton(root, text="成功時に通知", variable=notify_success_var).pack(
            anchor='w', padx=20)

        notify_failure_var = tk.BooleanVar(
            value=udp_config.get('notify_on_failure', True))
        tk.Checkbutton(root, text="失敗時に通知", variable=notify_failure_var).pack(
            anchor='w', padx=20)

        notify_change_var = tk.BooleanVar(
            value=udp_config.get('notify_on_response_change', True))
        tk.Checkbutton(root, text="レスポンス変更時に通知",
                       variable=notify_change_var).pack(anchor='w', padx=20)

        # レスポンスサイズ制限
        tk.Label(root, text="レスポンス内容の最大サイズ（バイト）:").pack(pady=5)
        size_entry = tk.Entry(root, width=20)
        size_entry.insert(
            0, str(udp_config.get('max_response_size_bytes', 1024)))
        size_entry.pack(pady=5)

        result = {'saved': False}

        def save_udp_config():
            try:
                # 入力値の取得と検証
                enabled = enabled_var.get()
                address = address_entry.get().strip()
                port_str = port_entry.get().strip()
                delay_str = delay_entry.get().strip()
                size_str = size_entry.get().strip()

                if not address:
                    messagebox.showerror("エラー", "送信先アドレスを入力してください")
                    return

                try:
                    port = int(port_str)
                    if port < 1 or port > 65535:
                        raise ValueError("ポート番号は1-65535の範囲で入力してください")
                except ValueError as e:
                    messagebox.showerror("エラー", f"ポート番号が正しくありません: {e}")
                    return

                try:
                    delay = float(delay_str)
                    if delay < 0:
                        raise ValueError("遅延時間は0以上で入力してください")
                except ValueError as e:
                    messagebox.showerror("エラー", f"遅延時間が正しくありません: {e}")
                    return

                try:
                    max_size = int(size_str)
                    if max_size < 0:
                        raise ValueError("サイズは0以上で入力してください")
                except ValueError as e:
                    messagebox.showerror("エラー", f"レスポンスサイズが正しくありません: {e}")
                    return

                # 新しい設定を作成
                new_udp_config = {
                    'enabled': enabled,
                    'server_address': address,
                    'port': port,
                    'delay_seconds': delay,
                    'notify_on_success': notify_success_var.get(),
                    'notify_on_failure': notify_failure_var.get(),
                    'notify_on_response_change': notify_change_var.get(),
                    'max_response_size_bytes': max_size,
                    'response_change_threshold': udp_config.get('response_change_threshold', 0.1)
                }

                # 設定を保存
                self.config['udp_notification'] = new_udp_config
                self.save_config()

                # スケジューラーコールバックで設定を更新
                if self.scheduler_callback:
                    self.scheduler_callback(
                        'update_udp_config', new_udp_config)

                result['saved'] = True
                messagebox.showinfo("成功", "UDP通知設定を更新しました")
                root.destroy()

            except Exception as e:
                messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")

        def test_udp_connection():
            """UDP接続テスト"""
            try:
                address = address_entry.get().strip()
                port_str = port_entry.get().strip()

                if not address or not port_str:
                    messagebox.showerror("エラー", "アドレスとポート番号を入力してください")
                    return

                port = int(port_str)

                # テストメッセージを送信
                import socket
                import json
                from datetime import datetime

                test_message = {
                    'application': 'WebRequestTimer',
                    'test': True,
                    'timestamp': datetime.now().isoformat(),
                    'message': 'UDP connection test'
                }

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    data = json.dumps(
                        test_message, ensure_ascii=False).encode('utf-8')
                    sock.sendto(data, (address, port))
                    messagebox.showinfo(
                        "成功", f"テストメッセージを {address}:{port} に送信しました")
                finally:
                    sock.close()

            except Exception as e:
                messagebox.showerror("エラー", f"接続テストに失敗しました: {e}")

        # ボタンフレーム
        button_frame = tk.Frame(root)
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="保存", command=save_udp_config).pack(
            side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="接続テスト", command=test_udp_connection).pack(
            side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="キャンセル", command=root.destroy).pack(
            side=tk.LEFT, padx=5)

        root.mainloop()
        return result['saved']

    def reload_config(self, icon, item):
        """設定をリロードする"""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self.config.clear()
                self.config.update(json.load(f))
            self._show_info("設定リロード", "設定ファイルをリロードしました")
        except Exception as e:
            self._show_error("エラー", f"設定リロードに失敗しました: {e}")

    def show_about(self, icon, item):
        """バージョン情報を表示する"""
        about_text = f"""
WebRequestTimer v1.0

指定された時刻・間隔でWebリクエストを送信する
システムトレイ常駐アプリケーション

機能:
- GET/POSTリクエスト対応
- 認証ヘッダー対応
- Cron式・間隔指定対応
- リクエスト履歴・統計
- 設定管理

設定ファイル: {CONFIG_PATH}
"""
        self._show_info("WebRequestTimer について", about_text)

    def show_help(self, icon, item):
        """使用方法を表示する"""
        help_text = """
WebRequestTimer 使用方法:

1. スケジュール管理
   - 「新しいスケジュールを追加」でWebリクエストを設定
   - URL、メソッド、ヘッダー、実行間隔を指定
   - 「スケジュール一覧を表示」で管理

2. スケジューラー操作
   - 「スケジューラーを開始」で自動実行開始
   - 「スケジューラーを停止」で停止
   
3. ログ・統計
   - 「リクエスト履歴を表示」で実行履歴確認
   - 「統計情報を表示」で成功率など確認

4. 設定
   - 「設定ファイルを編集」で詳細設定
   - 「設定をリロード」で変更を反映

注意: 
- スケジューラー開始後、設定された間隔でリクエストが実行されます
- 認証が必要な場合はHeaderにAuthorizationを設定してください
"""
        self._show_info("使用方法", help_text)

    def save_config(self):
        """設定をファイルに保存する"""
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            self._show_error("設定保存エラー", str(e))

    def on_exit(self, icon, item):
        """アプリケーションを終了する"""
        try:
            self.running = False

            # スケジューラーを停止
            if self.scheduler_callback:
                self.scheduler_callback('stop', {})

            # メインアプリケーションに終了を通知
            if self.scheduler_callback:
                self.scheduler_callback('exit', {})

            # トレイアイコンを停止
            self.icon.stop()

            # プロセス終了を確実にする
            import os
            import signal
            import threading

            def force_exit():
                import time
                time.sleep(1)  # 1秒待機してから強制終了
                os.kill(os.getpid(), signal.SIGTERM)

            # 1秒後に強制終了するスレッドを開始
            threading.Thread(target=force_exit, daemon=True).start()

        except Exception as e:
            self.logger.error(f"Exit error: {e}")
            # エラーが発生した場合は即座に強制終了
            import os
            import signal
            os.kill(os.getpid(), signal.SIGTERM)

    def run(self):
        """トレイアプリを実行する"""
        try:
            self.setup_tray()
            self.logger.info("Tray application started")
            self.icon.run()
        except Exception as e:
            self.logger.error(f"Tray application error: {e}")

    # ユーティリティメソッド
    def _run_dialog(self, dialog_func):
        """ダイアログを別スレッドで実行する"""
        def run_in_thread():
            try:
                dialog_func()
            except Exception as e:
                self.logger.error(f"Dialog error: {e}")

        threading.Thread(target=run_in_thread, daemon=True).start()

    def _show_info(self, title: str, message: str):
        """情報ダイアログを表示する"""
        def show():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(title, message)
            root.destroy()
        threading.Thread(target=show, daemon=True).start()

    def _show_error(self, title: str, message: str):
        """エラーダイアログを表示する"""
        def show():
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(title, message)
            root.destroy()
        threading.Thread(target=show, daemon=True).start()


# トレイアプリ起動用関数
def start_tray_app(config: Dict[str, Any], scheduler_callback: Optional[Callable] = None) -> WebRequestTimerTrayApp:
    """
    トレイアプリを起動する

    Args:
        config: アプリケーション設定
        scheduler_callback: スケジューラー操作のコールバック

    Returns:
        WebRequestTimerTrayApp: トレイアプリのインスタンス
    """
    app = WebRequestTimerTrayApp(config, scheduler_callback)
    tray_thread = threading.Thread(target=app.run, daemon=True)
    tray_thread.start()
    return app
