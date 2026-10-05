# ADR-004: Risk Manager authority

## Status

Accepted

## Context

Predicciones y análisis pueden ser inciertos o erróneos. Las restricciones de exposición no deben depender del mismo componente que propone una inversión ni de outputs probabilísticos de LLM.

## Decision

El Risk Manager es independiente y tiene autoridad final para `APPROVE`, `REDUCE` o `BLOCK`. Toda ruta hacia ejecución debe exigir una decisión de riesgo válida. Ni agentes, modelos ni optimizador pueden cambiar límites o eludirlo.

## Consequences

La propuesta de cartera y la orden ejecutable son objetos conceptualmente distintos. Algunas oportunidades serán reducidas o bloqueadas aunque tengan una predicción favorable. Se obtiene una frontera determinista, testeable y auditable.
