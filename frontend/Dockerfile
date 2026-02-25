# Build context: frontend/ directory
#
# ── Stage 1: dependency installer ────────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

# Copy package files only — cache this layer unless deps change
COPY package.json package-lock.json* ./

RUN npm ci --omit=dev

# ── Stage 2: builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy node_modules from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy all source files
COPY . .

# Build argument for the backend URL (injected at build time by docker-compose)
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE

# Disable Next.js telemetry in CI/Docker builds
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ── Stage 3: runtime ──────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Copy only the files needed to run the built app
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null 2>&1 || exit 1

CMD ["node", "server.js"]
