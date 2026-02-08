# -*- coding: utf-8 -*-
"""
Lotto 45 Add-on Main Application v2.0.0
Home Assistant Add-on for DH Lottery 6/45
v2.0.0 - Multi-account support
"""

import os
import asyncio
import logging
from typing import Optional, Dict, List
from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from dh_lottery_client import DhLotteryClient
from dh_lotto_645 import DhLotto645, DhLotto645SelMode
from dh_lotto_analyzer import DhLottoAnalyzer
from mqtt_discovery import MQTTDiscovery, publish_sensor_mqtt

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
        self.lotto_645: Optional[DhLotto645] = None
        self.analyzer: Optional[DhLottoAnalyzer] = None
        self.manual_numbers_state = "auto,auto,auto,auto,auto,auto"
        self.update_task: Optional[asyncio.Task] = None

# Configuration variables
config = {
    "accounts": [],  # Will be populated from env
    "enable_lotto645": os.getenv("ENABLE_LOTTO645", "true").lower() == "true",
    "update_interval": int(os.getenv("UPDATE_INTERVAL", "3600")),
    "use_mqtt": os.getenv("USE_MQTT", "false").lower() == "true",
    "ha_url": os.getenv("HA_URL", "http://supervisor/core"),
    "supervisor_token": os.getenv("SUPERVISOR_TOKEN", ""),
    "is_beta": os.getenv("IS_BETA", "false").lower() == "true",
}

# Global variables
accounts: Dict[str, AccountData] = {}  # username -> AccountData
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


# ============================================================================
# Helper Functions
# ============================================================================

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


def _format_with_commas(value) -> str:
    """Format number with thousand separators"""
    n = _safe_int(value)
    return f"{n:,}"


def _parse_yyyymmdd(text: str) -> Optional[str]:
    """Convert YYYYMMDD to YYYY-MM-DD format"""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) != 8:
        return None
    try:
        year = int(text[0:4])
        month = int(text[4:6])
        day = int(text[6:8])
        d = date(year, month, day)
        return d.isoformat()
    except ValueError:
        return None


def _get_lotto645_item(data: dict) -> dict:
    """Extract lotto645 result data"""
    if not data:
        return {}
    if "_raw" in data:
        return data["_raw"]
    items = data.get("list", [])
    if items:
        return items[0]
    return data


async def register_buttons_for_account(account: AccountData):
    """Register button entities for a specific account"""
    if not mqtt_client or not mqtt_client.connected:
        logger.warning(f"[BUTTON][{account.username}] MQTT not connected, skipping button registration")
        return
    
    username = account.username
    logger.info(f"[BUTTON][{username}] Registering button entities")
    
    # Device name with beta suffix if needed
    device_suffix = " (Beta)" if config.get("is_beta", False) else ""
    device_name = f"DH Lottery Addon{device_suffix} ({username})"
    device_id = f"dhlotto_addon_{username}"
    
    # Button 1: Buy 1 Auto Game
    button1_topic = f"homeassistant/button/{mqtt_client.topic_prefix}_{username}_buy_auto_1/command"
    mqtt_client.publish_button_discovery(
        button_id="buy_auto_1",
        name="Buy 1 Auto Game",
        command_topic=button1_topic,
        username=username,
        device_name=device_name,
        device_identifier=device_id,
        icon="mdi:ticket-confirmation",
    )
    
    # Button 2: Buy 5 Auto Games
    button2_topic = f"homeassistant/button/{mqtt_client.topic_prefix}_{username}_buy_auto_5/command"
    mqtt_client.publish_button_discovery(
        button_id="buy_auto_5",
        name="Buy 5 Auto Games",
        command_topic=button2_topic,
        username=username,
        device_name=device_name,
        device_identifier=device_id,
        icon="mdi:ticket-confirmation-outline",
    )
    
    # Button 3: Buy Manual Game
    button3_topic = f"homeassistant/button/{mqtt_client.topic_prefix}_{username}_buy_manual/command"
    mqtt_client.publish_button_discovery(
        button_id="buy_manual",
        name="Buy 1 Manual Game",
        command_topic=button3_topic,
        username=username,
        device_name=device_name,
        device_identifier=device_id,
        icon="mdi:hand-pointing-right",
    )
    
    # Input Text: Manual Numbers
    input_state_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/state"
    input_command_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/set"
    
    mqtt_client.publish_input_text_discovery(
        input_id="manual_numbers",
        name="Manual Numbers Input",
        state_topic=input_state_topic,
        command_topic=input_command_topic,
        username=username,
        device_name=device_name,
        device_identifier=device_id,
        icon="mdi:numeric",
        mode="text",
    )
    
    # Publish initial state
    mqtt_client.client.publish(input_state_topic, "auto,auto,auto,auto,auto,auto", qos=1, retain=True)
    
    logger.info(f"[BUTTON][{username}] All buttons and input text registered")


def on_button_command(client_mqtt, userdata, message):
    """Handle MQTT button commands and input text changes"""
    try:
        topic = message.topic
        payload = message.payload.decode()
        
        logger.info(f"[MQTT] Received message: topic={topic}, payload={payload}")
        
        # Extract username from topic
        # Format: homeassistant/button/dhlotto_USERNAME_BUTTON_ID/command
        #     or: homeassistant/text/dhlotto_USERNAME_INPUT_ID/set
        parts = topic.split("/")
        if len(parts) < 3:
            logger.error(f"[MQTT] Invalid topic format: {topic}")
            return
        
        entity_id_full = parts[2]  # dhlotto_USERNAME_...
        
        # Extract username (between dhlotto_ and the last underscore)
        if not entity_id_full.startswith(mqtt_client.topic_prefix + "_"):
            logger.error(f"[MQTT] Invalid entity ID: {entity_id_full}")
            return
        
        # Remove prefix
        without_prefix = entity_id_full[len(mqtt_client.topic_prefix) + 1:]  # Remove "dhlotto_"
        
        # Find the account username
        username = None
        for acc_username in accounts.keys():
            if without_prefix.startswith(acc_username + "_"):
                username = acc_username
                break
        
        if not username:
            logger.error(f"[MQTT] Could not extract username from: {entity_id_full}")
            return
        
        if username not in accounts:
            logger.error(f"[MQTT] Unknown account: {username}")
            return
        
        account = accounts[username]
        
        # Check if this is input_text
        if "/text/" in topic and "/set" in topic:
            logger.info(f"[INPUT][{username}] Manual numbers updated: {payload}")
            account.manual_numbers_state = payload
            
            # Publish back to state topic
            state_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/state"
            client_mqtt.publish(state_topic, payload, qos=1, retain=True)
            return
        
        # Handle button commands
        # Extract button_id
        button_suffix = without_prefix[len(username) + 1:]  # Remove "username_"
        
        logger.info(f"[BUTTON][{username}] Button pressed: {button_suffix}")
        
        # Execute purchase
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                execute_button_purchase(account, button_suffix),
                event_loop
            )
        else:
            logger.error(f"[BUTTON][{username}] Event loop not available")
    
    except Exception as e:
        logger.error(f"[MQTT] Error handling message: {e}", exc_info=True)


async def execute_button_purchase(account: AccountData, button_id: str):
    """Execute purchase for a specific account"""
    username = account.username
    logger.info(f"[PURCHASE][{username}] Starting purchase for button: {button_id}")
    
    if not account.lotto_645:
        logger.error(f"[PURCHASE][{username}] Lotto 645 not enabled")
        return
    
    try:
        import random
        
        # Determine purchase mode
        if button_id == "buy_manual":
            # Manual purchase
            manual_numbers_text = account.manual_numbers_state
            if not manual_numbers_text:
                error_msg = "Please enter manual numbers"
                logger.error(f"[PURCHASE][{username}] {error_msg}")
                await publish_purchase_error(account, error_msg)
                return
            
            logger.info(f"[PURCHASE][{username}] Manual numbers input: {manual_numbers_text}")
            
            # Parse input
            try:
                parts = [p.strip() for p in manual_numbers_text.split(",")]
                
                if len(parts) != 6:
                    error_msg = f"Must provide exactly 6 values (current: {len(parts)})"
                    logger.error(f"[PURCHASE][{username}] {error_msg}")
                    await publish_purchase_error(account, error_msg)
                    return
                
                manual_numbers = []
                auto_count = 0
                
                for part in parts:
                    if part.lower() == "auto":
                        auto_count += 1
                    else:
                        try:
                            num = int(part)
                            if num <= 0 or num >= 46:
                                error_msg = f"Numbers must be 1-45 (input: {num})"
                                logger.error(f"[PURCHASE][{username}] {error_msg}")
                                await publish_purchase_error(account, error_msg)
                                return
                            manual_numbers.append(num)
                        except ValueError:
                            error_msg = f"Invalid input: {part}"
                            logger.error(f"[PURCHASE][{username}] {error_msg}")
                            await publish_purchase_error(account, error_msg)
                            return
                
                # Check duplicates
                if len(manual_numbers) != len(set(manual_numbers)):
                    error_msg = "Duplicate numbers found"
                    logger.error(f"[PURCHASE][{username}] {error_msg}")
                    await publish_purchase_error(account, error_msg)
                    return
                
                # Determine mode
                if auto_count == 0:
                    mode = DhLotto645SelMode.MANUAL
                    final_numbers = sorted(manual_numbers)
                elif auto_count == 6:
                    mode = DhLotto645SelMode.AUTO
                    final_numbers = []
                else:
                    mode = DhLotto645SelMode.SEMI_AUTO
                    final_numbers = sorted(manual_numbers)
                
                slots = [DhLotto645.Slot(mode=mode, numbers=final_numbers)]
                
            except Exception as e:
                error_msg = f"Error processing input: {str(e)}"
                logger.error(f"[PURCHASE][{username}] {error_msg}", exc_info=True)
                await publish_purchase_error(account, error_msg)
                return
        else:
            # Auto purchase
            count = 5 if button_id == "buy_auto_5" else 1
            logger.info(f"[PURCHASE][{username}] Creating {count} auto game slots")
            slots = [DhLotto645.Slot(mode=DhLotto645SelMode.AUTO, numbers=[]) for _ in range(count)]
        
        # Execute purchase
        logger.info(f"[PURCHASE][{username}] Executing purchase: {len(slots)} game(s)")
        result = await account.lotto_645.async_buy(slots)
        
        logger.info(f"[PURCHASE][{username}] Purchase successful!")
        logger.info(f"[PURCHASE][{username}] Round: {result.round_no}, Barcode: {result.barcode}")
        
        # Update sensors
        await update_sensors_for_account(account)
        
        logger.info(f"[PURCHASE][{username}] Purchase completed!")
        
    except Exception as e:
        logger.error(f"[PURCHASE][{username}] Purchase failed: {e}", exc_info=True)
        await publish_purchase_error(account, str(e))


async def publish_purchase_error(account: AccountData, error_message: str):
    """Publish purchase error for a specific account"""
    error_data = {
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "friendly_name": "구매 오류",
        "icon": "mdi:alert-circle",
    }
    
    await publish_sensor_for_account(
        account,
        "lotto45_purchase_error",
        error_message[:255],
        error_data
    )


async def init_account(account: AccountData) -> bool:
    """Initialize a single account"""
    username = account.username
    
    if not account.enabled:
        logger.info(f"[INIT][{username}] Account disabled, skipping")
        return False
    
    try:
        logger.info(f"[INIT][{username}] Initializing account...")
        account.client = DhLotteryClient(account.username, account.password)
        await account.client.async_login()
        
        if config["enable_lotto645"]:
            account.lotto_645 = DhLotto645(account.client)
            account.analyzer = DhLottoAnalyzer(account.client)
        
        logger.info(f"[INIT][{username}] Account initialized successfully")
        return True
    except Exception as e:
        logger.error(f"[INIT][{username}] Failed to initialize: {e}", exc_info=True)
        return False


async def init_clients():
    """Initialize all client accounts"""
    global mqtt_client
    
    load_accounts_from_env()
    
    if not config["accounts"]:
        logger.error("No accounts configured")
        return False
    
    # Initialize each account
    success_count = 0
    for acc_config in config["accounts"]:
        username = acc_config.get("username", "")
        password = acc_config.get("password", "")
        enabled = acc_config.get("enabled", True)
        
        if not username or not password:
            logger.warning(f"Skipping account with missing credentials")
            continue
        
        account = AccountData(username, password, enabled)
        accounts[username] = account
        
        if await init_account(account):
            success_count += 1
    
    logger.info(f"Initialized {success_count}/{len(accounts)} account(s)")
    
    # Initialize MQTT
    if config["use_mqtt"]:
        logger.info("Initializing MQTT Discovery...")
        
        client_id_suffix = "_beta" if config["is_beta"] else ""
        mqtt_client = MQTTDiscovery(
            mqtt_url=os.getenv("MQTT_URL", "mqtt://homeassistant.local:1883"),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            client_id_suffix=client_id_suffix,
        )
        
        if mqtt_client.connect():
            logger.info("MQTT Discovery initialized successfully")
            
            # Register buttons for each account
            for account in accounts.values():
                if account.enabled and config["enable_lotto645"]:
                    await register_buttons_for_account(account)
            
            # Subscribe to commands
            if accounts:
                first_username = list(accounts.keys())[0]
                mqtt_client.subscribe_to_commands(first_username, on_button_command)
        else:
            logger.warning("MQTT connection failed")
            mqtt_client = None
    
    return success_count > 0


async def cleanup_clients():
    """Clean up all clients"""
    global mqtt_client
    
    if mqtt_client:
        try:
            mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting MQTT: {e}")
    
    for account in accounts.values():
        if account.client:
            try:
                await account.client.close()
            except Exception as e:
                logger.error(f"Error closing client for {account.username}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    global event_loop
    
    logger.info("Starting Lotto 45 Add-on v2.0.0 (Multi-Account)...")
    
    event_loop = asyncio.get_running_loop()
    
    await init_clients()
    
    # Start background tasks for each account
    tasks = []
    for account in accounts.values():
        if account.enabled:
            task = asyncio.create_task(background_tasks_for_account(account))
            account.update_task = task
            tasks.append(task)
    
    logger.info("Add-on started successfully")
    
    yield
    
    logger.info("Shutting down...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await cleanup_clients()
    logger.info("Shutdown complete")


# FastAPI app
app = FastAPI(
    title="Lotto 45 Multi-Account",
    version="2.0.0",
    lifespan=lifespan
)


async def background_tasks_for_account(account: AccountData):
    """Background tasks for a specific account"""
    username = account.username
    
    # Initial delay
    await asyncio.sleep(10)
    
    while True:
        try:
            await update_sensors_for_account(account)
            await asyncio.sleep(config["update_interval"])
        except asyncio.CancelledError:
            logger.info(f"[BG][{username}] Background task cancelled")
            break
        except Exception as e:
            logger.error(f"[BG][{username}] Error: {e}", exc_info=True)
            await asyncio.sleep(60)


async def update_sensors_for_account(account: AccountData):
    """Update sensors for a specific account"""
    username = account.username
    
    if not account.client or not account.client.logged_in:
        logger.warning(f"[SENSOR][{username}] Client not logged in, attempting login...")
        try:
            await account.client.async_login()
        except Exception as e:
            logger.error(f"[SENSOR][{username}] Login failed: {e}")
            return
    
    try:
        logger.info(f"[SENSOR][{username}] Updating sensors...")
        
        # Balance
        balance = await account.client.async_get_balance()
        await publish_sensor_for_account(account, "lotto45_balance", balance.deposit, {
            "purchase_available": balance.purchase_available,
            "reservation_purchase": balance.reservation_purchase,
            "withdrawal_request": balance.withdrawal_request,
            "this_month_accumulated": balance.this_month_accumulated_purchase,
            "unit_of_measurement": "KRW",
            "friendly_name": "예치금",
            "icon": "mdi:wallet",
        })
        
        # Lotto statistics (if enabled)
        if config["enable_lotto645"] and account.analyzer:
            # Latest round info
            latest_round_info = await account.lotto_645.async_get_round_info()
            
            # Winning numbers
            winning_numbers = latest_round_info.numbers
            bonus_number = latest_round_info.bonus_num
            round_no = latest_round_info.round_no
            winning_text = f"Round {round_no}: {', '.join(map(str, winning_numbers))} + {bonus_number}"
            
            await publish_sensor_for_account(account, "lotto645_winning_numbers", winning_text, {
                "numbers": winning_numbers,
                "bonus": bonus_number,
                "round": round_no,
                "friendly_name": "당첨 번호",
                "icon": "mdi:trophy-award",
            })
            
            # Purchase history
            history = await account.lotto_645.async_get_buy_history_this_week()
            if history:
                latest_purchase = history[0]
                games_info = [{
                    "slot": g.slot,
                    "mode": str(g.mode),
                    "numbers": g.numbers
                } for g in latest_purchase.games]
                
                await publish_sensor_for_account(account, "lotto45_latest_purchase", latest_purchase.round_no, {
                    "round_no": latest_purchase.round_no,
                    "barcode": latest_purchase.barcode,
                    "result": latest_purchase.result,
                    "games": games_info,
                    "games_count": len(latest_purchase.games),
                    "friendly_name": "최근 구매",
                    "icon": "mdi:receipt-text",
                })
        
        # Update time
        now = datetime.now(timezone.utc).isoformat()
        await publish_sensor_for_account(account, "lotto45_last_update", now, {
            "friendly_name": "마지막 업데이트",
            "icon": "mdi:clock-check-outline",
        })
        
        logger.info(f"[SENSOR][{username}] Sensors updated successfully")
        
    except Exception as e:
        logger.error(f"[SENSOR][{username}] Update failed: {e}", exc_info=True)


async def publish_sensor_for_account(
    account: AccountData,
    entity_id: str,
    state,
    attributes: dict = None
):
    """Publish sensor for a specific account"""
    username = account.username
    
    # MQTT first
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
            logger.error(f"[SENSOR][{username}] MQTT publish error: {e}")
    
    # Fallback to REST API
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
                    logger.error(f"[SENSOR][{username}] REST API failed: {resp.status}")
    except Exception as e:
        logger.error(f"[SENSOR][{username}] REST API error: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page"""
    accounts_html = "<ul>"
    for username, account in accounts.items():
        status = "✅ Connected" if account.client and account.client.logged_in else "❌ Disconnected"
        enabled = "✅" if account.enabled else "❌"
        accounts_html += f"<li><strong>{username}</strong>: {status} (Enabled: {enabled})</li>"
    accounts_html += "</ul>"
    
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Lotto 45 v2.0.0 Multi-Account</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>🎰 DH Lottery Lotto 45 <span style="color:#666;">v2.0.0 Multi-Account</span></h1>
            
            <div class="info">
                <h2>Accounts ({len(accounts)})</h2>
                {accounts_html}
            </div>
            
            <div class="info">
                <p><strong>Update Interval:</strong> {config['update_interval']}s</p>
                <p><strong>Lotto 645 Enabled:</strong> {config['enable_lotto645']}</p>
                <p><strong>MQTT Enabled:</strong> {config['use_mqtt']}</p>
            </div>
            
            <h2>API</h2>
            <ul>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/accounts">View All Accounts</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/health")
async def health():
    """Health check"""
    accounts_status = {}
    for username, account in accounts.items():
        accounts_status[username] = {
            "logged_in": account.client.logged_in if account.client else False,
            "enabled": account.enabled,
        }
    
    return {
        "status": "ok",
        "version": "2.0.0",
        "accounts": accounts_status,
        "total_accounts": len(accounts),
        "lotto645_enabled": config["enable_lotto645"],
        "mqtt_enabled": config["use_mqtt"],
    }


@app.get("/accounts")
async def list_accounts():
    """List all accounts"""
    result = []
    for username, account in accounts.items():
        result.append({
            "username": username,
            "enabled": account.enabled,
            "logged_in": account.client.logged_in if account.client else False,
        })
    return {"accounts": result}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=60099, log_level="info")
