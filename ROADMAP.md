# Roadmap

Los estados describen planificación, no autorizan iniciar una fase. Cada fase requiere instrucción explícita.

## Phase 0 — Architecture + Feature Store

**Status:** mostly complete

**Objetivo:** establecer contratos, configuración, protección point-in-time y almacenamiento local.  
**Entregables:** schemas, FeatureRow, Parquet/DuckDB, features cuantitativas base, agentes/LLM/modelos como interfaces, costos, cache, riesgo básico, auditoría, tests y documentación.  
**Finalización aproximada:** contratos estables, suite verde y revisión de los detalles pendientes de Phase 0 sin conexiones externas.

## Phase 1 — Market data ingestion + quantitative baseline

**Status:** next

**Objetivo:** incorporar OHLCV diario confiable y construir datasets causales reproducibles.  
**Entregables:** adaptador de proveedor, normalización, validación, calendario bursátil, universe de ~100 activos y pipeline incremental de features.  
**Finalización aproximada:** histórico versionado, controles de calidad y feature store reproducible sin look-ahead.

## Phase 2 — Backtesting engine

**Objetivo:** simular decisiones after-close y ejecución next-open.  
**Entregables:** loop temporal, fills, costos, cartera, benchmark, métricas y auditoría.  
**Finalización aproximada:** backtests deterministas con pruebas explícitas de ausencia de leakage.

## Phase 3 — Baseline predictive models

**Objetivo:** establecer benchmarks simples para regresión, clasificación y ranking.  
**Entregables:** splits temporales, pipelines, métricas, versionado y baselines lineal/logístico antes de modelos complejos.  
**Finalización aproximada:** evaluación out-of-sample reproducible y comparación contra baselines ingenuos.

## Phase 4 — News Agent

**Objetivo:** convertir noticias point-in-time en análisis explicable y features estructuradas.  
**Entregables:** fuente, deduplicación/cache, scoring, citas, router y costos.  
**Finalización aproximada:** resultados validados, trazables y sin acceso a ejecución.

## Phase 5 — Analyst + Earnings Agents

**Objetivo:** incorporar cambios de consenso y análisis pre/post earnings.  
**Entregables:** datos de analistas, revisiones, calendarios/resultados, modos PRE/POST y features correspondientes.  
**Finalización aproximada:** timestamps auditables y evaluación incremental sobre el baseline.

## Phase 6 — Fundamental + Macro + Event Agents

**Objetivo:** añadir calidad/valoración, regímenes globales y riesgos de eventos.  
**Entregables:** fuentes point-in-time, scores separados, regímenes y flags de eventos.  
**Finalización aproximada:** features estables, documentadas y evaluadas sin mezclar análisis con órdenes.

## Phase 7 — Portfolio optimization + Risk Manager

**Objetivo:** transformar forecasts en propuestas long-only y aplicar autoridad de riesgo.  
**Entregables:** objetivo retorno/riesgo/costo, restricciones, estado de cartera y reglas completas de APPROVE/REDUCE/BLOCK.  
**Finalización aproximada:** ninguna propuesta puede llegar a ejecución sin decisión de riesgo testeada.

## Phase 8 — Paper trading

**Objetivo:** operar el pipeline completo con dinero simulado.  
**Entregables:** adaptador paper, scheduler, reconciliación, monitoreo y auditoría.  
**Finalización aproximada:** operación estable durante un período acordado, sin órdenes reales.

## Phase 9 — Supervised live trading

**Objetivo:** permitir ejecución real con aprobación humana explícita.  
**Entregables:** integración segura con broker, gestión de secrets, controles operacionales, kill switch y aprobación.  
**Finalización aproximada:** revisión de seguridad/riesgo y trazabilidad completa con exposición limitada.

## Phase 10 — Potential automated execution

**Objetivo:** evaluar ejecución automática bajo límites estrictos.  
**Entregables:** gobernanza, monitoreo, alertas, fail-safe, rollback y aprobación operacional formal.  
**Finalización aproximada:** solo tras evidencia suficiente de fases anteriores y autorización explícita; puede decidirse no implementarla.

## Expansión futura — Crypto

**Objetivo:** explorar crypto sin contaminar supuestos de equities.  
**Entregables:** universo, calendario 24/7, datos, riesgo y modelos predictivos separados.  
**Finalización aproximada:** arquitectura y validación específicas; no reutilizar modelos de equities sin evidencia.
