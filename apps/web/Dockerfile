# Multi-stage. The `dev` stage is intentionally LAST so a plain
# `build: { context: ../apps/web }` (no target) still produces the dev image,
# keeping the dev compose unchanged. Production builds target the `prod` stage.

# --- deps: install node_modules (shared by build and dev) ---
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

# --- build: produce the static production bundle ---
FROM deps AS build
COPY . .
# Empty API base => relative URLs (/api/v1, /health); nginx proxies them, so the
# same bundle works behind any host without a rebuild.
ENV VITE_API_BASE_URL=""
RUN npm run build

# --- prod: serve the bundle via nginx, reverse-proxying the API ---
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

# --- dev: Vite live-reload server (default target for the dev compose) ---
FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
