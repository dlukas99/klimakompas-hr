FROM python:3.12-slim
# libgomp1 is the OpenMP runtime for LightGBM; libexpat1 is needed by the GDAL in rasterio.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libexpat1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
COPY config/ /app/config/
RUN uv sync --locked --no-dev
ENV PATH="/app/backend/.venv/bin:$PATH"
# Created here so the named volume mounted on it is writable by the runtime user.
RUN mkdir -p /app/data/raw /app/data/processed /app/data/export && chown -R 1000:1000 /app/data
USER 1000
