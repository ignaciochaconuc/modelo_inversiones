# Especificación funcional actual

## Objetivo y alcance

El proyecto establece la base de un sistema multiagente para análisis y gestión táctica de inversiones de corto/medio plazo. Combinará información cuantitativa y análisis de IA con predicción, construcción de cartera, control de riesgo, backtesting y ejecución progresivamente habilitada.

La versión 1 cubre aproximadamente 100 acciones líquidas de Estados Unidos. Opera conceptualmente con frecuencia diaria, horizonte predictivo principal de 10 días bursátiles y estrategia Long + Cash. Crypto no pertenece a V1; una expansión futura deberá mantener datos y modelos predictivos separados de equities.

## Convenciones operativas

- Decisión: después del cierre del mercado estadounidense.
- Ejecución simulada: apertura de la siguiente sesión bursátil.
- Posiciones máximas: 10–15; la configuración actual fija 15.
- Peso máximo por activo: 10%.
- Exposición máxima: 100%.
- Short selling: no permitido.
- Leverage: no permitido.
- Cash: permitido.
- Benchmark: SPY.

Los valores configurables viven en `config/settings.yaml`, `config/universe.yaml` y `config/risk_limits.yaml`.

## Datos y Feature Store

Toda observación externa puede conservar `observed_at`, `published_at`, `available_at` e `ingested_at`. Para una decisión solo son elegibles registros cuyo `available_at <= decision_time`. Esta condición es obligatoria en datasets históricos y backtests.

El Feature Store representa una fila por `ticker + decision_date`. Su almacenamiento inicial es Parquet y su capa de consulta DuckDB; no se usa PostgreSQL. `FeatureRow` define identificación, variables cuantitativas y estructuradas de agentes, categorías de régimen y targets opcionales.

Las familias de features son: identificación; OHLCV; retornos; momentum; riesgo/volatilidad; tendencia técnica; volumen/liquidez; posición histórica; mercado/sector; News; Analyst; Earnings; Fundamental; Macro; y Event. La lista canónica está en `src/investment_system/data/schemas/features.py`.

## Targets

- `target_return_5d`
- `target_return_10d`
- `target_return_20d`
- `target_positive_10d`
- `target_rank_10d`

El objetivo principal es `target_return_10d = P(t+10) / P(t) - 1`; `target_positive_10d` indica si este retorno es positivo. Targets y features permanecen disjuntos y los targets no pueden participar en una decisión.

## Agentes

- **NewsAgent:** impacto, novedad, polaridad, tipo y horizonte de noticias.
- **AnalystAgent:** consenso, cambios, upgrades/downgrades, precios objetivo y revisiones; prioriza el cambio sobre el nivel absoluto.
- **EarningsAgent:** modos PRE_EARNINGS y POST_EARNINGS para expectativas, sorpresas, guidance, márgenes y sentiment.
- **FundamentalAgent:** separa crecimiento, rentabilidad, balance, valoración y momentum fundamental.
- **MacroAgent:** produce contexto global y regímenes de growth, inflation, rates, liquidity y risk.
- **EventAgent:** mide proximidad, impacto e incertidumbre de eventos; no recomienda compras o ventas.

Cada agente entrega simultáneamente una explicación humana y features estructuradas, junto con confianza, fuentes y timestamps. Actualmente todos son stubs sin búsquedas ni APIs.

## LLM y control de costos

`LLMRouter` selecciona proveedor/modelo por agente y tarea, usando `config/models.yaml`. Los clientes de OpenAI y Ollama son stubs deliberados. El pricing es configurable y no incluye precios reales hardcodeados.

Cada llamada puede registrar tokens, cache, costo estimado, latencia, estado, agente, tarea, ticker, análisis y trade. Se contemplan agregaciones diarias, mensuales, por agente, ticker, análisis y trade.

## Modelos previstos

Se contemplan baseline lineal/logístico, LightGBM, XGBoost, Random Forest y modelos de ranking. Sus objetivos corresponden a regresión (`target_return_10d`), clasificación (`target_positive_10d`) y ranking (`target_rank_10d`). Actualmente solo existen interfaces; no hay entrenamiento ni inferencia real.

## Cartera y riesgo

El optimizador futuro buscará maximizar retorno esperado menos penalizaciones por riesgo y costos de transacción, respetando Long + Cash, máximo de posiciones, peso por activo y ausencia de leverage. Actualmente solo existen modelos de entrada/salida y una interfaz.

El Risk Manager es una autoridad separada que puede `APPROVE`, `REDUCE` o `BLOCK`. Las reglas previstas cubren tamaño y número de posiciones, exposición, drawdown, event risk, pérdida diaria, volatilidad y cash. La implementación actual aplica reglas básicas de long-only, número de posiciones, peso y exposición; las demás permanecen configuradas para desarrollo posterior.

## Backtesting, paper trading y ejecución

El backtesting deberá reproducir decisiones point-in-time después del cierre y fills en la apertura siguiente, con métricas y costos. Actualmente existen contrato y métricas básicas, no un motor funcional completo.

Paper trading corresponde a Phase 8. La ejecución real supervisada y una eventual ejecución automática corresponden a Phases 9 y 10. No existe conexión con brokers ni autorización para órdenes reales.

## Auditoría

Toda decisión futura debe poder reconstruirse mediante features usadas, versión del modelo, predicción, asignación propuesta, decisión de riesgo, acción final, outputs de agentes, fuentes y costo. `DecisionAuditRecord` y `AuditLogger` proporcionan el contrato y persistencia JSONL inicial.
