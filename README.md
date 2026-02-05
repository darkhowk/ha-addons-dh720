# DH Lottery Home Assistant Add-ons

Home Assistant 동행복권 로또 6/45 애드온 앱 입니다.

## 애드온 목록

### DH Lottery AddOn App
동행복권 로또 6/45 애드온 앱

**주요 기능:**
- 예치금 조회 및 모니터링
- 번호 통계 분석 (Hot/Cold 번호, 출현 빈도)
- 구매 내역 및 당첨금 조회
- 랜덤 번호 생성
- REST API 제공
- Web UI 제공

## 설치 방법

### 1. 저장소 추가

1. Home Assistant 웹 인터페이스 접속
2. **Settings** > **Add-ons** > **Add-on Store**
3. 우측 상단 메뉴(점 3개) 클릭 > **Repositories** 선택
4. 다음 URL 입력:
   ```
   https://github.com/redchupa/ha-addons-dhlottery
   ```
5. **Add** 클릭

### 2. 애드온 설치

1. Add-on Store에서 스크롤하여 "DH Lottery Add-ons" 섹션 찾기
2. **DH Lotto 45** 클릭
3. **Install** 클릭 (설치 완료까지 1-2분 소요)

### 3. 설정

Configuration 탭에서 동행복권 계정 정보 입력:

```yaml
username: "동행복권_아이디"
password: "동행복권_비밀번호"
enable_lotto645: true
update_interval: 3600
use_mqtt: false
```

### 4. 시작

Info 탭에서:
- **Start** 버튼 클릭
- **Watchdog** 활성화 (권장)
- **Start on boot** 활성화 (권장)

Log 탭에서 "Login successful" 메시지 확인

## 지원

문제가 발생하면 [Issues](https://github.com/redchupa/ha-addons-dhlottery/issues)에 보고해주세요.

자세한 사용법은 각 애드온의 Documentation 탭을 참고하세요.

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

## 라이선스

MIT License

## 면책 조항

본 애드온은 동행복권과 공식적인 관계가 없는 개인 프로젝트입니다.
사용자의 책임 하에 사용하시기 바랍니다.
