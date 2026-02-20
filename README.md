# 연금복권 720+ Home Assistant Add-on

Home Assistant에서 동행복권 연금복권 720+를 자동으로 구매할 수 있는 애드온입니다.

## 주요 기능

- **자동 구매**: 1장(1조) 또는 5장(모든 조) 자동 구매
- **잔액 조회**: 구매 가능 금액 실시간 모니터링
- **회차 정보**: 현재 회차 및 판매 잔여시간 조회
- **구매 이력**: 최근 구매 내역 확인
- **MQTT Discovery**: Home Assistant 센서/버튼 자동 통합
- **REST API**: 외부 앱에서도 사용 가능
- **멀티 계정**: 여러 동행복권 계정 동시 지원

---

## 설치 및 설정

### 저장소 추가

1. Home Assistant -> **Settings** -> **Add-ons** -> **Add-on Store**
2. 우측 상단 메뉴 -> **Repositories**
3. 다음 URL 추가:
   ```
   https://github.com/darkhowk/ha-addons-dhlottery
   ```

### 애드온 설치

1. Add-on Store에서 **연금복권 720+** 선택
2. **Install** 클릭
3. Configuration 탭에서 설정:

```yaml
accounts:
  - username: ""   # 동행복권 아이디
    password: ""   # 동행복권 비밀번호
    enabled: true
enable_pension720: true
update_interval: 3600    # 센서 업데이트 주기 (초)
use_mqtt: true
mqtt_url: "mqtt://homeassistant.local:1883"
mqtt_username: ""
mqtt_password: ""
```

4. **Start** 클릭
5. **Log** 탭에서 "Login successful" 확인

---

### 사용전 필수 체크

1. 동행복권 사이트 https://www.dhlottery.co.kr 에 직접 들어가서
   회원가입 -> 로그인 -> 마이페이지 -> 건전구매 서약하기 (필수)
2. 동행복권 사이트에서 예치금을 충전해놓으면 본 애드온을 사용해서 자동 구매 가능

---

## 생성되는 센서

### 잔액 센서
- `sensor.addon_{username}_pension720_balance` - 구매 가능 금액 (원)

### 로그인 상태 센서
- `sensor.addon_{username}_pension720_login_error` - 로그인 오류 메시지

---

## 버튼 엔티티

MQTT Discovery를 활성화하면 구매 버튼이 생성됩니다.

- `button.addon_{username}_pension720_buy_1` - 1장 구매 (1조 자동)
- `button.addon_{username}_pension720_buy_5` - 5장 구매 (모든 조 자동)

---

## REST API

**포트:** 60100

### 조회 API (GET)
- `/health` - 상태 확인
- `/accounts` - 계정 목록
- `/api/balance/{username}` - 잔액 조회
- `/api/history/{username}` - 구매 이력

### 구매 API (POST)
- `/api/purchase/{username}/1` - 1장 구매
- `/api/purchase/{username}/5` - 5장 구매

### 사용 예시

```bash
# 상태 확인
curl http://homeassistant.local:60100/health

# 잔액 조회
curl http://homeassistant.local:60100/api/balance/{username}

# 1장 구매
curl -X POST http://homeassistant.local:60100/api/purchase/{username}/1

# 5장 구매
curl -X POST http://homeassistant.local:60100/api/purchase/{username}/5
```

---

## 구매 플로우

연금복권 720+는 다음 3단계로 구매됩니다:

1. **makeOrderNo.do** - 주문번호 생성
2. **connPro.do** - 구매 실행
3. **checkDeposit.do** - 잔액 확인

모든 통신은 AES-128-CBC + PBKDF2(SHA256) 암호화로 보호됩니다.

---

## 문제 해결

### 로그인 실패
1. 동행복권 아이디/비밀번호 확인
2. 동행복권 웹사이트에서 직접 로그인 테스트
3. 5회 이상 실패 시 계정 잠김 - 잠시 대기 후 재시도

### 구매 실패
1. 예치금 충분한지 확인 (1장당 1,000원)
2. 판매 시간 확인 (토요일 20:00 마감)
3. Log 탭에서 에러 메시지 확인

---

## 면책 조항

본 애드온은 동행복권과 공식적인 관계가 없는 개인 프로젝트입니다.
사용자의 책임 하에 사용하시기 바랍니다.

---

**Made with Claude Code**
