# Contribuir

## Setup local

Requiere Python 3.11 o posterior.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
```

No agregue credenciales al repositorio. Copie `.env.example` a `.env` solo localmente y mantenga placeholders en archivos versionados.

## Antes de cambiar código

Lea `AGENTS.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md` y los ADR relacionados. Las decisiones de arquitectura no se cambian silenciosamente. Un cambio material requiere documentar motivación, consecuencias y migración, normalmente en un ADR nuevo que superseda al anterior.

## Estructura y convenciones

El paquete está bajo `src/investment_system`. Use type hints, funciones pequeñas, nombres explícitos y tests. Prefiera transformaciones puras de pandas/numpy. Mantenga configuración en YAML/env y evite dependencias pesadas o infraestructura no necesaria.

Ejecute antes de entregar:

```bash
python -m pytest
python scripts/validate_data.py
```

Para probar el plan de ingestión sin red ni credenciales:

```bash
python scripts/ingest_market_data.py --ticker AAPL --start 2020-01-01 --dry-run
python scripts/build_quantitative_feature_store.py --ticker AAPL --start 2010-01-01 --dry-run
```

## Añadir una feature

1. Confirme que puede calcularse solo con información disponible en `decision_time`.
2. Añada la columna al registro correcto de `data/schemas/features.py`; nunca a `TARGET_COLUMNS` si es input.
3. Implemente una función pura en `features/quantitative.py` o el módulo de agente correspondiente.
4. Integre la transformación en `FeatureBuilder` cuando proceda.
5. Añada tests de fórmula, bordes, ventanas y causalidad.
6. Documente unidad, rango, ventana y tratamiento de nulos si no es evidente.

## Añadir un agente

1. Herede de `BaseAgent` y mantenga `AgentContext`/`AgentResponse`.
2. Produzca explicación humana y `structured_features` tipadas.
3. Incluya confianza, fuentes y timestamps.
4. Pase toda interacción de modelo por `LLMRouter`.
5. Registre costos y use cache cuando el contenido no cambió.
6. No importe ni invoque `execution`, no modifique riesgo y no emita órdenes.
7. Añada tests de serialización, routing y point-in-time.

## Añadir una fuente de datos

1. Implemente `BaseDataSource` y transforme la respuesta a un schema de `data.schemas`.
2. Preserve `observed_at`, `published_at`, `available_at` e `ingested_at` según su semántica real.
3. Defina identificadores, deduplicación, revisiones y política de errores.
4. Valide `available_at <= decision_time` antes de joins o features.
5. Mantenga credenciales en entorno, nunca en código/config versionada.
6. Añada fixtures locales; los tests unitarios no deben depender de APIs reales.

Para EOD, no propague nombres de campos del proveedor fuera de `data.sources`. Conserve raw y corporate actions por separado y use la convención de splits de ADR-007. El artefacto latest-basis se regenera cuando cambia una acción, pero features históricas deben usar la vista as-of de ADR-008. Una nueva feature cuantitativa debe aceptar las columnas split-adjusted internas, no `adj*` del proveedor.

## Añadir un proveedor LLM

1. Implemente `BaseLLMClient` en `llm/`.
2. Registre el cliente en la composición del `LLMRouter`; ningún agente lo llama directamente.
3. Configure rutas y modelos fuera del código.
4. Añada pricing mediante `PricingRegistry`, sin precios hardcodeados en agentes.
5. Genere registros completos de tokens, costo, latencia y errores.
6. Pruebe con un fake/mock, sin claves ni llamadas reales en la suite.

## Integridad point-in-time

La regla `available_at <= decision_time` prevalece sobre conveniencia y rendimiento. No haga joins con “último dato” sin condición temporal, no rellene retrospectivamente revisiones y no use targets como features. Todo cambio en ingestión, datasets o backtesting necesita una prueba que falle ante información futura.

Features viven en `data/features` y targets en `data/targets`. No añada labels al Feature Store de inferencia. Una feature de mercado debe provenir de la vista split-adjusted as-of. Al cambiar fórmulas incremente `quantitative_feature_version` y evalúe si requiere reconstrucción completa.
