FROM node:22-alpine

WORKDIR /app

# Install dependencies first for better layer caching. The node_modules named
# volume in docker-compose is seeded from this image layer on first run.
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
