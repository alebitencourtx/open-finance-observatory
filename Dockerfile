FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --create-home worker && mkdir /app/data /app/dist /app/docs && chown worker:worker /app/data /app/dist /app/docs
COPY config ./config
USER worker
ENTRYPOINT ["observatory"]
CMD ["--help"]
