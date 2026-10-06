FROM node:24-alpine AS build

RUN npm install -g pnpm@12

WORKDIR /app

COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY apps/web .
RUN pnpm build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
