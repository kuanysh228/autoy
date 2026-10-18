FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AUTOY_HOME=/app \
    FONT_BOLD=/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf \
    FONT_REGULAR=/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-liberation git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install ".[newsscout]"

RUN useradd --create-home --uid 1000 autoy \
    && mkdir -p /app/credentials /app/data /app/output /app/cache \
    && chown -R autoy:autoy /app
USER autoy
WORKDIR /app

ENTRYPOINT ["autoy"]
CMD ["--help"]
