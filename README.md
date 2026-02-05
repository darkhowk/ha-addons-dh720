# DH Lottery Home Assistant Add-ons

[![License](https://img.shields.io/github/license/redchupa/ha-addons-dhlottery)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/redchupa/ha-addons-dhlottery?style=social)](https://github.com/redchupa/ha-addons-dhlottery/stargazers)

Home Assistant에서 동행복권 로또 6/45를 자동으로 구매하고 분석할 수 있는 애드온입니다.

## 주요 기능

-  **자동 구매**: 버튼 클릭만으로 로또 자동 구매
-  **실시간 분석**: 당첨번호, 상금, 통계 정보 자동 업데이트
-  **자동화 연동**: Home Assistant 자동화와 완벽하게 통합
-  **통계 분석**: Hot/Cold 번호, 출현 빈도 분석
-  **예치금 관리**: 잔액 및 구매 가능 금액 모니터링
-  **MQTT Discovery**: Home Assistant와 자동 통합
-  **REST API**: 외부 앱에서도 사용 가능
-  **모바일 알림**: 구매 완료, 당첨번호 발표 등 자동 알림

---

## 목차

- [설치 및 설정](#설치-및-설정)
- [생성되는 센서](#생성되는-센서)
- [버튼 엔티티](#버튼-엔티티)
- [자동화 예시](#자동화-예시)
- [REST API](#rest-api)
- [문제 해결](#문제-해결)
- [후원](#후원)
- [라이선스](#라이선스)

---

## 설치 및 설정

### 저장소 추가

1. Home Assistant → **Settings** → **Add-ons** → **Add-on Store**
2. 우측 상단 메뉴(⋮) → **Repositories**
3. 다음 URL 추가:
   ```
   https://github.com/redchupa/ha-addons-dhlottery
   ```

### 애드온 설치

1. Add-on Store에서 **DH Lotto 45** 선택
2. **Install** 클릭
3. Configuration 탭에서 설정:

```yaml
username: "동행복권_아이디"
password: "동행복권_비밀번호"
enable_lotto645: true
update_interval: 3600  # 센서 업데이트 주기 (초), 기본값: 3600 (1시간)
use_mqtt: true  # MQTT Discovery 사용 (권장)
mqtt_url: "mqtt://homeassistant.local:1883"  # MQTT 브로커 주소
mqtt_username: ""  # MQTT 사용자명 (선택사항)
mqtt_password: ""  # MQTT 비밀번호 (선택사항)
```

4. **Start** 클릭
5. **Log** 탭에서 "Login successful" 확인

---

## 생성되는 센서

애드온을 시작하면 다음 센서들이 자동으로 생성됩니다.

<details>
<summary><b>📊 계정 정보 센서</b></summary>

### 동행복권 예치금
- **센서 ID**: `sensor.dhlotto_{username}_lotto45_balance`
- **단위**: KRW
- **추가 속성**:
  - `purchase_available`: 구매 가능 금액
  - `reservation_purchase`: 예약 구매 금액
  - `withdrawal_request`: 출금 신청 중 금액
  - `this_month_accumulated`: 이번 달 누적 구매 금액

</details>

<details>
<summary><b>🎱 로또 당첨 결과 센서</b></summary>

### 기본 정보
- `sensor.dhlotto_{username}_lotto645_round` - 최신 회차 번호
- `sensor.dhlotto_{username}_lotto645_draw_date` - 추첨일 (YYYY-MM-DD)
- `sensor.dhlotto_{username}_lotto645_winning_numbers` - 전체 당첨번호

### 당첨번호 (개별)
- `sensor.dhlotto_{username}_lotto645_number1` ~ `number6` - 당첨번호 1~6
- `sensor.dhlotto_{username}_lotto645_bonus` - 보너스 번호

</details>

<details>
<summary><b>💰 상금 및 당첨자 정보 센서</b></summary>

### 총 판매액
- `sensor.dhlotto_{username}_lotto645_total_sales` (KRW)

### 등수별 정보
각 등수마다 **상금**과 **당첨자** 센서가 생성됩니다:

**1등**
- `sensor.dhlotto_{username}_lotto645_first_prize` - 1등 상금 (1인당, KRW)
- `sensor.dhlotto_{username}_lotto645_first_winners` - 1등 당첨자 수 (명)

**2등**
- `sensor.dhlotto_{username}_lotto645_second_prize` - 2등 상금 (KRW)
- `sensor.dhlotto_{username}_lotto645_second_winners` - 2등 당첨자 (명)

**3등**
- `sensor.dhlotto_{username}_lotto645_third_prize` - 3등 상금 (KRW)
- `sensor.dhlotto_{username}_lotto645_third_winners` - 3등 당첨자 (명)

**4등**
- `sensor.dhlotto_{username}_lotto645_fourth_prize` - 4등 상금 (KRW)
- `sensor.dhlotto_{username}_lotto645_fourth_winners` - 4등 당첨자 (명)

**5등**
- `sensor.dhlotto_{username}_lotto645_fifth_prize` - 5등 상금 (KRW)
- `sensor.dhlotto_{username}_lotto645_fifth_winners` - 5등 당첨자 (명)

**전체**
- `sensor.dhlotto_{username}_lotto645_total_winners` - 총 당첨자 수 (1~5등, 명)

</details>

<details>
<summary><b>📈 번호 통계 분석 센서</b></summary>

### 통계 센서
- `sensor.dhlotto_{username}_lotto45_top_frequency_number` - 최다 출현 번호 (최근 50회차)
- `sensor.dhlotto_{username}_lotto45_hot_numbers` - 핫 넘버 (최근 20회차 상위 10개)
- `sensor.dhlotto_{username}_lotto45_cold_numbers` - 콜드 넘버 (최근 20회차 하위 10개)
- `sensor.dhlotto_{username}_lotto45_total_winning` - 총 당첨금 (최근 1년, KRW)

### total_winning 추가 속성
- `total_purchase`: 총 구매 금액
- `total_purchase_count`: 총 구매 횟수
- `total_winning_count`: 총 당첨 횟수
- `win_rate`: 당첨률 (%)
- `roi`: 수익률 (%)
- `rank_distribution`: 등수별 당첨 횟수

</details>

<details>
<summary><b>🎫 구매 내역 센서</b></summary>

### 구매 정보
- `sensor.dhlotto_{username}_lotto45_latest_purchase` - 가장 최근 구매 정보
- `sensor.dhlotto_{username}_lotto45_purchase_history_count` - 구매 기록 수 (최근 1주일)

### 게임별 센서
- `sensor.dhlotto_{username}_lotto45_game_1` ~ `game_5` - 구매한 게임 1~5 번호

### latest_purchase 추가 속성
- `round_no`: 구매 회차
- `barcode`: 바코드 번호
- `result`: 당첨 결과
- `games`: 구매한 게임 목록
- `games_count`: 구매한 게임 수

### game 추가 속성
- `slot`: 슬롯 번호 (A, B, C, D, E)
- `mode`: 구매 모드 (자동, 수동, 반자동)
- `numbers`: 번호 리스트
- `round_no`: 구매 회차
- `result`: 당첨 결과

</details>

<details>
<summary><b>⚙️ 시스템 센서</b></summary>

- `sensor.dhlotto_{username}_lotto45_last_update` - 마지막 업데이트 시간

</details>

---

## 버튼 엔티티

MQTT Discovery를 활성화하면 자동 구매 버튼이 생성됩니다.

### 자동 구매 버튼
- `button.dhlotto_{username}_buy_auto_1` - 1게임 자동 구매
- `button.dhlotto_{username}_buy_auto_5` - 5게임 자동 구매 (주간 최대)

### 사용 방법
- 버튼을 누르면 자동으로 로또를 구매합니다
- 구매 제한 (주간 5게임)은 자동으로 체크됩니다
- **구매 가능 시간**:
  - 평일: 06:00-24:00
  - 토요일: 06:00-20:00
  - 일요일: 06:00-24:00
- 구매 후 센서가 자동으로 업데이트됩니다

---

## 자동화 예시

### 1. 예치금 부족 알림

예치금이 5,000원 미만일 때 알림을 받습니다.

```yaml
alias: "로또 예치금 부족 알림"
description: "예치금이 5,000원 미만일 때 알림"
trigger:
  - platform: numeric_state
    entity_id: sensor.dhlotto_ng410808_lotto45_balance
    below: 5000
action:
  - service: notify.mobile_app
    data:
      title: "로또 예치금 부족"
      message: "현재 예치금: {{ states('sensor.dhlotto_ng410808_lotto45_balance') }}원"
mode: single
```

### 2. 매주 자동 구매

매주 토요일 저녁 7시에 자동으로 5게임을 구매합니다.

```yaml
alias: "로또 매주 자동 구매"
description: "매주 토요일 저녁 7시에 5게임 자동 구매"
trigger:
  - platform: time
    at: "19:00:00"
condition:
  - condition: time
    weekday:
      - sat
action:
  - service: button.press
    target:
      entity_id: button.dhlotto_ng410808_buy_auto_5
  - service: notify.mobile_app
    data:
      title: "로또 자동 구매 완료"
      message: "5게임 구매가 완료되었습니다."
mode: single
```

### 3. 당첨번호 발표 알림

매주 토요일 밤 8시 30분에 당첨번호를 알림으로 받습니다.

```yaml
alias: "로또 당첨번호 알림"
description: "매주 토요일 밤 8시 30분에 당첨번호 발표"
trigger:
  - platform: time
    at: "20:30:00"
condition:
  - condition: time
    weekday:
      - sat
action:
  - delay:
      minutes: 5
  - service: homeassistant.update_entity
    target:
      entity_id: sensor.dhlotto_ng410808_lotto645_winning_numbers
  - delay:
      seconds: 10
  - service: notify.mobile_app
    data:
      title: "로또 당첨번호 발표"
      message: >
        {{ states('sensor.dhlotto_ng410808_lotto645_winning_numbers') }}
        
        1등 상금: {{ states('sensor.dhlotto_ng410808_lotto645_first_prize') | int | round(0) }}원
        1등 당첨자: {{ states('sensor.dhlotto_ng410808_lotto645_first_winners') }}명
mode: single
```

### 4. 고액 당첨 알림

1등 상금이 10억원 이상일 때 알림을 받습니다.

```yaml
alias: "로또 고액 당첨 알림"
description: "1등 상금이 10억원 이상일 때 알림"
trigger:
  - platform: numeric_state
    entity_id: sensor.dhlotto_ng410808_lotto645_first_prize
    above: 1000000000
action:
  - service: notify.mobile_app
    data:
      title: "로또 고액 당첨!"
      message: >
        이번 주 1등 상금: {{ (states('sensor.dhlotto_ng410808_lotto645_first_prize') | int / 100000000) | round(1) }}억원!
        당첨자: {{ states('sensor.dhlotto_ng410808_lotto645_first_winners') }}명
mode: single
```

### 5. 핫 넘버 기반 자동 구매

핫 넘버가 업데이트되면 알림을 받습니다.

```yaml
alias: "로또 핫 넘버 업데이트 알림"
description: "핫 넘버 정보가 업데이트되면 알림"
trigger:
  - platform: state
    entity_id: sensor.dhlotto_ng410808_lotto45_hot_numbers
action:
  - service: notify.mobile_app
    data:
      title: "로또 핫 넘버 업데이트"
      message: >
        최근 자주 나온 번호:
        {{ states('sensor.dhlotto_ng410808_lotto45_hot_numbers') }}
mode: single
```

### 6. 구매 완료 알림

로또 구매가 완료되면 구매 내역을 알림으로 받습니다.

```yaml
alias: "로또 구매 완료 알림"
description: "구매 후 구매 내역 알림"
trigger:
  - platform: state
    entity_id: sensor.dhlotto_ng410808_lotto45_latest_purchase
action:
  - service: notify.mobile_app
    data:
      title: "로또 구매 완료"
      message: >
        회차: {{ state_attr('sensor.dhlotto_ng410808_lotto45_latest_purchase', 'round_no') }}회
        
        게임 1: {{ states('sensor.dhlotto_ng410808_lotto45_game_1') }}
        게임 2: {{ states('sensor.dhlotto_ng410808_lotto45_game_2') }}
        게임 3: {{ states('sensor.dhlotto_ng410808_lotto45_game_3') }}
        게임 4: {{ states('sensor.dhlotto_ng410808_lotto45_game_4') }}
        게임 5: {{ states('sensor.dhlotto_ng410808_lotto45_game_5') }}
mode: single
```

### 7. 대시보드 카드 예시

Lovelace 대시보드에 로또 정보를 표시하는 카드 예시입니다.

```yaml
type: vertical-stack
cards:
  - type: entities
    title: 로또 6/45 당첨번호
    entities:
      - entity: sensor.dhlotto_ng410808_lotto645_round
        name: 회차
      - entity: sensor.dhlotto_ng410808_lotto645_winning_numbers
        name: 당첨번호
      - entity: sensor.dhlotto_ng410808_lotto645_draw_date
        name: 추첨일
      - type: divider
      - entity: sensor.dhlotto_ng410808_lotto645_first_prize
        name: 1등 상금
      - entity: sensor.dhlotto_ng410808_lotto645_first_winners
        name: 1등 당첨자
  
  - type: entities
    title: 내 계정 정보
    entities:
      - entity: sensor.dhlotto_ng410808_lotto45_balance
        name: 예치금
      - entity: sensor.dhlotto_ng410808_lotto45_total_winning
        name: 총 당첨금
      - entity: sensor.dhlotto_ng410808_lotto45_purchase_history_count
        name: 구매 기록
  
  - type: entities
    title: 빠른 구매
    entities:
      - entity: button.dhlotto_ng410808_buy_auto_1
        name: 1게임 구매
      - entity: button.dhlotto_ng410808_buy_auto_5
        name: 5게임 구매
  
  - type: entities
    title: 📊 번호 통계
    entities:
      - entity: sensor.dhlotto_ng410808_lotto45_hot_numbers
        name: 핫 넘버
      - entity: sensor.dhlotto_ng410808_lotto45_cold_numbers
        name: 콜드 넘버
      - entity: sensor.dhlotto_ng410808_lotto45_top_frequency_number
        name: 최다 출현 번호
  
  - type: entities
    title: 최근 구매 내역
    entities:
      - entity: sensor.dhlotto_ng410808_lotto45_game_1
        name: 게임 1
      - entity: sensor.dhlotto_ng410808_lotto45_game_2
        name: 게임 2
      - entity: sensor.dhlotto_ng410808_lotto45_game_3
        name: 게임 3
      - entity: sensor.dhlotto_ng410808_lotto45_game_4
        name: 게임 4
      - entity: sensor.dhlotto_ng410808_lotto45_game_5
        name: 게임 5
```

---

## REST API

애드온은 REST API를 제공하며, 포트 60099를 통해 접근할 수 있습니다.

**베이스 URL:** `http://homeassistant.local:60099`

<details>
<summary><b>📡 API 엔드포인트 목록</b></summary>

### 조회 API (GET)
- `/health` - 상태 확인
- `/balance` - 예치금 조회
- `/stats` - 통계 정보 조회
- `/buy/history` - 구매 내역 조회

### 실행 API (POST)
- `/random?count=6&games=1` - 랜덤 번호 생성
- `/check` - 당첨 확인
- `/buy` - 로또 구매
- `/buy/auto?count=1` - 자동 구매

</details>

### API 사용 예시

#### 1. 상태 확인

```bash
curl http://homeassistant.local:60099/health
```

#### 2. 예치금 조회

```bash
curl http://homeassistant.local:60099/balance
```

#### 3. 랜덤 번호 생성 (2게임)

```bash
curl -X POST "http://homeassistant.local:60099/random?count=6&games=2"
```

#### 4. 자동 구매 (3게임)

```bash
curl -X POST "http://homeassistant.local:60099/buy/auto?count=3"
```

#### 5. 구매 내역 조회

```bash
curl http://homeassistant.local:60099/buy/history
```

### Swagger UI

Swagger UI를 통해 API를 테스트할 수 있습니다:

**URL:** `http://homeassistant.local:60099/docs`

> **참고:** Ingress를 통해 접근하는 경우 `/api-docs` 페이지를 사용하세요.

---

## 문제 해결

### 로그인 실패

**증상:** "Login failed" 메시지 표시

**해결 방법:**
1. 동행복권 아이디와 비밀번호가 정확한지 확인
2. 동행복권 웹사이트에서 직접 로그인 테스트
3. 5회 이상 로그인 실패 시 계정이 잠길 수 있으니 잠시 대기 후 재시도
4. 로그 탭에서 상세한 에러 메시지 확인

### 센서가 업데이트되지 않음

**증상:** 센서 값이 오래된 상태로 유지됨

**해결 방법:**
1. 애드온이 정상 실행 중인지 확인 (Log 탭)
2. `update_interval` 설정 확인 (기본 3600초 = 1시간)
3. 수동 업데이트: Developer Tools → Services → `homeassistant.update_entity` 실행

### MQTT 센서가 생성되지 않음

**증상:** 버튼이나 센서가 Home Assistant에 나타나지 않음

**해결 방법:**
1. Configuration에서 `use_mqtt: true` 확인
2. MQTT 브로커가 정상 작동 중인지 확인
3. MQTT URL이 올바른지 확인 (기본: `mqtt://homeassistant.local:1883`)
4. 애드온 재시작

### 구매 실패

**증상:** 버튼을 눌렀지만 구매가 되지 않음

**해결 방법:**
1. 구매 가능 시간 확인:
   - 평일: 06:00-24:00
   - 토요일: 06:00-20:00
   - 일요일: 06:00-24:00
2. 예치금이 충분한지 확인 (1게임당 1,000원)
3. 주간 구매 제한 확인 (최대 5게임)
4. Log 탭에서 에러 메시지 확인

### 포트 충돌

**증상:** 애드온 시작 실패, "Address already in use" 에러

**해결 방법:**
1. 포트 60099를 사용하는 다른 애드온이나 서비스 확인
2. 필요시 다른 애드온 중지
3. 애드온 재시작

---

## 참고 사항

### 구매 제한

- **시간 제한:** 평일/일요일 06:00-24:00, 토요일 06:00-20:00
- **게임 제한:** 주간 최대 5게임
- **최소 예치금:** 게임당 1,000원

### 업데이트 주기

- **기본 주기:** 3600초 (1시간)
- **수동 업데이트:** Developer Tools → Services → `homeassistant.update_entity`

### 보안

- 비밀번호는 암호화되어 저장됩니다
- 세션은 자동으로 관리됩니다
- HTTPS 연결을 사용합니다

---

## 후원

이 애드온이 유용하셨다면 커피 한 잔 후원 부탁드립니다!

<table>
  <tr>
    <td align="center">
      <b>Toss (토스)</b><br>
      <img src="https://raw.githubusercontent.com/redchupa/ha-addons-dhlottery/main/images/toss-donation.png" width="200">
    </td>
    <td align="center">
      <b>PayPal</b><br>
      <img src="https://raw.githubusercontent.com/redchupa/ha-addons-dhlottery/main/images/paypal-donation.png" width="200">
    </td>
  </tr>
</table>

---

## 지원 및 문의

문제가 발생하거나 제안이 있으시면:

- **GitHub Issues:** https://github.com/redchupa/ha-addons-dhlottery/issues
- **GitHub Discussions:** https://github.com/redchupa/ha-addons-dhlottery/discussions

---

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.

---

## 면책 조항

본 애드온은 동행복권과 공식적인 관계가 없는 개인 프로젝트입니다.
사용자의 책임 하에 사용하시기 바랍니다.

---

## 기여

이 프로젝트에 기여하고 싶으시다면:

1. 이 저장소를 Fork 하세요
2. Feature 브랜치를 생성하세요 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋하세요 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 Push 하세요 (`git push origin feature/AmazingFeature`)
5. Pull Request를 생성하세요

---

**Made with ❤️ for Home Assistant Community**
