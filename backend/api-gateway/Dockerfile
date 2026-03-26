FROM python:3.11-slim

WORKDIR /app

# Argument for GitLab Job Token to install private packages
ARG TOKEN
ENV GITLAB_TOKEN=${TOKEN}

# Copy only requirements first to leverage cache
COPY requirements.txt .

# Install dependencies (from GitLab registry if needed)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Port for uvicorn
EXPOSE 8000

# Healthcheck for orchestration
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

# Start uvicorn
CMD ["uvicorn", "api_gateway:app", "--host", "0.0.0.0", "--port", "8000"]
