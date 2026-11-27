#!/bin/sh
# ==============================================================================
# Idempotent bootstrap for Hermes Agent v0.23.4 /opt/data/config.yaml
# Official Dockerfile creates `useradd -u 10000 -m -d /opt/data hermes`.
# Copies /opt/data/config.template.yaml -> /opt/data/config.yaml on first boot
# with restricted permissions (0700 dir / 0600 file, owned by HERMES_UID:HERMES_GID)
# without overwriting existing configuration unless HERMES_FORCE_CONFIG_RESET=true.
# ==============================================================================
set -eu

DATA_DIR="${HERMES_DATA_DIR:-/opt/data}"
TEMPLATE="${DATA_DIR}/config.template.yaml"
TARGET="${DATA_DIR}/config.yaml"
FORCE_RESET="${HERMES_FORCE_CONFIG_RESET:-false}"
HERMES_UID="${HERMES_UID:-10000}"
HERMES_GID="${HERMES_GID:-10000}"

if [ ! -f "${TEMPLATE}" ]; then
  echo "[hermes_init] ERROR: Plantilla no encontrada en ${TEMPLATE}" >&2
  exit 1
fi

mkdir -p "${DATA_DIR}"
chmod 0700 "${DATA_DIR}"

if [ ! -f "${TARGET}" ] || [ "${FORCE_RESET}" = "true" ]; then
  cp "${TEMPLATE}" "${TARGET}"
  chmod 0600 "${TARGET}"
  if [ "$(id -u)" = "0" ]; then
    chown "${HERMES_UID}:${HERMES_GID}" "${DATA_DIR}" "${TARGET}"
  fi
  echo "[hermes_init] Inicializado ${TARGET} desde ${TEMPLATE} (uid=${HERMES_UID}, gid=${HERMES_GID}, force=${FORCE_RESET})."
else
  chmod 0600 "${TARGET}"
  if [ "$(id -u)" = "0" ]; then
    chown "${HERMES_UID}:${HERMES_GID}" "${DATA_DIR}" "${TARGET}"
  fi
  echo "[hermes_init] Conservando ${TARGET} existente (define HERMES_FORCE_CONFIG_RESET=true para restablecer)."
fi
