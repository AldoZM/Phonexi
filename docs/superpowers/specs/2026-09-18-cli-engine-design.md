# Phonexi — Motor CLI local (`--engine`)

> **Estado: medido el 20 de septiembre de 2026, en implementación.** El spike
> corrió en la máquina Windows con `claude` 2.1.278 y `agy` 1.2.7 y contestó las
> cuatro preguntas abiertas. Tres supuestos del diseño original salieron falsos y
> están corregidos abajo, marcados como **corregido por el spike**.
> Escrito el 18 de septiembre de 2026.

## Problema

Phonexi depende de una sola API externa. Todo pasa por Groq: la visión del
screenshot, la transcripción Whisper y la respuesta de texto. Eso implica una
`GROQ_API_KEY`, un límite de 14,400 peticiones al día, y que cada respuesta
sale de un modelo sobre el que no se elige nada más que el nombre.

En la máquina del usuario ya viven agentes de línea de comandos con sesión
propia y suscripción propia: `claude` (Claude Code) y `agy` (Antigravity CLI).
Son más capaces que el modelo del free tier y no consumen cuota de Groq.

## Idea

Dar la opción de que el motor que responde sea un CLI local, **reutilizando
toda la herramienta que ya existe**. No es un modo nuevo ni un flujo nuevo:
son los mismos hotkeys, la misma captura, la misma transcripción y las mismas
vistas. Lo único que cambia es quién contesta.

```
hotkey → screenshot / audio → [ MOTOR ] → vista (popup o web)
         └─ intacto ─┘         ↑           └─ intacto ─┘
                        groq | claude | agy
```

## Por qué encaja sin romper nada

`processor.py` ya dejó la costura hecha: `process()` y `process_text()`
devuelven `Iterator[str]`, y tanto `ResultWindow` como `WebView` consumen eso
en `show_and_collect()`. Cualquier motor que sepa ceder tokens encaja sin que
`listener.py` ni las vistas se enteren — es la misma jugada que ya se hizo con
`view_factory` para el modo web.

## Alcance

- Flag `-cli`, sin valor, que abre el picker de flechas con los CLIs instalados
  — el mismo `choose()` de `picker.py` que ya sirve a `-model`. Sin el flag,
  Phonexi usa la API como hoy. Combina con `-P`, `-w` y `-c` como las demás.
  **Corregido por el spike:** el diseño original proponía
  `--engine groq|claude|agy`, que competía con el `-model` que ya existe.
- Capa `phonexi/engines/`, simétrica a la capa `backends/` de la rama
  `linux-port`.
- El motor CLI se amarra para que no actúe como agente: sin herramientas más
  allá de lo mínimo (ver *Riesgos*).
- Los tests cubren el motor CLI con mocks del subproceso, igual que hoy se
  mockea Groq.

Fuera de alcance (YAGNI): descubrir CLIs automáticamente, elegir motor por
hotkey en caliente, fallback automático entre motores, configurar el motor
desde la página web, historial persistente de conversación.

## Arquitectura

```
phonexi/engines/
├── base.py       # Protocol Engine, CliEngine, errores neutrales
├── __init__.py   # get_engine(name), installed()
├── api.py        # adapta processor.py (Groq/Gemini) a la interfaz Engine
├── claude.py     # banderas y parser de Claude Code
└── agy.py        # banderas y parser de Antigravity
```

**Corregido por el spike:** el diseño original tenía un solo `cli.py` porque
suponía que los dos CLIs hablaban el mismo NDJSON. No lo hacen (ver *Formas de
salida*), así que cada uno trae su parser. Y `processor.py` no se mueve: se
queda donde está y `api.py` lo envuelve. Moverlo obligaría a reescribir las 808
líneas de `tests/test_processor.py` sin ganar nada.

### Interfaz

La interfaz es chica porque `processor.py` ya la definió de facto:

```python
class Engine(Protocol):
    def answer_image(self, path: Path, briefing: str | None) -> Iterator[str]: ...
    def answer_text(self, q: str, context, briefing: str | None) -> Iterator[str]: ...
```

`HotkeyListener` recibe el motor inyectado, igual que hoy recibe `view_factory`
y `briefing`. `main.py` resuelve el motor desde el flag antes de registrar los
hotkeys — mismo criterio que `-c`: si el motor no sirve, se sabe al arrancar y
no a media entrevista.

Los errores se vuelven neutrales al proveedor: `EngineNotConfiguredError` y
`EngineError` en lugar de `GroqNotConfiguredError` y `GroqAPIError`.

### Mecánica del motor CLI

Levanta el subproceso en modo no interactivo y lee NDJSON línea por línea,
cediendo cada delta de texto conforme llega:

```
Popen(argv, stdout=PIPE, stdin=DEVNULL)
  → por cada línea: json.loads → extract() del motor → si hay texto → yield
```

Tres detalles que el spike obligó a fijar y que no son opcionales:

- **`shutil.which()` para resolver el binario.** En Windows `claude` es un
  `.CMD` de npm, no un `.exe`: `Popen(["claude", ...])` muere con `WinError 2`.
  `agy` sí es `.exe`, pero se resuelve igual por simetría.
- **`stdin=DEVNULL`.** `claude` espera datos por stdin y se rinde a los 3
  segundos con un warning. Cerrarle stdin bajó el primer token de 7.78 s a
  4.89 s en el modo captura.
- **`--include-partial-messages` en `claude`.** Ver *Formas de salida*.

### Formas de salida

**Corregido por el spike.** Cada CLI emite un NDJSON distinto, así que no hay
un lector común:

- `claude` → `{"type":"stream_event","event":{"type":"content_block_delta",
  "delta":{"text":"..."}}}`, y **solo si se pasa `--include-partial-messages`**.
  Sin esa bandera, `--output-format stream-json` entrega la respuesta completa
  en un único evento `assistant` al final: 1 bloque a los 6.6 s en vez de 292
  deltas con hueco máximo de 0.26 s. La bandera no aparecía en el diseño
  original ni en su lista de banderas verificadas.
- `agy` → `{"event":"step_update","step_update":{"step_type":"agent_response",
  "text_delta":"..."}}`. No tiene equivalente de `--include-partial-messages`:
  entrega los deltas en ráfaga (0.20 s de dispersión en texto, 1.43 s en
  captura). Como el total es corto, se nota menos.

### Mapeo de lo que ya existe

| Pieza actual | En el motor CLI |
|---|---|
| `PROMPT` y briefing `-c` | `claude`: `--system-prompt`, verificado. `agy`: **sin bandera equivalente**, se anteponen al prompt |
| Screenshot | A Groq se le manda el PNG en base64; al agente se le pasa **la ruta** y él la lee con su herramienta — un viaje extra |
| Follow-ups (`Context`) | Los CLIs traen `--continue` nativo, pero se mantiene `Context` para que ambos motores se comporten igual y el motor siga siendo stateless |
| Transcripción Whisper | Se queda en Groq: ninguno de los dos CLIs procesa audio |

### Banderas verificadas (18 de septiembre, ampliado el 20)

- `claude` 2.1.278 — `-p/--print`, `--output-format stream-json`,
  `--include-partial-messages` (**la que faltaba**), `--verbose`, `--model`,
  `--system-prompt`, `--append-system-prompt`, `--allowed-tools`,
  `--disallowed-tools`, `--continue`, `--resume`.
- `agy` 1.2.7 — `-p/--print`, `--output-format`, `--model`, `--effort`,
  `--json-schema`, `--continue`, `--conversation`, `--mode`, `--sandbox`,
  `--agent`, `--dangerously-skip-permissions`. **Sin bandera de system prompt y
  sin bandera para restringir herramientas**, confirmado en su `--help`.

## Riesgos

### Son agentes, no chat completions

El riesgo principal. Un CLI de agente puede decidir ejecutar comandos, buscar
en la web o tocar archivos. En una entrevista se quiere una respuesta y nada
más, no que se ponga a explorar. El motor CLI debe arrancar amarrado desde el
primer día: `--disallowed-tools` en `claude` dejando solo lectura para el caso
del screenshot, y `--sandbox` con `--mode` en `agy`.

### Latencia

Phonexi existe para responder en segundos. Cada pregunta levanta un proceso
nuevo, y el screenshot además paga el tool call de leer la imagen. Groq
responde casi al instante; esto puede no hacerlo. Es lo primero que hay que
medir.

### El modo voz puede quedar híbrido

El flujo de voz hace **dos** llamadas a Groq, no una: Whisper transcribe y
luego el LLM responde. Si ningún CLI acepta un `.wav`, Whisper se queda aunque
la respuesta la dé el CLI. Eso sigue siendo útil, pero no es reemplazo total.

## Resultados del spike (20 de septiembre de 2026)

1. **¿El streaming es incremental de verdad?** En `claude`, sí, pero solo con
   `--include-partial-messages`. Sin ella llega todo al final. En `agy` los
   deltas salen en ráfaga, no token por token.
2. **¿La imagen sale a un costo tolerable?** Sí. Los dos leyeron un PNG de
   1600x900 con una pregunta de entrevista y contestaron correctamente.
   `claude` gasta un tool call de `Read`; `agy` gasta dos pasos de herramienta.
   El modo captura funciona con ambos motores.
3. **¿Alguno transcribe `.wav`?** No. `claude` lo dice de frente. `agy` no
   transcribe pero tampoco se rinde: se fue a investigar el archivo con 38
   llamadas a herramientas durante 49 segundos para acabar reportando que no
   había voz. **Whisper de Groq se queda**, y el modo voz sigue necesitando
   `GROQ_API_KEY`.
4. **¿Están `claude` y `agy` en la máquina Windows?** Sí, los dos.
   `claude` 2.1.278 en `AppData\Roaming\npm\claude.CMD`,
   `agy` 1.2.7 en `AppData\Local\agy\bin\agy.exe`.

### Latencia medida

Segundos hasta el primer texto visible y hasta terminar:

- `claude`, captura, respuesta corta — 4.9 s / 9.7 s
- `claude`, captura, respuesta larga — 5.1 s / 21.6 s
- `agy`, captura — 6.9 s / 8.9 s
- `claude`, texto suelto — 3.0 s / 15.6 s
- `agy`, texto suelto — 3.8 s / 4.6 s

`agy` termina antes; `claude` empieza a escribir antes y fluye más parejo.
Ninguno se acerca a Groq, que contesta casi al instante: son 3 a 7 segundos
fijos de arranque de proceso por pregunta. Es el precio de usar los modelos de
paga, y hay que asumirlo a sabiendas.

### El riesgo de agente, confirmado

El episodio de los 49 segundos con el `.wav` es la prueba de que la sección
*Riesgos* no era teórica. Y el reparto de correas es desigual:

- `claude` tiene `--allowed-tools` y `--disallowed-tools`. Verificado: con
  `--allowed-tools ""` no tocó nada, con `--allowed-tools Read` solo leyó la
  imagen. Queda bien amarrado.
- `agy` **no tiene ninguna bandera para restringir herramientas**. Su `--help`
  solo ofrece `--sandbox` y `--mode`. Es una correa más floja, y eso va dicho
  en el README en vez de escondido.

`claude --system-prompt` sí se respeta (verificado con un token centinela).
`agy` no tiene equivalente, así que el `PROMPT` se antepone al texto.

## Qué NO cambia

Los hotkeys, `screenshot.py`, `audio.py`, `listener.py`, `ui.py`,
`webserver.py`, el modo web con SSE y QR, el flag `-c` y su validación al
arrancar, y el comportamiento por default: sin `--engine`, Phonexi sigue
usando Groq exactamente como hoy.

## Nota sobre plataformas

`main` es Windows puro: `ctypes.windll` en `screenshot.py` y `pyaudiowpatch`
(WASAPI) en `audio.py`. En macOS el screenshot es adaptable — `mss` soporta
Mac, solo cambia cómo se obtiene la posición del cursor — pero el audio no:
macOS no permite capturar audio del sistema sin un dispositivo virtual tipo
BlackHole. Esa restricción es del sistema operativo, no del código.

Nada de esto bloquea este diseño: la capa de motores es Python puro con
`subprocess`, se escribe y se testea con mocks en cualquier plataforma. Solo
la prueba de punta a punta necesita Windows.
