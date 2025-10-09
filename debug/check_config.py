#!/usr/bin/env python3
"""
設定ファイルの内容を確認・検証するスクリプト
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def validate_config():
    """設定ファイルの妥当性をチェックする"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    config_path = project_root / "config.json"

    if not config_path.exists():
        print(f"設定ファイルが見つかりません: {config_path.absolute()}")
        return False

    print(f"設定ファイルパス: {config_path.absolute()}")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        print("\n=== 基本設定 ===")
        print(f"アプリ名: {config.get('app_name', 'N/A')}")
        print(f"トレイ有効: {config.get('enable_tray', 'N/A')}")
        print(f"ログレベル: {config.get('log_level', 'N/A')}")
        print(f"ログファイル: {config.get('log_file', 'N/A')}")

        print("\n=== リクエストスケジュール ===")
        schedules = config.get('request_schedules', [])
        print(f"総スケジュール数: {len(schedules)}")

        enabled_count = 0
        for i, schedule in enumerate(schedules, 1):
            enabled = schedule.get('enabled', False)
            if enabled:
                enabled_count += 1

            print(f"\n--- スケジュール {i} ---")
            print(f"ID: {schedule.get('id', 'N/A')}")
            print(f"名前: {schedule.get('name', 'N/A')}")
            print(f"有効: {'Yes' if enabled else 'No'}")
            print(f"URL: {schedule.get('url', 'N/A')}")
            print(f"メソッド: {schedule.get('method', 'N/A')}")
            print(f"スケジュール種類: {schedule.get('schedule_type', 'N/A')}")

            if schedule.get('schedule_type') == 'interval':
                print(f"実行間隔: {schedule.get('interval_seconds', 'N/A')}秒")
            elif schedule.get('schedule_type') == 'cron':
                print(f"Cron式: {schedule.get('cron_expression', 'N/A')}")

            print(f"タイムアウト: {schedule.get('timeout_seconds', 'N/A')}秒")
            print(f"リトライ回数: {schedule.get('retry_count', 'N/A')}")

        print(f"\n有効なスケジュール数: {enabled_count}/{len(schedules)}")

        print("\n=== グローバル設定 ===")
        global_settings = config.get('global_settings', {})
        for key, value in global_settings.items():
            print(f"{key}: {value}")

        print("\n=== UDP通知設定 ===")
        udp_settings = config.get('udp_notification', {})
        for key, value in udp_settings.items():
            print(f"{key}: {value}")

        # 設定の妥当性チェック
        print("\n=== 妥当性チェック ===")
        issues = []

        # 必須フィールドの確認
        required_fields = ['app_name', 'request_schedules', 'global_settings']
        for field in required_fields:
            if field not in config:
                issues.append(f"必須フィールド '{field}' が見つかりません")

        # スケジュールの妥当性チェック
        for i, schedule in enumerate(schedules):
            schedule_issues = []

            # 必須フィールド
            required_schedule_fields = ['id', 'url', 'method', 'schedule_type']
            for field in required_schedule_fields:
                if field not in schedule or not schedule[field]:
                    schedule_issues.append(f"必須フィールド '{field}' が空です")

            # URL形式チェック
            url = schedule.get('url', '')
            if url and not url.startswith(('http://', 'https://')):
                schedule_issues.append(f"無効なURL形式: {url}")

            # スケジュール設定チェック
            schedule_type = schedule.get('schedule_type')
            if schedule_type == 'interval':
                if not schedule.get('interval_seconds'):
                    schedule_issues.append("interval_secondsが設定されていません")
            elif schedule_type == 'cron':
                if not schedule.get('cron_expression'):
                    schedule_issues.append("cron_expressionが設定されていません")

            if schedule_issues:
                issues.append(
                    f"スケジュール {i+1} ({schedule.get('id', 'unknown')}): {', '.join(schedule_issues)}")

        if issues:
            print("⚠️  問題が見つかりました:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ 設定ファイルは正常です")
            return True

    except json.JSONDecodeError as e:
        print(f"JSONパースエラー: {e}")
        return False
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return False


def backup_config():
    """設定ファイルのバックアップを作成する"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    config_path = project_root / "config.json"

    if not config_path.exists():
        print("設定ファイルが見つかりません")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = project_root / f"config_backup_{timestamp}.json"

    try:
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"設定ファイルをバックアップしました: {backup_path.name}")
        return True
    except Exception as e:
        print(f"バックアップ作成に失敗しました: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backup":
        backup_config()
    else:
        validate_config()
