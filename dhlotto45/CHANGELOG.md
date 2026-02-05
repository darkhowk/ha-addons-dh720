# 변경 이력

## [0.4.6] - 2026-02-05

### 수정
- UTF-8 인코딩 문제 해결 (중요)
  - 모든 센서 friendly_name을 영어로 변경
  - 한글 인코딩 깨짐 현상 완전 해결
  - unit_of_measurement: 원→KRW, 회→times

### 센서 이름 변경
- "동행복권 잔액" → "DH Lottery Balance"
- "로또6/45 회차" → "Lotto 645 Round"
- "로또6/45 번호 N" → "Lotto 645 Number N"
- "로또6/45 보너스" → "Lotto 645 Bonus"
- "로또6/45 추첨일" → "Lotto 645 Draw Date"
- "로또45 Hot 번호" → "Lotto 45 Hot Numbers"
- "로또45 Cold 번호" → "Lotto 45 Cold Numbers"
- "로또45 최다 출현 번호" → "Lotto 45 Top Frequency Number"
- "로또45 이 당첨금" → "Lotto 45 Total Winning"
- "최근 업데이트" → "Last Update"

## [0.4.5] - 2026-02-05

### 추가
- 애드온 센서 엔티티 ID에 "addon_" 프리픽스 추가
  - 통합구성요소(custom_components)와 동시 사용 가능
  - 센서 이름 예: sensor.addon_lotto45_balance
  - 엔티티 ID 충돌 문제 해결

### 수정
- publish_sensor 함수 개선
  - entity_id → addon_entity_id 자동 변환
  - 로그 메시지 업데이트

### 기술
- 통합구성요소와 애드온 공존 지원
- 총 센서 개수: 통합 10개 + 애드온 10개 = 20개

## [0.4.4] - 2026-02-05

### 수정
- 구매 통계 분석 시 None 값 처리 버그 수정
  - prchsQty, ltWnAmt 필드에서 None 반환 시 안전하게 0으로 변환
  - 타입 검증 추가로 안정성 강화

## [0.4.3] - 2026-02-05

### 수정
- 로그인 로직 안정화 (중요 업데이트)
  - RSA 키 획득을 이중화 (API + HTML 파싱)
  - 세션 생성 및 관리 개선
  - 로그인 검증 로직 강화 (리다이렉트 추적)
  - URL을 www.dhlottery.co.kr로 수정
  - User-Agent 및 헤더 최신화
  - 상세한 로그 추가

### 기술적 개선
- 세션 생성 함수 분리 (_create_session)
- RSA 키 획득 실패 시 폴백 메커니즘
- 로그인 상태 추적 개선
- 에러 처리 강화

## [0.4.0] - 2025-02-05

### 수정
- Python import 오류 수정: 상대 import를 절대 import로 변경
- dh_lotto_645.py, dh_lotto_analyzer.py의 import 문 수정
- 애드온 실행 안정화

## [0.3.9] - 2025-02-05

### 수정
- Python 3.12 PEP 668 정책 대응: --break-system-packages 플래그 추가
- Docker 컨테이너 환경에서 pip 패키지 설치 정상화

## [0.3.8] - 2025-02-05

### 수정
- build.json과 build.yaml 파일도 amd64-base:latest로 통일
- 모든 빌드 설정 파일 동기화

## [0.3.7] - 2025-02-05

### 수정
- Dockerfile 빌드 오류 수정
- Alpine Linux 베이스에서 Python 직접 설치하도록 변경
- 베이스 이미지를 amd64-base:latest로 변경
- pip 명령어를 python3 -m pip로 안정화

## [0.3.0] - 2025-02-05

### 추가
- 초기 릴리스
- 동행복권 계정 연동
- 예치금 조회 및 모니터링
- 로또 6/45 번호 통계 분석
  - 번호별 출현 빈도 (최근 50회차)
  - Hot & Cold 번호 분석 (최근 20회차)
- 구매 내역 조회
- 당첨금 조회 및 통계
- 랜덤 번호 생성 기능
- REST API 제공
- Web UI 제공
- Home Assistant 센서 자동 등록

### 기술 스택
- Python 3.11
- FastAPI 웹 서버
- aiohttp 비동기 HTTP 클라이언트
- RSA 암호화 로그인

### 보안
- RSA 공개키 암호화를 통한 안전한 로그인
- Session 관리 최적화
- Timeout 설정 (30초)

## 향후 계획

- MQTT Discovery 지원
- 자동 구매 기능
- 당첨 알림 (Push notification)
- 구매 내역 상세 조회
- 통계 차트 UI
- 다국어 지원
