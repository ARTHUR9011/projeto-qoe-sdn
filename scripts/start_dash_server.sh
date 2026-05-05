#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT/video/dash"

echo "Iniciando servidor DASH em http://10.0.0.1:8000/manifest.mpd ..."
exec python3 -m http.server 8000 --bind 10.0.0.1
