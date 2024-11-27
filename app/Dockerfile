# Start with the FastAPI Uvicorn image
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

# Set environment variables for Playwright and Xvfb
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV DISPLAY=:99

# Copy the FastAPI application code
COPY ./ /app

# Set the working directory
WORKDIR /app

# Install necessary dependencies for Playwright and browser rendering in Docker
RUN apt-get update -y && \
    apt-get install -y wget gnupg xvfb libnss3 libxss1 libasound2 fonts-noto-color-emoji x11-apps dbus && \
    pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Expose the application port
EXPOSE 8000

# Start DBus and the application with Xvfb
CMD ["sh", "-c", "service dbus start && Xvfb :99 -screen 0 1024x768x16 & uvicorn main:app --host 0.0.0.0 --port 8000"]