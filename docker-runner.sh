#!/bin/bash

# define variables
CONTAINER_NAME="nanobot-dev"
DATA_DIR="./nanobot-data"
PROJECT_DIR="."

# clean old container and data
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# remove corrupted data directory
if [ -e "$DATA_DIR" ]; then
  rm -rf "$DATA_DIR"
  echo "cleaned old data directory"
fi

# create data directory
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/skills"
mkdir -p "$DATA_DIR/workspace"
mkdir -p "$DATA_DIR/memory"

# copy workspace files
if [ -d "$PROJECT_DIR/workspace" ]; then
  cp -r "$PROJECT_DIR/workspace/"* "$DATA_DIR/workspace/" 2>/dev/null || true
  echo "workspace files copied to $DATA_DIR/workspace/"
fi

# onboard nanobot to generate default config first
docker run --rm --name "$CONTAINER_NAME" \
  -v "$(pwd)/$DATA_DIR:/root/.nanobot" \
  nanobot onboard

# check onboard success
if [ $? -ne 0 ]; then
  echo "warn: nanobot onboard failed, please check error message"
  exit 1
fi

# copy userskills
if [ -d "$PROJECT_DIR/userskills" ]; then
  cp -r "$PROJECT_DIR/userskills/"* "$DATA_DIR/workspace/skills/"
  echo "userskills copied to $DATA_DIR/workspace/skills/"
else
  echo "warn: userskills directory not found"
fi

# copy custom config.json to overwrite default config
if [ -f "$PROJECT_DIR/config/config.json" ]; then
  cp "$PROJECT_DIR/config/config.json" "$DATA_DIR/config.json"
  echo "config file copied to $DATA_DIR/config.json"
else
  echo "warn: config file not found, use default config"
fi

# start nanobot gateway
docker run -d --name "$CONTAINER_NAME" \
  -p 18790:18790 \
  -v "$(pwd)/$DATA_DIR:/root/.nanobot" \
  -v "$(pwd)/$PROJECT_DIR/nanobot:/app/nanobot" \
  -v "$(pwd)/$PROJECT_DIR/bridge:/app/bridge" \
  nanobot gateway

# check gateway start success
if [ $? -eq 0 ]; then
  echo "nanobot gateway started successfully!"
  echo "container name: $CONTAINER_NAME"
  echo "access address: http://localhost:18790"
else
  echo "warn: nanobot gateway start failed, please check error message"
  exit 1
fi