FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["sh", "-c", "python src/enterprise_pipeline.py enterprise_data/demo_company_raw enterprise_data/demo_company_mapping.json && python src/enterprise_dashboard.py --host 0.0.0.0 --no-browser"]
