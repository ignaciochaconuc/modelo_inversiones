# ADR-006: Agents do not execute trades

## Status

Accepted

## Context

Los agentes procesan fuentes externas y generan texto probabilístico. Pueden recibir información incorrecta o adversarial y no son una frontera segura para custodiar credenciales, límites o autoridad de órdenes.

## Decision

Los agentes solo investigan, explican y producen features estructuradas. No dependen de `execution`, no acceden a brokers, no generan órdenes ejecutables y no modifican límites. El flujo obligatorio es agentes/features, predicción, optimización, Risk Manager y recién entonces ejecución.

## Consequences

Se necesita una canalización con contratos entre etapas, pero los fallos de un agente quedan contenidos. Toda acción es atribuible, el Risk Manager conserva autoridad y una futura automatización no elimina esta separación.
