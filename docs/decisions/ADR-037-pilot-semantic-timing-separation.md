# ADR-037: Disposiciones semánticas y temporales del piloto de desarrollo

## Estado y autoridad

Aceptado para el mecanismo offline mínimo del piloto de desarrollo por instrucción
expresa del propietario. La propuesta v2 conserva su texto y hash históricos;
la aprobación posterior se documenta por separado. No se autorizaron cierres
individuales, adaptador contractual, inferencias o cambios de fase.

## Problema

Los seis contenidos factuales fueron aprobados con asistencia ChatGPT y revisión
del propietario no independiente. Ninguna sesión dispone de cronometraje completo.
Los formularios y validadores históricos acoplan cierre y procedencia temporal,
por lo que usar `completed` para preservar esas aprobaciones falsificaría el
significado operativo del cierre. Repetir lecturas no recuperaría el tiempo perdido.

## Decisión

Añadir `news-pilot-review-disposition-v1` fuera de los formularios v1. Distinguir
aprobación, decisión de cierre, validez temporal y elegibilidad para esfuerzo.
El CLI offline solo actúa con selección explícita `--validate`, verifica cadenas
de hashes y procedencia, y no escribe estados ni carga credenciales.

Crear seis disposiciones con contenido aprobado, cierre abierto y esfuerzo
excluido. Enlazar anotaciones, aprobaciones y formularios temporales originales
sin reescribirlos. Registrar tiempos desconocidos, estimados y declarados con
su naturaleza real. No convertir aprobación de la metodología en cierre de caso.

Un cierre futuro necesita decisión expresa separada, mismo hash y cobertura
material declarada, con incertidumbres preservadas. No equivale a cierre integral
o independencia humana. El modo histórico conserva sus requisitos. La validación
no certifica verdad semántica, autenticidad de personas o veracidad del reloj.

Metadata temporal medida conserva el vencimiento de 90 días desde el final de la
medición; nuevas disposiciones no renuevan ese plazo. No acceder a respuestas
de proveedor o alterar su TTL de 24 horas. El adaptador contractual queda ausente.

## Compatibilidad y consecuencias

No modificar agentes, contratos económicos, prompts, corpus o validadores v1.
Las aprobaciones mantienen hashes, procedencia asistida y ausencia de adjudicación.
Los seis factuales siguen `in_progress`; el piloto no obtiene capacidad medida.
El balance cualitativo puede conservarse sin imputar tiempos o fingir revisores.

Probar hashes, decisiones separadas, vínculos, faltantes, alcance de medición,
caducidad, exclusión histórica, compatibilidad, sanitización y ausencia de efectos
laterales con fixtures offline. Documentación operativa:
[disposiciones del piloto](../phase4c2-pilot-review-dispositions.md).
