# Deployment Guide for University Server

This guide explains how to deploy the `Mark Agent` ecosystem using Docker Compose.

## Prerequisites
- Docker & Docker Compose installed on the server.
- Redis server (or use the one in `docker-compose.yml`).
- (Optional) Nginx as a reverse proxy.

## Step 1: Clone and Switch Branch
```bash
git clone <repository_url>
cd <project_directory>
git checkout ilyabranch
```

## Step 2: Configure Environment
Create a `.env` file in the root:
```env
REDIS_HOST=redis
REDIS_PORT=6379
DB_PATH=/app/data/students_profiles.db
NEXT_PUBLIC_API_URL=http://your-server-ip:8000
```

## Step 3: Start the Ecosystem
```bash
docker-compose up -d --build
```

## Step 4: Verify
- API: `http://your-server-ip:8000/docs`
- Frontend: `http://your-server-ip:3000`

## Production Notes
- **SSL**: If deploying to a public/university domain, use Nginx with Certbot for HTTPS.
- **Persistent Data**: The database is stored in `./backend/data/students_profiles.db`. Ensure this directory has write permissions for the Docker user.
- **Agents**: Currently, the `MarksAgent` and `TutorAgent` need to be running to process the queue. Ensure their environment variables point to the same Redis instance.
