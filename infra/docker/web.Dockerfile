FROM node:26-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2.11.7-alpine
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
