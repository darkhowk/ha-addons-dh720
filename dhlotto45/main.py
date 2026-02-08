# -*- coding: utf-8 -*-
"""
Lotto 45 Add-on Main Application v0.6.8
Home Assistant Add-on for DH Lottery 6/45
v0.6.8 - Optimized encoding and English sensor names
"""

import os
import asyncio
import logging
from typing import Optional
from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

from dh_lottery_client import DhLotteryClient
from dh_lotto_645 import DhLotto645
from dh_lotto_analyzer import DhLottoAnalyzer
from mqtt_discovery import MQTTDiscovery, publish_sensor_mqtt

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuration variables
config = {
    "username": os.getenv("USERNAME", ""),
    "password": os.getenv("PASSWORD", ""),
    "enable_lotto645": os.getenv("ENABLE_LOTTO645", "true").lower() == "true",
    "update_interval": int(os.getenv("UPDATE_INTERVAL", "3600")),
    "use_mqtt": os.getenv("USE_MQTT", "false").lower() == "true",
    "ha_url": os.getenv("HA_URL", "http://supervisor/core"),
    "supervisor_token": os.getenv("SUPERVISOR_TOKEN", ""),
}

client: Optional[DhLotteryClient] = None
lotto_645: Optional[DhLotto645] = None
analyzer: Optional[DhLottoAnalyzer] = None
mqtt_client: Optional[MQTTDiscovery] = None
event_loop: Optional[asyncio.AbstractEventLoop] = None


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


def _translate_result(result: str) -> str:
    """Translate Korean lottery result to English"""
    if not result:
        return "Unknown"
    
    result_lower = result.lower()
    translations = {
        "pending": "Pending",
        "no win": "No Win",
        "1st": "1st Prize",
        "2nd": "2nd Prize",
        "3rd": "3rd Prize",
        "4th": "4th Prize",
        "5th": "5th Prize",
    }
    
    for key, english in translations.items():
        if key in result_lower:
            return english
    
    return result


async def register_buttons():
    """Register button entities via MQTT Discovery"""
    if not mqtt_client or not mqtt_client.connected:
        logger.warning("[BUTTON] MQTT not connected, skipping button registration")
        return
    
    username = config["username"]
    logger.info(f"[BUTTON] Registering button entities for user: {username}")
    
    main_device_name = f"DH Lottery Addon ({username})"
    main_device_id = f"dhlotto_addon_{username}"
    
    # Button 1: Buy 1 Auto Game
    button1_topic = f"homeassistant/button/dhlotto_{username}_buy_auto_1/command"
    logger.info(f"[BUTTON] Button 1 command topic: {button1_topic}")
    
    success1 = mqtt_client.publish_button_discovery(
        button_id="buy_auto_1",
        name="Buy Auto Game",  # English
        command_topic=button1_topic,
        username=username,
        device_name=main_device_name,
        device_identifier=main_device_id,
        icon="mdi:ticket-confirmation",
    )
    if success1:
        logger.info("[BUTTON] Button registered: buy_auto_1")
    else:
        logger.error("[BUTTON] Failed to register button: buy_auto_1")
    
    # Button 2: Buy 5 Auto Games
    button2_topic = f"homeassistant/button/dhlotto_{username}_buy_auto_5/command"
    logger.info(f"[BUTTON] Button 2 command topic: {button2_topic}")
    
    success2 = mqtt_client.publish_button_discovery(
        button_id="buy_auto_5",
        name="Buy 5 Auto Games",  # English
        command_topic=button2_topic,
        username=username,
        device_name=main_device_name,
        device_identifier=main_device_id,
        icon="mdi:ticket-confirmation-outline",
    )
    if success2:
        logger.info("[BUTTON] Button registered: buy_auto_5")
    else:
        logger.error("[BUTTON] Failed to register button: buy_auto_5")
    
    if success1 and success2:
        logger.info("[BUTTON] All buttons registered successfully")
    else:
        logger.warning("[BUTTON] Some buttons failed to register")


def on_button_command(client_mqtt, userdata, message):
    """Handle MQTT button commands"""
    try:
        topic = message.topic
        payload = message.payload.decode()
        
        logger.info(f"[BUTTON] Received command: topic={topic}, payload={payload}")
        
        parts = topic.split("/")
        if len(parts) >= 3:
            entity_id = parts[2]
            logger.info(f"[BUTTON] Entity ID: {entity_id}")
            
            parts_entity = entity_id.split("_")
            logger.info(f"[BUTTON] Entity parts: {parts_entity}")
            
            if len(parts_entity) >= 4:
                button_id = "_".join(parts_entity[-3:])
                logger.info(f"[BUTTON] Button pressed: {button_id}")
                
                if event_loop and event_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        execute_button_purchase(button_id), 
                        event_loop
                    )
                    logger.info(f"[BUTTON] Purchase task scheduled for {button_id}")
                else:
                    logger.error("[BUTTON] Event loop not available or not running")
            else:
                logger.error(f"[BUTTON] Invalid entity_id format: {entity_id}")
        else:
            logger.error(f"[BUTTON] Invalid topic format: {topic}")
    
    except Exception as e:
        logger.error(f"[BUTTON] Error handling button command: {e}", exc_info=True)


async def execute_button_purchase(button_id: str):
    """Execute purchase based on button_id"""
    logger.info(f"[PURCHASE] Starting purchase for button_id: {button_id}")
    
    if not lotto_645:
        logger.error("[PURCHASE] Lotto 645 not enabled")
        return
    
    try:
        from dh_lotto_645 import DhLotto645, DhLotto645SelMode
        
        count = 5 if button_id == "buy_auto_5" else 1
        logger.info(f"[PURCHASE] Creating {count} auto game slots...")
        
        slots = [DhLotto645.Slot(mode=DhLotto645SelMode.AUTO, numbers=[]) for _ in range(count)]
        
        logger.info(f"[PURCHASE] Executing purchase: {count} game(s)...")
        result = await lotto_645.async_buy(slots)
        
        logger.info(f"[PURCHASE] Purchase successful!")
        logger.info(f"[PURCHASE] Round: {result.round_no}")
        logger.info(f"[PURCHASE] Barcode: {result.barcode}")
        logger.info(f"[PURCHASE] Issue Date: {result.issue_dt}")
        logger.info(f"[PURCHASE] Games: {len(result.games)}")
        
        for game in result.games:
            logger.info(f"[PURCHASE]   Slot {game.slot}: {game.numbers} ({game.mode})")
        
        logger.info(f"[PURCHASE] Updating all sensors...")
        await update_sensors()
        
        logger.info(f"[PURCHASE] Purchase completed successfully!")
        
    except Exception as e:
        logger.error(f"[PURCHASE] Purchase failed: {e}", exc_info=True)
        
        error_data = {
            "error": str(e),
            "button_id": button_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "friendly_name": "구매 오류",  # Korean
            "icon": "mdi:alert-circle",
        }
        
        logger.info(f"[PURCHASE] Publishing error sensor...")
        await publish_sensor("lotto45_purchase_error", str(e)[:255], error_data)


async def init_client():
    """Initialize client"""
    global client, lotto_645, analyzer, mqtt_client
    
    if not config["username"] or not config["password"]:
        logger.error("Username or password not configured")
        return False
    
    try:
        logger.info("Initializing DH Lottery client v0.6.8...")
        client = DhLotteryClient(config["username"], config["password"])
        await client.async_login()
        
        if config["enable_lotto645"]:
            lotto_645 = DhLotto645(client)
            analyzer = DhLottoAnalyzer(client)
        
        if config["use_mqtt"]:
            logger.info("Initializing MQTT Discovery...")
            mqtt_client = MQTTDiscovery(
                mqtt_url=os.getenv("MQTT_URL", "mqtt://homeassistant.local:1883"),
                username=os.getenv("MQTT_USERNAME"),
                password=os.getenv("MQTT_PASSWORD"),
            )
            if mqtt_client.connect():
                logger.info("MQTT Discovery initialized successfully")
                
                if config["enable_lotto645"]:
                    logger.info("Registering button entities...")
                    await register_buttons()
                    
                    logger.info("Subscribing to button commands...")
                    success = mqtt_client.subscribe_to_commands(
                        config["username"],
                        on_button_command
                    )
                    if success:
                        logger.info("Button command subscription successful")
                    else:
                        logger.error("Button command subscription failed")
            else:
                logger.warning("MQTT connection failed, falling back to REST API")
                mqtt_client = None
        
        logger.info("Client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}", exc_info=True)
        return False


async def cleanup_client():
    """Clean up client"""
    global client, mqtt_client
    
    if mqtt_client:
        try:
            mqtt_client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting MQTT client: {e}")
    
    if client:
        try:
            await client.close()
            logger.info("Client session closed")
        except Exception as e:
            logger.error(f"Error closing client session: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    global event_loop
    
    logger.info("Starting Lotto 45 Add-on v0.6.8...")
    logger.info(f"Configuration: username={config['username']}, "
                f"enable_lotto645={config['enable_lotto645']}, "
                f"update_interval={config['update_interval']}")
    
    event_loop = asyncio.get_running_loop()
    logger.info(f"Event loop stored: {event_loop}")
    
    await init_client()
    
    task = asyncio.create_task(background_tasks())
    
    logger.info("Add-on started successfully")
    
    yield
    
    logger.info("Shutting down Lotto 45 Add-on...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await cleanup_client()
    logger.info("Add-on shut down successfully")


# FastAPI app
app = FastAPI(
    title="Lotto 45",
    version="0.6.8",
    lifespan=lifespan
)


async def background_tasks():
    """Background tasks"""
    await asyncio.sleep(10)
    
    while True:
        try:
            await update_sensors()
            await asyncio.sleep(config["update_interval"])
        except asyncio.CancelledError:
            logger.info("Background task cancelled")
            break
        except Exception as e:
            logger.error(f"Background task error: {e}", exc_info=True)
            await asyncio.sleep(60)


async def update_sensors():
    """Update sensors - optimized version with English names"""
    if not client or not client.logged_in:
        logger.warning("Client not logged in, attempting to login...")
        try:
            await client.async_login()
        except Exception as e:
            logger.error(f"Failed to login: {e}")
            return
    
    try:
        logger.info("Updating sensors...")
        
        # 1. Balance
        balance = await client.async_get_balance()
        
        await publish_sensor("lotto45_balance", balance.deposit, {
            "purchase_available": balance.purchase_available,
            "reservation_purchase": balance.reservation_purchase,
            "withdrawal_request": balance.withdrawal_request,
            "this_month_accumulated": balance.this_month_accumulated_purchase,
            "unit_of_measurement": "KRW",
            "friendly_name": "동행복권 예치금",  # Korean
            "icon": "mdi:wallet",
        })
        
        # 2. Lotto statistics
        if config["enable_lotto645"] and analyzer:
            try:
                # Get raw data
                params = {
                    "_": int(datetime.now().timestamp() * 1000),
                }
                raw_data = await client.async_get('lt645/selectPstLt645Info.do', params)
                
                items = raw_data.get('list', [])
                if not items:
                    raise Exception("No lotto data available")
                
                item = items[0]
                
                latest_round_info = await lotto_645.async_get_round_info()
                lotto_result = {
                    "_raw": {
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
                }
                
                result_item = _get_lotto645_item(lotto_result)
                
                # Round number
                await publish_sensor("lotto645_round", _safe_int(result_item.get("ltEpsd")), {
                    "friendly_name": "로또 645 회차",  # Korean
                    "icon": "mdi:counter",
                })
                
                # Numbers 1-6
                for i in range(1, 7):
                    await publish_sensor(f"lotto645_number{i}", _safe_int(result_item.get(f"tm{i}WnNo")), {
                        "friendly_name": f"로또 645 번호 {i}",  # Korean
                        "icon": f"mdi:numeric-{i}-circle",
                    })
                
                # Bonus number
                await publish_sensor("lotto645_bonus", _safe_int(result_item.get("bnsWnNo")), {
                    "friendly_name": "로또 645 보너스",  # Korean
                    "icon": "mdi:star-circle",
                })
                
                # Winning numbers combined
                winning_numbers = [
                    _safe_int(result_item.get("tm1WnNo")),
                    _safe_int(result_item.get("tm2WnNo")),
                    _safe_int(result_item.get("tm3WnNo")),
                    _safe_int(result_item.get("tm4WnNo")),
                    _safe_int(result_item.get("tm5WnNo")),
                    _safe_int(result_item.get("tm6WnNo")),
                ]
                bonus_number = _safe_int(result_item.get("bnsWnNo"))
                round_no = _safe_int(result_item.get("ltEpsd"))
                winning_text = f"Round {round_no}, {', '.join(map(str, winning_numbers))} + {bonus_number}"
                
                await publish_sensor("lotto645_winning_numbers", winning_text, {
                    "numbers": winning_numbers,
                    "bonus": bonus_number,
                    "round": round_no,
                    "friendly_name": "로또 645 당첨번호",  # Korean
                    "icon": "mdi:trophy-award",
                })
                
                # Draw date
                draw_date = _parse_yyyymmdd(result_item.get("ltRflYmd"))
                if draw_date:
                    await publish_sensor("lotto645_draw_date", draw_date, {
                        "friendly_name": "로또 645 추첨일",  # Korean
                        "icon": "mdi:calendar",
                        "device_class": "date",
                    })
                
                # Prize details
                await publish_sensor("lotto645_total_sales", _safe_int(item.get("wholEpsdSumNtslAmt")), {
                    "friendly_name": "로또 645 이번 회차 총 판매액",  # Korean
                    "unit_of_measurement": "KRW",
                    "icon": "mdi:cash-multiple",
                })
                
                # 1st prize
                await publish_sensor("lotto645_first_prize", _safe_int(item.get("rnk1WnAmt")), {
                    "friendly_name": "로또 645 1등 상금",  # Korean
                    "unit_of_measurement": "KRW",
                    "total_amount": _safe_int(item.get("rnk1SumWnAmt")),
                    "winners": _safe_int(item.get("rnk1WnNope")),
                    "icon": "mdi:trophy",
                })
                
                await publish_sensor("lotto645_first_winners", _safe_int(item.get("rnk1WnNope")), {
                    "friendly_name": "로또 645 1등 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account-multiple",
                })
                
                # 2nd prize
                await publish_sensor("lotto645_second_prize", _safe_int(item.get("rnk2WnAmt")), {
                    "friendly_name": "로또 645 2등 상금",  # Korean
                    "unit_of_measurement": "KRW",
                    "total_amount": _safe_int(item.get("rnk2SumWnAmt")),
                    "winners": _safe_int(item.get("rnk2WnNope")),
                    "icon": "mdi:medal",
                })
                
                await publish_sensor("lotto645_second_winners", _safe_int(item.get("rnk2WnNope")), {
                    "friendly_name": "로또 645 2등 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account-multiple-outline",
                })
                
                # 3rd prize
                await publish_sensor("lotto645_third_prize", _safe_int(item.get("rnk3WnAmt")), {
                    "friendly_name": "로또 645 3등 상금",  # Korean
                    "unit_of_measurement": "KRW",
                    "total_amount": _safe_int(item.get("rnk3SumWnAmt")),
                    "winners": _safe_int(item.get("rnk3WnNope")),
                    "icon": "mdi:medal-outline",
                })
                
                await publish_sensor("lotto645_third_winners", _safe_int(item.get("rnk3WnNope")), {
                    "friendly_name": "로또 645 3등 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account-group-outline",
                })
                
                # 4th prize
                await publish_sensor("lotto645_fourth_prize", _safe_int(item.get("rnk4WnAmt")), {
                    "friendly_name": "로또 645 4등 상금",  # Korean
                    "unit_of_measurement": "KRW",
                    "total_amount": _safe_int(item.get("rnk4SumWnAmt")),
                    "winners": _safe_int(item.get("rnk4WnNope")),
                    "icon": "mdi:currency-krw",
                })
                
                await publish_sensor("lotto645_fourth_winners", _safe_int(item.get("rnk4WnNope")), {
                    "friendly_name": "로또 645 4등 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account-group",
                })
                
                # 5th prize
                await publish_sensor("lotto645_fifth_prize", _safe_int(item.get("rnk5WnAmt")), {
                    "friendly_name": "로또 645 5등 상금",  # Korean
                    "unit_of_measurement": "KRW",
                    "total_amount": _safe_int(item.get("rnk5SumWnAmt")),
                    "winners": _safe_int(item.get("rnk5WnNope")),
                    "icon": "mdi:cash",
                })
                
                await publish_sensor("lotto645_fifth_winners", _safe_int(item.get("rnk5WnNope")), {
                    "friendly_name": "로또 645 5등 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account",
                })
                
                # Total winners
                await publish_sensor("lotto645_total_winners", _safe_int(item.get("sumWnNope")), {
                    "friendly_name": "로또 645 총 당첨자",  # Korean
                    "unit_of_measurement": "명",
                    "icon": "mdi:account-group",
                })
                
            except Exception as e:
                logger.warning(f"Failed to fetch lotto results: {e}")
            
            # Number frequency analysis
            try:
                frequency = await analyzer.async_analyze_number_frequency(50)
                top_num = frequency[0] if frequency else None
                if top_num:
                    await publish_sensor("lotto45_top_frequency_number", top_num.number, {
                        "count": top_num.count,
                        "percentage": top_num.percentage,
                        "unit_of_measurement": "회",
                        "friendly_name": "로또 45 최다 출현 번호",  # Korean
                        "icon": "mdi:star",
                    })
            except Exception as e:
                logger.warning(f"Failed to analyze frequency: {e}")
            
            # Hot/Cold numbers
            try:
                hot_cold = await analyzer.async_get_hot_cold_numbers(20)
                await publish_sensor("lotto45_hot_numbers", 
                    ",".join(map(str, hot_cold.hot_numbers)), {
                        "numbers": hot_cold.hot_numbers,
                        "friendly_name": "로또 45 핫 넘버",  # Korean
                        "icon": "mdi:fire",
                    })
                await publish_sensor("lotto45_cold_numbers",
                    ",".join(map(str, hot_cold.cold_numbers)), {
                        "numbers": hot_cold.cold_numbers,
                        "friendly_name": "로또 45 콜드 넘버",  # Korean
                        "icon": "mdi:snowflake",
                    })
            except Exception as e:
                logger.warning(f"Failed to get hot/cold numbers: {e}")
            
            # Purchase statistics
            try:
                stats = await analyzer.async_get_purchase_statistics(365)
                await publish_sensor("lotto45_total_winning", stats.total_winning_amount, {
                    "total_purchase": stats.total_purchase_amount,
                    "total_purchase_count": stats.total_purchase_count,
                    "total_winning_count": stats.total_winning_count,
                    "win_rate": stats.win_rate,
                    "roi": stats.roi,
                    "rank_distribution": stats.rank_distribution,
                    "unit_of_measurement": "KRW",
                    "friendly_name": "로또 45 총 당첨금",  # Korean
                    "icon": "mdi:trophy",
                })
            except Exception as e:
                logger.warning(f"Failed to get purchase stats: {e}")
            
            # Purchase history (last week)
            try:
                history = await lotto_645.async_get_buy_history_this_week()
                
                if history:
                    latest_purchase = history[0]
                    
                    games_info = []
                    for game in latest_purchase.games:
                        games_info.append({
                            "slot": game.slot,
                            "mode": str(game.mode),
                            "numbers": game.numbers
                        })
                    
                    await publish_sensor("lotto45_latest_purchase", latest_purchase.round_no, {
                        "round_no": latest_purchase.round_no,
                        "barcode": latest_purchase.barcode,
                        "result": latest_purchase.result,
                        "games": games_info,
                        "games_count": len(latest_purchase.games),
                        "friendly_name": "최근 구매",  # Korean
                        "icon": "mdi:receipt-text",
                    })
                    
                    # Publish individual game sensors
                    all_games = []
                    for purchase in history:
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
                    
                    logger.info(f"Publishing {len(all_games)} individual game sensors...")
                    
                    latest_round_no = await lotto_645.async_get_latest_round_no()
                    
                    for i, game_info in enumerate(all_games, 1):
                        game = game_info['game']
                        round_no = game_info['round_no']
                        numbers_str = ", ".join(map(str, game.numbers))
                        
                        await publish_sensor(f"lotto45_game_{i}", numbers_str, {
                            "slot": game.slot,
                            "mode": str(game.mode),
                            "numbers": game.numbers,
                            "round_no": round_no,
                            "result": game_info['result'],
                            "friendly_name": f"게임 {i}",  # Korean
                            "icon": f"mdi:numeric-{i}-box-multiple",
                        })
                        logger.info(f"Game {i} ({game.slot}): {numbers_str} - {game.mode} (Round {round_no})")
                        
                        # Check winning result
                        try:
                            result_text = "미추첨"
                            result_icon = "mdi:clock-outline"
                            result_color = "grey"
                            matching_count = 0
                            bonus_match = False
                            winning_numbers = []
                            bonus_number = 0
                            rank = 0
                            
                            if round_no <= latest_round_no:
                                winning_data = await lotto_645.async_get_round_info(round_no)
                                winning_numbers = winning_data.numbers
                                bonus_number = winning_data.bonus_num
                                
                                check_result = await analyzer.async_check_winning(game.numbers, round_no)
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
                            
                            await publish_sensor(f"lotto45_game_{i}_result", result_text, {
                                "round_no": round_no,
                                "my_numbers": game.numbers,
                                "winning_numbers": winning_numbers,
                                "bonus_number": bonus_number,
                                "matching_count": matching_count,
                                "bonus_match": bonus_match,
                                "rank": rank,
                                "result": result_text,
                                "color": result_color,
                                "friendly_name": f"게임 {i} 당첨 결과",  # Korean
                                "icon": result_icon,
                            })
                            logger.info(f"Game {i} result: {result_text} (일치: {matching_count}개, Rank: {rank})")
                            
                        except Exception as e:
                            logger.warning(f"Failed to check winning for game {i}: {e}")
                            await publish_sensor(f"lotto45_game_{i}_result", "확인 불가", {
                                "round_no": round_no,
                                "my_numbers": game.numbers,
                                "error": str(e),
                                "friendly_name": f"게임 {i} 당첨 결과",  # Korean
                                "icon": "mdi:alert-circle-outline",
                            })
                    
                    pending_count = sum(1 for h in history if "not" in str(h.result).lower() or "drawn" not in str(h.result).lower())
                    total_games = sum(len(h.games) for h in history)
                    
                    await publish_sensor("lotto45_purchase_history_count", len(history), {
                        "total_games": total_games,
                        "pending_count": pending_count,
                        "friendly_name": "구매 기록 수",  # Korean
                        "icon": "mdi:counter",
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to get purchase history: {e}")
        
        # Update time
        now = datetime.now(timezone.utc).isoformat()
        await publish_sensor("lotto45_last_update", now, {
            "friendly_name": "마지막 업데이트",  # Korean
            "icon": "mdi:clock-check-outline",
        })
        
        logger.info("Sensors updated successfully")
        
    except Exception as e:
        logger.error(f"Failed to update sensors: {e}", exc_info=True)


async def publish_sensor(entity_id: str, state, attributes: dict = None):
    """Publish sensor state using MQTT or REST API"""
    is_important = "purchase" in entity_id or "latest" in entity_id
    
    if is_important:
        logger.info(f"[SENSOR] Publishing {entity_id}: {state}")
    
    # Try MQTT first
    if config["use_mqtt"] and mqtt_client and mqtt_client.connected:
        try:
            success = await publish_sensor_mqtt(
                mqtt_client=mqtt_client,
                entity_id=entity_id,
                state=state,
                username=config["username"],
                attributes=attributes
            )
            if success:
                if is_important:
                    logger.info(f"[SENSOR] Published via MQTT: {entity_id}")
                return
            else:
                logger.warning(f"[SENSOR] MQTT publish failed for {entity_id}, falling back to REST API")
        except Exception as e:
            logger.error(f"[SENSOR] Error publishing via MQTT: {e}")
    
    # Fallback to REST API
    import aiohttp
    
    if not config["supervisor_token"]:
        return
    
    addon_entity_id = f"addon_{config['username']}_{entity_id}"
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
                    logger.error(f"[SENSOR] Failed to publish {addon_entity_id}: {resp.status} - {await resp.text()}")
                elif is_important:
                    logger.info(f"[SENSOR] Published via REST API: {addon_entity_id}")
    except Exception as e:
        logger.error(f"[SENSOR] Error publishing {addon_entity_id}: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Main page"""
    status_icon = "✅" if client and client.logged_in else "❌"
    status_text = "Connected" if client and client.logged_in else "Disconnected"
    
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Lotto 45 v0.6.8</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .status {{ font-size: 18px; margin: 20px 0; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .version {{ color: #666; font-size: 14px; }}
                a {{ color: #0066cc; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>DH Lottery Lotto 45 <span class="version">v0.6.8</span></h1>
            <div class="status">
                Status: {status_icon} {status_text}
            </div>
            <div class="info">
                <p><strong>Username:</strong> {config['username']}</p>
                <p><strong>Update Interval:</strong> {config['update_interval']}s</p>
                <p><strong>Lotto 645 Enabled:</strong> {config['enable_lotto645']}</p>
                <p><strong>Version:</strong> 0.6.8 (Optimized)</p>
            </div>
            <h2>Features</h2>
            <ul>
                <li>✅ Optimized encoding</li>
                <li>✅ English sensor names with Korean friendly_name</li>
                <li>✅ MQTT Discovery integration</li>
                <li>✅ Auto-purchase buttons</li>
            </ul>
            <h2>Links</h2>
            <ul>
                <li><a href="health">Health Check</a></li>
                <li><a href="stats">Statistics</a></li>
                <li><a href="docs">API Documentation</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok" if client and client.logged_in else "error",
        "logged_in": client.logged_in if client else False,
        "username": config["username"],
        "lotto645_enabled": config["enable_lotto645"],
        "mqtt_enabled": config["use_mqtt"],
        "version": "0.6.8",
    }


@app.post("/random")
async def generate_random(count: int = 6, games: int = 1):
    """Generate random numbers"""
    if not analyzer:
        raise HTTPException(status_code=400, detail="Lotto 645 not enabled")
    
    if count < 1 or count > 45:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 45")
    
    if games < 1 or games > 5:
        raise HTTPException(status_code=400, detail="Games must be between 1 and 5")
    
    results = []
    for _ in range(games):
        numbers = analyzer.generate_random_numbers(count)
        results.append(numbers)
    
    return {"numbers": results}


@app.post("/check")
async def check_winning(numbers: list[int], round_no: Optional[int] = None):
    """Check winning"""
    if not analyzer:
        raise HTTPException(status_code=400, detail="Lotto 645 not enabled")
    
    if len(numbers) != 6:
        raise HTTPException(status_code=400, detail="Must provide exactly 6 numbers")
    
    if any(n < 1 or n > 45 for n in numbers):
        raise HTTPException(status_code=400, detail="Numbers must be between 1 and 45")
    
    try:
        result = await analyzer.async_check_winning(numbers, round_no)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get statistics"""
    if not analyzer:
        raise HTTPException(status_code=400, detail="Lotto 645 not enabled")
    
    try:
        frequency = await analyzer.async_analyze_number_frequency(50)
        hot_cold = await analyzer.async_get_hot_cold_numbers(20)
        purchase_stats = await analyzer.async_get_purchase_statistics(365)
        
        return {
            "frequency": [
                {"number": f.number, "count": f.count, "percentage": f.percentage} 
                for f in frequency[:10]
            ],
            "hot_numbers": hot_cold.hot_numbers,
            "cold_numbers": hot_cold.cold_numbers,
            "most_frequent": [
                {"number": f.number, "count": f.count, "percentage": f.percentage}
                for f in hot_cold.most_frequent
            ],
            "purchase_stats": {
                "total_purchase_count": purchase_stats.total_purchase_count,
                "total_purchase_amount": purchase_stats.total_purchase_amount,
                "total_winning_count": purchase_stats.total_winning_count,
                "total_winning_amount": purchase_stats.total_winning_amount,
                "win_rate": purchase_stats.win_rate,
                "roi": purchase_stats.roi,
                "rank_distribution": purchase_stats.rank_distribution,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/balance")
async def get_balance():
    """Get balance"""
    if not client:
        raise HTTPException(status_code=400, detail="Client not initialized")
    
    try:
        balance = await client.async_get_balance()
        return {
            "deposit": balance.deposit,
            "purchase_available": balance.purchase_available,
            "reservation_purchase": balance.reservation_purchase,
            "withdrawal_request": balance.withdrawal_request,
            "purchase_impossible": balance.purchase_impossible,
            "this_month_accumulated_purchase": balance.this_month_accumulated_purchase,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/buy")
async def buy_lotto(games: list[dict]):
    """Buy Lotto 6/45"""
    if not lotto_645:
        raise HTTPException(status_code=400, detail="Lotto 645 not enabled")
    
    if not games or len(games) == 0:
        raise HTTPException(status_code=400, detail="At least 1 game required")
    
    if len(games) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 games allowed")
    
    try:
        from dh_lotto_645 import DhLotto645, DhLotto645SelMode
        
        mode_map = {
            "Auto": DhLotto645SelMode.AUTO,
            "Manual": DhLotto645SelMode.MANUAL,
            "Semi-Auto": DhLotto645SelMode.SEMI_AUTO,
        }
        
        slots = []
        for i, game in enumerate(games):
            mode_str = game.get("mode", "Auto")
            numbers = game.get("numbers", [])
            
            if mode_str not in mode_map:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Game {i+1}: Invalid mode '{mode_str}'. Must be 'Auto', 'Manual', or 'Semi-Auto'"
                )
            
            mode = mode_map[mode_str]
            
            if mode in [DhLotto645SelMode.MANUAL, DhLotto645SelMode.SEMI_AUTO]:
                if not numbers:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Game {i+1}: Numbers required for mode '{mode_str}'"
                    )
                if len(numbers) > 6:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Game {i+1}: Maximum 6 numbers allowed"
                    )
                if any(n < 1 or n > 45 for n in numbers):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Game {i+1}: Numbers must be between 1 and 45"
                    )
            
            slots.append(DhLotto645.Slot(mode=mode, numbers=numbers))
        
        logger.info(f"Purchasing {len(slots)} games...")
        result = await lotto_645.async_buy(slots)
        
        response = {
            "success": True,
            "round_no": result.round_no,
            "barcode": result.barcode,
            "issue_dt": result.issue_dt,
            "games": [
                {
                    "slot": game.slot,
                    "mode": str(game.mode),
                    "numbers": game.numbers,
                }
                for game in result.games
            ]
        }
        
        logger.info(f"Purchase successful: Round {result.round_no}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Purchase failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/buy/auto")
async def buy_lotto_auto(count: int = 1):
    """Buy Lotto 6/45 Auto"""
    if count < 1 or count > 5:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 5")
    
    games = [{"mode": "Auto"} for _ in range(count)]
    return await buy_lotto(games)


@app.get("/buy/history")
async def get_buy_history():
    """Get purchase history from last week"""
    if not lotto_645:
        raise HTTPException(status_code=400, detail="Lotto 645 not enabled")
    
    try:
        history = await lotto_645.async_get_buy_history_this_week()
        
        results = []
        for item in history:
            results.append({
                "round_no": item.round_no,
                "barcode": item.barcode,
                "result": item.result,
                "games": [
                    {
                        "slot": game.slot,
                        "mode": str(game.mode),
                        "numbers": game.numbers,
                    }
                    for game in item.games
                ]
            })
        
        return {
            "count": len(results),
            "items": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=60099, log_level="info")
