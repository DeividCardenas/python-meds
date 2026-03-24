FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ARG VITE_API_URL=http://localhost:8000/graphql
ENV VITE_API_URL=${VITE_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /app/dist ./dist
RUN npm install -g serve
USER app
EXPOSE 3000
CMD ["serve", "-s", "dist", "-l", "3000"]
