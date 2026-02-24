FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY backend/ ./backend/
COPY rules_config.json ./
RUN pip install --no-cache-dir fastapi uvicorn google-cloud-bigquery google-genai pandas pydantic
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
