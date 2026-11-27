# Hermes Agent v0.23.4 — `services/hermes`

Integración oficial de **NousResearch Hermes Agent (`v0.23.4`)** para **La Casa del Jean V2** (Issue #11 / F3-02).

## Estructura

- `config/config.yaml`: Plantilla oficial de configuración (`_config_version: 54`, `model`, `agent`, `stt`, `plugins.enabled`). Se monta como `/opt/data/config.template.yaml:ro` y el servicio one-shot `hermes_init` la copia de forma idempotente a `/opt/data/config.yaml` (escribible para migraciones de Hermes) antes de iniciar `hermes`. Sin `mcp_servers` estático para impedir elusión del puente confiable.
- `scripts/init-hermes-config.sh`: Script idempotente ejecutado por `hermes_init` (`depends_on: service_completed_successfully`). No sobrescribe `/opt/data/config.yaml` existente salvo que se defina `HERMES_FORCE_CONFIG_RESET=true`.
- `config/SOUL.md`: Instrucciones operativas acotadas (propuesta/vista previa obligatoria, nunca publicar ni mutar sin confirmación explícita, moneda PAB).
- `plugins/lacasadeljean_mcp_bridge/`: Plugin oficial v0.23.4 (`provides_tools` + `provides_hooks`: `pre_llm_call`, `pre_tool_call`, `on_session_end`) que vincula `sender_id` de Telegram por sesión, bloquea spoofing/herramientas no permitidas, inyecta `X-Actor-Assertion` firmado por llamada vía `httpx.Client` síncrono y ofrece `TrustedApprovalStore` para el flujo de confirmación de #12 sin exponer secretos al LLM.
- `tests/test_hermes_bridge.py`: Pruebas automatizadas de contrato v0.23.4, aislamiento cross-session, anti-spoofing, fallos MCP, lectura E2E contra `services/mcp` (FastMCP ASGI) y validación de Compose/bootstrap.

## Documentación completa

Consulta [docs/fase3-hermes-integration.md](../../docs/fase3-hermes-integration.md) para despliegue en Docker Compose, bootstrap idempotente `hermes_init`, presupuesto de RAM (8 GB Ryzen 3), rutas de facturación (Codex OAuth vs OpenAI API vs Nous Portal) y STT/Visión.
