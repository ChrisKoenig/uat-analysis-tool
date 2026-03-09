# =============================================================================
# Field Portal UI — React SPA for field submissions (Vite build → nginx)
# =============================================================================
# Build from project root:
#   az acr build -r acrgcsdevgg4a6y -f infra/docker/field-ui.Dockerfile -t gcs/field-ui:latest .
#
# MSAL auth is DISABLED at build time via VITE_AUTH_DISABLED=true.
# Access control is handled by nginx basic auth instead.
# =============================================================================

# ── Stage 1: Build the React app with auth disabled ──
FROM node:20-alpine AS build
WORKDIR /app

COPY apps/field-portal/ui/package.json apps/field-portal/ui/package-lock.json ./
RUN npm ci --production=false

COPY apps/field-portal/ui/ ./

# Build with MSAL auth disabled — nginx basic auth replaces it
ENV VITE_AUTH_DISABLED=true
RUN chmod +x node_modules/.bin/* && npx vite build

# ── Stage 2: Serve with nginx + basic auth ──
FROM nginx:alpine

# Install apache2-utils for htpasswd, then generate credentials
RUN apk add --no-cache apache2-utils \
    && htpasswd -bc /etc/nginx/.htpasswd gcs 'TriageGCS2026!' \
    && apk del apache2-utils

# Copy nginx config template (envsubst replaces ${API_URL} at startup)
COPY infra/docker/nginx-field.conf.template /etc/nginx/templates/default.conf.template

# Copy built React app
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine entrypoint already runs envsubst on /etc/nginx/templates/*.template
