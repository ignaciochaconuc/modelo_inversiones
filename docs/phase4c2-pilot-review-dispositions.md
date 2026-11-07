# Disposiciones del piloto: contenido, cierre y tiempo — v1

Implementación offline del mecanismo mínimo aprobado de la propuesta
[v2](phase4c2-pilot-semantic-timing-separation-proposal-v2.md).
Versión: `news-pilot-review-disposition-v1`. Alcance: piloto asistido de desarrollo.
El adaptador contractual no está implementado ni activado. No se cambia el estado
oficial de Phase 4C.2 ni se inicia Phase 4C.3.

## Compatibilidad del alcance autorizado

Se contrastó la instrucción del propietario con el texto exacto de la propuesta
v2 (SHA-256 `663102a7caaf7ef6ea53b5dfec90a1b0bf22933d72a6982ebd4b0e385601d453`).
No hay contradicción: la propuesta prevé registro lateral, verificador opt-in,
cuatro ejes y un adaptador posterior. La autorización actual implementa solo los
dos primeros; no autoriza cierres individuales ni el adaptador. La propuesta y
sus manifiestos históricos se conservan como documentos de su momento original.
Su encabezado histórico pendiente no se reescribe; la aprobación posterior consta
en `evaluation/phase4c2_pilot_review_disposition_v1/authorization.json`.

## Materiales y comprobación

- `tools/evaluation/pilot_review_disposition.py`: modelos cerrados, identidad
  canónica, validación de referencias y CLI de lectura explícita.
- `evaluation/phase4c2_pilot_review_disposition_v1/`: autorización metodológica,
  cinco esquemas JSON y manifiesto técnico de la entrega.
- `data/cache/news_development_pilot/review-dispositions-v1/`: seis registros nuevos
  y manifiesto de sus hashes, fuera de los formularios históricos.
- `tests/unit/test_pilot_review_disposition.py`: fixtures técnicas en temporales;
  no son casos de evaluación nuevos ni juicios de revisores.

Ejecutar desde la raíz del repositorio:

```powershell
python tools/evaluation/pilot_review_disposition.py --validate data/cache/news_development_pilot/review-dispositions-v1
```

El comando exige `--validate`; no se activa por importación. No escribe archivos,
carga `.env`, usa proveedores, genera interpretaciones ni abre revisión contractual.
Reconstruye los paquetes originales con el verificador histórico y comprueba las
seis cadenas de origen contra el inventario documental fijado por hash. Ese uso
revalida integridad y estructura, sin repetir la revisión semántica del propietario.
Salida esperada: seis aprobaciones, cero cierres y cero intentos elegibles medidos.
Los errores CLI son genéricos y sanitizados, sin imprimir documentos o excepciones.

## Los cuatro ejes

| Eje | Representación | Validación |
| --- | --- | --- |
| Contenido | `content.status=owner_approved_content` y referencia a la decisión anterior | Caso, fingerprint, versión, SHA-256 exacto del factual y aprobación, alcance, responsable, fuente y procedencia real |
| Cierre factual | `closure.status=open`, `closed_content_only_untimed` o `closed_under_legacy_protocol` | Un cierre requiere un documento separado, decisión explícita, mismo contenido/aprobación/política y revisión declarada de cobertura material e incertidumbres |
| Cronometraje | `timing.status`, fuente original, declaración y eventual medición separadas | No convertir declaración en medición; intervalos y totales verificables para mediciones, alcance específico y caducidad |
| Esfuerzo humano | `effort.status=excluded` o `eligible_for_named_scope` | La inclusión requiere medición válida y atestación vinculada al reloj, tarea, revisor, asistencia, familiaridad y población |

Esta versión consume aprobaciones completas ya documentadas; no genera ni adjudica
aprobaciones nuevas. Para el segundo registro histórico, que no tenía un campo
`annotation_version`, se reconoce exclusivamente la versión v2 nombrada por su
decisión `approved_factual_proposal_v2_including_materiality_changes`. No se infiere
la versión a partir del nombre de archivo. Los demás vínculos deben ser explícitos.

Las seis anotaciones y decisiones originales conservan sus bytes y hashes. El
registro lateral puede expresar 20.0 segundos en su serialización numérica; esto
no modifica los 20 segundos declarados ni su procedencia en el origen. No se
convierten unidades, calculan duraciones nuevas o reconstruyen fechas.

## Resultado aplicado a los seis intentos

| Orden | Caso | Contenido | Cierre lateral | Tiempo conservado | Esfuerzo |
| --- | --- | --- | --- | --- | --- |
| 1 | D-293a6cbca3479505 | Aprobado, borrador v2 | Abierto | Desconocido | Excluido |
| 2 | D-a8db3a0c74d93eb8 | Aprobado, propuesta v2 | Abierto | ≈1 minuto, estimación del propietario | Excluido |
| 3 | D-fbf4c5c9e02691b3 | Aprobado, propuesta v1 | Abierto | 30 segundos declarados sin registro completo | Excluido |
| 4 | D-40e8a2188273506b | Aprobado, propuesta v2 | Abierto | 20 segundos declarados sin registro completo | Excluido |
| 5 | D-1211fcda178c57ab | Aprobado, propuesta v1 | Abierto | 30 segundos declarados sin registro completo | Excluido |
| 6 | D-6c6ef03a91cca2a9 | Aprobado, propuesta v1 | Abierto | 20 segundos declarados sin registro completo | Excluido |

Los seis formularios factuales históricos siguen `in_progress`; sus timing siguen
vacíos. No se generaron documentos de cierre. Los registros nuevos conservan origen
ChatGPT, propietario no independiente, ausencia de adjudicación y timestamps
desconocidos como null. La autorización de implementación tampoco proporciona
una hora de revisión, aprobación factual o cierre.

## Condiciones de una futura decisión de cierre

Un documento `news-pilot-factual-closure-decision-v1` debe proceder de una nueva
decisión real y explícita del propietario, distinta de su aprobación de contenido.
Debe identificar caso, fingerprint, hashes del factual, aprobación y autorización,
modo y fuente de decisión. Conserva `decided_at=null` si no hay hora conocida.
El verificador no redacta ni atribuye ese acto al propietario.

Para cierre sin tiempos: 13 dimensiones evaluadas, incertidumbres justificadas,
citas exactas, ausencia declarada de cambios semánticos pendientes y cobertura
material explícita hacia IDs canónicos `must_not_omit`. La estructura de cobertura
se verifica; su corrección semántica sigue siendo responsabilidad del revisor.
No es necesario repetir la revisión factual ya aprobada para documentar un cierre
real sobre el mismo hash. No se requiere fabricar un reloj para ese modo.

El modo histórico exige además factual `completed`, sesión temporal válida,
`factual_closed_at` real y tareas de anotación/citas anteriores a ese cierre. No
exige haber terminado el contrato. El cierre integral continúa sujeto al validador
histórico de los tres formularios: no se redefine mediante el sidecar.

Una actualización requiere otro archivo y otro `disposition_id`, con `supersedes`
apuntando al registro previo y su hash; conservar todos los originales. Se valida
la cadena completa y se rechaza reabrir silenciosamente el mismo contenido cerrado.
El manifiesto del nuevo directorio selecciona exactamente una disposición por
caso; los antecedentes se conservan fuera de ese directorio seleccionado. El CLI
solo valida, no migra ni sobrescribe. Una edición factual invalida la aprobación
anterior para los nuevos bytes; el CLI de estos seis intentos mantiene fijados los
hashes de su inventario histórico.

## Tiempo, elegibilidad y retención

Una duración declarada aislada y una estimación siguen excluidas. Una medición
por alcance exige sesión acotada, intervalos observados, totales coherentes y
fases realmente observadas. Leer durante un minuto no mide la anotación completa.
La medición completa exige todos los requisitos temporales v1. Incluso una
medición válida permanece excluida hasta contar con una atestación de elegibilidad
humana para tareas y población concretas; no se deduce independencia o capacidad.

Las rutas de medición y elegibilidad se prueban con fixtures. El CLI para los seis
intentos históricos rechaza añadir una medición o promover su elegibilidad; una
sesión prospectiva futura necesita otro intento y una integración autorizada,
sin rehabilitar estos tiempos históricos. No calcula sumas, promedios o capacidad.

Metadata temporal medida: vencimiento estricto a los 90 días desde `completed_at`
de la medición original, incluso si la disposición se registra después. Al vencer
se bloquea su uso; cambiar el sidecar no renueva el plazo. `invalid_or_expired`
no es una vía de aceptación: datos inválidos o vencidos bloquean la verificación.
No existe purga automática nueva ni ampliación de la política de fuentes propias.
Las declaraciones incompletas se conservan como historia documental del intento,
sin atribuirles una medición con vigencia indefinida. Las respuestas de proveedor
continúan bajo su TTL de 24 horas y no se leen ni copian en este mecanismo.

## Límites y trabajo contractual pendiente

El verificador comprueba estructura, coherencia e integridad de declaraciones.
Los hashes detectan alteraciones; no son firmas del propietario ni prueban que
una afirmación, reloj o identidad declarada sea auténtica. `semantic_truth` sigue
`not_assessed`. No acredita independencia humana o generalización del corpus.

El adaptador contractual requiere autorización posterior, instrumento versionado,
vínculo al SHA factual y a la disposición cerrada, sesión contractual nueva con
procedencia propia y pruebas del agregado. Debe mantener incertidumbre factual
separada de representabilidad y conservar el bloqueo de los flujos v1. Riesgos:
tratar aprobación como cierre, reutilizar un hash obsoleto, inventar un tiempo
factual desde el inicio contractual o eludir el agregado histórico. Esta entrega
no implementa ese adaptador ni permite iniciar la revisión contractual.

No se repiten anotaciones, generan casos o evaluaciones del modelo, ejecutan
inferencias, renuevan perfiles o modifican fases oficiales. Las pruebas de la
entrega y los hashes se registran en el manifiesto técnico del instrumento.
