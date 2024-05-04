#!/bin/bash

source venv/bin/activate

source .env

# If the DATABASE_URL environment variable is not set, set a default value
if [ -z "$DATABASE_PATH" ]; then
	export DATABASE_PATH=./data/app.db
fi

# If the LOG_PATH environment variable is not set, set a default value
if [ -z "$LOG_PATH" ]; then
	export LOG_PATH=./data/app.server.log
fi

# TODO: replace with a production-ready server
export IPFS_HOST=localhost
export IPFS_PORT=5001
export IPFS_GATEWAY=http://localhost:8080
export DEBUG=False
python3 src/server.py >/dev/null 2>&1

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0
