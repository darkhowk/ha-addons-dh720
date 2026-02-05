# DH Lotto 45

Home Assistant 동행복권 로또 6/45 애드온

## 🆕 버전 0.4.9 변경사항

### 버튼 엔티티 추가! 🎯
- ✅ MQTT 모드에서 구매 버튼 2개 자동 생성
- ✅ 1게임 자동 구매 버튼
- ✅ 5게임 자동 구매 버튼 (주간 최대)
- ✅ 구매 후 센서 자동 업데이트

### MQTT가 이제 기본값입니다
- ✅ `use_mqtt: true`가 기본 설정
- ✅ unique_id 지원으로 UI에서 수정 가능
- ✅ 버튼 엔티티 지원

### 사용 방법
```yaml
# 최소 설정 (MQTT 기본 활성화)
username: "your_id"
password: "your_password"
```

## 🆕 버전 0.4.7 변경사항

### MQTT Discovery 지원 (unique_id 추가!)
- ✅ 모든 센서에 unique_id 추가
- ✅ UI에서 엔티티 이름/아이콘 변경 가능
- ✅ 통합구성요소와 충돌 없는 명확한 entity_id
- ✅ 자동 디바이스 등록

### 사용 방법
1. **MQTT 비활성화** (기본값): REST API 사용
   - Entity ID: `sensor.addon_[USERNAME]_lotto45_balance`
   - ⚠️ unique_id 없음 (이름 변경 불가)
   
2. **MQTT 활성화**: MQTT Discovery 사용 (권장!)
   - Entity ID: `sensor.dhlottery_addon_[USERNAME]_lotto45_balance`
   - ✅ unique_id 있음 (이름 변경 가능)
   - ✅ 디바이스로 그룹화됨

## 기능

### 기본 기능
- 동행복권 계정 연동
- 예치금 조회 및 모니터링
- 구매 내역 조회
- 당첨금 조회

### 분석 기능
- 번호별 출현 빈도 분석 (최근 50회차)
- Hot & Cold 번호 분석 (최근 20회차)
- 구매 통계 분석 (최근 1년)
- 당첨 확인 기능

### 유틸리티
- 랜덤 번호 생성
- REST API 제공
- Web UI 제공

## 설정

### 필수 설정

**username** (필수)
- 동행복권 아이디

**password** (필수)
- 동행복권 비밀번호

### 선택 설정

**enable_lotto645** (기본값: true)
- 로또 6/45 기능 활성화 여부

**update_interval** (기본값: 3600)
- 센서 업데이트 주기 (초)
- 범위: 60 ~ 86400

**use_mqtt** (기본값: false)
- MQTT Discovery 사용 여부
- **권장: true** (unique_id 지원)

**mqtt_broker** (기본값: homeassistant.local)
- MQTT 브로커 주소

**mqtt_port** (기본값: 1883)
- MQTT 브로커 포트

**mqtt_username** (선택)
- MQTT 사용자명 (필요한 경우)

**mqtt_password** (선택)
- MQTT 비밀번호 (필요한 경우)

### 설정 예시

#### 기본 설정 (MQTT 모드 - 권장 ⭐)
```yaml
username: "your_id"
password: "your_password"
enable_lotto645: true
update_interval: 3600
# use_mqtt는 기본값 true이므로 생략 가능
```

#### MQTT 모드 명시적 설정
```yaml
username: "your_id"
password: "your_password"
enable_lotto645: true
update_interval: 3600
use_mqtt: true
mqtt_broker: "homeassistant.local"
mqtt_port: 1883
```

#### REST API 모드 (버튼 없음)
```yaml
username: "your_id"
password: "your_password"
enable_lotto645: true
update_interval: 3600
use_mqtt: false
```

## 생성되는 센서 및 버튼

### REST API 모드
애드온 시작 후 다음 센서들이 생성됩니다:
- **sensor.addon_[USERNAME]_lotto45_balance**: 예치금 정보
- **sensor.addon_[USERNAME]_lotto45_top_frequency_number**: 최다 출현 번호
- **sensor.addon_[USERNAME]_lotto45_hot_numbers**: Hot 번호
- **sensor.addon_[USERNAME]_lotto45_cold_numbers**: Cold 번호
- **sensor.addon_[USERNAME]_lotto45_total_winning**: 총 당첨금
- **sensor.addon_[USERNAME]_lotto645_round**: 회차 번호
- **sensor.addon_[USERNAME]_lotto645_number1~6**: 당첨 번호
- **sensor.addon_[USERNAME]_lotto645_bonus**: 보너스 번호
- **sensor.addon_[USERNAME]_lotto645_draw_date**: 추첨일

⚠️ **주의**: REST API 모드에서는 unique_id가 없어 UI에서 엔티티 이름 변경 불가
⚠️ **버튼 없음**: REST API 모드에서는 버튼 엔티티 생성 안 됨

### MQTT Discovery 모드 (권장 ⭐)
디바이스로 그룹화된 센서와 버튼이 생성됩니다:

**디바이스**: DH Lottery Add-on ([USERNAME])

**센서** (10개):
- **sensor.dhlottery_addon_[USERNAME]_lotto45_balance**: 예치금 정보
- **sensor.dhlottery_addon_[USERNAME]_lotto45_top_frequency_number**: 최다 출현 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto45_hot_numbers**: Hot 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto45_cold_numbers**: Cold 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto45_total_winning**: 총 당첨금
- **sensor.dhlottery_addon_[USERNAME]_lotto645_round**: 회차 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto645_number1~6**: 당첨 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto645_bonus**: 보너스 번호
- **sensor.dhlottery_addon_[USERNAME]_lotto645_draw_date**: 추첨일

**버튼** (2개) 🆕:
- **button.dhlottery_addon_[USERNAME]_buy_auto_1**: 1게임 자동 구매
- **button.dhlottery_addon_[USERNAME]_buy_auto_5**: 5게임 자동 구매 (주간 최대)

✅ **장점**: 
- unique_id 있음 (UI에서 자유롭게 수정 가능)
- 디바이스로 그룹화되어 관리 편리
- 통합구성요소와 충돌 없음
- 버튼으로 간편하게 구매 가능

## 사용법

### Web UI 접속

Info 탭에서 **OPEN WEB UI** 버튼 클릭

또는 브라우저에서 직접 접속:
```
http://homeassistant.local:60099
```

### API 사용

- API 문서: `http://homeassistant.local:60099/api-docs`
- 헬스체크: `GET /health`
- 예치금 조회: `GET /balance`
- 통계 조회: `GET /stats`
- 랜덤 번호: `POST /random?count=6&games=1`
- 당첨 확인: `POST /check`

### 자동화 예시

**예치금 부족 알림:**
```yaml
automation:
  - alias: "로또 예치금 부족 알림"
    trigger:
      - platform: numeric_state
        entity_id: sensor.dhlottery_addon_ng410808_lotto45_balance
        attribute: purchase_available
        below: 5000
    action:
      - service: notify.mobile_app
        data:
          title: "로또 예치금 부족"
          message: "구매 가능 금액이 5,000원 미만입니다."
```

**토요일 Hot 번호 알림:**
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
          message: "{{ states('sensor.dhlottery_addon_ng410808_lotto45_hot_numbers') }}"
```

**매주 토요일 자동 구매:** 🆕
```yaml
automation:
  - alias: "매주 토요일 로또 자동 구매"
    trigger:
      - platform: time
        at: "19:00:00"
    condition:
      - condition: time
        weekday:
          - sat
      - condition: numeric_state
        entity_id: sensor.dhlottery_addon_ng410808_lotto45_balance
        attribute: purchase_available
        above: 5000
    action:
      - service: button.press
        target:
          entity_id: button.dhlottery_addon_ng410808_buy_auto_1
      - service: notify.mobile_app
        data:
          title: "로또 구매 완료"
          message: "자동 1게임 구매가 완료되었습니다."
```

## 문제 해결

### MQTT 연결 실패

**증상**: Log에 "MQTT connection failed" 메시지

**해결 방법**:
1. MQTT 브로커가 실행 중인지 확인 (`mosquitto` 애드온 설치)
2. Configuration에서 MQTT 설정 확인
3. MQTT 사용자명/비밀번호가 필요한 경우 입력
4. 네트워크 문제 확인

### 센서가 생성되지 않음

**증상**: Developer Tools > States에서 센서를 찾을 수 없음

**원인 & 해결**:
1. **REST API 모드**: 
   - `supervisor_token` 확인
   - Log 탭에서 "Login successful" 확인
   
2. **MQTT 모드**:
   - MQTT 브로커 연결 확인
   - Configuration > MQTT에서 자동 발견 활성화 확인
   - 애드온 재시작

### 통합구성요소와 충돌

**해결 방법**:
- **MQTT 모드 사용** (권장): `use_mqtt: true`
- Entity ID가 완전히 다름:
  - 통합구성요소: `sensor.dhlottery_ng410808_*`
  - 애드온 MQTT: `sensor.dhlottery_addon_ng410808_*`
  - 애드온 REST: `sensor.addon_ng410808_*`

## 통합구성요소 vs 애드온

### 통합구성요소 (custom_components)
- ✅ unique_id 지원
- ✅ 버튼 엔티티 (1개/모두 구매)
- ✅ 서비스 호출
- ⚠️ Python 코드 직접 설치 필요

### 애드온 (이 프로젝트)
- ✅ 간편한 설치 (애드온 스토어)
- ✅ Web UI & API 제공
- ✅ MQTT Discovery 지원 (unique_id)
- ✅ 버튼 엔티티 지원 (MQTT 모드) 🆕
- ⚠️ REST API 모드는 unique_id + 버튼 없음

**권장**: 
- 두 가지 모두 사용 (충돌 없음)
- 애드온은 MQTT 모드로 설정 (기본값)
- 통합구성요소: 고급 기능 (수동 구매, 서비스 등)
- 애드온: 센서 + 간편 구매 + 통계

## 보안 주의사항

- 동행복권 계정 정보는 안전하게 보관하세요
- 애드온 설정의 비밀번호는 암호화되지 않습니다
- 외부 네트워크 접근 시 HTTPS 사용을 권장합니다

## 지원

문제 보고: [GitHub Issues](https://github.com/redchupa/ha-addons-dhlottery/issues)

## 라이선스

MIT License
