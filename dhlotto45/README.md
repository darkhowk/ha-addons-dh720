# DH Lottery 6/45 애드온

Home Assistant에서 동행복권 로또 6/45를 자동으로 구매하고 분석할 수 있는 애드온입니다.

## 주요 기능

- 🎫 **자동 구매**: 버튼 클릭만으로 로또 자동 구매
- 📊 **실시간 분석**: 당첨번호, 상금, 통계 정보 자동 업데이트
- 🔔 **자동화 연동**: Home Assistant 자동화와 완벽하게 통합
- 📈 **통계 분석**: Hot/Cold 번호, 출현 빈도 분석
- 💰 **예치금 관리**: 잔액 및 구매 가능 금액 모니터링

## 설정

Configuration 탭에서 동행복권 계정 정보를 입력하세요:

```yaml
username: "동행복권_아이디"
password: "동행복권_비밀번호"
enable_lotto645: true
update_interval: 3600  # 센서 업데이트 주기 (초)
use_mqtt: true  # MQTT Discovery 사용 (권장)
```

## 빠른 시작

1. 애드온 설치 후 **Configuration** 탭에서 계정 정보 입력
2. **Start** 버튼 클릭
3. **Log** 탭에서 "Login successful" 확인
4. Home Assistant에서 생성된 센서 및 버튼 확인

## 문서

자세한 사용 방법과 자동화 예시는 **Documentation** 탭을 참고하세요.

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

## 면책 조항

본 애드온은 동행복권과 공식적인 관계가 없는 개인 프로젝트입니다.
사용자의 책임 하에 사용하시기 바랍니다.

---

**GitHub**: https://github.com/redchupa/ha-addons-dhlottery
