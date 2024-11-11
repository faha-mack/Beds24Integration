# nginx/Dockerfile
FROM nginx:latest

# Remove the default Nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy your custom Nginx configuration
COPY ./nginx.conf /etc/nginx/conf.d/default.conf