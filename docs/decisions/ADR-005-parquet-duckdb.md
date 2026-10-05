# ADR-005: Parquet and DuckDB for local storage

## Status

Accepted

## Context

La fase inicial necesita almacenamiento columnar reproducible y consultas analíticas sin operar un servicio de base de datos. PostgreSQL o infraestructura distribuida añadirían carga operacional antes de demostrar su necesidad.

## Decision

Persistir inicialmente datos procesados y features en Parquet y consultarlos con DuckDB. Mantener una fila conceptual por `ticker + decision_date` en el Feature Store. No introducir PostgreSQL en esta fase.

## Consequences

El entorno es local, simple y portable, con buen rendimiento analítico para el universo V1. Escrituras concurrentes, servicio multiusuario y escalado distribuido quedan fuera de alcance; un cambio futuro requiere medición y otro ADR.
