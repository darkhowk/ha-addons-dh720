# 변경 이력

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
