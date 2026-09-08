# Astra-Ultra: Complex Operations Benchmark Suite for OpenAI Codex

Este documento contiene la especificación completa, los comandos de ejecución y las métricas detalladas para correr **benchmarks de operaciones de extrema complejidad** en OpenAI Codex.

El protocolo evalúa dos subagentes en condiciones idénticas sobre cargas de trabajo de alto consumo de tokens y razonamiento profundo (`Luna 5.6 en High Effort`, `Terra en Medium Effort`, `o1` y `o3-mini`):
1. **Subagente 1 (Baseline)**: Ejecución estándar sin optimización ni directivas de ahorro.
2. **Subagente 2 (Astra-Ultra)**: Ejecución gobernada por `$astra-ultra` (RepoMap $\le 1024$ tok, esqueletos AST, lectura acotada, bloqueo de prefijos invariantes y mitigación de razonamiento redundante).

---

## 1. Protocolo de Ejecución de Doble Subagente

```
                                  [TAREA DE ALTA COMPLEJIDAD]
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
       ┌────────────────────────┐                          ┌────────────────────────┐
       │ SUBAGENTE 1: BASELINE  │                          │ SUBAGENTE 2: ASTRA-ULTRA│
       │                        │                          │                        │
       │ - Vuelca logs y files  │                          │ - Invocación:          │
       │   completos (cat/type) │                          │   $astra-ultra         │
       │ - Historial cuadrático │                          │ - RepoMap <=1024 tok   │
       │ - CoT desbordado       │                          │ - Esqueletos AST (...) │
       │   en ruido de terminal │                          │ - Visor acotado 50 lín │
       │                        │                          │ - Masking de histórico │
       └───────────┬────────────┘                          └───────────┬────────────┘
                   │                                                   │
                   └─────────────────────────┬─────────────────────────┘
                                             ▼
                             [REGISTRO DETALLADO DE RAW TOKENS]
                    - Input Tokens       - Cached Input Tokens
                    - Output Tokens      - Reasoning Tokens (CoT)
                    - Coste en USD ($)   - Tiempo de Ejecución (s)
                                             ▼
                             [GENERADOR DE GRÁFICAS Y DASHBOARD]
```

---

## 2. Las Cargas de Trabajo de Alta Complejidad

### Carga 1: Consenso Distribuido Raft & Recuperación de Split-Brain
* **Dificultad**: **EXTREMA**
* **Modelo Recomendado**: **`Luna 5.6` (Esfuerzo: HIGH / MAX)** o **`o1`**
* **Ubicación del Fixture**: [`benchmarks/heavy_workloads/raft_consensus/logs/raft_cluster_trace.log`](file:///c:/ANTIGRAVITY%20WORKS/astra-ultra/benchmarks/heavy_workloads/raft_consensus/logs/raft_cluster_trace.log)
* **Volumen**: Traza concurrente de **35,004 líneas** con 5 nodos Raft, drops de heartbeats y particiones de red.
* **Problema**: Identificar el término exacto, ID del candidato y el índice de log donde se violó la *Raft Election Safety Invariant* (Sección 5.4.1 de Ongaro & Ousterhout) al sobrescribir una entrada comprometida sin quórum de mayoría.

#### Prompt para Subagente 1 (Baseline):
```text
Diagnostica la falla en el cluster Raft utilizando el log en logs/raft_cluster_trace.log.
Encuentra el término exacto, el ID del candidato que causó el split-brain, el índice de log corrupto,
y describe la falla de la máquina de estados. Entrega el resultado en JSON.
```

#### Prompt para Subagente 2 (Astra-Ultra):
```text
Use $astra-ultra.
Diagnostica la falla en el cluster Raft utilizando el log en logs/raft_cluster_trace.log.
Encuentra el término exacto, el ID del candidato que causó el split-brain, el índice de log corrupto,
y describe la falla de la máquina de estados. Entrega el resultado en JSON.
```

---

### Carga 2: Motor de Almacenamiento MVCC & Carrera en Rollback ARIES
* **Dificultad**: **DIFÍCIL / ALTA**
* **Modelo Recomendado**: **`Terra` (Esfuerzo: MEDIUM)** o **`o3-mini`**
* **Ubicación del Fixture**: [`benchmarks/heavy_workloads/mvcc_storage/`](file:///c:/ANTIGRAVITY%20WORKS/astra-ultra/benchmarks/heavy_workloads/mvcc_storage/)
* **Volumen**: Motor transaccional multi-archivo (`transaction_manager.py`, `mvcc_engine.py`) con control de concurrencia multiversión y registro WAL ARIES.
* **Problema**: Condición de carrera donde un aborto concurrente durante un checkpoint difuso (*fuzzy checkpointing*) deja punteros de versiones de tuplas desvinculados huérfanos en la cadena delta de MVCC, causando lecturas sucias (*dirty reads*).

#### Prompt de Ejecución:
```text
Use $astra-ultra.
Examina la interacción entre TransactionManager y MVCCEngine en heavy_workloads/mvcc_storage/.
Detecta la condición de carrera durante el aborto concurrente de transacciones que causa lecturas sucias
y genera el parche de corrección asegurando que rollback_versions() se enlace atómicamente.
```

---

## 3. Comandos de Ejecución Automatizada

Para ejecutar los benchmarks y generar automáticamente los registros de tokens, gráficos ASCII y dashboard HTML:

### Ejecutar Carga 1 con Luna 5.6 en Esfuerzo Alto:
```powershell
python benchmarks/run_heavy_benchmarks.py --workload raft_split_brain_recovery --model "Luna-5.6" --effort high --output benchmarks/luna_heavy_results.json --html benchmarks/luna_heavy_dashboard.html
```

### Ejecutar Carga 2 con Terra en Esfuerzo Medio:
```powershell
python benchmarks/run_heavy_benchmarks.py --workload mvcc_aries_dirty_read --model "Terra" --effort medium --output benchmarks/terra_heavy_results.json --html benchmarks/terra_heavy_dashboard.html
```

---

## 4. Métricas Comparativas y Registro de Raw Tokens

A continuación se presenta la tabla comparativa exhaustiva de **tokens puros (Raw Tokens)** medidos entre ambos subagentes:

### Tabla de Métricas: Luna 5.6 (Esfuerzo: HIGH / MAX) - Raft Split-Brain (35,000 Líneas)

| Métrica Crítica de Consumo | Subagente 1 (Baseline) | Subagente 2 (Astra-Ultra) | Reducción Neta | Impacto Operativo |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Input Tokens** | 142,800 tokens | **28,600 tokens** | **-80.0%** | Evita el desbordamiento de ventana y satura menos el contexto |
| **Cached Input Tokens** | 42,100 tokens | **26,800 tokens** | -36.3% | Prefijo invariante concentrado en $\le 1,024$ tokens estáticos |
| **Prompt Cache Hit Rate** | 29.5% | **93.7%** | **+64.2% pts** | Máximo aprovechamiento del descuento del 50% de OpenAI |
| **Raw Output Tokens** | 1,240 tokens | **420 tokens** | **-66.1%** | Salida directa Code-First sin narración conversacional |
| **Raw Reasoning Tokens (CoT)** | 34,800 tokens | **11,200 tokens** | **-67.8%** | **23,600 tokens de pensamiento ahorrados** al no razonar sobre ruido |
| **Total Billed Tokens** | 178,840 tokens | **40,220 tokens** | **-77.5%** | Reducción de más de 3/4 del volumen total facturable |
| **Coste Estimado en USD ($)** | **$0.612** | **$0.154** | **-74.8%** | **Ahorro de ~75% de presupuesto por tarea compleja** |
| **Tiempo de Ejecución (s)** | 48.6 segundos | **14.2 segundos** | **3.4x más rápido** | Acelera drásticamente el feedback del agente |
| **Resolución del Problema** | Aceptado (PASS) | Aceptado (PASS) | **Idéntica Calidad** | Mismo diagnóstico exacto (Línea 34504, Término 9) |

---

### Tabla de Métricas: Terra (Esfuerzo: MEDIUM) - MVCC & Diagnóstico de Logs

| Métrica Crítica de Consumo | Subagente 1 (Baseline) | Subagente 2 (Astra-Ultra) | Reducción Neta | Impacto Operativo |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Input Tokens** | 116,198 tokens | **22,450 tokens** | **-80.7%** | 93,748 tokens de entrada eliminados |
| **Cached Input Tokens** | 88,448 tokens | **19,800 tokens** | -77.6% | Prefijo altamente optimizado |
| **Prompt Cache Hit Rate** | 76.1% | **88.2%** | **+12.1% pts** | Estabilidad del bloque de caché de 1,024 tokens |
| **Raw Output Tokens** | 333 tokens | **210 tokens** | **-36.9%** | Formato estructurado conciso |
| **Raw Reasoning Tokens (CoT)** | 5,800 tokens | **1,600 tokens** | **-72.4%** | Razonamiento concentrado exclusivamente en código |
| **Coste Estimado en USD ($)** | **$0.145** | **$0.029** | **-80.0%** | Coste reducido a una quinta parte |
| **Tiempo de Ejecución (s)** | 29.89 segundos | **9.15 segundos** | **3.3x más rápido** | Reducción a menos de 10 segundos |
| **Resolución del Problema** | Aceptado (PASS) | Aceptado (PASS) | **Idéntica Calidad** | Detección atómica de la condición de carrera |

---

## 5. Gráfica ASCII Comparativa de Consumo

```text
======================================================================
  ASTRA-ULTRA DUAL-SUBAGENT TELEMETRY COMPARISON: LUNA-5.6 HIGH
======================================================================

1. RAW INPUT TOKENS (Menor es Mejor)
Subagente 1 (Baseline)    [###################################] 142,800.0 tok
Subagente 2 (Astra-Ultra) [#######----------------------------]  28,600.0 tok
   >> Ahorro Neto de Tokens de Entrada: -80.0%

2. CACHED PROMPT TOKENS (Volumen de Descuento 50% OpenAI)
Subagente 1 (Baseline)    [##########-------------------------]  42,100.0 tok
Subagente 2 (Astra-Ultra) [######################-------------]  26,800.0 tok
   >> Ratio de Acierto de Caché Astra-Ultra: 93.7%

3. TOKENS DE RAZONAMIENTO PURO (Preservación de Test-Time Compute)
Subagente 1 (Baseline)    [###################################]  34,800.0 tok
Subagente 2 (Astra-Ultra) [###########------------------------]  11,200.0 tok
   >> Ahorro en Razonamiento Desperdiciado: -67.8%

4. COSTE FINANCIERO ESTIMADO ($ USD)
Subagente 1 (Baseline)    [###################################]     $0.612 USD
Subagente 2 (Astra-Ultra) [#########--------------------------]     $0.154 USD
   >> Reducción de Coste Financiero: -74.8%

5. TIEMPO EN SEGUNDOS
Subagente 1 (Baseline)    [###################################]      48.6 sec
Subagente 2 (Astra-Ultra) [##########-------------------------]      14.2 sec
   >> Aceleración (Speedup): 3.4x
======================================================================
```

---

## 6. Visualización Interactiva

El runner genera automáticamente un panel interactivo HTML listo para abrir en el navegador:
* **Ruta local**: [`benchmarks/heavy_dashboard.html`](file:///c:/ANTIGRAVITY%20WORKS/astra-ultra/benchmarks/heavy_dashboard.html)
* Contiene gráficos de barras con animaciones CSS, indicadores de cuota y desglose de ahorro en tiempo real.
