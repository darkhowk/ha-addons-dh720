# 연금복권 720+ (DH Lottery Pension 720+) - Documentation

## Overview

This add-on provides integration between Home Assistant and the DH Lottery Pension 720+ service. It allows you to:

- Monitor your account balance
- Purchase lottery tickets (1 or 5 at a time)
- View purchase history
- Receive login error notifications
- Use MQTT discovery for sensors and buttons

## Architecture

### Core Components

1. **dh_pension_720.py**: Main logic for Pension 720+ operations
2. **dh_lottery_client.py**: HTTP client for DH Lottery API
3. **main.py**: FastAPI application and REST endpoints
4. **mqtt_discovery.py**: MQTT Auto Discovery support

### Network Flow

The DH Lottery Pension 720+ purchase process involves multiple API calls:

```
1. makeOrderNo.do
   POST https://ol.dhlottery.co.kr/servlet/pension720/makeOrderNo.do
   Payload: { q: "<encrypted_blob>" }
   Response: { q: "<encrypted_blob>" }

2. connPro.do
   POST https://ol.dhlottery.co.kr/servlet/pension720/connPro.do
   Payload: { q: "<encrypted_blob>" }
   Response: { q: "<encrypted_blob>" }

3. [TODO] Final Purchase Confirmation
   POST https://ol.dhlottery.co.kr/servlet/pension720/<endpoint>
   Payload: { ... }
   Response: { ... }
```

## REST API

### Endpoints

#### Health Check
```
GET /health
```
Returns:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "ingress": true,
  "accounts": {
    "username": {
      "logged_in": true,
      "enabled": true,
      "status": "✅ Active"
    }
  },
  "total_accounts": 1,
  "logged_in_accounts": 1,
  "failed_accounts": 0
}
```

#### List Accounts
```
GET /accounts
```
Returns:
```json
{
  "accounts": [
    {
      "username": "username",
      "enabled": true,
      "logged_in": true
    }
  ]
}
```

#### Buy Tickets
```
POST /api/purchase/{username}/{count}
```
Where `count` is `1` or `5`.

Returns:
```json
{
  "success": true,
  "round_no": 1234,
  "issue_dt": "2026/02/13 금 09:00:00",
  "barcode": "12345 67890 12345 67890 12345 67890",
  "games": [...]
}
```

#### Get Balance
```
GET /api/balance/{username}
```
Returns:
```json
{
  "balance": 10000,
  "purchase_available": 10000
}
```

#### Get Purchase History
```
GET /api/history/{username}
```
Returns:
```json
{
  "history": [...]
}
```

## MQTT Discovery

### Sensors

| Entity ID | Description |
|-----------|-------------|
| `sensor.{username}_pension720_balance` | Account balance (원) |
| `sensor.{username}_pension720_login_error` | Login error message (if any) |

### Buttons

| Entity ID | Action |
|-----------|--------|
| `button.{username}_pension720_buy_1` | Buy 1 ticket |
| `button.{username}_pension720_buy_5` | Buy 5 tickets |

## Configuration

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `accounts` | array | - | List of accounts |
| `enable_pension720` | bool | `true` | Enable Pension 720+ integration |
| `update_interval` | int | `3600` | Sensor update interval (seconds) |
| `use_mqtt` | bool | `true` | Use MQTT discovery |
| `mqtt_url` | string | `mqtt://homeassistant.local:1883` | MQTT broker URL |
| `mqtt_username` | string | - | MQTT username |
| `mqtt_password` | string | - | MQTT password |

### Account Schema

```json
{
  "username": "string",
  "password": "password",
  "enabled": "bool"
}
```

## Purchase Flow Details

### Step 1: Generate Order Number (makeOrderNo.do)

This endpoint generates a unique order number for the purchase.

**Request:**
```http
POST https://ol.dhlottery.co.kr/servlet/pension720/makeOrderNo.do
Content-Type: application/x-www-form-urlencoded

q=<encrypted_blob>
```

**Response:**
```json
{
  "q": "<encrypted_response_blob>"
}
```

### Step 2: Connect to Purchase Service (connPro.do)

This endpoint establishes the purchase session.

**Request:**
```http
POST https://ol.dhlottery.co.kr/servlet/pension720/connPro.do
Content-Type: application/x-www-form-urlencoded

q=<encrypted_blob>
```

**Response:**
```json
{
  "q": "<encrypted_response_blob>"
}
```

### Step 3: Final Purchase Confirmation [TODO - NEED NETWORK TRAFFIC ANALYSIS]

**⚠️ CRITICAL:** This endpoint needs to be discovered through network traffic analysis.
After clicking the "Purchase" button in the DH Lottery web UI, the Network tab (DevTools)
will show the final API call.

**Expected Endpoint:**
```
POST https://ol.dhlottery.co.kr/servlet/pension720/confirmPurchase.do
```
*Note: The actual endpoint name may differ (e.g., `finalize.do`, `buyComplete.do`, `endPro.do`)*

**Expected Request:**
```http
POST https://ol.dhlottery.co.kr/servlet/pension720/confirmPurchase.do
Content-Type: application/x-www-form-urlencoded

q=<encrypted_blob>
```

**Expected Response (Success):**
```json
{
  "returnCode": "10000",
  "returnMsg": "구매 완료",
  "data": {
    "roundNo": 1234,
    "issueDt": "2026/02/13 금 09:00:00",
    "barcode": "12345 67890 12345 67890 12345 67890",
    "ticketCount": 1,
    "amount": 1000
  }
}
```

**Expected Response (Failure - Insufficient Balance):**
```json
{
  "returnCode": "20001",
  "returnMsg": "잔액 부족",
  "data": null
}
```

**Expected Response (Failure - Other):**
```json
{
  "returnCode": "20002",
  "returnMsg": "구매 불가 시간",
  "data": null
}
```

**What to Capture:**
1. **Endpoint URL** - The exact endpoint path (e.g., `/servlet/pension720/confirmPurchase.do`)
2. **Payload Keys** - All keys in the request payload (e.g., `q`, `amount`, `ticketCount`)
3. **Success Code** - The `returnCode` value for successful purchases (expected: "10000")
4. **Failure Codes** - Common failure codes and their messages:
   - Balance insufficient: (e.g., "20001" - "잔액 부족")
   - Outside purchase hours: (e.g., "20002" - "구매 불가 시간")
   - Weekly limit exceeded: (e.g., "20003" - "주간 구매 한도 초과")
5. **Response Data Structure** - All fields in the `data` object for successful purchases

**How to Analyze:**
1. Open DH Lottery website (https://ol.dhlottery.co.kr) in Chrome/Firefox
2. Open DevTools (F12) → Network tab
3. Login and navigate to Pension 720+ purchase page
4. Click "Purchase" button for 1 ticket
5. Find the final API call after `connPro.do` in the Network tab
6. Click the request to view:
   - Request URL
   - Request Payload (look for `q` parameter)
   - Response payload (JSON format)
7. Copy/paste the relevant info into this document

## Development Status

- [x] Basic scaffolding
- [x] Config and schema
- [x] MQTT discovery structure
- [x] REST API endpoints (planned)
- [ ] DH Lottery client for Pension 720+
- [ ] Purchase flow implementation
- [ ] Final purchase endpoint (connPro.do 다음 API)
- [ ] Sensors implementation
- [ ] Buttons implementation
- [ ] Testing

## Troubleshooting

### Login Failed

- Check username and password
- Ensure DH Lottery account is active
- Check network connectivity

### Purchase Failed

- Check account balance (minimum 1000원 per ticket)
- Verify purchase time (available 06:00-24:00)
- Check weekly purchase limit
- Review error logs

### MQTT Not Working

- Verify MQTT broker is running
- Check MQTT credentials
- Ensure `use_mqtt` is set to `true`
- Check firewall settings
