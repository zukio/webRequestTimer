#!/usr/bin/env python3
"""
データベースの内容を確認するスクリプト
"""

import sqlite3
import json
import os
from pathlib import Path


def check_database():
    # スクリプトの場所から親ディレクトリに移動してlogsフォルダを探す
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    db_path = project_root / "logs" / "request_history.db"

    if not db_path.exists():
        print(f"データベースファイルが見つかりません: {db_path.absolute()}")
        return

    print(f"データベースパス: {db_path.absolute()}")

    try:
        with sqlite3.connect(db_path) as conn:
            # テーブル一覧
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"\nテーブル一覧: {[table[0] for table in tables]}")

            # リクエスト履歴の件数
            cursor = conn.execute("SELECT COUNT(*) FROM request_history;")
            count = cursor.fetchone()[0]
            print(f"\nリクエスト履歴の総件数: {count}")

            if count > 0:
                # 最新5件のリクエスト履歴を表示
                print("\n=== 最新5件のリクエスト履歴 ===")
                cursor = conn.execute("""
                    SELECT timestamp, request_id, url, method, success, status_code, 
                           response_time_ms, response_body, error_message
                    FROM request_history 
                    ORDER BY timestamp DESC 
                    LIMIT 5;
                """)

                rows = cursor.fetchall()
                for i, row in enumerate(rows, 1):
                    timestamp, request_id, url, method, success, status_code, response_time_ms, response_body, error_message = row
                    print(f"\n--- リクエスト {i} ---")
                    print(f"時刻: {timestamp}")
                    print(f"リクエストID: {request_id}")
                    print(f"URL: {url}")
                    print(f"メソッド: {method}")
                    print(f"成功: {'Yes' if success else 'No'}")
                    if success:
                        print(f"ステータスコード: {status_code}")
                        print(f"応答時間: {response_time_ms}ms")
                        if response_body:
                            try:
                                # JSONとしてパースして整形表示
                                parsed_body = json.loads(response_body)
                                print(
                                    f"レスポンス内容: {json.dumps(parsed_body, indent=2, ensure_ascii=False)}")
                            except json.JSONDecodeError:
                                print(f"レスポンス内容: {response_body}")
                    else:
                        print(f"エラー: {error_message}")

            # スケジュール統計
            cursor = conn.execute("SELECT COUNT(*) FROM schedule_stats;")
            stats_count = cursor.fetchone()[0]
            print(f"\n統計データ件数: {stats_count}")

            if stats_count > 0:
                print("\n=== スケジュール統計 ===")
                cursor = conn.execute("""
                    SELECT schedule_name, total_requests, successful_requests, 
                           failed_requests, average_response_time_ms, last_request_time
                    FROM schedule_stats;
                """)

                for row in cursor.fetchall():
                    schedule_name, total, success, failed, avg_time, last_time = row
                    success_rate = (success / total * 100) if total > 0 else 0
                    print(f"\nスケジュール: {schedule_name}")
                    print(f"  総リクエスト数: {total}")
                    print(f"  成功: {success}, 失敗: {failed}")
                    print(f"  成功率: {success_rate:.1f}%")
                    # avg_timeがNoneや文字列の場合に備えて安全に処理
                    try:
                        avg_time_float = float(
                            avg_time) if avg_time is not None else 0.0
                        print(f"  平均応答時間: {avg_time_float:.1f}ms")
                    except (ValueError, TypeError):
                        print(f"  平均応答時間: N/A")
                    print(f"  最終実行: {last_time}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    check_database()
