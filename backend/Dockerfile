FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1


COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

RUN pip install --upgrade pip && \
    pip install -e .

EXPOSE 8000

CMD ["uvicorn", "clauseguard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
