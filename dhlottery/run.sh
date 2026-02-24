#!/usr/bin/with-contenv bashio

bashio::log.info "Starting DH Lottery Add-on v1.0.0 (로또 6/45 + 연금복권 720+)..."

# Build accounts JSON array properly
ACCOUNT_COUNT=$(bashio::config 'accounts | length')
bashio::log.info "Total accounts: ${ACCOUNT_COUNT}"

# Build JSON array manually
ACCOUNTS_JSON="["
for i in $(seq 0 $((ACCOUNT_COUNT - 1))); do
    USERNAME=$(bashio::config "accounts[${i}].username")
    PASSWORD=$(bashio::config "accounts[${i}].password")
    ENABLED=$(bashio::config "accounts[${i}].enabled")

    # Default enabled to true if not set
    if [ -z "${ENABLED}" ] || [ "${ENABLED}" == "null" ]; then
        ENABLED="true"
    fi

    bashio::log.info "  Account $((i+1)): ${USERNAME} (enabled: ${ENABLED})"

    if [ $i -gt 0 ]; then
        ACCOUNTS_JSON="${ACCOUNTS_JSON},"
    fi
    ACCOUNTS_JSON="${ACCOUNTS_JSON}{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\",\"enabled\":${ENABLED}}"
done
ACCOUNTS_JSON="${ACCOUNTS_JSON}]"

export ACCOUNTS="${ACCOUNTS_JSON}"
bashio::log.info "Accounts JSON built successfully"

# Feature flags
export ENABLE_LOTTO645=$(bashio::config 'enable_lotto645')
export ENABLE_PENSION720=$(bashio::config 'enable_pension720')
export UPDATE_INTERVAL=$(bashio::config 'update_interval')
export USE_MQTT=$(bashio::config 'use_mqtt')
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

# MQTT configuration (optional)
export MQTT_URL=$(bashio::config 'mqtt_url' 'mqtt://homeassistant.local:1883')
export MQTT_USERNAME=$(bashio::config 'mqtt_username' '')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password' '')

# Home Assistant URL
export HA_URL="http://supervisor/core"

bashio::log.info "Configuration:"
bashio::log.info "  Update interval: ${UPDATE_INTERVAL}s"
bashio::log.info "  Lotto 645 enabled: ${ENABLE_LOTTO645}"
bashio::log.info "  Pension 720+ enabled: ${ENABLE_PENSION720}"
bashio::log.info "  Use MQTT: ${USE_MQTT}"

if bashio::config.true 'use_mqtt'; then
    bashio::log.info "  MQTT URL: ${MQTT_URL}"
fi

bashio::log.info "Starting application..."
cd /app
python3 -u /app/main.py
