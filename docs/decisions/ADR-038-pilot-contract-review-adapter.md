# ADR-038: Adaptador contractual separado del piloto de desarrollo

## Estado

Aceptado para implementación y preparación offline por instrucción expresa del
propietario. No autoriza apertura de casos, juicios del propietario, inferencias,
evaluaciones del modelo o cambios oficiales de Phase 4C.2/4C.3.

## Contexto y decisión

Los seis factuales tienen cierre lateral `closed_content_only_untimed`, mientras
sus formularios históricos siguen `in_progress`. El flujo contractual v1 exige
`completed` y cronometraje factual que no existe. Se mantiene intacto ese bloqueo.

Añadir `news-pilot-contract-form-v2`, sesión nueva y CLI de lectura opt-in en un
módulo separado. Validar la selección vigente de los seis cierres y sus cadenas
originales antes de aceptar incluso un formulario vacío. Fijar el contrato
económico v3 y sus validadores mediante referencia técnica por hash, sin ejecutarlo.

El formulario conserva un snapshot exacto del factual completo, no una selección
de `must_not_omit`. Todos los hechos requieren mapping al completar. Los mappings
solo contienen representabilidad y límites; no pueden reemplazar el juicio factual.
Conservar certeza, evidencia y estados de dimensión sin normalización o promoción.

La apertura necesita otra autorización específica por caso/review_id. La sesión
contractual registra identidad, asistencia y tiempos propios, sin campo de cierre
temporal factual ni reutilización de estimaciones. Una decisión contractual final
requiere aprobación expresa vinculada al fingerprint del contenido y su sesión.

## Consecuencias y límites

Preparar seis formularios y seis plantillas temporales vacíos es distinto de abrir
seis revisiones. El CLI no escribe, carga credenciales o llama proveedores. Una
validación de preparación informa cero iniciados y no permite reclamar completion.
Metadata temporal contractual conserva TTL de 90 días desde el final real de su
sesión; no modifica políticas anteriores ni rehabilita cronometrajes factuales.

La estructura impide cambiar incertidumbres factuales o borrarlas de los mappings,
pero no certifica la verdad del razonamiento libre. La revisión del propietario
sigue siendo necesaria y no constituye independencia humana o adjudicación.

No adaptar silenciosamente validadores viejos, cambiar estados históricos o
permitir que cerrar este instrumento complete el experimento o autorice inferencia.
Pruebas con fixtures offline deben cubrir hashes, cierres, totalidad de hechos,
incertidumbre, autorizaciones separadas, reloj, TTL y compatibilidad histórica.

Guía: [adaptador contractual del piloto](../phase4c2-pilot-contract-adapter-v1.md).
