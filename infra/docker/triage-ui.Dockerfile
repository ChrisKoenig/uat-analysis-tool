# =============================================================================
# Triage UI — React admin dashboard (Vite build → nginx)
# =============================================================================
# Build from project root:
#   az acr build -r acrgcsdevgg4a6y -f infra/docker/triage-ui.Dockerfile -t gcs/triage-ui:latest .
# =============================================================================

# ── Stage 1: Build the React app ──
FROM node:20-alpine AS build
WORKDIR /app

COPY apps/triage-ui/package.json apps/triage-ui/package-lock.json ./
RUN npm ci --production=false

COPY apps/triage-ui/ ./
RUN chmod +x node_modules/.bin/* && npx vite build

# ── Stage 2: Serve with nginx + basic auth ──
FROM nginx:alpine

# Install apache2-utils for htpasswd, then generate credentials
RUN apk add --no-cache apache2-utils \
    && htpasswd -bc /etc/nginx/.htpasswd gcs 'TriageGCS2026!' \
    && apk del apache2-utils

# Copy nginx config template (envsubst replaces ${API_URL} at startup)
COPY infra/docker/nginx-triage.conf.template /etc/nginx/templates/default.conf.template

# Copy built React app
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine entrypoint already runs envsubst on /etc/nginx/templates/*.template
# and writes output to /etc/nginx/conf.d/. No custom CMD needed.
