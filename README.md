# AI Investment System

Base modular para un sistema multiagente de análisis de acciones estadounidenses a frecuencia diaria. Phase 1A incorpora ingestión EOD desde Tiingo, corporate actions explícitas, calendario XNYS y series split-adjusted; no realiza entrenamiento ni trading.

## Documentación

- [Especificación funcional](PROJECT_SPEC.md)
- [Arquitectura y dependencias](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Guía para agentes de IA](AGENTS.md)
- [Guía de contribución](CONTRIBUTING.md)
- [Architecture Decision Records](docs/decisions/)

## Arquitectura y flujo

El código vive bajo `src/investment_system` para evitar colisiones con paquetes genéricos de Python. Los datos se validan con Pydantic, se escriben en Parquet y se consultan con DuckDB.

1. Una fuente produce observaciones con `observed_at`, `published_at`, `available_at` e `ingested_at`.
2. Antes de construir un dataset, `available_at <= decision_time` impide usar información futura.
3. El motor cuantitativo transforma OHLCV en una fila por `ticker + decision_date`.
4. Los agentes producen un informe explicable y `structured_features` numéricas.
5. Toda petición LLM pasa por `LLMRouter`; los clientes incluidos son stubs y el costo se registra por separado.
6. Features y targets tienen listas distintas. Los targets futuros nunca entran en `model_features()`.
7. Las decisiones futuras quedan auditadas y pasan obligatoriamente por Risk Manager antes de ejecución.

## Componentes

- `core`: configuración YAML/env, enums, tiempo, excepciones y logging JSON.
- `data`: schemas point-in-time, validadores, fuentes y almacenamiento Parquet/DuckDB.
- `features`: cálculos puros con pandas/numpy, builder y registro de columnas.
- `agents`: contrato común y stubs para News, Analyst, Earnings, Fundamental, Macro y Event.
- `llm`: contratos de cliente/router, pricing configurable, tracking y cache local por hash.
- `models`, `portfolio`, `risk`, `backtesting`, `execution`: interfaces para fases posteriores.
- `audit`: registro serializable para reconstruir decisiones.

## Protección contra leakage

La regla invariante es `available_at <= decision_time`. `FeatureRow` separa identificación, features y targets; `FEATURE_COLUMNS` y `TARGET_COLUMNS` son disjuntos y `model_features()` nunca devuelve targets. El target principal es `P(t+10) / P(t) - 1`. Las señales se calculan tras el cierre y una ejecución simulada corresponde a la apertura de la siguiente sesión (el calendario bursátil completo queda para backtesting).

## Instalación

Requiere Python 3.11 o posterior.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
pytest
```

Copie `.env.example` a `.env` si necesita configurar proveedores en fases futuras. Los precios de LLM están en `config/models.yaml` y comienzan vacíos deliberadamente.

```bash
python scripts/validate_data.py
python scripts/build_feature_store.py
python scripts/ingest_market_data.py --ticker AAPL --start 2020-01-01 --dry-run
python scripts/build_quantitative_feature_store.py --ticker AAPL --start 2010-01-01 --dry-run
python scripts/run_real_data_pilot.py --end 2026-10-05 --with-targets
python scripts/build_full_universe.py --raw-start 2009-01-01 --feature-start 2010-01-01 --end 2026-10-05 --with-targets
```

Para una descarga real, defina `TIINGO_API_KEY` solo en el `.env` local y quite `--dry-run`. También puede usar `--universe`; el procesamiento es secuencial y respeta el throttling configurado.

Los datasets quedan separados en `data/raw/tiingo/daily`, `data/raw/tiingo/corporate_actions` y `data/processed/market/split_adjusted_latest`. Este último usa la base accionaria más reciente y no debe utilizarse ciegamente en backtests; las decisiones históricas requieren la vista split-adjusted as-of. El universo versionado es fijo: no es point-in-time e introduce survivorship bias.

Phase 1D.1 añade `config/provider_symbols.yaml` para aliases request-only y
`data/processed/market/corporate_action_events` para clasificaciones auditables.
Los eventos complejos no reescriben precios: marcan contaminación separada de
features y targets. `config/corporate_action_overrides.yaml` permite revisiones
versionadas sin ajustes manuales de precio.

El Feature Store cuantitativo se particiona anualmente en `data/features/quantitative/year=YYYY/data.parquet`. Los targets opcionales se guardan físicamente aparte en `data/targets/quantitative`; una construcción de inferencia no usa `--with-targets`. `manifest.json` y `build_report.json` registran versiones, universo, cobertura, nulos y calidad.

`model_eligible` sigue describiendo capacidad de inferencia. La elegibilidad de
entrenamiento solo se crea en un join supervisado explícito y combina ese flag
con contaminación de features y validez/contaminación del horizonte objetivo.

Los rebuilds reemplazan autoritativamente las filas del ticker y rango solicitados, por lo que una corrección puede eliminar registros obsoletos. Los targets de 5/10/20 días apuntan a la sesión bursátil exacta; si falta su barra, quedan NULL. `history_count` es acumulativo por decision time y no se reinicia después de splits.

El piloto acotado de Phase 1C orquesta SPY, AAPL, MSFT y NVDA (configurables por CLI), audita raw, splits reales, point-in-time, benchmark, outliers y targets, y escribe `data/reports/real_data_pilot.json`. `--skip-download` permite reconstruir y diagnosticar datos locales sin red; `--skip-features` audita un Feature Store ya construido. Las reglas de outliers son solo diagnósticas y nunca alteran observaciones.

`python scripts/benchmark_feature_builder.py` ejecuta un benchmark sintético opcional de 4.500 sesiones. No forma parte de pytest. El manifest y el reporte del piloto incluyen versiones, configuración relevante, timestamp UTC y metadata Git best-effort; si Git no puede ejecutarse, sus campos quedan `null` sin interrumpir el pipeline.

Phase 1D reutiliza el mismo pipeline mediante `build_full_universe.py` y escribe `data/reports/full_universe_build.json`. La ejecución es incremental y reanudable: `--skip-features` continúa descargas pendientes sin reconstruir el dataset tras cada lote, y `--skip-download` realiza el rebuild final desde raw local. `--skip-provider-ticker` solo excluye explícitamente un símbolo ya revisado; nunca inventa un mapping.

`python scripts/diagnose_provider_symbol.py BRK.B --start 2009-01-01` consulta
metadata y cobertura sin persistir datos. Para un alias revisado, una ingesta
puntual puede usar `--force-full-refresh`; el adapter solicita el alias, pero raw,
features y targets conservan el ticker interno.

## Estado y roadmap

Son funcionales los schemas, validación point-in-time, adapter Tiingo EOD, actualización incremental, calendario XNYS, normalización as-of, Feature Store cuantitativo, targets separados, cache y reglas básicas de riesgo. Son contratos/stubs: clientes OpenAI/Ollama, modelos predictivos, optimización, backtesting completo y ejecución.

Phase 2A.3 añade contratos, `PortfolioLedger`, loop temporal por sesiones XNYS y
reportes económicos versionados. Performance, costos, turnover, exposición y un
benchmark SPY interno se calculan sin mezclar reporting con simulación. Phase 2B
añade SPY buy-and-hold, equal-weight diario y momentum 20d top-10 como generadores
de allocations, sin ML ni targets. La implementación está completa; la validación
real se amplía en Phase 2B.1 con treatments revisados para MDLZ/KRFT y
TMUS/MetroPCS. Estos transforman holdings/cash sin reescribir precios; cualquier
otro evento complejo conserva el error explícito. KRFT es un security auxiliar,
no un miembro del universo invertible. No se reutiliza `PaperExecutor` ni se
modifica la autoridad de riesgo.

La validación real 2010-01-01 a 2026-10-02 ya completa Momentum después de
aplicar TMUS. Equal Weight supera MDLZ y se detiene en el siguiente evento no
revisado, ABT 2013-01-02; por eso Phase 2 continúa validada solo parcialmente.

Phases: 0 Architecture + feature store; 1 ingestión + baseline cuantitativo; 2 backtesting; 3 modelos baseline; 4 News; 5 Analyst + Earnings; 6 Fundamental + Macro + Event; 7 Portfolio + Risk; 8 paper trading; 9 live supervisado; 10 posible ejecución automática. Crypto será una expansión con schemas y predictores separados.
