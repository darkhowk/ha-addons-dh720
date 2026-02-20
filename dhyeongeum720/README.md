# 연금복권 720+ (DH Lottery Pension 720+)

Home Assistant Add-on for DH Lottery Pension 720+

## Features

- **Multi-account support**: Manage multiple DH Lottery accounts
- **MQTT Discovery**: Auto-discovery for Home Assistant sensors and buttons
- **REST API**: Full API for integration with other services
- **Web UI**: Built-in web interface
- **Auto-purchase**: Buy lottery tickets with buttons (1 or 5 tickets)
- **Balance monitoring**: Track account balance
- **Purchase history**: View purchase history

## Installation

1. Add this repository to Home Assistant Supervisor
2. Install the "연금복권 720+" add-on
3. Configure with your DH Lottery credentials
4. Start the add-on

## Configuration

```json
{
  "accounts": [
    {
      "username": "your_username",
      "password": "your_password",
      "enabled": true
    }
  ],
  "enable_pension720": true,
  "update_interval": 3600,
  "use_mqtt": true,
  "mqtt_url": "mqtt://homeassistant.local:1883",
  "mqtt_username": "",
  "mqtt_password": ""
}
```

## REST API

The add-on exposes a REST API on port 60100:

- `GET /` - Web UI
- `GET /health` - Health check
- `GET /accounts` - List accounts
- `POST /api/purchase/{username}/1` - Buy 1 ticket
- `POST /api/purchase/{username}/5` - Buy 5 tickets
- `GET /api/balance/{username}` - Get account balance
- `GET /api/history/{username}` - Get purchase history

## MQTT Discovery

Sensors and buttons are automatically discovered via MQTT:

- `sensor.{username}_pension720_balance` - Account balance
- `sensor.{username}_pension720_login_error` - Login errors
- `button.{username}_pension720_buy_1` - Buy 1 ticket button
- `button.{username}_pension720_buy_5` - Buy 5 tickets button

## Network Flow

The add-on implements the DH Lottery Pension 720+ purchase flow:

1. `makeOrderNo.do` - Generate order number (payload: `q=<blob>`, response: `{"q": "..."}`)
2. `connPro.do` - Connect to purchase service (payload: `q=<blob>`, response: `{"q": "..."}`)
3. **[TODO]** Final purchase confirmation endpoint

## License

MIT License
