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

EXPOSE 60100

CMD ["/run.sh"]
