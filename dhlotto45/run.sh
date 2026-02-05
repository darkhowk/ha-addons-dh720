#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Lotto 45 Add-on..."

# 설정 읽기
export USERNAME=$(bashio::config 'username')
export PASSWORD=$(bashio::config 'password')
export ENABLE_LOTTO645=$(bashio::config 'enable_lotto645')
export UPDATE_INTERVAL=$(bashio::config 'update_interval')
export USE_MQTT=$(bashio::config 'use_mqtt')
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

# Home Assistant 정보
export HA_URL="http://supervisor/core"

bashio::log.info "Configuration loaded"
bashio::log.info "Username: ${USERNAME}"
bashio::log.info "Update interval: ${UPDATE_INTERVAL}s"

# Python 애플리케이션 실행
cd /app
python3 -u /app/main.py
