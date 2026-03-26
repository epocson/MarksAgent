FROM python:3.11-slim

WORKDIR /app

# Argument for GitLab Job Token to install private packages
ARG TOKEN
ENV GITLAB_TOKEN=${TOKEN}

# Copy requirements from the tutorial agent folder
COPY tutorial_agent_new/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy models and agent logic
COPY marks_agent marks_agent
COPY tutorial_agent_new tutorial_agent_new

# Start the agent
CMD ["python", "tutorial_agent_new/tutor_agent.py"]