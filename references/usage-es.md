# Usar Astra-cheap

La carpeta `astra-cheap` es una skill personal y portable. No depende de un proyecto concreto.
Instalala en la carpeta de skills personales de tu host.

Invocación:

```text
Usá $astra-cheap para esta tarea. Conservá el alcance completo y las verificaciones necesarias.
```

Podés usarla al programar, investigar, escribir, revisar datos o diagnosticar operaciones.
No necesitás ejecutar los scripts vos: la skill le indica al agente cuándo sirven y cuándo
es más barato usar las herramientas habituales. No cambia automáticamente de modelo ni activa
proveedores externos. El nombre visible es **Astra-cheap**; el identificador es `astra-cheap`.

Si la app todavía no la muestra, probá en una tarea nueva o recargá la lista de skills si tu
versión ofrece esa opción. Crear los archivos no demuestra que una sesión ya abierta haya
actualizado su catálogo. También podés indicar la ruta de `SKILL.md` para que se lea explícitamente.

## Qué incluye

- Una entrada breve que prioriza la siguiente decisión y evita repetir trabajo.
- Lecturas parciales con referencias y acceso al original intacto.
- Cápsulas de dependencias: detectan cambios o vencimiento antes de reutilizar una observación.
- Tratamiento especial de información viva: siempre pide evidencia fresca.
- Guías para varios tipos de trabajo, cargadas sólo cuando hacen falta.
- Pruebas locales y un benchmark reproducible de los helpers.

Los artefactos de una tarea deben quedar en una ubicación permitida de esa tarea, no mezclados
en la carpeta global de la skill. El paquete no instala un servicio ni mantiene una memoria
global de tus proyectos. No lee credenciales ni conecta un proxy a tu cuenta.

## Límites honestos

El paquete puede reducir material repetido y volumen de herramientas. No cambia la tarifa de
OpenAI, no controla cada token interno y no garantiza un porcentaje de ahorro de Plus. Las pruebas
del paquete verifican sus herramientas; no prueban por sí mismas que Astra conserve idéntica
calidad con menos cuota. Eso requiere comparar tareas reales aceptadas.

Para suspender el comportamiento, pedí: “Para esta tarea no uses Astra-cheap”. No cambia las
reglas del proyecto ni los controles del host. Para usarla en otra máquina, copiá la carpeta a
la ubicación de skills personales de ese host; los helpers requieren Python 3.10 o posterior.

No hace falta comprimir tu forma de hablar. Describí normalmente lo que necesitás: la economía
de ejecución es responsabilidad del agente, no del usuario.

## Uso cotidiano

Para archivos pequeños, conviene leer el contenido relevante completo. Antes de delegar,
`local_handoff.py` puede actualizar la evidencia localmente. Los packs son opcionales: si
provocan otra llamada para ampliar información, pueden terminar costando más.

No se ejecutan canaries, benchmarks ni tests de la skill en cada tarea. Las mediciones usan
sólo los datos que el host ya exponga; si faltan, quedan desconocidos. Un registro breve de
decisiones y evidencia puede ayudar en trabajos largos, pero no hace falta para una consulta corta.

La preferencia de modelo para subagentes la define el usuario en cada entorno. La skill no
impone una selección global ni sustituye modelos silenciosamente.
