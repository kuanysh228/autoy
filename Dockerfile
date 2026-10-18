FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    AUTOY_HOME=/app \
    NOTEBOOKLM_HOME=/app/credentials/notebooklm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

RUN useradd --create-home --uid 1000 autoy \
    && mkdir -p /app/credentials /app/data /app/output /app/cache \
    && chown -R autoy:autoy /app
USER autoy
WORKDIR /app

ENTRYPOINT ["autoy"]
CMD ["--help"]
