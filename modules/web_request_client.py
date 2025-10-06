"""
Web Request Client Module for WebRequestTimer

このモジュールはHTTPリクエストの送信を行う機能を提供します。
GET/POSTリクエスト、認証ヘッダー、エラーハンドリングを含みます。
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import aiohttp
from aiohttp import ClientTimeout, ClientError


class WebRequestClient:
    """非同期HTTPリクエストクライアント"""

    def __init__(self, global_settings: Dict[str, Any]):
        """
        コンストラクタ

        Args:
            global_settings: グローバル設定
        """
        self.global_settings = global_settings
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリー"""
        connector = aiohttp.TCPConnector(
            verify_ssl=self.global_settings.get('verify_ssl', True),
            limit=self.global_settings.get('max_concurrent_requests', 5)
        )

        timeout = ClientTimeout(
            total=self.global_settings.get('default_timeout', 30)
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': self.global_settings.get('user_agent', 'WebRequestTimer/1.0')}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        if self.session:
            await self.session.close()

    async def send_request(self, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        リクエストを送信する

        Args:
            schedule_config: スケジュール設定

        Returns:
            Dict: リクエスト結果
        """
        request_id = schedule_config.get('id', 'unknown')
        url = schedule_config.get('url')
        method = schedule_config.get('method', 'GET').upper()
        headers = schedule_config.get('headers', {})
        body = schedule_config.get('body')
        timeout_seconds = schedule_config.get(
            'timeout_seconds', self.global_settings.get('default_timeout', 30))
        retry_count = schedule_config.get(
            'retry_count', self.global_settings.get('default_retry_count', 3))
        retry_delay = schedule_config.get(
            'retry_delay_seconds', self.global_settings.get('default_retry_delay', 5))

        # リクエスト開始時刻
        start_time = datetime.now()

        for attempt in range(retry_count + 1):
            try:
                result = await self._execute_request(
                    url=url,
                    method=method,
                    headers=headers,
                    body=body,
                    timeout_seconds=timeout_seconds,
                    request_id=request_id,
                    attempt=attempt + 1
                )

                # 成功時の結果
                result.update({
                    'request_id': request_id,
                    'timestamp': start_time.isoformat(),
                    'attempt': attempt + 1,
                    'success': True
                })

                self.logger.info(
                    f"Request {request_id} completed successfully on attempt {attempt + 1}")
                return result

            except Exception as e:
                self.logger.warning(
                    f"Request {request_id} failed on attempt {attempt + 1}: {str(e)}")

                if attempt < retry_count:
                    # リトライ前の待機
                    await asyncio.sleep(retry_delay)
                else:
                    # 最終的な失敗
                    return {
                        'request_id': request_id,
                        'timestamp': start_time.isoformat(),
                        'attempt': attempt + 1,
                        'success': False,
                        'error': str(e),
                        'status_code': None,
                        'response_body': None,
                        'response_headers': None,
                        'response_time_ms': None
                    }

    async def _execute_request(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        body: Any,
        timeout_seconds: int,
        request_id: str,
        attempt: int
    ) -> Dict[str, Any]:
        """
        実際のHTTPリクエストを実行する

        Args:
            url: リクエストURL
            method: HTTPメソッド
            headers: リクエストヘッダー
            body: リクエストボディ
            timeout_seconds: タイムアウト秒数
            request_id: リクエストID
            attempt: 試行回数

        Returns:
            Dict: レスポンス情報
        """
        if not self.session:
            raise RuntimeError(
                "Session not initialized. Use async context manager.")

        # ボディの処理
        data = None
        json_data = None

        if body is not None:
            if isinstance(body, dict):
                # timestampの自動設定
                if 'timestamp' in body and body['timestamp'] == 'auto':
                    body['timestamp'] = datetime.now().isoformat()
                json_data = body
            elif isinstance(body, str):
                data = body
            else:
                data = str(body)

        # カスタムタイムアウトの設定
        timeout = ClientTimeout(total=timeout_seconds)

        # リクエスト開始時刻
        request_start = time.time()

        self.logger.debug(
            f"Sending {method} request to {url} (attempt {attempt})")

        async with self.session.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            json=json_data,
            timeout=timeout,
            allow_redirects=self.global_settings.get('follow_redirects', True)
        ) as response:
            # レスポンス時間の計算
            response_time_ms = int((time.time() - request_start) * 1000)

            # レスポンスボディの取得
            try:
                response_text = await response.text()
                # JSONとしてパースを試行
                try:
                    response_body = json.loads(response_text)
                except json.JSONDecodeError:
                    response_body = response_text
            except Exception as e:
                response_body = f"Failed to read response body: {str(e)}"

            # レスポンスヘッダーの取得
            response_headers = dict(response.headers)

            self.logger.debug(
                f"Response received: {response.status} in {response_time_ms}ms")

            # ステータスコードが400以上の場合はエラーとして扱う
            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"HTTP {response.status}: {response.reason}",
                    headers=response.headers
                )

            return {
                'status_code': response.status,
                'response_body': response_body,
                'response_headers': response_headers,
                'response_time_ms': response_time_ms,
                'url': str(response.url),
                'method': method
            }

    def validate_schedule_config(self, schedule_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        スケジュール設定の妥当性を検証する

        Args:
            schedule_config: スケジュール設定

        Returns:
            Tuple[bool, str]: (妥当性, エラーメッセージ)
        """
        required_fields = ['id', 'url', 'method']

        for field in required_fields:
            if field not in schedule_config or not schedule_config[field]:
                return False, f"Required field '{field}' is missing or empty"

        # URLの基本的な妥当性チェック
        url = schedule_config['url']
        if not url.startswith(('http://', 'https://')):
            return False, f"Invalid URL format: {url}"

        # HTTPメソッドの妥当性チェック
        method = schedule_config['method'].upper()
        if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
            return False, f"Unsupported HTTP method: {method}"

        return True, ""


async def test_web_request_client():
    """WebRequestClientのテスト用関数"""
    global_settings = {
        'user_agent': 'WebRequestTimer/1.0',
        'default_timeout': 30,
        'default_retry_count': 2,
        'default_retry_delay': 3,
        'verify_ssl': True,
        'follow_redirects': True,
        'max_concurrent_requests': 5
    }

    test_schedule = {
        'id': 'test_request',
        'url': 'https://httpbin.org/get',
        'method': 'GET',
        'headers': {
            'Custom-Header': 'Test-Value'
        },
        'body': None,
        'timeout_seconds': 10,
        'retry_count': 2,
        'retry_delay_seconds': 1
    }

    async with WebRequestClient(global_settings) as client:
        result = await client.send_request(test_schedule)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(test_web_request_client())
