FROM node:18-alpine

WORKDIR /app

COPY package.json  ./

# Install dependencies, vite, and wget for healthcheck
RUN apk add wget && \
    npm install && \
    npm install -g vite

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
