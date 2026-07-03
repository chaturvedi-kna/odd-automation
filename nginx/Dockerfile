FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

# ── Nginx stage ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Inject our config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy compiled React app
COPY --from=frontend-build /app/dist /usr/share/nginx/html

EXPOSE 80
