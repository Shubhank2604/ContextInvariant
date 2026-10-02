FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && groupadd --system contextos \
    && useradd --system --gid contextos --home-dir /nonexistent contextos

USER contextos

ENTRYPOINT ["contextos"]
CMD ["--help"]
