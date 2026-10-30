FROM node:20-slim AS builder

WORKDIR /app

# Copy dependency files first
COPY frontend/package.json ./
RUN npm install

# Copy frontend source and build Next.js application
COPY frontend ./
RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["npm", "run", "start"]
