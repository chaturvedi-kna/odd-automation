#!/bin/bash

set -e

############################################
# Configuration
############################################

WORKDIR="$(pwd)"
COMPOSE_FILE="${WORKDIR}/docker-compose.yml"

PEER_SCRIPT="${WORKDIR}/daimeter_PeerRouteRule_clenaup.sh"
ADDRESS_SCRIPT="${WORKDIR}/daimeter_Rbar_AddressRange_clenaup.sh"

CRON_TIME="20 4 * * *"

cd "${WORKDIR}"

############################################
# Flags
############################################

DO_CRON=false
DO_BUILD=false
DO_UP=false
DO_DOWN=false

usage() {
    echo "Usage:"
    echo "  ./start.sh [--cron] [--build] [--up] [--down] [--all]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cron)
            DO_CRON=true
            ;;
        --build)
            DO_BUILD=true
            ;;
        --up)
            DO_UP=true
            ;;
        --down)
            DO_DOWN=true
            ;;
        --all)
            DO_CRON=true
            DO_BUILD=true
            DO_UP=true
            ;;
        *)
            usage
            ;;
    esac
    shift
done

############################################
# Ensure Cron Jobs
############################################

setup_cron() {

    TMP=$(mktemp)

    crontab -l 2>/dev/null > "$TMP" || true

    PEER_JOB="${CRON_TIME} ${PEER_SCRIPT}"
    ADDRESS_JOB="${CRON_TIME} ${ADDRESS_SCRIPT}"

    if grep -Fq "${PEER_SCRIPT}" "$TMP"; then
        echo "[OK] PeerRouteRule cleanup cron already exists."
    else
        echo "$PEER_JOB" >> "$TMP"
        echo "[ADD] PeerRouteRule cleanup cron added."
    fi

    if grep -Fq "${ADDRESS_SCRIPT}" "$TMP"; then
        echo "[OK] AddressRange cleanup cron already exists."
    else
        echo "$ADDRESS_JOB" >> "$TMP"
        echo "[ADD] AddressRange cleanup cron added."
    fi

    crontab "$TMP"
    rm -f "$TMP"
}

############################################
# Docker Commands
############################################

# Detect the available compose engine: podman-compose → podman compose → docker compose
compose_cmd() {
    if command -v podman-compose >/dev/null 2>&1; then
        echo "podman-compose"
    elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
        echo "podman compose"
    elif command -v docker >/dev/null 2>&1; then
        echo "docker compose"
    else
        echo ""
    fi
}

COMPOSE="$(compose_cmd)"
if [ -z "${COMPOSE}" ]; then
    echo "ERROR: no compose engine found (install podman-compose, podman >= 4.7, or docker)."
    exit 1
fi
echo "Using compose engine: ${COMPOSE}"

build() {
    echo "Building images..."
    ${COMPOSE} -f "${COMPOSE_FILE}" build
}

up() {
    echo "Starting containers..."
    ${COMPOSE} -f "${COMPOSE_FILE}" up -d
}

down() {
    echo "Stopping containers..."
    ${COMPOSE} -f "${COMPOSE_FILE}" down
}

############################################
# Execute
############################################

$DO_CRON && setup_cron
$DO_BUILD && build
$DO_UP && up
$DO_DOWN && down

echo "Done."