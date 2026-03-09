FROM node:20-alpine AS build

WORKDIR /app

# Copy everything (respects .dockerignore)
COPY . .

# Build partner-components, then remove its node_modules to avoid conflicts
RUN cd partner-components && npm install && npm run build && rm -rf node_modules

# Install main app deps (links local partner-components dist via file: reference)
RUN npm ci

# Build the frontend
ENV VITE_API_URL=""
RUN npm run build

# Serve with nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
