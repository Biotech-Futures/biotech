# Dev image for Vue + TS (Vite)
FROM node:20-bookworm-slim

USER node
WORKDIR /app

# Copy only manifests first to leverage layer caching
COPY --chown=node:node package.json package-lock.json* ./

# Install deps (ci if lockfile present; otherwise install)
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# For hot-reload with Vite
EXPOSE 5173 24678

# Default: run Vite dev server on all interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
