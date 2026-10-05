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
```

Para una descarga real, defina `TIINGO_API_KEY` solo en el `.env` local y quite `--dry-run`. También puede usar `--universe`; el procesamiento es secuencial y respeta el throttling configurado.

Los datasets quedan separados en `data/raw/tiingo/daily`, `data/raw/tiingo/corporate_actions` y `data/processed/market/split_adjusted`. El universo versionado es una lista fija de desarrollo similar al S&P 100 actual: no es point-in-time e introduce survivorship bias en backtests históricos.

## Estado y roadmap

Son funcionales los schemas, validación point-in-time, adapter Tiingo EOD, actualización incremental Parquet, calendario XNYS, normalización de splits, cálculos cuantitativos principales, cache y reglas básicas de riesgo. Son contratos/stubs: clientes OpenAI/Ollama, modelos predictivos, optimización, backtesting completo y ejecución.

Phases: 0 Architecture + feature store; 1 ingestión + baseline cuantitativo; 2 backtesting; 3 modelos baseline; 4 News; 5 Analyst + Earnings; 6 Fundamental + Macro + Event; 7 Portfolio + Risk; 8 paper trading; 9 live supervisado; 10 posible ejecución automática. Crypto será una expansión con schemas y predictores separados.
