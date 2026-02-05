ARG BUILD_FROM
FROM ${BUILD_FROM}

# Python 및 필수 패키지 설치
RUN apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    curl

# 환경 변수
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

# 작업 디렉토리
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages --upgrade pip && \
    python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# 애플리케이션 복사
COPY *.py ./
COPY run.sh /

# 실행 권한
RUN chmod a+x /run.sh

# 헬스체크 (선택사항)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD wget --no-verbose --tries=1 --spider http://localhost:60099/health || exit 1

# 포트 노출
EXPOSE 60099

# 실행
CMD ["/run.sh"]
