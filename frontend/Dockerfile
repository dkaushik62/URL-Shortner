FROM node:24.19.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --include=optional
COPY . .
RUN npm run build
FROM scratch AS assets
COPY --from=build /app/dist/ /
