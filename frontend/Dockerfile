# syntax=docker/dockerfile:1.4
# Étage 0 — dépendances Node seules (réutilisé par le build ET le lint conteneurisé,
# make lint — aucun outillage Node requis sur l'hôte).
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
# package-lock absent en dev : on installe sans lock strict.
# Cache BuildKit du dossier de cache npm : les paquets déjà téléchargés sont réutilisés
# d'un build à l'autre (les rebuilds après un changement de package.json passent de
# ~13 min à quelques secondes). N'affecte pas le PREMIER build (cache froid).
RUN --mount=type=cache,target=/root/.npm npm install --no-audit --no-fund

# Étage 1 — build du bundle Vite.
FROM deps AS build
COPY . .
RUN npm run build

# Étage 2 — service statique + reverse proxy (config montée par le compose).
FROM nginx:1.27-alpine
# Le bundle statique est servi par Nginx ; la config (nginx.conf) et les certificats
# TLS sont fournis par docker-compose (source unique dans deploy/nginx).
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
