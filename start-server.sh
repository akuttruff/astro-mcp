#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python -m astro_mcp.server
