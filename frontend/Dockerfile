# MatchGuard - frontend
# Just static files behind nginx, no build step needed since it's plain
# HTML/CSS/JS (same approach as the Lab Session 01 static site exercise).
# Author: Elias
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

# nginx.conf and the Dockerfile itself don't need to be served as static
# assets, but leaving them there doesn't hurt anything for this project.

EXPOSE 80
