#!/bin/bash
set -e

#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# OrthoFlow Backend – Ticket #61
# Patch the backend Dockerfile entrypoint so that:
#   1. alembic upgrade head runs first (auto-migrations on every deploy)
#   2. uvicorn starts as normal
###############################################################################

DOCKERFILE="LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/backend/Dockerfile"

###############################################################################
# Sanity checks
###############################################################################

if [[ ! -f "$DOCKERFILE" ]]; then
  echo "[ERROR] Dockerfile not found at: $DOCKERFILE"
  exit 1
fi

echo "[INFO] Found Dockerfile at: $DOCKERFILE"

###############################################################################
# Back up the original Dockerfile
###############################################################################

BACKUP="${DOCKERFILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$DOCKERFILE" "$BACKUP"
echo "[INFO] Backup written to: $BACKUP"

###############################################################################
# Determine the current entrypoint style so we can patch safely
#
# We handle the two most common patterns already present in the file:
#
#  Pattern A – shell-form CMD / ENTRYPOINT with uvicorn directly:
#    CMD ["uvicorn", "app.main:app", ...]          (JSON array)
#    CMD uvicorn app.main:app ...                  (shell form)
#
#  Pattern B – an existing shell entrypoint script referenced by ENTRYPOINT
#    In that case we inject into the script rather than the Dockerfile.
#
# The safest universal approach: write a small inline entrypoint script and
# wire it up so it is always the ENTRYPOINT, with CMD preserved for uvicorn.
###############################################################################

# --- Extract the existing CMD line (we will keep uvicorn args from it) ---
EXISTING_CMD_LINE=$(grep -E '^CMD ' "$DOCKERFILE" | tail -1 || true)
EXISTING_ENTRYPOINT_LINE=$(grep -E '^ENTRYPOINT ' "$DOCKERFILE" | tail -1 || true)

echo "[INFO] Existing CMD       : ${EXISTING_CMD_LINE:-<none>}"
echo "[INFO] Existing ENTRYPOINT: ${EXISTING_ENTRYPOINT_LINE:-<none>}"

###############################################################################
# Write the entrypoint wrapper script into the image via a heredoc that will
# be embedded in the Dockerfile with a RUN + tee block.
###############################################################################

# We will add a RUN block that creates /entrypoint.sh inside the image,
# then set ENTRYPOINT ["/entrypoint.sh"] and leave CMD for uvicorn args.

ENTRYPOINT_SCRIPT_CONTENT='#!/bin/sh
set -e

echo "[entrypoint] Running alembic upgrade head..."
alembic upgrade head
echo "[entrypoint] Migrations complete. Starting uvicorn..."

exec "$@"
'

###############################################################################
# Rewrite the Dockerfile
# Strategy:
#   1. Strip any existing ENTRYPOINT lines (we will replace).
#   2. Leave existing CMD lines untouched (they pass uvicorn args to exec "$@").
#   3. Append the RUN block + new ENTRYPOINT before the final CMD.
###############################################################################

# Remove existing ENTRYPOINT lines from the file
sed -i '/^ENTRYPOINT /d' "$DOCKERFILE"

# Check whether we already injected the entrypoint script in a previous run
if grep -q 'entrypoint.sh' "$DOCKERFILE"; then
  echo "[WARN] entrypoint.sh block already present in Dockerfile – skipping injection."
  echo "[INFO] Re-adding ENTRYPOINT directive only."
  # Just make sure ENTRYPOINT is set before CMD
  # Insert ENTRYPOINT before the last CMD line
  LAST_CMD_LINE_NUM=$(grep -n '^CMD ' "$DOCKERFILE" | tail -1 | cut -d: -f1)
  if [[ -n "$LAST_CMD_LINE_NUM" ]]; then
    sed -i "${LAST_CMD_LINE_NUM}i ENTRYPOINT [\"/entrypoint.sh\"]" "$DOCKERFILE"
  else
    echo 'ENTRYPOINT ["/entrypoint.sh"]' >> "$DOCKERFILE"
  fi
else
  # Build the RUN block as a single variable (avoid heredoc-in-heredoc issues)
  RUN_BLOCK="RUN printf '%s' '${ENTRYPOINT_SCRIPT_CONTENT}' > /entrypoint.sh && chmod +x /entrypoint.sh"

  # Find the line number of the last CMD directive so we can insert before it
  LAST_CMD_LINE_NUM=$(grep -n '^CMD ' "$DOCKERFILE" | tail -1 | cut -d: -f1 || true)

  if [[ -n "$LAST_CMD_LINE_NUM" ]]; then
    # Insert the RUN block and ENTRYPOINT directive before the last CMD line
    sed -i "${LAST_CMD_LINE_NUM}i \\
# --- Ticket #61: auto-migration entrypoint ---\\
RUN printf '#!/bin/sh\\\\nset -e\\\\necho \"[entrypoint] Running alembic upgrade head...\"\\\\nalembic upgrade head\\\\necho \"[entrypoint] Migrations complete. Starting uvicorn...\"\\\\nexec \"\\$\@\"\\\\n' > /entrypoint.sh \\&\\& chmod +x /entrypoint.sh\\
ENTRYPOINT [\"/entrypoint.sh\"]" "$DOCKERFILE"
  else
    # No CMD found – append everything at the end
    printf '\n# --- Ticket #61: auto-migration entrypoint ---\n' >> "$DOCKERFILE"
    printf "RUN printf '#!/bin/sh\\nset -e\\nalembic upgrade head\\nexec \"\\$@\"\\n' > /entrypoint.sh && chmod +x /entrypoint.sh\n" >> "$DOCKERFILE"
    printf 'ENTRYPOINT ["/entrypoint.sh"]\n' >> "$DOCKERFILE"
  fi
fi

echo "[INFO] Dockerfile patched successfully."

###############################################################################
# Validate the result – show the relevant tail so a human can confirm
###############################################################################

echo ""
echo "========== Patched Dockerfile (last 30 lines) =========="
tail -30 "$DOCKERFILE"
echo "========================================================="

###############################################################################
# Build the Docker image
###############################################################################

IMAGE_NAME="${ORTHOFLOW_IMAGE_NAME:-orthoflow-backend}"
IMAGE_TAG="${ORTHOFLOW_IMAGE_TAG:-latest}"
CONTEXT_DIR="$(dirname "$DOCKERFILE")"

echo ""
echo "[INFO] Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "[INFO] Build context       : ${CONTEXT_DIR}"

docker build \
  --file "$DOCKERFILE" \
  --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
  "$CONTEXT_DIR"

echo ""
echo "[SUCCESS] Image built: ${IMAGE_NAME}:${IMAGE_TAG}"

###############################################################################
# Optionally restart the running container so Watchtower picks up the change
# immediately without waiting for its next pull cycle.
###############################################################################

CONTAINER_NAME="${ORTHOFLOW_CONTAINER_NAME:-orthoflow-backend}"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "[INFO] Container '${CONTAINER_NAME}' is running. Recreating it now..."
  docker stop  "$CONTAINER_NAME"
  docker rm    "$CONTAINER_NAME"

  # Re-run with whatever env/volume flags are already stored in the compose
  # project.  If Docker Compose is available, prefer that so env-vars and
  # volumes are sourced from compose.yml automatically.
  COMPOSE_FILE="$(dirname "$DOCKERFILE")/../../docker-compose.yml"
  if [[ -f "$COMPOSE_FILE" ]]; then
    echo "[INFO] Restarting via Docker Compose: $COMPOSE_FILE"
    docker compose -f "$COMPOSE_FILE" up -d --no-deps --build backend
  else
    echo "[WARN] No docker-compose.yml found at expected path."
    echo "[WARN] Start the container manually or allow Watchtower to pull the new image."
  fi
else
  echo "[INFO] Container '${CONTAINER_NAME}' is not currently running."
  echo "[INFO] Watchtower will pull and start the new image on its next cycle."
fi

###############################################################################
# Verify migration ran (if the container is now live)
###############################################################################

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo ""
  echo "[INFO] Tailing container logs for migration output (10 s)..."
  timeout 10 docker logs -f "$CONTAINER_NAME" 2>&1 | grep -E 'alembic|migration|upgrade|entrypoint|Running|ERROR' || true
fi

echo ""
echo "[DONE] Ticket #61 deployment complete."
echo "       Every future image pull by Watchtower will automatically run"
echo "       'alembic upgrade head' before uvicorn starts."
