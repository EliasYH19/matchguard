#!/usr/bin/env bash
# MatchGuard - blue/green demo for the frontend container
#
# Same exercise as the CI/CD lab's blue/green task, applied to this project:
# run the current "blue" frontend image and a "green" candidate side by
# side, then flip a reverse proxy between them without downtime.
#
# Usage:
#   ./scripts/deploy_blue_green.sh up        # start blue on :8080
#   ./scripts/deploy_blue_green.sh green     # build+start green on :8081
#   ./scripts/deploy_blue_green.sh switch    # point router at green
#   ./scripts/deploy_blue_green.sh rollback  # point router back at blue
#   ./scripts/deploy_blue_green.sh down      # tear everything down
#
# Author: Elias

set -euo pipefail
cd "$(dirname "$0")/.."

ROUTER_CONF="/tmp/matchguard-router.conf"
ROUTER_NAME="matchguard-router"

start_router() {
  local target_port="$1"
  cat > "$ROUTER_CONF" <<EOF
events {}
http {
  server {
    listen 9090;
    location / {
      proxy_pass http://host.docker.internal:${target_port};
    }
  }
}
EOF
  docker rm -f "$ROUTER_NAME" >/dev/null 2>&1 || true
  docker run -d --name "$ROUTER_NAME" -p 9090:9090 \
    --add-host=host.docker.internal:host-gateway \
    -v "$ROUTER_CONF:/etc/nginx/nginx.conf:ro" nginx:1.27-alpine >/dev/null
  echo "router now pointing at :${target_port} (public entrypoint: http://localhost:9090)"
}

case "${1:-}" in
  up)
    docker build -t matchguard/frontend:blue frontend
    docker rm -f matchguard-frontend-blue >/dev/null 2>&1 || true
    docker run -d --name matchguard-frontend-blue -p 8080:80 matchguard/frontend:blue
    start_router 8080
    ;;
  green)
    # Make your "minor change" in frontend/ first (e.g. tweak the hero text),
    # then run this to build and start the green version alongside blue.
    docker build -t matchguard/frontend:green frontend
    docker rm -f matchguard-frontend-green >/dev/null 2>&1 || true
    docker run -d --name matchguard-frontend-green -p 8081:80 matchguard/frontend:green
    echo "green is up on :8081 - traffic is still on blue (:8080) until you run 'switch'"
    ;;
  switch)
    start_router 8081
    ;;
  rollback)
    start_router 8080
    ;;
  down)
    docker rm -f matchguard-frontend-blue matchguard-frontend-green "$ROUTER_NAME" >/dev/null 2>&1 || true
    echo "torn down"
    ;;
  *)
    echo "usage: $0 {up|green|switch|rollback|down}"
    exit 1
    ;;
esac
