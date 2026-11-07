# Preparación definitiva de los seis cierres factuales — v2

Estado: propuesta pendiente de autorización expresa del propietario. Modo:
`closed_content_only_untimed`. Ninguna decisión de cierre se ha registrado o
aplicado. El paquete v1 y su diagnóstico se conservan intactos como historial.

## Resolución documental del primer caso

Caso: D-293a6cbca3479505. Anotación aprobada: `factual-borrador-v2`, SHA-256
`9072b179f81639e507d0c05c84fbe495f17de3647984591c335d99c32ecb396b`.

La preparación v1 detectó correctamente que faltaba justificar dos enlaces, pero
su recomendación de posible v3 partía de leer los IDs canónicos como si fueran
una sustitución autosuficiente del factual. El instrumento conserva la anotación
completa por hash y admite una justificación por cada hecho material. No exige
que el texto aislado del representante sea una equivalencia de todos sus
desgloses. Esta distinción permite proponer una cobertura contextual explícita.
No se añaden hechos, se cambia materialidad o se atribuye al propietario una
decisión sobre esta justificación nueva.

### Contenido material de F001 y F006

- **F001:** identifica una entrada, su contexto de boletín del permiso del horno
  asociado al nombre Yrvexil Bioceramics y la fecha que aparece en ella. Conserva
  el límite de que el texto no afirma aprobación ni entrada en vigor. F002/F003
  contienen la función de la fecha y la vigencia no informada, pero aisladas no
  vuelven a nombrar ese sujeto y contexto.
- **F006:** conserva la mención literal de Yrvexil Bioceramics vinculada a ese
  boletín y el límite de que no acredita identidad bursátil. El nombre procede de
  su propia cita, no de la fecha, el registry o una inferencia sobre titularidad.
  Ese nombre y su límite tampoco figuran literalmente en F002–F004.

Ambos remiten a la primera frase del mismo summary: evidence_id
`f200cf2bd8e1752483fc091f2497f67397ceefa20ee3b3cbf7af71eb9081f701`,
campo `summary`, offsets Unicode `[0,74)`. La evidencia y el significado de ambos
hechos permanecen en sus entradas originales. No se cambia su certainty ni se
convierten el nombre del boletín en operador, titular legal o exposición económica.

### Correspondencia propuesta

| Hecho | IDs canónicos | Relación y contenido conservado |
| --- | --- | --- |
| F001 | F002, F003 | F001 fija el referente de «el boletín» y «el permiso» al que F002 atribuye una fecha de publicación y F003 una fecha efectiva no informada. Sujeto, entrada y contexto se conservan en F001 y en la justificación del enlace. No se infiere aprobación o vigencia. |
| F006 | F002 | F006, mediante el contexto de F001, identifica el nombre literal asociado al boletín de F002. Es un anclaje de referente; F002 no demuestra ni implica por sí sola esa identidad. Se conserva el límite bursátil de F006 y `ticker_link=insufficient`, con registry elegible vacío. |

Esta correspondencia **no afirma que una proposición sobre fechas implique una
identidad**. La identidad está respaldada por F006 y su cita; el enlace señala
a qué obligación pertenece su contexto. El cierre conservaría el conjunto:
factual completo + citas + 13 dimensiones + mapa y justificaciones. No se reduce
la referencia a tres frases aisladas ni se omiten F001/F006 por no ser canónicos.

La cobertura completa propuesta, sin cambiar `must_not_omit`, es:

| Hechos materiales | Representantes canónicos |
| --- | --- |
| F001 | F002, F003 |
| F002 | F002 |
| F003 | F003 |
| F004 | F004 |
| F005 | F002, F003 |
| F006 | F002 |
| F007 | F003 |
| F008 | F004 |
| F009 | F002, F003 |
| F010 | F003 |
| F011 | F004 |

Se cubren las once entradas materiales mediante los tres representantes
existentes. El mapa usa solo IDs permitidos y justificaciones no vacías conforme
a `Coverage`; su corrección contextual es una propuesta del asistente para la
decisión expresa del propietario, no una verdad certificada por el validador.

## Por qué no requiere modificar la anotación

F001 y F006 ya están presentes, enlazados a sus dimensiones y aprobados por hash.
La corrección agrega únicamente su trazabilidad contextual a `material_coverage`
del borrador de cierre. No modifica F002 para introducirle un nombre, amplía la
semántica de una fecha, cambia la lista canónica, materialidad, citas, offsets,
esquemas o reglas de los validadores. No se necesita una v3 para este modo de
cierre que conserva el factual completo.

El instrumento posterior no puede tratar los IDs canónicos como un export de
hechos reducido: perdería ese contexto. Si en el futuro se exige tal export
autosuficiente, corresponderá otra decisión de representación y revisión; este
mapa no lo habilita. El adaptador contractual sigue sin implementar. El flujo
histórico de contrato completo exige mapear todos los hechos, no solo los de
`must_not_omit`; no se altera ese comportamiento.

## Comprobación de los seis casos

Se verificaron las seis aprobaciones completas, sus versiones y hashes, los
fingerprints, las citas con offsets Unicode y las dimensiones. Se reutilizan las
auditorías de cobertura documentadas de los casos 2–6, sin repetir sus revisiones
semánticas. Las incertidumbres se conservan exactamente en los borradores nuevos.

| Caso / versión aprobada | Dimensiones / citas | Entradas materiales / canónicos | Límite central preservado | Propuesta |
| --- | --- | --- | --- | --- |
| D-293a6cbca3479505 — borrador v2 | 13 / 11 | 11 / 3 | Publicación no acredita vigencia; identidad nominal no es bursátil. Cobertura contextual anterior pendiente de aprobación. | Cierre sin tiempos |
| D-a8db3a0c74d93eb8 — propuesta v2 | 13 / 22 | 10 / 5 | 640.000 USD brutos por cada mes, sin neto conocido; año, composición y contraparte no documentados. | Cierre sin tiempos |
| D-fbf4c5c9e02691b3 — propuesta v1 | 13 / 26 | 10 / 6 | R7 definido como aceptación física y liberación operativa, sin prueba de producción, plena capacidad o retorno. | Cierre sin tiempos |
| D-40e8a2188273506b — propuesta v2 | 13 / 31 | 11 / 8 | Fecha efectiva distinta de función de publicación; sin hora efectiva, operador, titular legal o emisor identificados. | Cierre sin tiempos |
| D-1211fcda178c57ab — propuesta v1 | 13 / 40 | 12 / 8 | 640.000 USD brutos por los tres meses combinados; sin reparto mensual de toneladas ni neto, margen o retorno conocidos. | Cierre sin tiempos |
| D-6c6ef03a91cca2a9 — propuesta v1 | 13 / 29 | 11 / 8 | R7 indefinido; no importar el glosario del otro caso ni concluir aceptación, operación o producción. | Cierre sin tiempos |

Las dimensiones insuficientes o indeterminadas mantienen sus notas; no impiden
cerrar contenido fielmente delimitado. Las ausencias significan información no
documentada, nunca inexistencia. Se mantienen separadas identidad, participación,
rol, vínculo bursátil e impacto. No se proponen inferencias económicas nuevas.

## Versiones por hash que quedarían vinculadas al cierre

| Caso | SHA-256 del factual aprobado, sin cambios |
| --- | --- |
| D-293a6cbca3479505 | `9072b179f81639e507d0c05c84fbe495f17de3647984591c335d99c32ecb396b` |
| D-a8db3a0c74d93eb8 | `77e82bca3bd1358f54faffd59babfe12b62b0ca40eb1131437cb100433260ec6` |
| D-fbf4c5c9e02691b3 | `5c0ff99410a3371b5cfdcd49e9134842bd4dcca9333ecec2bfcb2da33a2b457b` |
| D-40e8a2188273506b | `67ab00ba7c50a6415820a77b57901dcb3b6a372cb986c7f7451325a21cbeea65` |
| D-1211fcda178c57ab | `62806d79ae2f8455a0408cf2b34e681599b94fd2cd2219f7ca2ee1e02129552d` |
| D-6c6ef03a91cca2a9 | `3d8bfb39f17fc3f5e0430220d2c6f5dfe82e1a862bcf7426147aec347a837afe` |

## Paquete sometido a autorización

`data/cache/news_development_pilot/closure-preparation-v2/` contiene seis
plantillas, un índice y `first-case-context-coverage-v2.json`, enlazados al paquete
anterior por hash. Los cinco payloads de decisión de los casos 2–6 permanecen
idénticos a sus borradores v1. En el primero solo se completó la propuesta de mapa
contextual y su documentación. El manifiesto de preparación registra los hashes
y verificaciones, no una autorización o decisión de cierre.

En los seis, los campos de decisión del propietario permanecen null, incluidos
`explicitly_approved`, `decided_by` y `decision_source`; tampoco se inventó
`decided_at`. Las seis plantillas siguen siendo rechazadas como decisiones
efectivas por esos campos pendientes. Se comprobó la estructura del mapa por
separado, sin simular una aprobación ni registrar cierres en nombre del propietario.

La autorización pendiente abarcaría los seis cierres
`closed_content_only_untimed` vinculados a estas versiones, aceptando expresamente
la cobertura contextual propuesta para el primero. Una decisión posterior deberá
registrar su fuente real, preservar originales y crear disposiciones nuevas;
esta preparación no realiza esas transiciones.

Los formularios históricos siguen `in_progress`; las seis disposiciones actuales
siguen abiertas. Los seis intentos permanecen excluidos de estadísticas medidas:
lectura desconocida, ≈1 minuto estimado, y 30/20/30/20 segundos declarados sin
cronometraje completo. No se reconstruyen tiempos ni se atribuyen independencia
humana, adjudicación o ground truth. No se abre contrato, cambia una fase oficial,
ejecuta inferencia o llama a proveedores.
