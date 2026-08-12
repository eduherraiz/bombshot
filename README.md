# bombshot

A defuse-the-bomb party game running entirely on a **Home Assistant Voice
PE**. Triple-click the button, it reads out a serial number, 30 seconds of
accelerating ticking start, and someone has to cut the right wire.

*Juego de desactivar una bomba para fiestas, funcionando entero dentro de un
**Home Assistant Voice PE**. Triple clic, lee un número de serie, arrancan 30
segundos de tic-tac acelerando y alguien tiene que cortar el cable correcto.*

**[English](#english) · [Español](#español)**

---

## English

### What it is

A physical *Keep Talking and Nobody Explodes*-ish toy, built for a house
party. No custom PCB and no soldering iron required: everything runs on a
stock Home Assistant Voice PE (ESP32-S3, speaker, 12-LED ring, button, dial),
plus two wires plugged into its Grove port.

It is a **toy**, decorated as a cartoon bomb — round, black, painted fuse.
Nothing about it is meant to look realistic, and it is meant for indoors, at
a private party, among people who know what it is.

### How you play

1. **Triple-click** the center button. The ring lights up and the device
   reads out a 4-digit serial number.
2. The rule (print it on a card for the players):
   **last digit EVEN → cut RED. ODD → cut BLUE.**
3. You get 30 seconds of ticking. Cut the right wire and it is defused; cut
   the wrong one, or run out of time, and it explodes (and someone drinks).
4. Between rounds, screw the two wires back into the terminal block. The ring
   turns off by itself once it sees them reconnected. Triple-click again.

Triple-click re-arms from anywhere, including mid-round.

### Runs standalone, on purpose

The whole game lives in the **firmware**, not in Home Assistant. The device
was built to be taken to somebody else's house: no Home Assistant instance,
no known Wi-Fi, no cloud. It boots and it works.

The factory voice assistant is left completely intact and simply never
triggers without a Home Assistant connection, so the device can be reflashed
back to stock afterwards and used as a normal voice assistant again.

### Wiring

Two wires go to the **Grove port** on the base, under a tab you have to snap
off (irreversible, but purely cosmetic).

| Grove wire | Signal | GPIO | Game wire |
|---|---|---|---|
| White | SDA | GPIO1 | RED → GND |
| Yellow | SCL | GPIO2 | BLUE → GND |
| Red | 5V | — | unused, cut and insulate |

Internal pull-ups: intact = LOW, cut = HIGH.

> **The gotcha that cost hours with a multimeter:** the Grove port carries no
> signal at all unless its power rail is switched on (`grove_port_power`,
> GPIO46). Without it, SDA/SCL sit at 0 V no matter what you do outside, and
> the symptom is indistinguishable from a broken cable. `standalone.yaml`
> turns it on. If the wires ever stop responding, check this **first**.

### Build and flash

```bash
cd src/esphome
cp secrets.yaml.example secrets.yaml     # your Wi-Fi (only for OTA/logs)
esphome run standalone.yaml --device /dev/ttyACM0
```

`test_cables.yaml` is a minimal firmware with no game logic that just beeps
when either Grove pin sees continuity — useful for debugging wiring.

**Note:** a fresh clone will not compile until you deal with the victory
jingle. See [The intro audio](#the-intro-audio).

### Layout

```
src/
  esphome/standalone.yaml    the whole game; imports the official
                             home-assistant-voice-pe firmware as a package
  esphome/test_cables.yaml   minimal firmware to debug the Grove port
  esphome/sounds/            audio compiled into the firmware
  audio/*.py                 scripts that generate every sound
                             (numpy + ffmpeg, espeak-ng for speech)
  ha/packages/bomba.yaml     alternative version orchestrated from Home
                             Assistant, kept as a secondary option
  arduino/                   alternative version on an Arduino Nano
CLAUDE.md                    full design context and decision log
```

`CLAUDE.md` and the code comments are **in Spanish**.

### The intro audio

Winning plays a snippet of the MacGyver theme. That file is **not in this
repo** — it is third-party material, used privately on one device, and this
repo is public. Two one-line ways out:

- point `snd_intro` in `standalone.yaml` at `sounds/intro.mp3`, a synthesized
  copyright-free jingle that *is* included; or
- drop your own clip at `esphome/sounds/macgyver_intro_recorte.mp3`.

### Why the code looks like this

The interesting part of this repo is not the game, it is the three things
that had to be un-learned before it became reliable. All three are documented
at length in `CLAUDE.md` and in the header of `standalone.yaml`:

- **No global countdown timer.** The round length is a `delay: 30s` inside
  the game script; cutting a wire just stops that script. A global counter
  driven by an `interval` was the actual cause of "the countdown doesn't play
  on the round after it played through" — it carried the previous round's
  value into the next one.
- **No audio queue.** One script stops whatever is playing and starts the new
  clip, never enqueuing, and callers wait with fixed delays measured from the
  real file durations. Polling the media player's `is_announcing` and queuing
  announcements was what made sounds vanish mid-party.
- **Only one owner for the LED ring.** `led_ring` and `voice_assistant_leds`
  are two partitions over the *same* 12 physical LEDs, and with no Home
  Assistant connected the stock firmware keeps the second one running its red
  "disconnected" twinkle right over your effects.

### License

MIT — see [LICENSE](LICENSE). It covers the code, the YAML and the sounds
produced by the scripts in `src/audio/`. It does **not** cover the MacGyver
theme snippet, which is third-party material and is deliberately not part of
this repo — see [The intro audio](#the-intro-audio).

The Home Assistant Voice PE firmware is not vendored here: `standalone.yaml`
imports it at build time from
[esphome/home-assistant-voice-pe](https://github.com/esphome/home-assistant-voice-pe),
under its own license.

---

## Español

### Qué es

Un juguete físico tipo *Keep Talking and Nobody Explodes*, hecho para una
fiesta en casa. Sin PCB a medida ni soldador: todo corre sobre un Home
Assistant Voice PE de serie (ESP32-S3, altavoz, aro de 12 LEDs, botón y
rueda), más dos cables enchufados a su puerto Grove.

Es un **juguete**, decorado como una bomba de dibujos animados: redonda,
negra, con la mecha pintada. Nada de estética realista, y pensado para
usarlo en interior, en una fiesta privada, entre gente que sabe lo que es.

### Cómo se juega

1. **Triple clic** en el botón central. El aro se ilumina y el aparato lee un
   número de serie de 4 dígitos.
2. La regla (imprímela en una tarjeta para los jugadores):
   **último dígito PAR → cortar ROJO. IMPAR → cortar AZUL.**
3. Hay 30 segundos de tic-tac. Aciertas y se desactiva; fallas, o se acaba el
   tiempo, y explota (y alguien bebe un chupito).
4. Entre rondas, volver a atornillar los dos cables en la regleta. El aro se
   apaga solo en cuanto detecta que están puestos. Triple clic otra vez.

El triple clic rearma desde cualquier punto, también a media partida.

### Autónomo a propósito

El juego entero vive en el **firmware**, no en Home Assistant. El aparato se
hizo para llevárselo a casa de otra persona: sin instancia de Home Assistant,
sin WiFi conocida, sin nube. Arranca y funciona.

El asistente de voz de fábrica se deja intacto y, sencillamente, nunca se
activa sin Home Assistant conectado, así que después se puede reflashear el
firmware de stock y volver a usarlo como asistente de voz normal.

### Cableado

Los dos cables van al **puerto Grove** de la base, bajo una pestaña que hay
que romper (irreversible, pero solo estético).

| Hilo del Grove | Señal | GPIO | Cable del juego |
|---|---|---|---|
| Blanco | SDA | GPIO1 | ROJO → GND |
| Amarillo | SCL | GPIO2 | AZUL → GND |
| Rojo | 5V | — | no se usa: cortar y aislar |

Pull-up interno: intacto = LOW, cortado = HIGH.

> **El detalle que costó horas de multímetro:** el puerto Grove no lleva
> señal ninguna si no se enciende su interruptor de alimentación
> (`grove_port_power`, GPIO46). Sin él, SDA/SCL se quedan a 0 V pase lo que
> pase por fuera, y el síntoma es idéntico al de un cable roto.
> `standalone.yaml` ya lo enciende. Si algún día los cables dejan de
> responder, mira esto **lo primero**.

### Compilar y flashear

```bash
cd src/esphome
cp secrets.yaml.example secrets.yaml     # tu WiFi (solo para OTA/logs)
esphome run standalone.yaml --device /dev/ttyACM0
```

`test_cables.yaml` es un firmware mínimo, sin lógica de juego, que solo pita
cuando alguno de los pines del Grove ve continuidad — útil para depurar el
cableado.

**Ojo:** un clon recién hecho no compila hasta resolver lo del audio de
victoria. Ver [El audio de la intro](#el-audio-de-la-intro).

### Estructura

```
src/
  esphome/standalone.yaml    el juego entero; importa el firmware oficial
                             de home-assistant-voice-pe como paquete
  esphome/test_cables.yaml   firmware mínimo para depurar el Grove
  esphome/sounds/            audio que se compila dentro del firmware
  audio/*.py                 scripts que generan todos los sonidos
                             (numpy + ffmpeg, espeak-ng para la voz)
  ha/packages/bomba.yaml     variante orquestada desde Home Assistant,
                             como opción secundaria
  arduino/                   variante alternativa con Arduino Nano
CLAUDE.md                    contexto completo y registro de decisiones
```

### El audio de la intro

Al ganar suena un trozo de la sintonía de MacGyver. Ese fichero **no está en
el repo**: es material de terceros, se usa en privado en un solo dispositivo
y este repo es público. Dos salidas, las dos de una línea:

- apuntar `snd_intro` en `standalone.yaml` a `sounds/intro.mp3`, un jingle
  sintetizado sin copyright que sí viene incluido; o
- poner tu propio recorte en `esphome/sounds/macgyver_intro_recorte.mp3`.

### Por qué el código es así

Lo interesante de este repo no es el juego, son las tres cosas que hubo que
desaprender para que fuese fiable. Las tres están explicadas a fondo en
`CLAUDE.md` y en la cabecera de `standalone.yaml`:

- **Sin cronómetro global.** La duración de la ronda es un `delay: 30s`
  dentro del script de la partida; cortar un cable simplemente para ese
  script. Un contador global movido por un `interval` era la causa real de
  "la cuenta atrás no suena en la ronda siguiente a la que sonó entera":
  arrastraba el valor de la ronda anterior.
- **Sin cola de audio.** Un solo script para lo que esté sonando y lanza el
  clip nuevo, sin encolar nunca, y quien llama espera con delays fijos
  medidos de la duración real de cada fichero. Sondear `is_announcing` del
  media player y encolar anuncios era lo que hacía desaparecer sonidos en
  plena fiesta.
- **Un solo dueño para el aro de LEDs.** `led_ring` y `voice_assistant_leds`
  son dos particiones sobre las *mismas* 12 LEDs físicas, y sin Home
  Assistant conectado el firmware de fábrica mantiene la segunda con su
  parpadeo rojo de "sin conexión" pintando por encima de tus efectos.

### Licencia

MIT — ver [LICENSE](LICENSE). Cubre el código, el YAML y los sonidos que
generan los scripts de `src/audio/`. **No** cubre el trozo de la sintonía de
MacGyver, que es material de terceros y que a propósito no está en este repo
— ver [El audio de la intro](#el-audio-de-la-intro).

El firmware del Home Assistant Voice PE no está copiado aquí:
`standalone.yaml` lo importa al compilar desde
[esphome/home-assistant-voice-pe](https://github.com/esphome/home-assistant-voice-pe),
con su propia licencia.
