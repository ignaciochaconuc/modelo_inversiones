# ADR-003: LLM Router

## Status

Accepted

## Context

Los agentes necesitarán modelos locales y remotos con capacidades, costos y políticas distintas. Integrar proveedores directamente en cada agente duplicaría lógica y dificultaría costos, cache, observabilidad y sustitución.

## Decision

Toda llamada de un agente a un modelo pasa por `LLMRouter` o una abstracción común equivalente basada en `BaseLLMClient`. Las rutas se configuran por agente/tarea y permiten Ollama, OpenAI y futuros proveedores. Los agentes nunca llaman SDKs de proveedores directamente.

## Consequences

El router se convierte en frontera obligatoria para selección, control y telemetría. Añadir un proveedor requiere un cliente y configuración, pero no cambios dispersos en agentes. Los clientes actuales permanecen deshabilitados hasta una fase autorizada.
