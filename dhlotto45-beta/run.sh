#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Lotto 45 Add-on v0.6.8..."

# UTF-8 encoding settings
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=utf-8

# Configuration variables
export USERNAME=$(bashio::config 'username')
export PASSWORD=$(bashio::config 'password')
export ENABLE_LOTTO645=$(bashio::config 'enable_lotto645')
export UPDATE_INTERVAL=$(bashio::config 'update_interval')
export USE_MQTT=$(bashio::config 'use_mqtt')
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

# MQTT configuration (optional)
export MQTT_URL=$(bashio::config 'mqtt_url' 'mqtt://homeassistant.local:1883')
export MQTT_USERNAME=$(bashio::config 'mqtt_username' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')

# Home Assistant URL
export HA_URL="http://supervisor/core"

bashio::log.info "Configuration loaded"
bashio::log.info "Username: ${USERNAME}"
bashio::log.info "Update interval: ${UPDATE_INTERVAL}s"
bashio::log.info "Use MQTT: ${USE_MQTT}"

if bashio::config.true 'use_mqtt'; then
    bashio::log.info "MQTT enabled - URL: ${MQTT_URL}"
fi

# Run Python application
cd /app
python3 -u /app/main.py
