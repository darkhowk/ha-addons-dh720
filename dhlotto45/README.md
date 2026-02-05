# DH Lotto 45

Home Assistant용 동행복권 로또 6/45 통합 애드온

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
- MQTT 사용 여부 (현재 미구현)

### 설정 예시

```yaml
username: "your_id"
password: "your_password"
enable_lotto645: true
update_interval: 3600
use_mqtt: false
```

## 생성되는 센서

애드온 시작 후 다음 센서들이 자동으로 생성됩니다:

- **sensor.lotto45_deposit**: 예치금 정보
- **sensor.lotto45_top_frequency_number**: 최다 출현 번호
- **sensor.lotto45_hot_numbers**: Hot 번호 (최근 자주 출현)
- **sensor.lotto45_cold_numbers**: Cold 번호 (최근 잘 안 나옴)
- **sensor.lotto45_total_winning**: 총 당첨금

자세한 센서 정보는 Documentation 탭을 참고하세요.

## 사용법

### Web UI 접속

Info 탭에서 **OPEN WEB UI** 버튼 클릭

또는 브라우저에서 직접 접속:
```
http://homeassistant.local:8099
```

### API 사용

- API 문서: `http://homeassistant.local:8099/docs`
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
        entity_id: sensor.lotto45_deposit
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
          message: "{{ states('sensor.lotto45_hot_numbers') }}"
```

## 문제 해결

자세한 문제 해결 방법은 Documentation 탭을 참고하세요.

### 일반적인 문제

**로그인 실패**
- 동행복권 웹사이트에서 직접 로그인 테스트
- 비밀번호 5회 이상 실패 시 웹사이트에서 비밀번호 변경 필요
- 특수문자가 있으면 따옴표로 감싸기: `password: "pass!@#"`

**센서 업데이트 안 됨**
- Log 탭에서 에러 확인
- update_interval 시간 대기 (기본 1시간)
- 애드온 재시작

**API 접근 불가**
- 애드온 상태가 "Running"인지 확인
- Log 탭에서 에러 확인
- Ingress 사용 (OPEN WEB UI 버튼)

## 보안 주의사항

- 동행복권 계정 정보는 안전하게 보관하세요
- 애드온 설정의 비밀번호는 암호화되지 않습니다
- 외부 네트워크 접근 시 HTTPS 사용을 권장합니다

## 지원

문제 보고: [GitHub Issues](https://github.com/redchupa/ha-addons-dhlottery/issues)

## 후원

이 애드온이 유용하셨다면 커피 한 잔 후원 부탁드립니다!

### Toss (토스)
![Toss](https://raw.githubusercontent.com/redchupa/ha-addons-dhlottery/main/images/toss-donation.png)

### PayPal
![PayPal](https://raw.githubusercontent.com/redchupa/ha-addons-dhlottery/main/images/paypal-donation.png)

## 라이선스

MIT License
