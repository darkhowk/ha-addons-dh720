# -*- coding: utf-8 -*-
"""
Lotto 45 Add-on Main Application v2.0.0
Home Assistant Add-on for DH Lottery 6/45
v2.0.0 - Multi-account support with full sensor suite
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
    "accounts": [],
    "enable_lotto645": os.getenv("ENABLE_LOTTO645", "true").lower() == "true",
    "update_interval": int(os.getenv("UPDATE_INTERVAL", "3600")),
    "use_mqtt": os.getenv("USE_MQTT", "false").lower() == "true",
    "ha_url": os.getenv("HA_URL", "http://supervisor/core"),
    "supervisor_token": os.getenv("SUPERVISOR_TOKEN", ""),
    "is_beta": os.getenv("IS_BETA", "false").lower() == "true",
}

# Global variables
accounts: Dict[str, AccountData] = {}
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
        logger.warning(f"[BUTTON][{account.username}] MQTT not connected")
        return
    
    username = account.username
    logger.info(f"[BUTTON][{username}] Registering button entities")
    
    device_suffix = " (Beta)" if config.get("is_beta", False) else ""
    device_name = f"DH Lottery Addon{device_suffix} ({username})"
    device_id = f"dhlotto_addon_{username}"
    
    # Buttons
    for button_id, button_name, icon in [
        ("buy_auto_1", "1 게임 자동 구매", "mdi:ticket-confirmation"),
        ("buy_auto_5", "5 게임 자동 구매", "mdi:ticket-confirmation-outline"),
        ("buy_manual", "1 게임 수동 구매", "mdi:hand-pointing-right"),
        ("generate_random", "랜덤 번호 생성", "mdi:dice-multiple"),
    ]:
        button_topic = f"homeassistant/button/{mqtt_client.topic_prefix}_{username}_{button_id}/command"
        mqtt_client.publish_button_discovery(
            button_id=button_id,
            name=button_name,
            command_topic=button_topic,
            username=username,
            device_name=device_name,
            device_identifier=device_id,
            icon=icon,
        )
    
    # Input Text
    input_state_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/state"
    input_command_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/set"
    
    mqtt_client.publish_input_text_discovery(
        input_id="manual_numbers",
        name="수동 번호 입력 (쉼표로 구분, 자동은 auto)",
        state_topic=input_state_topic,
        command_topic=input_command_topic,
        username=username,
        device_name=device_name,
        device_identifier=device_id,
        icon="mdi:numeric",
        mode="text",
    )
    
    mqtt_client.client.publish(input_state_topic, "auto,auto,auto,auto,auto,auto", qos=1, retain=True)
    logger.info(f"[BUTTON][{username}] All buttons registered")


def on_button_command(client_mqtt, userdata, message):
    """Handle MQTT button commands"""
    try:
        topic = message.topic
        payload = message.payload.decode()
        
        logger.info(f"[MQTT] Received: topic={topic}, payload={payload}")
        
        parts = topic.split("/")
        if len(parts) < 3:
            return
        
        entity_id_full = parts[2]
        
        if not entity_id_full.startswith(mqtt_client.topic_prefix + "_"):
            return
        
        without_prefix = entity_id_full[len(mqtt_client.topic_prefix) + 1:]
        
        username = None
        for acc_username in accounts.keys():
            if without_prefix.startswith(acc_username + "_"):
                username = acc_username
                break
        
        if not username or username not in accounts:
            return
        
        account = accounts[username]
        
        # Input text
        if "/text/" in topic and "/set" in topic:
            logger.info(f"[INPUT][{username}] Manual numbers updated: {payload}")
            account.manual_numbers_state = payload
            state_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/state"
            client_mqtt.publish(state_topic, payload, qos=1, retain=True)
            return
        
        # Button
        button_suffix = without_prefix[len(username) + 1:]
        logger.info(f"[BUTTON][{username}] Button pressed: {button_suffix}")

        # Handle random number generation button
        if button_suffix == "generate_random":
            logger.info(f"[RANDOM][{username}] Generating random numbers")
            random_numbers = DhLottoAnalyzer.generate_random_numbers(6)
            random_str = ",".join(map(str, random_numbers))
            logger.info(f"[RANDOM][{username}] Generated: {random_str}")
            
            # Update manual_numbers_state
            account.manual_numbers_state = random_str
            
            # Publish to input_text state topic
            state_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{username}_manual_numbers/state"
            client_mqtt.publish(state_topic, random_str, qos=1, retain=True)
            
            logger.info(f"[RANDOM][{username}] Random numbers published to input text")
            return

        
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                execute_button_purchase(account, button_suffix),
                event_loop
            )
    
    except Exception as e:
        logger.error(f"[MQTT] Error: {e}", exc_info=True)


async def execute_button_purchase(account: AccountData, button_id: str):
    """Execute purchase for account"""
    username = account.username
    logger.info(f"[PURCHASE][{username}] Starting purchase: {button_id}")
    
    if not account.lotto_645:
        logger.error(f"[PURCHASE][{username}] Lotto 645 not enabled")
        return
    
    try:
        if button_id == "buy_manual":
            manual_numbers_text = account.manual_numbers_state
            if not manual_numbers_text:
                await publish_purchase_error(account, "Please enter manual numbers")
                return
            
            try:
                parts = [p.strip() for p in manual_numbers_text.split(",")]
                if len(parts) != 6:
                    await publish_purchase_error(account, f"Must provide 6 values (got {len(parts)})")
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
                                await publish_purchase_error(account, f"Numbers must be 1-45 (got {num})")
                                return
                            manual_numbers.append(num)
                        except ValueError:
                            await publish_purchase_error(account, f"Invalid input: {part}")
                            return
                
                if len(manual_numbers) != len(set(manual_numbers)):
                    await publish_purchase_error(account, "Duplicate numbers")
                    return
                
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
                await publish_purchase_error(account, f"Error: {str(e)}")
                return
        else:
            count = 5 if button_id == "buy_auto_5" else 1
            slots = [DhLotto645.Slot(mode=DhLotto645SelMode.AUTO, numbers=[]) for _ in range(count)]
        
        logger.info(f"[PURCHASE][{username}] Executing: {len(slots)} game(s)")
        result = await account.lotto_645.async_buy(slots)
        
        logger.info(f"[PURCHASE][{username}] Success! Round: {result.round_no}")
        
        await update_sensors_for_account(account)
        
    except Exception as e:
        logger.error(f"[PURCHASE][{username}] Failed: {e}", exc_info=True)
        await publish_purchase_error(account, str(e))


async def publish_purchase_error(account: AccountData, error_message: str):
    """Publish purchase error"""
    error_data = {
        "error": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "friendly_name": "구매 오류",
        "icon": "mdi:alert-circle",
    }
    await publish_sensor_for_account(account, "lotto45_purchase_error", error_message[:255], error_data)


async def init_account(account: AccountData) -> bool:
    """Initialize account"""
    username = account.username
    
    if not account.enabled:
        logger.info(f"[INIT][{username}] Account disabled")
        return False
    
    try:
        logger.info(f"[INIT][{username}] Initializing...")
        account.client = DhLotteryClient(account.username, account.password)
        await account.client.async_login()
        
        if config["enable_lotto645"]:
            account.lotto_645 = DhLotto645(account.client)
            account.analyzer = DhLottoAnalyzer(account.client)
        
        logger.info(f"[INIT][{username}] Success")
        return True
    except Exception as e:
        logger.error(f"[INIT][{username}] Failed: {e}", exc_info=True)
        return False


async def init_clients():
    """Initialize all clients"""
    global mqtt_client
    
    load_accounts_from_env()
    
    if not config["accounts"]:
        logger.error("No accounts configured")
        return False
    
    success_count = 0
    for acc_config in config["accounts"]:
        username = acc_config.get("username", "")
        password = acc_config.get("password", "")
        enabled = acc_config.get("enabled", True)
        
        if not username or not password:
            continue
        
        account = AccountData(username, password, enabled)
        accounts[username] = account
        
        if await init_account(account):
            success_count += 1
    
    logger.info(f"Initialized {success_count}/{len(accounts)} account(s)")
    
    # MQTT
    if config["use_mqtt"]:
        logger.info("Initializing MQTT...")
        
        client_id_suffix = "_beta" if config["is_beta"] else ""
        mqtt_client = MQTTDiscovery(
            mqtt_url=os.getenv("MQTT_URL", "mqtt://homeassistant.local:1883"),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            client_id_suffix=client_id_suffix,
        )
        
        if mqtt_client.connect():
            logger.info("MQTT connected")
            
            # Only register buttons for successfully logged in accounts
            for account in accounts.values():
                if account.enabled and config["enable_lotto645"] and account.client and account.client.logged_in:
                    await register_buttons_for_account(account)
                elif account.enabled and (not account.client or not account.client.logged_in):
                    logger.warning(f"[BUTTON][{account.username}] Skipping button registration - not logged in")
            
            # Subscribe to button commands for ALL logged-in accounts
            if accounts:
                # Set callback once
                mqtt_client.client.on_message = on_button_command
                
                # Subscribe to each account's buttons
                for account in accounts.values():
                    if account.enabled and account.client and account.client.logged_in:
                        button_ids = ["buy_auto_1", "buy_auto_5", "buy_manual", "generate_random"]
                        
                        # Subscribe to button commands
                        for button_id in button_ids:
                            command_topic = f"homeassistant/button/{mqtt_client.topic_prefix}_{account.username}_{button_id}/command"
                            mqtt_client.client.subscribe(command_topic)
                            logger.info(f"[MQTT] Subscribed: {command_topic}")
                        
                        # Subscribe to input_text
                        input_command_topic = f"homeassistant/text/{mqtt_client.topic_prefix}_{account.username}_manual_numbers/set"
                        mqtt_client.client.subscribe(input_command_topic)
                        logger.info(f"[MQTT] Subscribed: {input_command_topic}")
                
                logger.info(f"[MQTT] Subscribed to {len([a for a in accounts.values() if a.enabled and a.client and a.client.logged_in])} account(s)")
        else:
            logger.warning("MQTT connection failed")
            mqtt_client = None
    
    return success_count > 0


async def cleanup_clients():
    """Cleanup"""
    global mqtt_client
    
    if mqtt_client:
        try:
            mqtt_client.disconnect()
        except:
            pass
    
    for account in accounts.values():
        if account.client:
            try:
                await account.client.close()
            except:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle"""
    global event_loop
    
    logger.info("Starting v2.0.0 Multi-Account...")
    
    event_loop = asyncio.get_running_loop()
    await init_clients()
    
    tasks = []
    for account in accounts.values():
        if account.enabled:
            task = asyncio.create_task(background_tasks_for_account(account))
            account.update_task = task
            tasks.append(task)
    
    logger.info("Started")
    
    yield
    
    logger.info("Shutting down...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await cleanup_clients()


app = FastAPI(title="Lotto 45 Multi", version="2.0.0", lifespan=lifespan)


async def background_tasks_for_account(account: AccountData):
    """Background tasks"""
    username = account.username
    
    # Skip if not logged in
    if not account.client or not account.client.logged_in:
        logger.warning(f"[BG][{username}] Skipping background task - not logged in")
        return
    
    await asyncio.sleep(10)
    
    while True:
        try:
            await update_sensors_for_account(account)
            await asyncio.sleep(config["update_interval"])
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[BG][{account.username}] Error: {e}", exc_info=True)
            await asyncio.sleep(60)


async def update_sensors_for_account(account: AccountData):
    """Update all sensors for account - FULL VERSION"""
    username = account.username
    
    if not account.client or not account.client.logged_in:
        logger.warning(f"[SENSOR][{username}] Not logged in, attempting login...")
        try:
            await account.client.async_login()
        except Exception as e:
            logger.error(f"[SENSOR][{username}] Login failed: {e}")
            await publish_sensor_for_account(account, "lotto45_login_error", str(e)[:255], {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "friendly_name": "로그인 오류",
                "icon": "mdi:account-alert",
            })
            logger.warning(f"[SENSOR][{username}] Skipping sensor update due to login failure")
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
        
        # Purchase time info
        await publish_sensor_for_account(account, "lotto45_purchase_available_time",
            "weekdays: 06:00-24:00, saturday: 06:00-20:00, sunday: 06:00-24:00", {
            "weekdays": "06:00-24:00",
            "saturday": "06:00-20:00",
            "sunday": "06:00-24:00",
            "friendly_name": "구매 가능 시간",
            "icon": "mdi:clock-time-eight",
        })
        
        # Lotto stats
        if config["enable_lotto645"] and account.analyzer:
            try:
                # Get raw prize data
                params = {"_": int(datetime.now().timestamp() * 1000)}
                raw_data = await account.client.async_get('lt645/selectPstLt645Info.do', params)
                
                items = raw_data.get('list', [])
                if not items:
                    raise Exception("No data")
                
                item = items[0]
                
                # Get round info
                latest_round_info = await account.lotto_645.async_get_round_info()
                result_item = {
                    "ltEpsd": latest_round_info.round_no,
                    "tm1WnNo": latest_round_info.numbers[0],
                    "tm2WnNo": latest_round_info.numbers[1],
                    "tm3WnNo": latest_round_info.numbers[2],
                    "tm4WnNo": latest_round_info.numbers[3],
                    "tm5WnNo": latest_round_info.numbers[4],
                    "tm6WnNo": latest_round_info.numbers[5],
                    "bnsWnNo": latest_round_info.bonus_num,
                    "ltRflYmd": latest_round_info.draw_date,
                }
                
                # Round number
                await publish_sensor_for_account(account, "lotto645_round", _safe_int(result_item.get("ltEpsd")), {
                    "friendly_name": "로또 회차",
                    "icon": "mdi:counter",
                })
                
                # Individual numbers
                for i in range(1, 7):
                    await publish_sensor_for_account(account, f"lotto645_number{i}",
                        _safe_int(result_item.get(f"tm{i}WnNo")), {
                        "friendly_name": f"로또 번호 {i}",
                        "icon": f"mdi:numeric-{i}-circle",
                    })
                
                # Bonus
                await publish_sensor_for_account(account, "lotto645_bonus", _safe_int(result_item.get("bnsWnNo")), {
                    "friendly_name": "로또 보너스 번호",
                    "icon": "mdi:star-circle",
                })
                
                # Combined winning numbers
                winning_numbers = [_safe_int(result_item.get(f"tm{i}WnNo")) for i in range(1, 7)]
                bonus_number = _safe_int(result_item.get("bnsWnNo"))
                round_no = _safe_int(result_item.get("ltEpsd"))
                winning_text = f"Round {round_no}: {', '.join(map(str, winning_numbers))} + {bonus_number}"
                
                await publish_sensor_for_account(account, "lotto645_winning_numbers", winning_text, {
                    "numbers": winning_numbers,
                    "bonus": bonus_number,
                    "round": round_no,
                    "friendly_name": "당첨 번호",
                    "icon": "mdi:trophy-award",
                })
                
                # Draw date
                draw_date = _parse_yyyymmdd(result_item.get("ltRflYmd"))
                if draw_date:
                    await publish_sensor_for_account(account, "lotto645_draw_date", draw_date, {
                        "friendly_name": "로또 추첨일",
                        "icon": "mdi:calendar",
                        "device_class": "date",
                    })
                
                # Prize details
                await publish_sensor_for_account(account, "lotto645_total_sales",
                    _safe_int(item.get("wholEpsdSumNtslAmt")), {
                    "friendly_name": "총 판매액",
                    "unit_of_measurement": "KRW",
                    "icon": "mdi:cash-multiple",
                })
                
                # 1st-5th prizes
                for rank in range(1, 6):
                    await publish_sensor_for_account(account, f"lotto645_{['first','second','third','fourth','fifth'][rank-1]}_prize",
                        _safe_int(item.get(f"rnk{rank}WnAmt")), {
                        "friendly_name": f"로또 {rank}등 당첨금",
                        "unit_of_measurement": "KRW",
                        "total_amount": _safe_int(item.get(f"rnk{rank}SumWnAmt")),
                        "winners": _safe_int(item.get(f"rnk{rank}WnNope")),
                        "icon": ["mdi:trophy", "mdi:medal", "mdi:medal-outline", "mdi:currency-krw", "mdi:cash"][rank-1],
                    })
                
            except Exception as e:
                logger.warning(f"[SENSOR][{username}] Failed to fetch lotto results: {e}")
            
            # Purchase history - GAME SENSORS HERE!
            try:
                history = await account.lotto_645.async_get_buy_history_this_week()
                
                # Collect games (max 5)
                all_games = []
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
                        "friendly_name": "로또 최근 구매 회차",
                        "icon": "mdi:receipt-text",
                    })
                    
                    # Collect all games (max 5)
                    for purchase in reversed(history):
                        for game in purchase.games:
                            all_games.append({
                                'game': game,
                                'round_no': purchase.round_no,
                                'result': purchase.result
                            })
                            if len(all_games) >= 5:
                                break
                        if len(all_games) >= 5:
                            break
                else:
                    # No purchase history
                    logger.info(f"[SENSOR][{username}] No purchase history in the last week")
                
                logger.info(f"[SENSOR][{username}] Publishing 5 game sensors (filled: {len(all_games)})")
                
                latest_round_no = await account.lotto_645.async_get_latest_round_no()
                weekly_purchase_count = 0
                
                # ALWAYS CREATE 5 GAME SENSORS (fixed slots)
                for i in range(1, 6):
                    if i <= len(all_games):
                        # Game exists - fill with data
                        game_info = all_games[i-1]
                        game = game_info['game']
                        round_no = game_info['round_no']
                        numbers_str = ", ".join(map(str, game.numbers))
                        
                        # Game numbers sensor - ADD KOREAN KEYS HERE!
                        await publish_sensor_for_account(account, f"lotto45_game_{i}", numbers_str, {
                            "slot": game.slot,
                            "슬롯": game.slot,  # 한글 키 추가
                            "mode": str(game.mode),
                            "선택": str(game.mode),  # 한글 키 추가 (자동/수동/반자동)
                            "numbers": game.numbers,
                            "round_no": round_no,
                            "result": game_info['result'],
                            "friendly_name": f"게임 {i}",
                            "icon": f"mdi:numeric-{i}-box-multiple",
                        })
                        logger.info(f"[SENSOR][{username}] Game {i}: {numbers_str}")
                        
                        # Game result sensor
                        try:
                            result_text = "미추첨"
                            result_icon = "mdi:clock-outline"
                            result_color = "grey"
                            matching_count = 0
                            bonus_match = False
                            winning_numbers_check = []
                            bonus_number_check = 0
                            rank = 0
                            
                            if round_no <= latest_round_no:
                                winning_data = await account.lotto_645.async_get_round_info(round_no)
                                winning_numbers_check = winning_data.numbers
                                bonus_number_check = winning_data.bonus_num
                                
                                check_result = await account.analyzer.async_check_winning(game.numbers, round_no)
                                matching_count = check_result['matching_count']
                                bonus_match = check_result['bonus_match']
                                rank = check_result['rank']
                                
                                if rank == 1:
                                    result_text = "1등 당첨"
                                    result_icon = "mdi:trophy"
                                    result_color = "gold"
                                elif rank == 2:
                                    result_text = "2등 당첨"
                                    result_icon = "mdi:medal"
                                    result_color = "silver"
                                elif rank == 3:
                                    result_text = "3등 당첨"
                                    result_icon = "mdi:medal-outline"
                                    result_color = "bronze"
                                elif rank == 4:
                                    result_text = "4등 당첨"
                                    result_icon = "mdi:currency-krw"
                                    result_color = "blue"
                                elif rank == 5:
                                    result_text = "5등 당첨"
                                    result_icon = "mdi:cash"
                                    result_color = "green"
                                else:
                                    result_text = "낙첨"
                                    result_icon = "mdi:close-circle-outline"
                                    result_color = "red"
                            else:
                                weekly_purchase_count += 1
                            
                            await publish_sensor_for_account(account, f"lotto45_game_{i}_result", result_text, {
                                "round_no": round_no,
                                "my_numbers": game.numbers,
                                "winning_numbers": winning_numbers_check,
                                "bonus_number": bonus_number_check,
                                "matching_count": matching_count,
                                "bonus_match": bonus_match,
                                "rank": rank,
                                "result": result_text,
                                "color": result_color,
                                "friendly_name": f"게임 {i} 결과",
                                "icon": result_icon,
                            })
                            logger.info(f"[SENSOR][{username}] Game {i} result: {result_text}")
                            
                        except Exception as e:
                            logger.warning(f"[SENSOR][{username}] Failed to check game {i}: {e}")
                            await publish_sensor_for_account(account, f"lotto45_game_{i}_result", "Check Failed", {
                                "round_no": round_no,
                                "my_numbers": game.numbers,
                                "error": str(e),
                                "friendly_name": f"게임 {i} 결과",
                                "icon": "mdi:alert-circle-outline",
                            })
                    else:
                        # Empty slot - create placeholder
                        await publish_sensor_for_account(account, f"lotto45_game_{i}", "Empty", {
                            "slot": "-",
                            "슬롯": "-",  # 한글 키
                            "mode": "-",
                            "선택": "-",  # 한글 키
                            "numbers": [],
                            "round_no": 0,
                            "result": "-",
                            "friendly_name": f"게임 {i}",
                            "icon": f"mdi:numeric-{i}-box-outline",
                        })
                        
                        await publish_sensor_for_account(account, f"lotto45_game_{i}_result", "Empty", {
                            "round_no": 0,
                            "my_numbers": [],
                            "winning_numbers": [],
                            "bonus_number": 0,
                            "matching_count": 0,
                            "bonus_match": False,
                            "rank": 0,
                            "result": "Empty",
                            "color": "grey",
                            "friendly_name": f"게임 {i} 결과",
                            "icon": "mdi:circle-outline",
                        })
                
                # Weekly purchase count
                weekly_limit = 5
                remaining_count = max(0, weekly_limit - weekly_purchase_count)
                
                await publish_sensor_for_account(account, "lotto45_weekly_purchase_count", weekly_purchase_count, {
                    "weekly_limit": weekly_limit,
                    "remaining": remaining_count,
                    "friendly_name": "주간 구매 횟수",
                    "unit_of_measurement": "games",
                    "icon": "mdi:ticket-confirmation" if remaining_count > 0 else "mdi:close-circle",
                })
                
                logger.info(f"[SENSOR][{username}] Weekly: {weekly_purchase_count}/{weekly_limit}")
                    
            except Exception as e:
                logger.warning(f"[SENSOR][{username}] Failed purchase history: {e}")
        
        # Hot/Cold Numbers Analysis
        if config["enable_lotto645"] and account.analyzer:
            try:
                hot_cold_data = await account.analyzer.async_get_hot_cold_numbers(recent_rounds=20)
                
                # Hot numbers sensor
                hot_numbers_str = ", ".join(map(str, hot_cold_data.hot_numbers))
                await publish_sensor_for_account(account, "lotto45_hot_numbers", hot_numbers_str, {
                    "numbers": hot_cold_data.hot_numbers,
                    "friendly_name": "가장 많이 나온 번호 10개 (최근 20회)",
                    "icon": "mdi:fire",
                })
                
                # Cold numbers sensor
                cold_numbers_str = ", ".join(map(str, hot_cold_data.cold_numbers))
                await publish_sensor_for_account(account, "lotto45_cold_numbers", cold_numbers_str, {
                    "numbers": hot_cold_data.cold_numbers,
                    "friendly_name": "가장 적게 나온 번호 10개 (최근 20회)",
                    "icon": "mdi:snowflake",
                })
                
                # Most frequent numbers sensor
                top_freq_str = "최근 50회차: " + ", ".join([f"{nf.number}번({nf.count}번 출현)" for nf in hot_cold_data.most_frequent[:5]])
                await publish_sensor_for_account(account, "lotto45_most_frequent_numbers", top_freq_str, {
                    "top_5": [{"number": nf.number, "count": nf.count, "percentage": nf.percentage} 
                             for nf in hot_cold_data.most_frequent[:5]],
                    "friendly_name": "가장 많이 나온 번호 5개 (최근 50회)",
                    "icon": "mdi:chart-bar",
                })
                
                logger.info(f"[SENSOR][{username}] Hot/Cold numbers updated")
                
            except Exception as e:
                logger.warning(f"[SENSOR][{username}] Failed to update hot/cold numbers: {e}")
        
        # Winning Probability Sensors
        if config["enable_lotto645"]:
            try:
                # Calculate probabilities (fixed values based on combinatorics)
                # Total combinations: C(45, 6) = 8,145,060
                total_combinations = 8145060
                
                # 1st prize: 6 numbers match = 1 / 8,145,060
                prob_1st = (1 / total_combinations) * 100
                await publish_sensor_for_account(account, "lotto645_probability_rank1", f"{prob_1st:.7f}", {
                    "probability_decimal": prob_1st,
                    "probability_fraction": "1/8,145,060",
                    "unit_of_measurement": "%",
                    "friendly_name": "1등 당첨 확률",
                    "icon": "mdi:trophy",
                })
                
                # 2nd prize: 5 numbers + bonus = 6 / 8,145,060
                prob_2nd = (6 / total_combinations) * 100
                await publish_sensor_for_account(account, "lotto645_probability_rank2", f"{prob_2nd:.7f}", {
                    "probability_decimal": prob_2nd,
                    "probability_fraction": "6/8,145,060",
                    "unit_of_measurement": "%",
                    "friendly_name": "2등 당첨 확률",
                    "icon": "mdi:medal",
                })
                
                # 3rd prize: 5 numbers = 234 / 8,145,060
                prob_3rd = (234 / total_combinations) * 100
                await publish_sensor_for_account(account, "lotto645_probability_rank3", f"{prob_3rd:.5f}", {
                    "probability_decimal": prob_3rd,
                    "probability_fraction": "234/8,145,060",
                    "unit_of_measurement": "%",
                    "friendly_name": "3등 당첨 확률",
                    "icon": "mdi:medal-outline",
                })
                
                # 4th prize: 4 numbers = 11,115 / 8,145,060
                prob_4th = (11115 / total_combinations) * 100
                await publish_sensor_for_account(account, "lotto645_probability_rank4", f"{prob_4th:.4f}", {
                    "probability_decimal": prob_4th,
                    "probability_fraction": "11,115/8,145,060",
                    "unit_of_measurement": "%",
                    "friendly_name": "4등 당첨 확률",
                    "icon": "mdi:currency-krw",
                })
                
                # 5th prize: 3 numbers = 185,220 / 8,145,060
                prob_5th = (185220 / total_combinations) * 100
                await publish_sensor_for_account(account, "lotto645_probability_rank5", f"{prob_5th:.3f}", {
                    "probability_decimal": prob_5th,
                    "probability_fraction": "185,220/8,145,060",
                    "unit_of_measurement": "%",
                    "friendly_name": "5등 당첨 확률",
                    "icon": "mdi:cash",
                })
                
                logger.info(f"[SENSOR][{username}] Winning probabilities updated")
                
            except Exception as e:
                logger.warning(f"[SENSOR][{username}] Failed to update winning probabilities: {e}")
        
        # Update time
        now = datetime.now(timezone.utc).isoformat()
        await publish_sensor_for_account(account, "lotto45_last_update", now, {
            "friendly_name": "마지막 업데이트",
            "icon": "mdi:clock-check-outline",
        })
        
        logger.info(f"[SENSOR][{username}] Updated successfully")
        
    except Exception as e:
        logger.error(f"[SENSOR][{username}] Update failed: {e}", exc_info=True)


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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page"""
    accounts_html = "<ul>"
    for username, account in accounts.items():
        status = "✅" if account.client and account.client.logged_in else "❌"
        enabled = "✅" if account.enabled else "❌"
        accounts_html += f"<li><strong>{username}</strong>: {status} (Enabled: {enabled})</li>"
    accounts_html += "</ul>"
    
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Lotto 45 v2.0.0</title>
            <style>
                body {{ font-family: Arial; margin: 40px; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>🎰 Lotto 45 <span style="color:#666;">v2.0.0 Multi-Account</span></h1>
            <div class="info">
                <h2>Accounts ({len(accounts)})</h2>
                {accounts_html}
            </div>
            <ul>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/accounts">Accounts</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/health")
async def health():
    """Health"""
    accounts_status = {}
    logged_in_count = 0
    
    for username, account in accounts.items():
        is_logged_in = account.client.logged_in if account.client else False
        if is_logged_in:
            logged_in_count += 1
            
        accounts_status[username] = {
            "logged_in": is_logged_in,
            "enabled": account.enabled,
            "status": "✅ Active" if is_logged_in else "❌ Login Failed",
        }
    
    return {
        "status": "ok" if logged_in_count > 0 else "degraded",
        "version": "2.0.0",
        "accounts": accounts_status,
        "total_accounts": len(accounts),
        "logged_in_accounts": logged_in_count,
        "failed_accounts": len(accounts) - logged_in_count,
    }


@app.get("/accounts")
async def list_accounts():
    """List accounts"""
    result = []
    for username, account in accounts.values():
        result.append({
            "username": username,
            "enabled": account.enabled,
            "logged_in": account.client.logged_in if account.client else False,
        })
    return {"accounts": result}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=60099, log_level="info")
