#!/bin/bash
# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate the virtual environment
source "$DIR/venv/bin/activate"

# Run the UI
python "$DIR/ui.py" "$@"
