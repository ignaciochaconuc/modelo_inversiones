# Aplicación de los seis cierres factuales sin cronometraje

Se registraron seis decisiones individuales `news-pilot-factual-closure-decision-v1`
y seis disposiciones nuevas `news-pilot-review-disposition-v1`, bajo el modo
`closed_content_only_untimed`. Fuente real: autorización expresa del propietario
en la conversación, titulada «Phase 4C.2 — Aplicación de los seis cierres factuales»,
incluida su aceptación del mapa contextual del primer caso. No se inició revisión
contractual ni se modificaron estados oficiales de fases.

## Decisiones e identidades

Directorio de documentos de cierre:
`data/cache/news_development_pilot/factual-closures-v1/`.
Cada `CASE_ID.closure-v1.json` se vincula al hash factual exactamente autorizado,
la aprobación previa y la autorización metodológica. `owner-authorization-v1.json`
conserva la fuente de la decisión y los seis hashes aportados por el propietario.

| Caso | SHA-256 del documento individual de cierre |
| --- | --- |
| D-293a6cbca3479505 | `c1bbc3a858742b140bbcbeb6466667f4a89d67a11e9ff3c7dd181969d0af3b30` |
| D-a8db3a0c74d93eb8 | `bdee5ae4a787d3ca7448ff1401568559c351786ef15b55957416836932efc95d` |
| D-fbf4c5c9e02691b3 | `e786d310485dd996fd4adb6469cbab2c73dc53e50eaa9891307e7de7641f74d6` |
| D-40e8a2188273506b | `870a51d9439ff95017545c832e7168c08a5362d7b3cceb7e1dcf91c9465f81e9` |
| D-1211fcda178c57ab | `b6db2db930f26aeb6596885559aa2fa3b4e8b5b529cf176c0ace79cc22e31ea0` |
| D-6c6ef03a91cca2a9 | `acfe4e4c2c6670fca17d6a2505c8ae1c468645303e508c23b422fd8dc31b71eb` |

La identidad de decisión conserva la misma etiqueta de propietario que la
aprobación factual anterior, sin inferir identidad legal verificada. La etiqueta
visible Nacho se conserva como tal en la constancia de autorización. No se
inventaron ID de mensaje, firma ni hora: `decided_at`, timestamp de autorización,
ID y firma desconocidos quedan null. La revisión factual anterior sigue siendo
asistida por ChatGPT, sin independencia humana ni adjudicación atribuida.

Las justificaciones de cobertura se copiaron de los borradores aprobados,
conservando su origen de propuesta del asistente. El acto nuevo de cierre consta
en la decisión expresa y sus campos de autorización, sin convertir las notas
anteriores en una adjudicación independiente. En el primer caso se mantienen
F001 → F002/F003 y F006 → F002, sus justificaciones y citas originales: el vínculo
contextual no deduce identidad a partir de una fecha.

## Selección vigente e historial

El verificador exige un directorio seleccionado con exactamente seis registros
y su manifiesto. Por eso se preservó cada versión abierta byte por byte antes
de publicar la nueva versión en la misma dirección de selección:

- Selección vigente: `data/cache/news_development_pilot/review-dispositions-v1/`.
- Seis versiones abiertas anteriores: `review-disposition-history/open-v1/`,
  bajo la misma raíz `data/cache/news_development_pilot/`.
- Manifiesto anterior original, sin modificar sus bytes:
  `review-disposition-history/original-selected-manifest-open-v1.json`.
- Manifiesto adicional de replay de las versiones abiertas:
  `review-disposition-history/open-v1/manifest.json`; sus rutas apuntan a las
  copias archivadas con los hashes originales.
- Copia verificable de las nuevas disposiciones antes de publicación:
  `review-dispositions-closed-v1/`.

Cada disposición nueva tiene otra identidad canónica y `supersedes` enlazado a la
versión abierta archivada. `factual-closures-v1/application-plan-v1.json` conserva
el mapa de ubicación original, hash e identidad anteriores, ubicación de archivo,
documento de cierre y nueva identidad. La selección vigente cambia seis JSON y
su manifiesto; las siete versiones originales se conservan exactamente en archivo.
No se reescribieron los borradores o manifiestos históricos de preparación.

Sus referencias a la ubicación entonces vigente se interpretan como snapshots
anteriores: para reconstruirlas después del cambio se usa el mapa explícito del
plan y los archivos con el mismo hash. No se presentan esas direcciones antiguas
como si todavía seleccionaran el registro abierto. El replay archivado permite
comprobarlo con el verificador original, sin modificar código o reglas.

## Validación

```powershell
python tools/evaluation/pilot_review_disposition.py --validate data/cache/news_development_pilot/review-dispositions-v1
```

Resultado verificado: seis contenidos aprobados, seis cierres
`closed_content_only_untimed`, cero intentos elegibles medidos,
`integral_pilot_completed=false`, `semantic_truth=not_assessed`, cero llamadas y
cero predicciones. El resultado completo se conserva en
`factual-closures-v1/offline-verification-result-v1.json`.

Replay de las seis disposiciones abiertas anteriores:

```powershell
python tools/evaluation/pilot_review_disposition.py --validate data/cache/news_development_pilot/review-disposition-history/open-v1
```

Ese replay sigue informando seis aprobaciones y cero cierres. Se comprobaron los
esquemas y la cadena completa de hashes, incluida la versión anterior de cada
disposición. Suite completa: **981 passed**, 161,12 segundos. Tests específicos y
de compatibilidad: **95 passed**. Validación de datos y compilación correctas.
No se cambió ningún validador, contrato, prompt o algoritmo.

Los seis factuales mantienen `in_progress` y sus SHA-256 previamente aprobados;
sus formularios temporales siguen vacíos. Las declaraciones de lectura conservan
su naturaleza: desconocida, ≈1 minuto estimado y 30/20/30/20 segundos declarados.
No se imputaron tiempos ni se habilitaron estadísticas de esfuerzo humano. El
inventario final de preservación y los hashes de entrega se registran en
`factual-closures-v1/application-manifest-v1.json`.

## Bloqueos y siguiente paso recomendado

El cierre factual lateral no abre el flujo contractual histórico: este exige un
factual `completed` y procedencia temporal que estos intentos no tienen. Esos
controles siguen intactos; no corresponde cambiar los factuales para superarlos.

Falta autorizar e implementar el adaptador contractual versionado, con vínculo a
la disposición cerrada y al hash factual, formularios independientes, manejo de
incertidumbres y una sesión contractual prospectiva con procedencia y reloj
propios. Requiere tests de compatibilidad, rechazo de vínculos obsoletos y ausencia
de reconstrucción temporal. No se implementó ni activó ese adaptador aquí.

Siguiente paso recomendado: autorizar por separado su diseño e implementación
offline antes de abrir la revisión contractual. La elegibilidad para estimar
esfuerzo seguirá necesitando mediciones prospectivas; este cierre no la resuelve.
El piloto integral y el experimento v3/v4 permanecen incompletos; no se ejecutaron
inferencias, evaluaciones del modelo, proveedores ni cambios oficiales de fase.
