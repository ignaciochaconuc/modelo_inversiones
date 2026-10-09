# Guía para agentes de IA

Este archivo contiene las restricciones operativas que todo agente debe respetar al trabajar en este repositorio. Para requisitos funcionales consulte [PROJECT_SPEC.md](PROJECT_SPEC.md); para límites entre componentes, [ARCHITECTURE.md](ARCHITECTURE.md); y para decisiones aceptadas, [docs/decisions/](docs/decisions/).

## Objetivo

Construir un sistema modular de análisis y gestión táctica de inversiones que combine datos cuantitativos, agentes de IA, modelos predictivos, optimización de cartera, Risk Manager, backtesting, paper trading y, en una etapa futura, ejecución.

V1 se limita a aproximadamente 100 acciones líquidas de Estados Unidos, frecuencia diaria y horizonte principal de 10 días bursátiles. La estrategia es Long + Cash, con 10–15 posiciones como máximo, 10% máximo por activo, sin posiciones cortas ni leverage. Las decisiones se calculan después del cierre y las operaciones simuladas se ejecutan en la apertura de la siguiente sesión. Crypto queda fuera de V1 y deberá usar modelos separados.

## Flujo y autoridad

Mantener estrictamente separadas estas etapas:

`Information gathering → Feature extraction → Prediction → Portfolio optimization → Risk management → Execution`

Los agentes LLM pueden investigar, analizar, resumir, producir bull/bear cases, identificar riesgos y generar features estructuradas. No pueden enviar órdenes, cambiar límites de riesgo, eludir al Risk Manager, alterar targets ni introducir información futura.

El Risk Manager es independiente de agentes y modelos. Tiene autoridad final para `APPROVE`, `REDUCE` o `BLOCK`. Nunca crear una ruta de ejecución que no requiera previamente su decisión.

## Point-in-time: invariante crítica

Nunca utilizar información que no estuviera disponible al tomar la decisión:

`available_at <= decision_time`

No intercambiar ni colapsar el significado de:

- `observed_at`: momento al que se refiere el hecho o medición;
- `published_at`: primera publicación por la fuente;
- `available_at`: momento desde el cual el sistema podía conocerlo;
- `ingested_at`: momento de entrada al sistema.

Todo cambio en ingestión, joins, feature building o backtesting debe conservar esta regla y tener tests contra look-ahead bias.

Para splits, no confundir el dataset persisted `split_adjusted_latest` con una vista point-in-time. Las decisiones históricas deben usar `build_split_adjusted_series_as_of()` y solo acciones con `effective_date <= decision_date` y `available_at <= decision_time`.

Una barra retrasada puede participar en decisiones posteriores a su disponibilidad, pero nunca debe modificar una fila cuyo `decision_time` sea anterior. Las optimizaciones por segmentos deben crear límites tanto por corporate actions como por aparición de barras históricas tardías.

## Features y targets

Los targets son exclusivamente:

- `target_return_5d`
- `target_return_10d`
- `target_return_20d`
- `target_positive_5d`
- `target_positive_10d`
- `target_positive_20d`
- `target_rank_5d`
- `target_rank_10d`
- `target_rank_20d`

Nunca incluirlos en entradas de entrenamiento, inferencia o decisiones. En el código, `FeatureRow.model_features()` y los registros `FEATURE_COLUMNS`/`TARGET_COLUMNS` materializan esta separación. La generación de targets debe permanecer separada de la generación causal de features.

La separación también es física: features de producción viven bajo `data/features` y targets supervisados bajo `data/targets`. Solo pueden unirse explícitamente por `ticker + decision_date` durante entrenamiento. Future corporate actions están permitidas únicamente al construir targets split-consistent, nunca features. Los targets persisten `target_end_date_{5,10,20}d` como metadata auditable; esas fechas no son features ni labels predictivos.

## Agentes

Existen `NewsAgent`, `AnalystAgent`, `EarningsAgent`, `FundamentalAgent`, `MacroAgent` y `EventAgent`. Actualmente son stubs. Toda respuesta debe mantener el contrato `AgentResponse` y contener salida explicable, `structured_features`, `confidence`, referencias de fuentes y timestamps. El texto libre no debe sustituir features numéricas cuando estas puedan expresarse estructuradamente.

## LLM y costos

Toda llamada futura debe pasar por `LLMRouter` o una abstracción común equivalente. Debe poder enrutar a Ollama/local, OpenAI y proveedores futuros. Nunca llamar directamente a OpenAI u otro proveedor desde un agente.

Cada llamada debe registrar provider, model, tokens de entrada/cache/salida, costo estimado, latencia, éxito/error, agente, tarea y ticker. No hardcodear precios dentro de agentes ni clientes: usar `PricingRegistry` y configuración editable. La arquitectura debe permitir medir costo por día, ticker, agente, análisis y trade, y eventualmente `incremental PnL / AI cost`.

## Convenciones de código

- Usar Python moderno, type hints y docstrings útiles.
- Preferir funciones pequeñas y puras para features cuantitativas.
- Mantener módulos desacoplados y configuración fuera del código.
- Añadir tests para toda lógica nueva, especialmente integridad temporal.
- Evitar dependencias pesadas, infraestructura distribuida y abstracciones sin necesidad actual.
- Mantener el paquete raíz `investment_system`; evita colisiones con módulos genéricos.
- No guardar secrets. `.env` está ignorado; `.env.example` solo contiene placeholders.

## Cambios arquitectónicos

Antes de cambiar Feature Store, timestamps, agentes, targets, Risk Manager, LLM Router, execution o backtesting:

1. revisar `PROJECT_SPEC.md`, `ARCHITECTURE.md` y los ADR relevantes;
2. explicar la razón técnica del cambio;
3. crear o actualizar un ADR si cambia una decisión aceptada;
4. actualizar documentación y tests junto con el cambio.

No modificar decisiones arquitectónicas silenciosamente.

## Fuera de alcance actual

No implementar sin instrucción explícita: trading o brokers reales, API keys reales, órdenes automáticas, modelos ML definitivos, scraping agresivo, almacenamiento de secretos ni crypto trading. Phase 3D.1–3D.6 está implementada para robustez walk-forward, sensibilidad de ventana y ablations diagnósticas con TEST sellado; no iniciar 3D.6.1, selección final, Phase 3E o posteriores por iniciativa propia.

## Verificación mínima

Antes de entregar cambios, ejecutar `python -m pytest`. Si se tocaron schemas, features o datos temporales, ejecutar también `python scripts/validate_data.py`. Informar cualquier desviación entre documentación, configuración e implementación.
