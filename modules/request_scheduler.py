"""
Request Scheduler Module for WebRequestTimer

このモジュールは指定された時刻や間隔でWebリクエストを実行するスケジューラー機能を提供します。
interval（間隔）とcron式の両方をサポートします。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import croniter
from dataclasses import dataclass, field


@dataclass
class ScheduleJob:
    """スケジュールジョブを表すデータクラス"""
    id: str
    name: str
    schedule_config: Dict[str, Any]
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    is_running: bool = False
    run_count: int = 0
    error_count: int = 0
    last_result: Optional[Dict[str, Any]] = None
    task: Optional[asyncio.Task] = None


class RequestScheduler:
    """Webリクエストスケジューラー"""

    def __init__(self, request_callback: Callable[[Dict[str, Any]], asyncio.Future]):
        """
        コンストラクタ

        Args:
            request_callback: リクエスト実行のコールバック関数
        """
        self.request_callback = request_callback
        self.logger = logging.getLogger(__name__)
        self.jobs: Dict[str, ScheduleJob] = {}
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None

    def add_schedule(self, schedule_config: Dict[str, Any]) -> bool:
        """
        スケジュールを追加する

        Args:
            schedule_config: スケジュール設定

        Returns:
            bool: 追加成功
        """
        job_id = schedule_config.get('id')
        if not job_id:
            self.logger.error("Schedule config missing 'id' field")
            return False

        if not schedule_config.get('enabled', True):
            self.logger.info(f"Schedule {job_id} is disabled, skipping")
            return True

        # 既存のジョブがある場合は停止
        if job_id in self.jobs:
            self.remove_schedule(job_id)

        # 次回実行時刻を計算
        next_run_time = self._calculate_next_run_time(schedule_config)
        if next_run_time is None:
            self.logger.error(
                f"Failed to calculate next run time for schedule {job_id}")
            return False

        # ジョブを作成
        job = ScheduleJob(
            id=job_id,
            name=schedule_config.get('name', job_id),
            schedule_config=schedule_config,
            next_run_time=next_run_time
        )

        self.jobs[job_id] = job
        self.logger.info(f"Added schedule {job_id}, next run: {next_run_time}")
        return True

    def remove_schedule(self, job_id: str) -> bool:
        """
        スケジュールを削除する

        Args:
            job_id: ジョブID

        Returns:
            bool: 削除成功
        """
        if job_id not in self.jobs:
            self.logger.warning(f"Schedule {job_id} not found")
            return False

        job = self.jobs[job_id]

        # 実行中のタスクがあれば停止
        if job.task and not job.task.done():
            job.task.cancel()

        del self.jobs[job_id]
        self.logger.info(f"Removed schedule {job_id}")
        return True

    def update_schedule(self, schedule_config: Dict[str, Any]) -> bool:
        """
        スケジュールを更新する

        Args:
            schedule_config: スケジュール設定

        Returns:
            bool: 更新成功
        """
        return self.add_schedule(schedule_config)

    def get_schedule_status(self, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        スケジュールの状態を取得する

        Args:
            job_id: 特定のジョブID（Noneの場合は全ジョブ）

        Returns:
            Dict: スケジュール状態
        """
        if job_id:
            if job_id not in self.jobs:
                return {}
            job = self.jobs[job_id]
            return self._job_to_status_dict(job)
        else:
            return {
                'total_jobs': len(self.jobs),
                'running_jobs': sum(1 for job in self.jobs.values() if job.is_running),
                'scheduler_running': self.is_running,
                'jobs': {job_id: self._job_to_status_dict(job) for job_id, job in self.jobs.items()}
            }

    def _job_to_status_dict(self, job: ScheduleJob) -> Dict[str, Any]:
        """ジョブを状態辞書に変換する"""
        return {
            'id': job.id,
            'name': job.name,
            'enabled': job.schedule_config.get('enabled', True),
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'last_run_time': job.last_run_time.isoformat() if job.last_run_time else None,
            'is_running': job.is_running,
            'run_count': job.run_count,
            'error_count': job.error_count,
            'last_result': job.last_result,
            'schedule_type': job.schedule_config.get('schedule_type'),
            'interval_seconds': job.schedule_config.get('interval_seconds'),
            'cron_expression': job.schedule_config.get('cron_expression'),
            'url': job.schedule_config.get('url'),
            'method': job.schedule_config.get('method')
        }

    async def start(self):
        """スケジューラーを開始する"""
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return

        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("Request scheduler started")

    async def stop(self):
        """スケジューラーを停止する"""
        if not self.is_running:
            return

        self.is_running = False

        # スケジューラータスクを停止
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        # 実行中のジョブタスクを停止
        for job in self.jobs.values():
            if job.task and not job.task.done():
                job.task.cancel()
                try:
                    await job.task
                except asyncio.CancelledError:
                    pass

        self.logger.info("Request scheduler stopped")

    async def _scheduler_loop(self):
        """スケジューラーのメインループ"""
        self.logger.info("Scheduler loop started")

        try:
            while self.is_running:
                current_time = datetime.now(timezone.utc)

                # 実行すべきジョブをチェック
                for job in list(self.jobs.values()):
                    if (job.next_run_time and
                        current_time >= job.next_run_time and
                            not job.is_running):

                        # ジョブを非同期で実行
                        job.task = asyncio.create_task(self._execute_job(job))

                # 1秒間隔でチェック
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Scheduler loop cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Scheduler loop error: {e}")
            raise

    async def _execute_job(self, job: ScheduleJob):
        """
        ジョブを実行する

        Args:
            job: 実行するジョブ
        """
        job.is_running = True
        job.last_run_time = datetime.now(timezone.utc)

        self.logger.info(f"Executing job {job.id}")

        try:
            # リクエストを実行
            result = await self.request_callback(job.schedule_config)
            job.last_result = result
            job.run_count += 1

            if not result.get('success', False):
                job.error_count += 1
                self.logger.warning(
                    f"Job {job.id} failed: {result.get('error', 'Unknown error')}")
            else:
                self.logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            job.error_count += 1
            job.last_result = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            self.logger.error(f"Job {job.id} execution error: {e}")

        finally:
            job.is_running = False

            # 次回実行時刻を計算
            job.next_run_time = self._calculate_next_run_time(
                job.schedule_config, job.last_run_time)

            if job.next_run_time:
                self.logger.info(
                    f"Job {job.id} next run scheduled for: {job.next_run_time}")
            else:
                self.logger.warning(
                    f"Failed to calculate next run time for job {job.id}")

    def _calculate_next_run_time(self, schedule_config: Dict[str, Any], from_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        次回実行時刻を計算する

        Args:
            schedule_config: スケジュール設定
            from_time: 基準時刻（Noneの場合は現在時刻）

        Returns:
            Optional[datetime]: 次回実行時刻
        """
        if from_time is None:
            from_time = datetime.now(timezone.utc)

        schedule_type = schedule_config.get('schedule_type', 'interval')

        if schedule_type == 'interval':
            interval_seconds = schedule_config.get('interval_seconds')
            if interval_seconds and interval_seconds > 0:
                from datetime import timedelta
                return from_time + timedelta(seconds=interval_seconds)

        elif schedule_type == 'cron':
            cron_expression = schedule_config.get('cron_expression')
            if cron_expression:
                try:
                    cron = croniter.croniter(cron_expression, from_time)
                    return cron.get_next(datetime)
                except Exception as e:
                    self.logger.error(
                        f"Invalid cron expression '{cron_expression}': {e}")
                    return None

        self.logger.error(f"Invalid schedule configuration: {schedule_config}")
        return None

    def validate_schedule_config(self, schedule_config: Dict[str, Any]) -> tuple[bool, str]:
        """
        スケジュール設定の妥当性を検証する

        Args:
            schedule_config: スケジュール設定

        Returns:
            tuple[bool, str]: (妥当性, エラーメッセージ)
        """
        # 必須フィールドの確認
        required_fields = ['id', 'url', 'method', 'schedule_type']
        for field in required_fields:
            if field not in schedule_config:
                return False, f"Required field '{field}' is missing"

        schedule_type = schedule_config.get('schedule_type')

        if schedule_type == 'interval':
            interval_seconds = schedule_config.get('interval_seconds')
            if not interval_seconds or interval_seconds <= 0:
                return False, "interval_seconds must be a positive number for interval schedule"

        elif schedule_type == 'cron':
            cron_expression = schedule_config.get('cron_expression')
            if not cron_expression:
                return False, "cron_expression is required for cron schedule"

            # Cron式の妥当性チェック
            try:
                croniter.croniter(cron_expression)
            except Exception as e:
                return False, f"Invalid cron expression: {e}"
        else:
            return False, f"Unsupported schedule_type: {schedule_type}"

        return True, ""


async def test_request_scheduler():
    """RequestSchedulerのテスト用関数"""

    async def mock_request_callback(schedule_config):
        """モックリクエストコールバック"""
        await asyncio.sleep(1)  # リクエスト処理をシミュレート
        return {
            'success': True,
            'status_code': 200,
            'response_time_ms': 100,
            'timestamp': datetime.now().isoformat()
        }

    scheduler = RequestScheduler(mock_request_callback)

    # テスト用スケジュール
    test_schedules = [
        {
            'id': 'test_interval',
            'name': 'Test Interval Job',
            'enabled': True,
            'url': 'https://httpbin.org/get',
            'method': 'GET',
            'schedule_type': 'interval',
            'interval_seconds': 5
        },
        {
            'id': 'test_cron',
            'name': 'Test Cron Job',
            'enabled': True,
            'url': 'https://httpbin.org/post',
            'method': 'POST',
            'schedule_type': 'cron',
            'cron_expression': '*/10 * * * * *'  # 10秒毎
        }
    ]

    # スケジュールを追加
    for schedule in test_schedules:
        scheduler.add_schedule(schedule)

    # スケジューラーを開始
    await scheduler.start()

    # 30秒間実行
    print("Scheduler started, running for 30 seconds...")
    await asyncio.sleep(30)

    # 状態確認
    status = scheduler.get_schedule_status()
    print("Final status:")
    import json
    print(json.dumps(status, indent=2, ensure_ascii=False))

    # 停止
    await scheduler.stop()


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_request_scheduler())
