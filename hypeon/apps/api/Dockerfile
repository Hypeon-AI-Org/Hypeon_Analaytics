FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "apps.api.src.app:app", "--host", "0.0.0.0", "--port", "8000"]
