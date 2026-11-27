# Hermes Agent v0.23.4 — `services/hermes`

Integración oficial de **NousResearch Hermes Agent (`v0.23.4`)** para **La Casa del Jean V2** (Issue #11 / F3-02).

## Estructura

- `config/config.yaml`: Configuración montada en `/opt/data/config.yaml` (solo lectura). Define Telegram en modo long polling saliente (`per_user`), MCP Streamable HTTP privado (`http://mcp:8010/mcp`), lista blanca de 9 herramientas de inventario, visión habilitada, STT integrado y plugin confiable habilitado.
- `config/SOUL.md`: Instrucciones operativas acotadas (propuesta/vista previa obligatoria, nunca publicar ni mutar sin confirmación explícita, moneda PAB).
- `plugins/lacasadeljean_mcp_bridge/`: Plugin confiable de Hermes (`pre_tool_call` + cliente puente MCP) que inyecta `X-Actor-Assertion` por usuario de Telegram, valida `approval_proof` acotado por payload y operador, y opera en modo **fail-closed** contra spoofing.
- `tests/test_hermes_bridge.py`: Pruebas automatizadas con herramientas simuladas, intentos de spoofing, fallos de MCP y validación de configuración.

## Documentación completa

Consulta [docs/fase3-hermes-integration.md](../../docs/fase3-hermes-integration.md) para despliegue en Docker Compose, persistencia `/opt/data`, presupuesto de RAM (8 GB Ryzen 3), rutas de facturación (Codex OAuth vs OpenAI API vs Nous Portal) y STT/Visión.
