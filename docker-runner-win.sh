#!/bin/bash

# docker-runner-win.sh - Run nanobot container for Windows/Docker Desktop

# define variables
CONTAINER_NAME="nanobot-dev"
DATA_DIR="nanobot-data"
PROJECT_DIR="."
NAPCAT_PORT=18790
NETWORK_NAME="nanobot-network"

# use absolute path for data directory
DATA_DIR_ABS="$(pwd)/$DATA_DIR"

# check if port is already in use
PORT_IN_USE=$(docker ps -q --filter "publish=$NAPCAT_PORT" 2>/dev/null)
if [ -n "$PORT_IN_USE" ]; then
  echo "warn: port $NAPCAT_PORT is already allocated by container:"
  docker ps --filter "publish=$NAPCAT_PORT" --format "  {{.Names}} ({{.ID}})"
  echo "stopping conflicting container..."
  docker stop $PORT_IN_USE 2>/dev/null || true
  docker rm $PORT_IN_USE 2>/dev/null || true
  echo "conflicting container stopped"
fi

# clean old container
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# check nanobot image exists
if ! docker images | grep -q "^nanobot "; then
  echo "error: nanobot image not found"
  echo "please run: bash docker-rebuild.sh"
  exit 1
fi
echo "nanobot image found"

# create docker network for inter-container communication
if ! docker network ls | grep -q "$NETWORK_NAME"; then
  echo "creating docker network: $NETWORK_NAME..."
  docker network create "$NETWORK_NAME"
  echo "network created"
else
  echo "docker network $NETWORK_NAME already exists"
fi

# remove old data directory
if [ -e "$DATA_DIR_ABS" ]; then
  echo "cleaning old data directory..."
  rm -rf "$DATA_DIR_ABS"
  echo "cleaned old data directory"
fi

# create data directory
echo "creating data directory: $DATA_DIR_ABS"
mkdir -p "$DATA_DIR_ABS/skills"
mkdir -p "$DATA_DIR_ABS/workspace"
mkdir -p "$DATA_DIR_ABS/memory"
echo "created data directory structure"

# copy config if exists
if [ -f "$PROJECT_DIR/config/config.json" ]; then
  mkdir -p "$DATA_DIR_ABS"
  cp "$PROJECT_DIR/config/config.json" "$DATA_DIR_ABS/"
  echo "config copied"
fi

# copy workspace files
if [ -d "$PROJECT_DIR/workspace" ]; then
  cp -r "$PROJECT_DIR/workspace/"* "$DATA_DIR_ABS/workspace/" 2>/dev/null || true
  echo "workspace files copied"
fi

# copy userskills
if [ -d "$PROJECT_DIR/userskills" ]; then
  mkdir -p "$DATA_DIR_ABS/workspace/skills"
  cp -r "$PROJECT_DIR/userskills/"* "$DATA_DIR_ABS/workspace/skills/"
  echo "userskills copied"
fi

# run nanobot gateway
echo "starting nanobot container..."
docker run -d --name "$CONTAINER_NAME" \
  --network "$NETWORK_NAME" \
  -p "$NAPCAT_PORT:$NAPCAT_PORT" \
  -v "$DATA_DIR_ABS:/root/.nanobot" \
  nanobot gateway --port "$NAPCAT_PORT"

# check run success
if [ $? -ne 0 ]; then
  echo "error: failed to start nanobot container"
  exit 1
fi

echo "nanobot container started successfully"
echo "connect napcat to: ws://host.docker.internal:$NAPCAT_PORT"
echo "view logs: docker logs -f $CONTAINER_NAME"
