FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY caniuse ./caniuse

RUN pip install --no-cache-dir .

ENTRYPOINT ["caniuse"]
CMD ["--help"]
