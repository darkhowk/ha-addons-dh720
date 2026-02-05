# DH Lotto 45 문서

## 설정 옵션

### username (필수)
- **타입**: 문자열
- **설명**: 동행복권 아이디
- **예시**: `"your_id"`

### password (필수)
- **타입**: 비밀번호
- **설명**: 동행복권 비밀번호
- **예시**: `"your_password"`
- **주의**: 특수문자가 있으면 따옴표로 감싸야 합니다

### enable_lotto645
- **타입**: 불리언
- **설명**: 로또 6/45 기능 활성화
- **기본값**: `true`

### update_interval
- **타입**: 정수
- **설명**: 센서 업데이트 주기 (초)
- **기본값**: `3600` (1시간)
- **범위**: 60 ~ 86400
- **권장**: 3600 (API 부하 방지)

### use_mqtt
- **타입**: 불리언
- **설명**: MQTT 사용 (현재 미구현)
- **기본값**: `false`

## 센서 상세

### sensor.lotto45_deposit

예치금 정보를 제공합니다.

**상태값**: 총 예치금 (원)

**속성**:
- `purchase_available`: 구매 가능 금액 (원)
- `reservation_purchase`: 예약 구매 금액 (원)
- `withdrawal_request`: 출금 신청 중 금액 (원)
- `this_month_accumulated`: 이번 달 누적 구매 금액 (원)
- `unit_of_measurement`: "원"
- `friendly_name`: "로또45 예치금"

**사용 예시**:
```yaml
{{ states('sensor.lotto45_deposit') }}
{{ state_attr('sensor.lotto45_deposit', 'purchase_available') }}
```

### sensor.lotto45_top_frequency_number

최근 50회차에서 가장 많이 출현한 번호입니다.

**상태값**: 번호 (1-45)

**속성**:
- `count`: 출현 횟수
- `percentage`: 출현 확률 (%)
- `unit_of_measurement`: "회"
- `friendly_name`: "로또45 최다 출현 번호"

### sensor.lotto45_hot_numbers

최근 20회차에서 자주 나온 상위 10개 번호입니다.

**상태값**: 쉼표로 구분된 번호 문자열

**속성**:
- `numbers`: 번호 리스트 (배열)
- `friendly_name`: "로또45 Hot 번호"

**사용 예시**:
```yaml
{{ states('sensor.lotto45_hot_numbers') }}
{{ state_attr('sensor.lotto45_hot_numbers', 'numbers') }}
```

### sensor.lotto45_cold_numbers

최근 20회차에서 잘 안 나온 하위 10개 번호입니다.

**상태값**: 쉼표로 구분된 번호 문자열

**속성**:
- `numbers`: 번호 리스트 (배열)
- `friendly_name`: "로또45 Cold 번호"

### sensor.lotto45_total_winning

최근 1년간 총 당첨금입니다.

**상태값**: 총 당첨금 (원)

**속성**:
- `total_purchase`: 총 구매 금액 (원)
- `total_purchase_count`: 총 구매 횟수
- `total_winning_count`: 총 당첨 횟수
- `win_rate`: 당첨률 (%)
- `roi`: 수익률 (%)
- `unit_of_measurement`: "원"
- `friendly_name`: "로또45 총 당첨금"

## API 엔드포인트

### GET /

Web UI 페이지

**응답**: HTML

### GET /health

헬스체크

**응답**:
```json
{
  "status": "ok",
  "logged_in": true,
  "username": "your_id",
  "lotto645_enabled": true
}
```

### GET /balance

예치금 조회

**응답**:
```json
{
  "deposit": 100000,
  "purchase_available": 95000,
  "reservation_purchase": 0,
  "withdrawal_request": 5000,
  "purchase_impossible": 5000,
  "this_month_accumulated_purchase": 50000
}
```

### GET /stats

통계 조회

**응답**:
```json
{
  "frequency": [
    {"number": 1, "count": 10, "percentage": 20.0},
    ...
  ],
  "hot_numbers": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "cold_numbers": [36, 37, 38, 39, 40, 41, 42, 43, 44, 45],
  "most_frequent": [
    {"number": 1, "count": 25, "percentage": 50.0},
    ...
  ],
  "purchase_stats": {
    "total_purchase_count": 100,
    "total_purchase_amount": 100000,
    "total_winning_count": 10,
    "total_winning_amount": 50000,
    "win_rate": 10.0,
    "roi": -50.0,
    "rank_distribution": {
      "1": 0,
      "2": 0,
      "3": 0,
      "4": 5,
      "5": 5
    }
  }
}
```

### POST /random

랜덤 번호 생성

**파라미터**:
- `count`: 번호 개수 (1-45, 기본값: 6)
- `games`: 게임 수 (1-5, 기본값: 1)

**요청 예시**:
```bash
curl -X POST "http://homeassistant.local:60099/random?count=6&games=2"
```

**응답**:
```json
{
  "numbers": [
    [1, 5, 12, 23, 34, 42],
    [3, 8, 15, 27, 33, 41]
  ]
}
```

### POST /check

당첨 확인

**요청 본문**:
```json
{
  "numbers": [1, 2, 3, 4, 5, 6],
  "round_no": 1000
}
```

**파라미터**:
- `numbers`: 내 번호 (6개, 필수)
- `round_no`: 확인할 회차 (선택, 없으면 최신 회차)

**응답**:
```json
{
  "round_no": 1000,
  "my_numbers": [1, 2, 3, 4, 5, 6],
  "winning_numbers": [7, 8, 9, 10, 11, 12],
  "bonus_number": 13,
  "matching_count": 0,
  "bonus_match": false,
  "rank": 0,
  "is_winner": false
}
```

**등수 기준**:
- 1등: 6개 일치
- 2등: 5개 일치 + 보너스 번호
- 3등: 5개 일치
- 4등: 4개 일치
- 5등: 3개 일치

## 자동화 예시

### 예치금 부족 알림

```yaml
automation:
  - alias: "로또 예치금 부족 알림"
    trigger:
      - platform: numeric_state
        entity_id: sensor.lotto45_deposit
        attribute: purchase_available
        below: 5000
    action:
      - service: notify.mobile_app
        data:
          title: "로또 예치금 부족"
          message: "구매 가능 금액: {{ state_attr('sensor.lotto45_deposit', 'purchase_available') }}원"
```

### 토요일 Hot 번호 알림

```yaml
automation:
  - alias: "로또 Hot 번호 추천"
    trigger:
      - platform: time
        at: "20:00:00"
    condition:
      - condition: time
        weekday:
          - sat
    action:
      - service: notify.mobile_app
        data:
          title: "이번 주 로또 Hot 번호"
          message: "{{ states('sensor.lotto45_hot_numbers') }}"
```

### 당첨금 변화 알림

```yaml
automation:
  - alias: "당첨금 증가 알림"
    trigger:
      - platform: state
        entity_id: sensor.lotto45_total_winning
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > trigger.from_state.state | int }}"
    action:
      - service: notify.mobile_app
        data:
          title: "당첨되었습니다!"
          message: "당첨금: {{ states('sensor.lotto45_total_winning') }}원"
```

## 문제 해결

### 로그인 실패

**증상**: Log에 "로그인에 실패했습니다" 메시지

**원인**:
1. 잘못된 아이디/비밀번호
2. 비밀번호 5회 이상 실패로 계정 잠김
3. 특수문자 처리 오류

**해결 방법**:
1. 동행복권 웹사이트(https://dhlottery.co.kr)에서 직접 로그인 테스트
2. 로그인 안 되면 웹사이트에서 비밀번호 변경
3. 특수문자가 있으면 Configuration에서 따옴표로 감싸기:
   ```yaml
   password: "pass!@#word123"
   ```
4. 애드온 재시작

### 센서 업데이트 안 됨

**증상**: 센서 값이 변경되지 않음

**원인**:
1. 애드온이 실행 중이 아님
2. 로그인 실패
3. update_interval 대기 중
4. API 에러

**해결 방법**:
1. Info 탭에서 애드온 상태 확인 (Running이어야 함)
2. Log 탭에서 에러 메시지 확인
3. update_interval 시간 대기 (기본 1시간)
4. 애드온 재시작

### API 접근 불가

**증상**: Web UI 또는 API 접근 불가

**원인**:
1. 애드온이 실행 중이 아님
2. 포트 충돌
3. 네트워크 문제

**해결 방법**:
1. Info 탭에서 상태 확인
2. Log 탭에서 "Port 60099 already in use" 확인
   - 포트 충돌 시 config.json 수정 필요 (고급 사용자)
3. Ingress 사용 (Info 탭 > OPEN WEB UI 버튼)

### 센서가 생성되지 않음

**증상**: Developer Tools > States에서 센서를 찾을 수 없음

**원인**:
1. enable_lotto645가 false
2. 로그인 실패
3. Home Assistant API 권한 문제

**해결 방법**:
1. Configuration에서 `enable_lotto645: true` 확인
2. Log에서 "Login successful" 확인
3. 애드온 재시작
4. Home Assistant 재시작

### 특정 기능이 작동하지 않음

**증상**: 일부 통계나 분석 기능이 작동하지 않음

**원인**:
1. 데이터 부족 (구매 내역이 없음)
2. API 응답 오류
3. 코드 버그

**해결 방법**:
1. Log 탭에서 상세 에러 메시지 확인
2. 동행복권 웹사이트에서 구매 내역 확인
3. GitHub Issues에 에러 로그와 함께 보고

## 제한 사항

### 동행복권 정책
- 주간 구매 제한: 5게임
- 1회 구매 제한: 5게임
- 구매 가능 시간: 매일 06:00 ~ 24:00
- 추첨일(토요일) 20:00 ~ 일요일 06:00: 판매 정지

### 기술적 제한
- 센서 업데이트 주기: 최소 60초
- API 타임아웃: 30초
- 동시 접속: 단일 세션만 지원

## 보안

### 권장 사항
- 외부 네트워크 접근 시 HTTPS 사용
- 강력한 비밀번호 사용
- 정기적으로 비밀번호 변경

### 주의 사항
- 애드온 설정의 비밀번호는 암호화되지 않습니다
- 로그에 민감한 정보가 기록될 수 있습니다
- API 키나 토큰을 공유하지 마세요

## 지원

문제가 계속되면 다음 정보와 함께 GitHub Issues에 보고해주세요:

1. Home Assistant 버전
2. 애드온 버전
3. Log 탭의 전체 로그
4. 문제 발생 전 수행한 작업
5. Configuration 설정 (비밀번호 제외)

GitHub Issues: https://github.com/YOUR_USERNAME/ha-addons-dhlottery/issues
