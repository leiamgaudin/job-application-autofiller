#!/usr/bin/env bash
# Script to launch Google Chrome on macOS with remote debugging enabled on port 9222.
# You can use your normal Chrome profile or an isolated dev profile.

PORT=9222
USER_DATA_DIR="$HOME/Library/Application Support/Google/Chrome-Autofiller-Profile"

echo "Launching Google Chrome with Remote Debugging on port $PORT..."
echo "User data directory: $USER_DATA_DIR"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=$PORT \
  --user-data-dir="$USER_DATA_DIR" \
  --no-first-run \
  --no-default-browser-check &

echo "Chrome launched! You can now navigate to any job application page in this Chrome window,"
echo "and then run 'python main.py' to autofill."
