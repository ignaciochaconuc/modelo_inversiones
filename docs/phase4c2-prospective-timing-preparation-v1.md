# Phase 4C.2 — Declaraciones preparatorias inciertas — v1

## Alcance y autoridad

Extensión aislada autorizada por el propietario mediante «Phase 4C.2: Resolver
bloqueo del preflight mediante registro preparatorio versionado». Autoriza
implementar este registro y conservar la declaración de la primera sesión;
no autoriza ejecutar, mostrar fuentes, medir o decidir elegibilidad final.
No se inventan fecha de declaración, firma o ID de mensaje.

Versión: `news-prospective-timing-preparation-v1`, separada de
`news-prospective-timing-authorization-v1`. No supersede ni modifica
[ADR-042](decisions/ADR-042-isolated-prospective-timing-pilot.md), el plan,
reservas, autorización ejecutable, esquemas o controles de inicio existentes.

## Problema y decisión mínima

La ausencia de recuerdo de exposición no acredita primera lectura o variantes
no vistas. El esquema ejecutable exige declaraciones booleanas y reviewer_id;
no debe rellenarse por inferencia ni convertirse null/unknown en true.

El nuevo registro admite responsable mediante referencia al propietario y
reviewer_id=null. Conserva declaración textual y fuente; familiarity_status,
first_reading y variant_exposure expresan unknown cuando falta certeza.
La identidad canónica es una referencia de rol, no un identificador personal
inventado ni una identidad legal autenticada.

status=preparation_only, scope=preparation_and_preflight_only,
start_authorized=false y eligibility_granted=false son campos requeridos,
sin valores predeterminados que permitan promover el documento. No se atribuyen
independencia humana ni adjudicación. Las declaraciones más definidas que
eventualmente pudieran conservarse tampoco convierten preparación en permiso.

pending_fields debe coincidir con la información efectivamente desconocida;
execution_authorization siempre permanece pendiente en este tipo de documento.
La plantilla admite también declaración y fuente todavía desconocidas, explícitas
en pending_fields. No constituye una declaración real atribuida al propietario.

## Archivos y primera declaración

- [Validador de lectura](../tools/evaluation/prospective_timing_preparation.py).
- [Esquema nuevo](../evaluation/phase4c2_prospective_timing_preparation_v1/preparation.schema.json).
- [Plantilla](../evaluation/phase4c2_prospective_timing_preparation_v1/PREPARATION-TEMPLATE.json).
- [Registro preparatorio real](../data/cache/news_prospective_timing_pilot/preparations/first-factual-v1.json).
- [Tests aislados](../tests/unit/test_prospective_timing_preparation.py).

El registro vincula D-5f21ec91317d6943 a la reserva factual
pt-7876c40dc93144768f9d1adc19b8b052 y al fingerprint vigente del plan
63203d4cb428ab2ff6a2727d83ce310f32c77c5b0db41f6dac0020bc8b52ae95.
El fingerprint del paquete se toma del plan verificado, no del nombre de archivo.

Se conserva literalmente la declaración del propietario: «No recuerdo haber leído
los tres casos ni sus variantes». Su alcance es ausencia de recuerdo, no garantía
de exposición inexistente. Primera lectura y exposición a variantes siguen unknown;
modalidad manual_chatgpt_owner; reviewer_id, declared_at y source_message_id null.
La fuente identifica la declaración y esta instrucción en la conversación, sin
crear una autorización ejecutable. No se muestra texto ni etiquetas de los casos.

El registro está bajo preparations/, separado de authorizations/ y calibration-v1/.
Su existencia no crea una sesión, evento o intervalo. No se copia la declaración
a una autorización de ejecución ni se escribe el archivo first-factual-v1.json
en authorizations/.

## Validación y rechazo de uso como autorización

```powershell
python -B tools/evaluation/prospective_timing_preparation.py --plan evaluation/phase4c2_prospective_timing_pilot_v1/plan.json --record data/cache/news_prospective_timing_pilot/preparations/first-factual-v1.json validate
```

Este es un CLI exclusivamente de lectura. Comprueba el esquema, pendientes,
case_id/session_id/etapa, paquete y plan fijados por hash. Reutiliza el preflight
de lectura existente y devuelve por separado preparación válida, permiso false,
elegibilidad false y estados temporales. Nunca muestra la declaración o las fuentes
de noticias en su salida. Importar el módulo no carga datos, .env o proveedores.

El parser ejecutable original rechaza el registro por su versión y estructura;
un simple cambio de ruta o de nombre no lo vuelve válido. Cambiar solo la etiqueta
de versión tampoco basta: faltan campos ejecutables y unknown no es un booleano.
El validador nuevo comprueba esa incompatibilidad y dispone de una frontera
explícita preparation_is_not_execution_authorization; no ofrece conversión.

No se modifica el CLI de reloj para añadir otro error: conserva su rechazo
tipado y su error público sanitizado originales. Así permanecen intactos su hash,
el fingerprint del plan, la autorización ejecutable y sus condiciones legítimas.
Las pruebas llaman al reloj original con fixtures sintéticos: comprueban rechazo
por versión, rutas copiadas y ausencia de escrituras, junto con aceptación de
autorizaciones ficticias completas que ya satisfacen sus controles originales.
No se invoca clock start contra las reservas reales.

## Límites, retención y pendientes

Una declaración preparatoria es metadata de procedencia, no una medición. No
contiene intervalos, horas de actividad o duraciones y no inicia ni renueva el
TTL temporal de 90 días. No copia respuestas de proveedor o contenido sujeto
al TTL de 24 horas. El preflight utiliza los lectores existentes sin eludir
su política de retención; no crea una política indefinida para tiempos medidos.

Continúan pendientes reviewer_id real o referencia instrumental expresamente
confirmada, aclaración factual de familiaridad/primera lectura/variantes y una
autorización posterior separada de inicio. No se exige inventar certeza ni un
ID personal: si las condiciones ejecutables no pueden sostenerse, el inicio
permanece bloqueado hasta otra decisión metodológica autorizada. Validar una
declaración no resuelve esos requisitos ni certifica atención humana.

Conservar integral_pilot_completed=false, semantic_truth=not_assessed y
factual_timing_rehabilitated=false; Phase 4C.2 y subfases siguen
implemented_pending_external_review y Phase 4C.3 not_started. No se abren los
seis expedientes históricos, no se cambian sus hashes y no se ejecutan inferencias.

Pruebas deterministas: fixtures marcados synthetic_fixture y relojes ficticios
en tmp_path; no registros reales. El plan y las reservas permanecen intactos.
Fuentes: [protocolo prospectivo v1](phase4c2-prospective-timing-pilot-v1.md),
[ADR-041](decisions/ADR-041-bounded-assisted-development-review-closure.md) y
[disposiciones](phase4c2-pilot-review-dispositions.md).
