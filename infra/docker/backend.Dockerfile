FROM python:3.12-slim
# libgomp1 is the OpenMP runtime LightGBM needs.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
COPY config/ /app/config/
RUN uv sync --locked --no-dev
ENV PATH="/app/backend/.venv/bin:$PATH"
USER 1000
