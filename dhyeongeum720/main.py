# -*- coding: utf-8 -*-
"""
연금복권 720+ Add-on Main Application v1.0.0
Home Assistant Add-on for DH Lottery Pension 720+
v1.0.0 - Multi-account support with full sensor suite
"""

import os
import asyncio
import logging
import time
from typing import Optional, Dict, List
from datetime import date, datetime, timezone, timedelta
from contextlib import asynccontextmanager

try:
    from zoneinfo import ZoneInfo
    _TZ_KST = ZoneInfo("Asia/Seoul")
except ImportError:
    _TZ_KST = timezone(timedelta(hours=9))
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from dh_lottery_client import DhLotteryClient, DhLotteryError, DhLotteryLoginError
from dh_pension_720 import DhPension720, DhPension720Error, DhPension720PurchaseError
from mqtt_discovery import MQTTDiscovery, publish_sensor_mqtt, publish_button_mqtt

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Account data structure
class AccountData:
    def __init__(self, username: str, password: str, enabled: bool = True):
        self.username = username
        self.password = password
        self.enabled = enabled
        self.client: Optional[DhLotteryClient] = None
        self.pension_720: Optional[DhPension720] = None
        self.update_task: Optional[asyncio.Task] = None

# Configuration variables
config = {
    "accounts": [],
    "enable_pension720": os.getenv("ENABLE_PENSION720", "true").lower() == "true",
    "update_interval": int(os.getenv("UPDATE_INTERVAL", "3600")),
    "use_mqtt": os.getenv("USE_MQTT", "false").lower() == "true",
    "ha_url": os.getenv("HA_URL", "http://supervisor/core"),
    "supervisor_token": os.getenv("SUPERVISOR_TOKEN", ""),
}

# Global variables
accounts: Dict[str, AccountData] = {}
_last_purchase_time: Dict[tuple, float] = {}  # (username, button_id) -> timestamp, 중복 실행 방지
mqtt_client: Optional[MQTTDiscovery] = None
event_loop: Optional[asyncio.AbstractEventLoop] = None


def load_accounts_from_env():
    """Load accounts from environment variables"""
    import json

    accounts_json = os.getenv("ACCOUNTS", "[]")
    try:
        accounts_list = json.loads(accounts_json)
        config["accounts"] = accounts_list
        logger.info(f"Loaded {len(accounts_list)} account(s) from configuration")

        for i, acc in enumerate(accounts_list, 1):
            username = acc.get("username", "")
            enabled = acc.get("enabled", True)
            logger.info(f"  Account {i}: {username} (enabled: {enabled})")
    except Exception as e:
        logger.error(f"Failed to parse accounts from environment: {e}")
        config["accounts"] = []


def is_ingress_request(request: Request) -> bool:
    """Check if request is via Home Assistant Ingress"""
    referer = request.headers.get("referer", "")
    x_ingress_path = request.headers.get("X-Ingress-Path", "")
    return bool(referer or x_ingress_path)


# Helper Functions
def _safe_int(value) -> int:
    """Safe integer conversion"""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


async def publish_sensor_for_account(account: AccountData, entity_id: str, state, attributes: dict = None):
    """Publish sensor"""
    username = account.username

    if config["use_mqtt"] and mqtt_client and mqtt_client.connected:
        try:
            success = await publish_sensor_mqtt(
                mqtt_client=mqtt_client,
                entity_id=entity_id,
                state=state,
                username=username,
                attributes=attributes
            )
            if success:
                return
        except Exception as e:
            logger.error(f"[SENSOR][{username}] MQTT error: {e}")

    # REST API fallback
    import aiohttp

    if not config["supervisor_token"]:
        return

    addon_entity_id = f"addon_{username}_{entity_id}"
    url = f"{config['ha_url']}/api/states/sensor.{addon_entity_id}"
    headers = {
        "Authorization": f"Bearer {config['supervisor_token']}",
        "Content-Type": "application/json",
    }
    data = {
        "state": state,
        "attributes": attributes or {},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers, ssl=False) as resp:
                if resp.status not in [200, 201]:
                    logger.error(f"[SENSOR][{username}] REST failed: {resp.status}")
    except Exception as e:
        logger.error(f"[SENSOR][{username}] REST error: {e}")


async def publish_button_for_account(account: AccountData, entity_id: str):
    """Publish button via MQTT"""
    username = account.username

    if config["use_mqtt"] and mqtt_client and mqtt_client.connected:
        try:
            success = await publish_button_mqtt(
                mqtt_client=mqtt_client,
                entity_id=entity_id,
                username=username
            )
            if success:
                return
        except Exception as e:
            logger.error(f"[BUTTON][{username}] MQTT error: {e}")


async def setup_mqtt_discovery():
    """Setup MQTT discovery for sensors and buttons"""
    if not config["use_mqtt"]:
        return

    global mqtt_client

    mqtt_url = os.getenv("MQTT_URL", "mqtt://homeassistant.local:1883")
    mqtt_username = os.getenv("MQTT_USERNAME", "")
    mqtt_password = os.getenv("MQTT_PASSWORD", "")

    try:
        mqtt_client = MQTTDiscovery(
            broker_url=mqtt_url,
            username=mqtt_username,
            password=mqtt_password,
            client_id="dhyeongeum720"
        )
        await mqtt_client.connect()
        logger.info("[MQTT] Connected to broker")

        # Publish sensors and buttons for all accounts
        for username, account in accounts.items():
            # Balance sensor
            await publish_sensor_for_account(account, "pension720_balance", 0, {
                "friendly_name": "잔액",
                "icon": "mdi:wallet",
                "unit_of_measurement": "원"
            })

            # Login error sensor
            await publish_sensor_for_account(account, "pension720_login_error", "", {
                "friendly_name": "로그인 오류",
                "icon": "mdi:account-alert"
            })

            # Buy 1 ticket button
            await publish_button_for_account(account, "pension720_buy_1")

            # Buy 5 tickets button
            await publish_button_for_account(account, "pension720_buy_5")

        logger.info("[MQTT] Discovery completed")

    except Exception as e:
        logger.error(f"[MQTT] Setup failed: {e}")


async def login_account(account: AccountData):
    """Login to DH Lottery"""
    try:
        account.client = DhLotteryClient(account.username, account.password)
        await account.client.async_login()

        if config["enable_pension720"]:
            account.pension_720 = DhPension720(account.client)

        logger.info(f"[ACCOUNT][{account.username}] Login successful")
        await publish_sensor_for_account(account, "pension720_login_error", "", {
            "friendly_name": "로그인 오류",
            "icon": "mdi:account-check",
        })

    except DhLotteryLoginError as e:
        if account.client:
            account.client.logged_in = False
        msg = str(e)[:255]
        await publish_sensor_for_account(account, "pension720_login_error", msg, {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "friendly_name": "로그인 오류",
            "icon": "mdi:account-alert",
        })
        logger.warning(f"[ACCOUNT][{account.username}] Login failed: {e}")
    except DhLotteryError as e:
        if account.client:
            account.client.logged_in = False
        msg = str(e)[:255]
        await publish_sensor_for_account(account, "pension720_login_error", msg, {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "friendly_name": "로그인/API 오류",
            "icon": "mdi:account-alert",
        })
        logger.warning(f"[ACCOUNT][{account.username}] Login/API failed: {e}")
    except Exception as e:
        logger.error(f"[ACCOUNT][{account.username}] Login failed: {e}", exc_info=True)


async def update_account_sensors(account: AccountData):
    """Update sensors for an account"""
    if not account.client or not account.client.logged_in:
        return

    try:
        # NOTE: el.dhlottery.co.kr 쪽이 JSESSIONID를 더 이상 발급하지 않는/차단되는 케이스가 있어
        # 연금720 잔액 센서는 www.dhlottery.co.kr의 마이페이지 API(로그인 기반)로 대체합니다.
        # (로또45 애드온과 동일한 방식)
        if config["enable_pension720"]:
            bal = await account.client.async_get_balance()
            purchase_available = bal.purchase_available
            deposit = bal.deposit
            await publish_sensor_for_account(account, "pension720_balance", purchase_available, {
                "friendly_name": "잔액",
                "icon": "mdi:wallet",
                "unit_of_measurement": "원",
                "deposit": deposit,
                "purchase_available": purchase_available,
                "source": "www_api",
            })

    except DhLotteryError as e:
        if account.client:
            account.client.logged_in = False
        msg = str(e)[:255]
        await publish_sensor_for_account(account, "pension720_login_error", msg, {
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "friendly_name": "로그인 오류",
            "icon": "mdi:account-alert",
        })
        logger.warning(f"[SENSOR][{account.username}] Login/API failed: {e}")
    except Exception as e:
        logger.error(f"[SENSOR][{account.username}] Update failed: {e}", exc_info=True)


async def periodic_update():
    """Periodic sensor update task"""
    while True:
        try:
            for username, account in accounts.items():
                if not account.enabled:
                    continue

                if not account.client or not account.client.logged_in:
                    await login_account(account)

                await update_account_sensors(account)

        except Exception as e:
            logger.error(f"[PERIODIC] Update error: {e}", exc_info=True)

        await asyncio.sleep(config["update_interval"])


async def initialize_accounts():
    """Initialize all accounts"""
    global accounts
    accounts.clear()

    for acc in config["accounts"]:
        username = acc.get("username", "")
        password = acc.get("password", "")
        enabled = acc.get("enabled", True)

        if not username or not password:
            logger.warning(f"Skipping account with empty username/password")
            continue

        account = AccountData(username, password, enabled)
        accounts[username] = account

        if enabled:
            await login_account(account)

    # Start periodic update task
    if accounts:
        asyncio.create_task(periodic_update())


# FastAPI App
app = FastAPI(title="연금복권 720+ Add-on")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Startup event"""
    global event_loop
    event_loop = asyncio.get_event_loop()

    load_accounts_from_env()
    await initialize_accounts()
    await setup_mqtt_discovery()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event"""
    for username, account in accounts.items():
        if account.client:
            await account.client.close()

    if mqtt_client:
        await mqtt_client.disconnect()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main page. Ingress 경유 시 배지 표시."""
    accounts_html = "<ul>"
    for username, account in accounts.items():
        status = "✅" if account.client and account.client.logged_in else "❌"
        enabled = "✅" if account.enabled else "❌"
        accounts_html += f"<li><strong>{username}</strong>: {status} (Enabled: {enabled})</li>"
    accounts_html += "</ul>"
    ingress_badge = (
        '<span style="background:#0d47a1;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">Ingress</span>'
        if is_ingress_request(request) else ""
    )
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>연금복권 720+ v1.0.0</title>
            <style>
                body {{ font-family: Arial; margin: 40px; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>🎫 연금복권 720+ <span style="color:#666;">v1.0.0 Multi-Account</span> {ingress_badge}</h1>
            <div class="info">
                <h2>Accounts ({len(accounts)})</h2>
                {accounts_html}
            </div>
            <ul>
                <li><a href="health">Health Check</a></li>
                <li><a href="accounts">Accounts</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/api/ingress")
async def api_ingress(request: Request):
    """현재 요청이 Home Assistant Ingress 경유인지 반환 (모바일/외부 연동 시 참고)."""
    return {"ingress": is_ingress_request(request)}


@app.get("/health")
async def health(request: Request):
    """Health check. Ingress 경유 접근 시 ingress: true 포함."""
    accounts_status = {}
    logged_in_count = 0

    for username, account in accounts.items():
        is_logged_in = bool(account.client and getattr(account.client, "logged_in", False))
        if is_logged_in:
            logged_in_count += 1
        accounts_status[username] = {
            "logged_in": is_logged_in,
            "enabled": account.enabled,
            "status": "✅ Active" if is_logged_in else "❌ Login Failed",
        }

    status = "ok" if (len(accounts) == 0 or logged_in_count > 0) else "degraded"

    return {
        "status": status,
        "version": "1.0.0",
        "ingress": is_ingress_request(request),
        "accounts": accounts_status,
        "total_accounts": len(accounts),
        "logged_in_accounts": logged_in_count,
        "failed_accounts": len(accounts) - logged_in_count,
    }


@app.get("/accounts")
async def list_accounts():
    """List accounts"""
    result = []
    for username, account in accounts.items():
        result.append({
            "username": username,
            "enabled": account.enabled,
            "logged_in": account.client.logged_in if account.client else False,
        })
    return {"accounts": result}


@app.post("/api/purchase/{username}/1")
async def purchase_1(username: str):
    """
    연금복권 1장 구매

    Returns:
        JSON response with purchase result
    """
    account = accounts.get(username)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.enabled:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # 구매는 el.dhlottery.co.kr 쪽 암호화 세션(JSESSIONID 기반)이 필요한데,
    # 현재 JSESSIONID 미발급/차단 케이스가 있어 "세션 안쓰는 방식"으로는 구매를 지원할 수 없습니다.
    # (잔액/이력은 www API로 제공 가능)
    raise HTTPException(status_code=501, detail="Purchase disabled: EL session required")

    # 중복 실행 방지 (10초 내에 같은 버튼 재클릭 방지)
    key = (username, "buy_1")
    now = time.time()
    if key in _last_purchase_time and now - _last_purchase_time[key] < 10:
        raise HTTPException(status_code=429, detail="Please wait before purchasing again")

    try:
        _last_purchase_time[key] = now
        buy_data = await account.pension_720.async_buy_1()

        # 잔액 센서 업데이트
        await update_account_sensors(account)

        return {
            "success": True,
            "round_no": buy_data.round_no,
            "ticket_count": buy_data.ticket_count,
            "tickets": buy_data.tickets,
            "fail_count": buy_data.fail_count,
            "amount": buy_data.amount,
            "deposit": buy_data.deposit,
        }

    except DhPension720PurchaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[PURCHASE][{username}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Purchase failed")


@app.post("/api/purchase/{username}/5")
async def purchase_5(username: str):
    """
    연금복권 5장 구매

    Returns:
        JSON response with purchase result
    """
    account = accounts.get(username)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.enabled:
        raise HTTPException(status_code=400, detail="Account is disabled")

    # 구매는 el.dhlottery.co.kr 쪽 암호화 세션(JSESSIONID 기반)이 필요한데,
    # 현재 JSESSIONID 미발급/차단 케이스가 있어 "세션 안쓰는 방식"으로는 구매를 지원할 수 없습니다.
    # (잔액/이력은 www API로 제공 가능)
    raise HTTPException(status_code=501, detail="Purchase disabled: EL session required")

    # 중복 실행 방지 (10초 내에 같은 버튼 재클릭 방지)
    key = (username, "buy_5")
    now = time.time()
    if key in _last_purchase_time and now - _last_purchase_time[key] < 10:
        raise HTTPException(status_code=429, detail="Please wait before purchasing again")

    try:
        _last_purchase_time[key] = now
        buy_data = await account.pension_720.async_buy_5()

        # 잔액 센서 업데이트
        await update_account_sensors(account)

        return {
            "success": True,
            "round_no": buy_data.round_no,
            "ticket_count": buy_data.ticket_count,
            "tickets": buy_data.tickets,
            "fail_count": buy_data.fail_count,
            "amount": buy_data.amount,
            "deposit": buy_data.deposit,
        }

    except DhPension720PurchaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[PURCHASE][{username}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Purchase failed")


@app.get("/api/balance/{username}")
async def get_balance(username: str):
    """
    계정 잔액 조회

    Returns:
        JSON response with balance data
    """
    account = accounts.get(username)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.enabled:
        raise HTTPException(status_code=400, detail="Account is disabled")

    if not account.client or not account.client.logged_in:
        raise HTTPException(status_code=400, detail="Not logged in")

    try:
        bal = await account.client.async_get_balance()
        return {
            "deposit": bal.deposit,
            "purchase_available": bal.purchase_available,
            "source": "www_api",
        }

    except Exception as e:
        logger.error(f"[BALANCE][{username}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get balance")


@app.get("/api/history/{username}")
async def get_history(username: str):
    """
    구매 이력 조회

    Returns:
        JSON response with purchase history
    """
    account = accounts.get(username)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.enabled:
        raise HTTPException(status_code=400, detail="Account is disabled")

    if not account.client or not account.client.logged_in:
        raise HTTPException(status_code=400, detail="Not logged in")

    # 구매이력은 www API를 사용 (로또45와 동일한 방식)
    try:
        items = await account.client.async_get_buy_list("P720")
        return {
            "source": "www_api",
            "history": [
                {
                    "round_no": item.get("round", 0),
                    "issue_dt": item.get("issueDt", ""),
                    "barcode": item.get("barcode", ""),
                    "ticket_count": item.get("ticketCount", 0),
                    "amount": item.get("amount", 0),
                    "result": item.get("result", "미추첨"),
                }
                for item in (items or [])
            ],
        }

    except Exception as e:
        logger.error(f"[HISTORY][{username}] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get history")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=60100, log_level="info")
