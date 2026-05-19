FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements-app.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY docs/samples/monthly-reports/monthly_pattern_b_content.template.md ./docs/samples/monthly-reports/monthly_pattern_b_content.template.md
COPY docs/samples/monthly-reports/tools ./docs/samples/monthly-reports/tools

USER app

CMD ["sh", "-c", "uvicorn eb_app.main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8080}"]
