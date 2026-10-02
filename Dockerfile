FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && groupadd --system context-invariant \
    && useradd --system --gid context-invariant --home-dir /nonexistent context-invariant

USER context-invariant

ENTRYPOINT ["context-invariant"]
CMD ["--help"]
