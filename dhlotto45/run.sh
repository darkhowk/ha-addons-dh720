#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Lotto 45 Add-on v2.0.0 (Multi-Account)..."

# Load accounts from configuration
ACCOUNTS=$(bashio::config 'accounts')
export ACCOUNTS="${ACCOUNTS}"

bashio::log.info "Loaded accounts configuration"

# Count accounts
ACCOUNT_COUNT=$(echo "${ACCOUNTS}" | jq '. | length')
bashio::log.info "Total accounts: ${ACCOUNT_COUNT}"

# Log each account (without password)
for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
    USERNAME=$(echo "${ACCOUNTS}" | jq -r ".[$i].username")
    ENABLED=$(echo "${ACCOUNTS}" | jq -r ".[$i].enabled")
    bashio::log.info "  Account $((i+1)): ${USERNAME} (enabled: ${ENABLED})"
done

# Other configuration
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

bashio::log.info "Update interval: ${UPDATE_INTERVAL}s"
bashio::log.info "Use MQTT: ${USE_MQTT}"

if bashio::config.true 'use_mqtt'; then
    bashio::log.info "MQTT enabled - URL: ${MQTT_URL}"
fi

# Run Python application
cd /app
python3 -u /app/main.py
