FROM node:20-alpine as frontend-build

WORKDIR /app
COPY frontend/package.json .
RUN npm install

COPY frontend .
RUN npm run build

FROM nginx:alpine

COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy built frontend into nginx
COPY --from=frontend-build /app/dist /usr/share/nginx/html