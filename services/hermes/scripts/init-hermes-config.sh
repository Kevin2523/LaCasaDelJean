#!/bin/sh
# ==============================================================================
# Idempotent bootstrap for Hermes Agent v0.23.4 /opt/data/config.yaml
# Copies /opt/data/config.template.yaml -> /opt/data/config.yaml on first boot
# without overwriting existing configuration unless HERMES_FORCE_CONFIG_RESET=true.
# ==============================================================================
set -eu

DATA_DIR="${HERMES_DATA_DIR:-/opt/data}"
TEMPLATE="${DATA_DIR}/config.template.yaml"
TARGET="${DATA_DIR}/config.yaml"
FORCE_RESET="${HERMES_FORCE_CONFIG_RESET:-false}"

if [ ! -f "${TEMPLATE}" ]; then
  echo "[hermes_init] ERROR: Plantilla no encontrada en ${TEMPLATE}" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}"

if [ ! -f "${TARGET}" ] || [ "${FORCE_RESET}" = "true" ]; then
  cp "${TEMPLATE}" "${TARGET}"
  # Keep config.yaml writable by the container's effective non-root UID for _config_version migrations
  if [ -n "${HERMES_UID:-}" ] && [ -n "${HERMES_GID:-}" ]; then
    chown "${HERMES_UID}:${HERMES_GID}" "${TARGET}"
    chmod 0664 "${TARGET}"
  else
    chmod 0666 "${TARGET}"
  fi
  echo "[hermes_init] Inicializado ${TARGET} desde ${TEMPLATE} (force=${FORCE_RESET})."
else
  echo "[hermes_init] Conservando ${TARGET} existente (define HERMES_FORCE_CONFIG_RESET=true para restablecer)."
fi
