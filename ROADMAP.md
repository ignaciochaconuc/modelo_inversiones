# Roadmap

Los estados describen planificación, no autorizan iniciar una fase. Cada fase requiere instrucción explícita.

## Phase 0 — Architecture + Feature Store

**Status:** mostly complete

**Objetivo:** establecer contratos, configuración, protección point-in-time y almacenamiento local.  
**Entregables:** schemas, FeatureRow, Parquet/DuckDB, features cuantitativas base, agentes/LLM/modelos como interfaces, costos, cache, riesgo básico, auditoría, tests y documentación.  
**Finalización aproximada:** contratos estables, suite verde y revisión de los detalles pendientes de Phase 0 sin conexiones externas.

## Phase 1A — Tiingo market data ingestion

**Status:** complete

**Objetivo:** incorporar OHLCV diario, corporate actions y series split-adjusted reproducibles.  
**Entregables:** adapter Tiingo, configuración temporal, calendario XNYS, storage incremental idempotente, CLI, universo fijo de desarrollo y tests mockeados.  
**Finalización aproximada:** cumplida para el alcance local; una descarga real requiere una API key del usuario.

## Phase 1B — Quantitative ingestion pipeline

**Status:** complete

**Objetivo:** conectar datos processed con construcción incremental del Feature Store.  
**Entregables:** selección point-in-time, cobertura/calidad ampliada y pipeline de features para el universo. Massive puede evaluarse más adelante solo como fuente de referencia histórica de tickers.  
**Finalización aproximada:** feature store reproducible para el universo sin look-ahead ni dependencia de la composición actual para backtests válidos.

### Phase 1B.1 correctness review

**Status:** complete

Se corrigieron conteos históricos globales, segmentación por barras retrasadas, targets por sesiones exactas y reemplazo autoritativo de rangos persistidos.

### Phase 1A.1 correction

**Status:** complete

Se separaron latest-basis y normalización split-adjusted as-of, se desacoplaron features de `adjClose` del proveedor y se añadieron anomalías no destructivas para fechas ausentes durante refresh.

### Phase 1C — Real Data Pilot

**Status:** complete for the four-ticker pilot

El runner acotado para SPY, AAPL, MSFT y NVDA valida cobertura raw, corporate actions, ventanas de splits, invariantes point-in-time, features de benchmark, outliers, targets y rendimiento. Produce `data/reports/real_data_pilot.json` sin cambiar fórmulas, schema, elegibilidad ni el universo principal. Los tests permanecen completamente offline. El piloto real fue ejecutado hasta 2026-10-05; esa sesión aún estaba antes del cutoff durante la consulta y quedó clasificada como pendiente, no como gap histórico inesperado.

La revisión de rendimiento reemplazó rescans por fecha en segmentación y conteos históricos por eventos de disponibilidad, y vectorizó los factores de splits. El benchmark sintético y el reporte reproducible permiten detectar regresiones antes de ampliar el universo.

### Phase 1D — Full Development Universe Dataset

**Status:** complete

El workflow reutiliza Tiingo, ingesta incremental, normalización as-of, Feature Store y targets existentes para los 101 activos configurados. Aísla fallos por ticker, valida calidad transversal y rankings, conserva la advertencia de survivorship bias y permite reanudar lotes sin repetir series locales completas.

### Phase 1D.1 — Corporate Action Integrity

**Status:** complete

Aliases provider-specific conservan la identidad interna; una tabla separada
clasifica eventos complejos sin alterar raw. Features usan flags point-in-time,
targets marcan horizontes que cruzan exclusiones y el ranking usa solo labels
training-valid. El reporte separa warm-up esperado y outliers explicados de los
movimientos aún no explicados.

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
