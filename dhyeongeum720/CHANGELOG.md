# Changelog

## [1.0.0] - 2026-02-13

### Added
- Initial release of 연금복권 720+ (DH Lottery Pension 720+) add-on
- Multi-account support
- MQTT Discovery for sensors and buttons
- REST API endpoints
- Web UI interface
- Balance monitoring
- Purchase history tracking

### In Progress
- Final purchase confirmation endpoint (connPro.do 다음 API 분석 필요)
- Purchase flow implementation (makeOrderNo.do → connPro.do → 최종 구매 확정)
- Testing

### TODO
- Implement actual DH Lottery Pension 720+ network flow
- Encrypt payload for makeOrderNo.do and connPro.do
- Discover and implement final purchase confirmation endpoint
- Add error handling for purchase failures
- Add win result checking
- Add notification support
