# ADR-002: Feature/target separation

## Status

Accepted

## Context

Los targets se calculan con precios futuros y pueden filtrarse accidentalmente hacia entrenamiento, inferencia o decisiones si se manejan como columnas ordinarias.

## Decision

Mantener registros canónicos y disjuntos `FEATURE_COLUMNS` y `TARGET_COLUMNS`. `FeatureRow.model_features()` nunca devuelve targets. La generación causal de features y `FeatureBuilder.add_targets()` son operaciones separadas; esta última se usa únicamente al preparar datasets supervisados.

## Consequences

La preparación de entrenamiento tiene un paso explícito adicional y tests de separación. Se evita que `target_return_5d`, `target_return_10d`, `target_return_20d`, `target_positive_10d` o `target_rank_10d` entren a una decisión.
