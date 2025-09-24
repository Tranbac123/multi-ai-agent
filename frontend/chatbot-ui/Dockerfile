FROM node:18-alpine

WORKDIR /app

# Install serve globally
RUN npm install -g serve

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["serve", "-s", "build", "-l", "3000"]




