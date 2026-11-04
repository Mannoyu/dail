FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY collector collector
COPY generator generator
COPY notifier notifier
COPY shared shared
COPY main.py .
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/app/.venv/bin/python", "main.py"]
