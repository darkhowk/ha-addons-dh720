#!/usr/bin/env python3
"""
MQTT 센서 삭제 스크립트
베타/정식 버전의 센서를 모두 삭제하고 재생성합니다.
"""

import paho.mqtt.client as mqtt
import time

# MQTT 브로커 설정
MQTT_BROKER = "homeassistant.local"
MQTT_PORT = 1883
MQTT_USERNAME = ""  # 필요시 입력
MQTT_PASSWORD = ""  # 필요시 입력

# 사용자 ID
USERNAME = "ng410808"  # 여기에 동행복권 아이디 입력

# 삭제할 센서 ID 목록
SENSOR_IDS = [
    "lotto45_balance",
    "lotto645_round",
    "lotto645_number1", "lotto645_number2", "lotto645_number3",
    "lotto645_number4", "lotto645_number5", "lotto645_number6",
    "lotto645_bonus",
    "lotto645_winning_numbers",
    "lotto645_draw_date",
    "lotto645_total_sales",
    "lotto645_first_prize", "lotto645_first_winners",
    "lotto645_second_prize", "lotto645_second_winners",
    "lotto645_third_prize", "lotto645_third_winners",
    "lotto645_fourth_prize", "lotto645_fourth_winners",
    "lotto645_fifth_prize", "lotto645_fifth_winners",
    "lotto645_total_winners",
    "lotto45_top_frequency_number",
    "lotto45_hot_numbers",
    "lotto45_cold_numbers",
    "lotto45_total_winning",
    "lotto45_latest_purchase",
    "lotto45_purchase_history_count",
    "lotto45_game_1", "lotto45_game_2", "lotto45_game_3",
    "lotto45_game_4", "lotto45_game_5",
    "lotto45_game_1_result", "lotto45_game_2_result", "lotto45_game_3_result",
    "lotto45_game_4_result", "lotto45_game_5_result",
    "lotto45_last_update",
    "lotto45_purchase_error",
]

BUTTON_IDS = ["buy_auto_1", "buy_auto_5", "buy_manual"]
INPUT_IDS = ["manual_numbers"]

# 정식 버전과 베타 버전 prefix
PREFIXES = ["dhlotto", "dhlotto_beta"]


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ MQTT 브로커 연결 성공")
    else:
        print(f"✗ MQTT 브로커 연결 실패: {rc}")


def delete_sensors():
    """센서 삭제"""
    print("=" * 60)
    print("MQTT 센서 삭제 시작")
    print("=" * 60)
    
    client = mqtt.Client(client_id="dhlotto_cleanup")
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    client.on_connect = on_connect
    
    print(f"MQTT 브로커 연결 중: {MQTT_BROKER}:{MQTT_PORT}")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    
    # 연결 대기
    time.sleep(2)
    
    deleted_count = 0
    
    for prefix in PREFIXES:
        print(f"\n[{prefix}] 센서 삭제 중...")
        
        # 센서 삭제
        for sensor_id in SENSOR_IDS:
            topic = f"homeassistant/sensor/{prefix}_{USERNAME}_{sensor_id}/config"
            client.publish(topic, "", qos=1, retain=True)
            deleted_count += 1
            print(f"  ✓ 삭제: {topic}")
        
        # 버튼 삭제
        for button_id in BUTTON_IDS:
            topic = f"homeassistant/button/{prefix}_{USERNAME}_{button_id}/config"
            client.publish(topic, "", qos=1, retain=True)
            deleted_count += 1
            print(f"  ✓ 삭제: {topic}")
        
        # Input Text 삭제
        for input_id in INPUT_IDS:
            topic = f"homeassistant/text/{prefix}_{USERNAME}_{input_id}/config"
            client.publish(topic, "", qos=1, retain=True)
            deleted_count += 1
            print(f"  ✓ 삭제: {topic}")
    
    # 메시지 전송 대기
    time.sleep(2)
    
    client.loop_stop()
    client.disconnect()
    
    print("\n" + "=" * 60)
    print(f"✓ 총 {deleted_count}개 센서 삭제 완료")
    print("=" * 60)
    print("\n다음 단계:")
    print("1. Home Assistant에서 기존 센서가 사라졌는지 확인")
    print("2. 애드온 재시작")
    print("3. 새로운 센서가 한글로 정상 생성되었는지 확인")


if __name__ == "__main__":
    delete_sensors()
