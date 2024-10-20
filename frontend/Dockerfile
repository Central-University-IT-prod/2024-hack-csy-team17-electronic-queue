FROM nginx:latest

# Скопировать файлы конфигурации Nginx
COPY nginx_config/nginx.conf /etc/nginx/conf.d/default.conf

# Скопировать файлы контента вашего приложения
COPY src /var/www/html

# Перезапустить Nginx
EXPOSE 80