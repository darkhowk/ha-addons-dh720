# Step 3: 네트워크 캡처 가이드

connPro.do 다음에 호출되는 "최종 구매 확정" 요청을 캡처하는 방법입니다.

---

## 캡처 단계

### 1. Chrome DevTools 준비

1. Chrome에서 `https://ol.dhlottery.co.kr/` 접속
2. **F12** (또는 Cmd+Option+I) → **Network** 탭
3. 필터: **XHR** 선택 (또는 All)
4. **Preserve log** 체크 (로그 유지)
5. 화면 분할하여 아래쪽에 Network 탭 고정

---

### 2. 로그인

1. 동영 720+ 로그인
2. 메인 페이지에서 **"연금복권 720+"** 메뉴 클릭

---

### 3. 구매 과정 캡처

1. **1장 구매** 또는 **5장 구매** 버튼 클릭
2. Network 탭에서 순서대로 호출되는 요청 확인:
   ```
   1. makeOrderNo.do     ← 이미 분석 완료
   2. connPro.do          ← 이미 분석 완료
   3. ??????.do          ← 이것이 Step 3! (캡처 필요)
   ```

3. **Step 3 요청 클릭** 후 아래 정보 캡처:

---

## Step 3에서 캡처할 정보

### Request Headers 탭
```
Request URL: https://ol.dhlottery.co.kr/?????.do
Request Method: POST
Status Code: 200 OK

Request Headers:
  Content-Type: application/x-www-form-urlencoded
  Cookie: JSESSIONID=*** (마스킹)
```

### Payload 탭 (Form Data 또는 JSON)
```
q: *** (암호화된 blob)
orderNo: *** (필요한 경우)
ticketCount: 1 (또는 5)
... 기타 키들
```

**⚠️ 스크린샷 캡처 필수**

### Response 탭
```
{
  "returnCode": "10000",          ← 성공 코드
  "returnMsg": "구매 완료",        ← 성공 메시지
  "data": {
    "roundNo": 1234,              ← 회차 번호
    "issueDt": "2026/02/13...",   ← 발행 일시
    "barcode": "1234 5678 ...",   ← 바코드
    "ticketCount": 1,             ← 구매 장수
    "amount": 1000                ← 구매 금액
  }
}
```

**⚠️ 스크린샷 캡처 필수**

---

## 실패 시나리오 캡처 (선택)

### 잔액 부족 시 Response 예시
```
{
  "returnCode": "20001",          ← 실패 코드
  "returnMsg": "잔액이 부족합니다",  ← 실패 메시지
  "data": null
}
```

### 이미 구매한 경우 Response 예시
```
{
  "returnCode": "20002",
  "returnMsg": "이미 구매한 회차입니다",
  "data": null
}
```

---

## 캡처 후 제출

캡처한 정보를 아래 형식으로 정리해서 제공해주세요:

```markdown
### Step 3: 최종 구매 확정

**요청 URL:**
`POST https://ol.dhlottery.co.kr/?????.do`

**Request Headers:**
- Content-Type: `application/x-www-form-urlencoded`
- Cookie: `JSESSIONID=***`

**Request Payload:**
```
q: ***
orderNo: ***
ticketCount: 1
```

**Response (성공):**
```json
{
  "returnCode": "10000",
  "returnMsg": "구매 완료",
  "data": {
    "roundNo": 1234,
    "issueDt": "2026/02/13 금 09:00:00",
    "barcode": "1234 5678 1234 5678 1234 5678",
    "ticketCount": 1,
    "amount": 1000
  }
}
```

**Response (실패 - 잔액 부족):**
```json
{
  "returnCode": "20001",
  "returnMsg": "잔액이 부족합니다",
  "data": null
}
```

**필요한 키 목록:**
- q (암호화된 blob)
- orderNo (주문번호)
- ticketCount (구매 장수)
```

---

## 팁

- **Preserve log** 체크 필수 (페이지 이동 시 로그 소실 방지)
- 캡처 후 스크린샷 찍어두면 좋음
- 실패 시나리오(잔액 부족) 테스트는 **실제 돈 나가니까 주의!**
- 성공 코드: 보통 `"10000"` 또는 `"0000"`
- 실패 코드: 보통 `"20001"`, `"20002"` 등

---

## 예상 엔드포인트 이름

일반적인 패턴:
- `confirmPurchase.do`
- `finalizePurchase.do`
- `buyComplete.do`
- `completePurchase.do`
- `processPurchase.do`
- `executePurchase.do`

---

캡처 완료 후 위 정보를 알려주시면 코드를 바로 업데이트하겠습니다!
