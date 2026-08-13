# Stage 1: Build
FROM node:20-alpine AS builder

ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}

WORKDIR /app

# Copy only frontend dependency manifests first for layer caching.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy the rest of the frontend source.
COPY frontend/ .
RUN npm run build

# Stage 2: Serve with unprivileged nginx
FROM nginxinc/nginx-unprivileged:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/frontend-nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:8080/index.html || exit 1

CMD ["nginx", "-g", "daemon off;"]
