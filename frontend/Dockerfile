# Étage 1 — build du bundle Vite.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
# package-lock absent en dev : on installe sans lock strict.
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# Étage 2 — service statique + reverse proxy (config montée par le compose).
FROM nginx:1.27-alpine
# Le bundle statique est servi par Nginx ; la config (nginx.conf) et les certificats
# TLS sont fournis par docker-compose (source unique dans deploy/nginx).
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
