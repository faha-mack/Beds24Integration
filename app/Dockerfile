# Start with the FastAPI Uvicorn image
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

# Set environment variables for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy the FastAPI application code
COPY ./ /app

# Set the working directory
WORKDIR /app

# Install necessary dependencies for Playwright and browser rendering in Docker
RUN apt-get update -y && \
    apt-get install -y wget gnupg libnss3 libxss1 libasound2 fonts-noto-color-emoji \
    libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libdrm2 libxkbcommon0 && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Expose the application port
EXPOSE 8000

# Start the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]