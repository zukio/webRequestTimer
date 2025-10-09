#!/usr/bin/env python3
"""
プロセス監視とシステム情報を確認するスクリプト
"""

import psutil
import sys
from pathlib import Path
from datetime import datetime
import json


def check_system_info():
    """システム情報を表示する"""
    print("=== システム情報 ===")
    print(f"Python バージョン: {sys.version}")
    print(f"プラットフォーム: {sys.platform}")

    # CPU情報
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    print(f"CPU使用率: {cpu_percent:.1f}%")
    print(f"CPUコア数: {cpu_count}")

    # メモリ情報
    memory = psutil.virtual_memory()
    print(f"メモリ使用率: {memory.percent:.1f}%")
    print(
        f"使用メモリ: {memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB")

    # ディスク情報
    disk = psutil.disk_usage('/')
    print(f"ディスク使用率: {disk.percent:.1f}%")
    print(
        f"使用ディスク: {disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB")


def find_webRequestTimer_processes():
    """WebRequestTimerのプロセスを検索する"""
    print("\n=== WebRequestTimer プロセス検索 ===")

    target_keywords = ['webRequestTimer', 'main.py', 'WebRequestTimer']
    found_processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_info']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            name = proc.info['name'] or ''

            # キーワードでマッチング
            if any(keyword.lower() in cmdline.lower() or keyword.lower() in name.lower()
                   for keyword in target_keywords):
                found_processes.append(proc.info)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if found_processes:
        print(f"見つかったプロセス数: {len(found_processes)}")
        for i, proc in enumerate(found_processes, 1):
            print(f"\n--- プロセス {i} ---")
            print(f"PID: {proc['pid']}")
            print(f"名前: {proc['name']}")
            print(f"コマンドライン: {' '.join(proc['cmdline'] or [])}")
            print(
                f"開始時刻: {datetime.fromtimestamp(proc['create_time']).strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                # リアルタイムの情報を取得
                process = psutil.Process(proc['pid'])
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()

                print(f"CPU使用率: {cpu_percent:.2f}%")
                print(f"メモリ使用量: {memory_info.rss / (1024**2):.1f}MB")
                print(f"ステータス: {process.status()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print("プロセス情報の取得に失敗しました")
    else:
        print("WebRequestTimerのプロセスが見つかりませんでした")


def check_network_connections():
    """ネットワーク接続を確認する"""
    print("\n=== ネットワーク接続 ===")

    # UDPポート12345の確認（設定ファイルのデフォルト）
    target_port = 12345
    connections = psutil.net_connections()

    udp_connections = [conn for conn in connections
                       if conn.type == psutil.SOCK_DGRAM and
                       conn.laddr and conn.laddr.port == target_port]

    if udp_connections:
        print(f"UDPポート {target_port} でリスニング中:")
        for conn in udp_connections:
            print(f"  アドレス: {conn.laddr.ip}:{conn.laddr.port}")
            print(f"  ステータス: {conn.status}")
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    print(f"  プロセス: {proc.name()} (PID: {conn.pid})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    print(f"  プロセス: PID {conn.pid} (詳細取得不可)")
    else:
        print(f"UDPポート {target_port} でリスニングしているプロセスは見つかりませんでした")


def check_log_files():
    """ログファイルの状態を確認する"""
    print("\n=== ログファイル確認 ===")

    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    logs_dir = project_root / "logs"

    if not logs_dir.exists():
        print("logsディレクトリが見つかりません")
        return

    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.db"))

    if log_files:
        print(f"ログファイル数: {len(log_files)}")
        total_size = 0

        for log_file in log_files:
            size_mb = log_file.stat().st_size / (1024**2)
            total_size += size_mb
            modified_time = datetime.fromtimestamp(log_file.stat().st_mtime)

            print(f"\n{log_file.name}:")
            print(f"  サイズ: {size_mb:.2f}MB")
            print(f"  最終更新: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")

        print(f"\n総ログサイズ: {total_size:.2f}MB")
    else:
        print("ログファイルが見つかりません")


def main():
    """メイン関数"""
    print(
        f"WebRequestTimer システム診断 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    check_system_info()
    find_webRequestTimer_processes()
    check_network_connections()
    check_log_files()

    print("\n" + "=" * 60)
    print("診断完了")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n診断が中断されました")
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
