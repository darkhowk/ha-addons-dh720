ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11
FROM ${BUILD_FROM}

# 환경 변수
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 작업 디렉토리
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY *.py ./
COPY run.sh /

# 실행 권한
RUN chmod a+x /run.sh

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8099/health', timeout=5)" || exit 1

# 포트 노출
EXPOSE 8099

# 실행
CMD ["/run.sh"]
