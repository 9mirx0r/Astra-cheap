# Comparativa de optimización para Codex

Fecha de revisión: 2026-09-08.

Este informe compara el diseño actual de Astra-Ultra con cinco repositorios que
tocan partes distintas del mismo problema: tokens, selección de modelo, contexto,
caching, telemetría y control del ciclo agente-herramientas. No todos son
competidores directos. La comparación útil es por mecanismo.

## Alcance y reproducibilidad

Se hicieron clones shallow (`--depth 1`) en `.local/comparison-repos/`; no se
modificó ninguno de ellos. Los commits auditados fueron:

| Proyecto | Commit auditado | Fecha del commit | Qué se inspeccionó |
|---|---|---:|---|
| [astra-advisor](https://github.com/DannyMac180/astra-advisor) | `c72d3280551f118eba51a5884e3971a0c0058aa6` | 2026-09-04 | plugin, skill de orquestación, operaciones, pricing, calculadora y 15 tests |
| [codex-usage-audit](https://github.com/razzededge/codex-usage-audit) | `a3347b75dd598984f600887316a0030dec2d9886` | 2026-07-22 | parser de rollouts, agregación, rate card, recomendaciones, hook y tests |
| [prompt-pack](https://github.com/Ozzeron/prompt-pack) | `cb517b26daca4fc6d8c3aba283606f16a0f416bd` | 2026-09-05 | targets Codex, router, progressive disclosure, token-discipline y hooks |
| [codex-efficiency-skills](https://github.com/soarinsky1/codex-efficiency-skills) | `3469ae872ad6b967a51707a767ca8eff3cf14d17` | 2026-08-13 | dos Skills, metodología de benchmark, casos de activación y validador |
| [prompt-cache-skills](https://github.com/OnlyTerp/prompt-cache-skills) | `5b58ae26bd446bfb2eee97e8dad076ffb46a6715` | 2026-08-28 | auditoría Codex CLI, mecánica OpenAI, verificador de caching y scorecard |

El historial local de cada clon tiene un solo commit por ser shallow; las
conclusiones son sobre el estado auditado, no sobre toda la historia del
proyecto.

### Verificación ejecutable de los clones

- `astra-advisor`: 15/15 tests Python pasan.
- `codex-efficiency-skills`: su validador estructural pasa (2 Skills).
- `prompt-pack`: sus 24 casos de hooks pasan. El linter de Skills no pudo iniciar
  porque el clon no tiene instalada la dependencia Node `yaml`; no se ejecutó un
  `npm install` para no alterar el checkout de comparación.
- `codex-usage-audit`: 18/21 tests pasan en Windows; fallan tres casos de cache
  privado/reparse y el caso del hook Unix porque el comando de shell intenta usar
  `$(find ...)` bajo el launcher Python de Windows. Es una señal de portabilidad,
  no un fallo del parser principal.
- `prompt-cache-skills`: no se pudo ejecutar su suite porque este entorno no tiene
  `pytest`; el código fue inspeccionado estáticamente y `check_cache.py --help`
  sigue siendo un script estándar sin dependencias externas visibles.

## Resumen ejecutivo

| Proyecto | Mecanismo principal | ¿Reduce directamente el prompt? | ¿Funciona con Codex? | Valor para Astra-Ultra |
|---|---|---:|---:|---|
| astra-advisor | routing dinámico, subagentes nativos, revisión y recibo de costo | No | Sí, plugin | Adoptar contabilidad cerrada, evidencia de runtime y revisión fresca |
| codex-usage-audit | parseo local de rollouts y recomendaciones | No | Sí, plugin/hook | Adoptar telemetría de contexto, compaction, tool calls y unknown≠zero |
| prompt-pack | Skills pequeñas, disciplina de lectura y hooks deterministas | Indirectamente | Sí, `.agents/skills`/Codex target | Adoptar sólo la base mínima; no instalar las 23 Skills sin necesidad |
| codex-efficiency-skills | polling largo y validación proporcional al riesgo | Indirectamente | Sí, Skills nativas | Adoptar metodología de repetición, aleatorización de orden y correctness-first |
| prompt-cache-skills | auditoría wire/source de caching por harness | No, preserva el prefijo | Parcialmente: Codex es referencia | No inventar `prompt_cache_key`; mantener prefijos estables y medir en sesiones cálidas |
| Astra-Ultra | AST, packet bounded, RepoMap, prefix lock, sanitización y governor | Sí | Sí, repo/scripts/runner | Núcleo correcto; necesita mejor instrumentación y límites operativos |

Conclusión: Astra-Ultra está bien encaminado en reducción de contexto. La pieza
que falta no es otra colección de prompts, sino una separación estricta entre
reconocimiento determinista, síntesis de alto esfuerzo, verificación y medición
de sesiones/cache reales.

## Análisis exhaustivo de `astra-advisor`

### Arquitectura

El repositorio es un plugin Codex, no un compresor de contexto:

1. `.codex-plugin/plugin.json` registra el plugin y su Skill.
2. `plugins/astra-advisor/skills/orchestration/SKILL.md` define a GPT-6 Astra como
   arquitecto y dueño de aceptación.
3. `references/operations.md` convierte esa política en un protocolo operativo.
4. `agents/openai.yaml` aporta la metadata de interfaz.
5. `scripts/cost_receipt.py` valida usage por llamada y calcula el recibo.
6. `tests/test_cost_receipt.py` prueba contabilidad, cobertura y rechazo de datos
   peligrosos.
7. `pricing/2026-09-04.json` versiona las tasas y sus URLs de origen.

El flujo es deliberadamente dinámico: declara el modelo/esfuerzo observado del
padre, decide si delegar, elige `gpt-5.6-sol`, `gpt-5.6-terra` o `gpt-5.6-luna`
según riesgo/contexto/trabajo independiente, y pasa `model`,
`reasoning_effort` y `fork_turns: none` explícitamente. No tiene un mapa fijo de
roles, número fijo de subagentes ni TOMLs de roles. Después de una implementación
sustancial exige revisar el diff con un reviewer nuevo y read-only; sólo acepta
`ship`.

### Lo que hace muy bien

- Separa requested de observed: una solicitud de modelo no se presenta como
  prueba de que el runtime la usó.
- Falla cerrado cuando el tool, modelo, esfuerzo o control no están disponibles;
  no sustituye silenciosamente.
- Da a cada delegado un deliverable acotado y mantiene trabajo útil en el padre.
- Distingue recibo de tarea completa, delegado-only y cobertura parcial.
- Rechaza llamadas no atómicas, agregados acumulativos y parent-inclusive que
  duplicarían tokens.
- Trata `cached_input_tokens` como subconjunto de input y reasoning como
  subconjunto de output; no los cuenta dos veces.
- Mantiene `unknown` separado de cero y no inventa una factura de ChatGPT.
- Usa `Decimal`, IDs únicos de llamada, roster de agentes, cutoff del padre,
  fuente de usage y estado de cobertura.
- Compara el mismo usage observado repriced a Astra, pero lo etiqueta como
  **same-token API price comparison**, no como un contrafactual all-Astra.

Los puntos principales están en `SKILL.md:30-92`, `operations.md:32-96` y
`cost_receipt.py:146-490`.

### Límites detectados

- No reduce el input que recibe el primer modelo; puede aumentar tokens totales
  si delega sin que exista trabajo independiente.
- El calculador sólo acepta contexto standard hasta 128k y rechaza long-context,
  service tiers no-standard y cache-write telemetry. Es una frontera segura de
  implementación, no una frontera de precio oficial.
- El recibo no mide calidad, latencia ni consumo real de créditos; mide precio API
  equivalente con tokens observados.
- La política de selección es excelente como protocolo, pero la selección concreta
  sigue dependiendo del juicio del modelo padre; no existe un router determinista
  comparable a nuestro `resolve_effort`.

### Qué tomar y qué no tomar

Tomar: el esquema de llamadas atómicas, cobertura explícita, observed-vs-requested,
falla cerrada, reviewer fresco y límites de pricing. No tomar como reemplazo del
núcleo AST/packet. Astra Advisor y Astra-Ultra son capas complementarias:
Advisor decide quién hace qué; Astra-Ultra decide qué evidencia entra al contexto.

## Análisis de los otros repositorios

### `codex-usage-audit`

`usage_report.py` parsea JSONL local de Codex (`parse_rollout_uncached`), excluye
el prefijo copiado de un subagente usando el timestamp de inicio, deduplica eventos
acumulativos mediante deltas positivos y construye el árbol padre/descendientes.
Agrega input, cached input, cache writes, output, reasoning, tool calls, turns,
subagents, sesiones, máxima presión de contexto y compactions. El rate card separa
créditos Codex de API-equivalent USD y detecta multiplicadores Fast.

La recomendación determinista usa thresholds de tool calls, subagentes y ocupación
de ventana para sugerir `continue`, `summarize`, `start fresh` o `split`. El hook
`Stop` sólo imprime agregados y nunca el transcript.

Es la referencia más útil para ampliar nuestro parser: hoy
`benchmarks/benchmark_support.py` mide la salida JSONL del proceso, pero no tiene
la deduplicación completa de rollouts, contexto máximo, compactions ni árbol de
subagentes.

### `prompt-pack`

Su decisión arquitectónica correcta es progressive disclosure: la metadata de cada
Skill permite descubrirla y el cuerpo/referencias se carga sólo cuando aplica. Su
target `codex` instala `.agents/skills/<name>/SKILL.md` más un `AGENTS.md` compacto;
el target legacy concatena con límite de 32 KiB y reporta lo que quedó fuera.

`meta/token-discipline/SKILL.md` insiste en que tokens son presupuesto de atención,
no una meta monetaria: excluir dependencias, build outputs, lockfiles y logs grandes;
buscar con grep antes de leer; ensanchar sólo cuando la corrección lo exige. El
hook `guard-noise-reads.mjs` vuelve deterministas parte de esas reglas: bloquea
dependencias/lockfiles/minificados y pregunta antes de build outputs. Los otros
hooks guardan archivos duplicados y dependencias nuevas. Todos fallan open.

Para este repo conviene portar la disciplina mínima, no todo el catálogo. Instalar
23 Skills a la vez aumentaría superficie de activación y contexto de instrucciones.

### `codex-efficiency-skills`

Mantiene dos Skills separadas: `long-task-polling` evita despertares que sólo
confirman que un proceso sigue vivo; `risk-calibrated-validation` conserva checks
fuertes cuando hay riesgo creíble. La metodología exige control/tratamiento,
inputs/runtime/modelo constantes, repeticiones, orden aleatorizado, raw events y
correctness antes de eficiencia.

Es una corrección importante para nuestros benchmarks: una sola pareja baseline /
Astra no estima varianza. Nuestro runner ya añade `--order`, status de timeout,
tool/turn/event counts y artifacts; falta añadir trials repetidos y agregación
mediana/p95 antes de afirmar una mejora estable.

### `prompt-cache-skills`

Su auditoría de Codex CLI identifica el patrón correcto: `prompt_cache_key` estable
derivado de `thread_id`, `base_instructions` byte-estable, misma key tras compaction
y herencia hacia subagentes. No propone parchear Codex. Su `check_cache.py` hace dos
requests cold/warm, extrae counters específicos por proveedor y devuelve hit rate;
es un verificador experimental, no un estimador teórico.

La lección para Astra-Ultra es negativa y positiva:

- No generar UUIDs ni un cache key nuevo por llamada.
- Mantener el prefijo estático antes del packet dinámico y mantener estable el
  schema JSON.
- Medir cache sólo dentro de una sesión reutilizada. Nuestros procesos benchmark
  usan `--ephemeral` para aislar pares; por eso el cache hit de una corrida nueva
  puede ser cero y no debe interpretarse como fallo del diseño de caching.

El repositorio también contiene afirmaciones de pricing/provider que deben
revalidarse contra documentación oficial antes de usarlas como rate card. Para el
runner usamos las tasas oficiales versionadas en `benchmark_support.py` y las
marcamos como estimación API, no facturación.

## Qué cambió en Astra-Ultra

Se implementaron cinco controles en el runner y sus tests:

1. **Esfuerzo por workload**: `--effort auto` resuelve Raft a `max` y MVCC a
   `high`; un esfuerzo explícito sigue teniendo prioridad.
2. **Packet determinista**: hashes SHA-256, evidencia acotada, AST skeletons,
   ventanas enfocadas y autoridad `untrusted_source_data`; no se vuelca el log
   completo al prompt.
3. **Output estructurado**: `--output-schema` y `--output-last-message` fuerzan
   `diagnosis`, `evidence` y `answer` y dejan el JSON final como evidencia.
4. **Discovery bounded**: prompt de Astra con prohibición de listar/leer todo,
   como máximo una lectura de 50 líneas, y ejecución `read-only`.
5. **Medición auditable**: ledger por corrida, JSONL/stderr/answer/schema/packet,
   eventos, turns, tool calls, cache writes, timeout explícito y orden de ejecución.

También se corrigieron dos defectos del benchmark: las rutas del manifiesto ahora
apuntan al workspace real (`benchmarks/heavy_workloads/...`) y el dashboard no se
rompe si un baseline termina por timeout sin usage final.

Archivos principales: `benchmarks/run_heavy_benchmarks.py`,
`benchmarks/benchmark_support.py`, `benchmarks/build_suite_report.py`,
`benchmarks/plot_benchmark_charts.py` y
`benchmarks/heavy_workloads/benchmark_manifest.json`.

## Observación live reproducible

Se ejecutó una corrida por workload, misma máquina, mismo modelo
`gpt-5.6-luna`, orden baseline-first, `--effort auto`, sandbox read-only y
salida JSON estructurada. Es una **observación local preliminar**, no un resultado
universal.

| Workload | Input baseline → Astra | Input delta | Output+reasoning delta | Latencia | Costo API-equivalent | Tool calls | Aceptación |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raft / max | 193,755 → 18,654 | −90.4% | −26.3% | 65.54s → 39.82s (1.65×) | $0.01454 → $0.00596 (−59.0%) | 10 → 0 | 4/4 |
| MVCC / high | 127,159 → 107,958 | −15.1% | −6.2% | 57.79s → 54.94s (1.05×) | $0.01307 → $0.00672 (−48.6%) | 14 → 12 | 4/4 baseline; Astra matched 3/4 keyword checks |
| Total | 320,914 → 126,612 | −60.6% | −17.1% | 123.33s → 94.76s (1.30×) | $0.02761 → $0.01268 (−54.1%) | 24 → 12 | 2/2 |

La validación MVCC de Astra produjo el diagnóstico correcto y la ubicación de
líneas, pero no repitió literalmente la frase `dirty read`; por eso el detalle del
ledger queda en 3/4 aunque la corrida se acepta bajo el umbral actual. Conviene
mejorar el acceptance checker para combinar keywords con assertions semánticas o
campos específicos, no relajar el criterio.

El dashboard agregado está en
`benchmarks/dashboard_luna56_optimized_suite_v2.html`; los ledgers y artefactos
por workload están junto a sus nombres en `benchmarks/` y `.local/benchmark-artifacts/`.

## Plan recomendado

### P0 — cerrar la medición

- Añadir `--trials N`, order randomizado y agregación median/p95.
- Separar `accepted`, `keyword_coverage` y `semantic_assertions`.
- Representar usage no observado como `unknown`, nunca como cero facturable.
- Incorporar contexto máximo, compactions y subagentes al ledger.

### P1 — separar cache de token packing

- Mantener el benchmark paired `--ephemeral` para medir reducción de contexto.
- Crear otro protocolo warm-session de 3 turnos con prefijo estable y schema estable.
- Medir `cached_input_tokens`, cache writes, hit ratio y coste de cold/warm por
  separado; no mezclarlo con el resultado de packet compression.

### P1 — adaptar la contabilidad de Astra Advisor

- Reusar el modelo de llamada atómica, IDs únicos y cobertura parent/delegate/reviewer.
- Emitir un recibo API-equivalent con fuente, snapshot de pricing y alcance.
- Rechazar long-context/service-tier/cache-write cuando no exista tasa validada.

### P2 — incorporar disciplina mínima de Skills

- Añadir una Skill pequeña equivalente a `token-discipline` para el workflow Codex.
- Mantener referencias on-demand; no concatenar todo en `AGENTS.md`.
- Si se agregan hooks, que sean deterministas, opt-in y fail-open.

### P2 — routing dinámico separado

- Si se integra la idea de `astra-advisor`, usarla como capa de routing y review,
  no como sustituto del packet.
- Medir si una delegación realmente elimina trabajo del padre; si no hay trabajo
  independiente, mantener una sola ejecución.
- Registrar siempre requested/observed model y effort.

## Veredicto

No estamos haciendo algo conceptualmente mal. La ventaja de Astra-Ultra está en
reducir contexto irrelevante antes del turno caro; `astra-advisor` aporta gobierno
de subagentes y aceptación; `codex-usage-audit` aporta observabilidad; los otros
repositorios aportan disciplina, metodología y verificación de cache. La prioridad
es no mezclarlos en un mega-prompt: integrar sus mecanismos como capas pequeñas y
medibles, empezando por trials, unknown≠zero y un benchmark warm-session de cache.
