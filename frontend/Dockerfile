# syntax=docker/dockerfile:1

# --- Étape 1 : build des statiques avec Vite ---
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .
RUN npm run build

# --- Étape 2 : service via Nginx ---
FROM nginx:1.27-alpine AS runtime

# Config Nginx : sert le SPA et proxifie /api vers le service backend
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
