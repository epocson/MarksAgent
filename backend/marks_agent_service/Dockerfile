FROM python:3.11-slim

WORKDIR /app

# Argument for GitLab Job Token to install private packages
ARG TOKEN
ENV GITLAB_TOKEN=${TOKEN}

# Copy only requirements first to leverage cache
# Note: since context is 'backend/', we copy from current directory relative to Dockerfile or context?
# Actually, inside Docker building context 'backend/', we need to copy from 'marks_agent_service/requirements.txt'
COPY marks_agent_service/requirements.txt .

# Install dependencies (from GitLab registry)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend or specific folders?
# We need 'marks_agent' package and 'marks_agent_service'
COPY marks_agent marks_agent
COPY marks_agent_service marks_agent_service

# Start the agent
CMD ["python", "marks_agent_service/marks_agent.py"]
