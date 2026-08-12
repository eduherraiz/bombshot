# Contexto del proyecto — Bomba de juguete

## Qué es

Juguete tipo *Keep Talking and Nobody Explodes* físico: una caja con cuenta
atrás, sonido de tic-tac y dos cables. Hay que deducir cuál cortar. Si aciertas
se desactiva, si fallas "explota". Para una fiesta **en una casa que no es la
mía** — el dispositivo no va a estar conectado a mi Home Assistant.

**Es un juguete de interior, decorado en plan bomba de dibujos animados (negra,
redonda, mecha pintada). Nada de estética realista.**

## Decisiones ya tomadas (no re-abrir sin motivo)

1. **Hardware: Home Assistant Voice PE.** Ya trae ESP32-S3, altavoz, aro de 12
   LEDs, botón central y rueda. La alternativa (Arduino Nano + TM1637 +
   DFPlayer) queda descartada como plan A pero el sketch está en `arduino/`
   por si se quiere una versión portátil permanente.

2. **La lógica vive en el propio firmware, ESPHome autónomo** (`esphome/standalone.yaml`),
   **no en Home Assistant.** Motivo: el juguete se usa en casa de otra
   persona, no en la mía, así que no puede depender de mi instancia de HA ni
   de que haya WiFi/servidor disponible allí. La variante con Home Assistant
   (`ha/packages/bomba.yaml`) queda como opción secundaria, solo útil si algún
   día se monta en una casa que ya tenga HA propio y se prefiera TTS en vivo
   en vez de audios de dígitos pregrabados.
   - `standalone.yaml` **importa el firmware oficial como `packages:`**
     (`github://esphome/home-assistant-voice-pe/home-assistant-voice.yaml@dev`)
     en vez de partir de una copia pegada a mano — así se actualiza solo si
     el firmware oficial cambia.
   - **No se elimina el asistente de voz de fábrica** (`voice_assistant:`,
     `micro_wake_word:`, `voice_kit:`): se deja intacto y convive con el
     juego. Sin Home Assistant conectado nunca se activa (el propio firmware
     ya maneja ese estado con su animación de "sin conexión"), así que no
     hay downside en dejarlo — y evita tener que desmontar a mano un
     subsistema grande que no puedo compilar-verificar aquí.
   - El sonido usa el componente real `audio_file:` + una llamada
     `.set_media_url("audio-file://" + nombre).set_announcement(true).perform()`
     sobre `external_media_player` — el mismo patrón que usa el propio
     firmware de fábrica para sus sonidos de botón/mute/etc. (Los intentos
     anteriores de usar `play_file` o `play_on_device_media_file` no existen
     en el firmware real, se han corregido.)
   - El botón central ya trae de fábrica una máquina de estados compleja
     (clic simple/doble/triple/largo, combo Morse, reset de fábrica). Para
     armar el juego se reutiliza el **triple clic** (hoy solo dispara un
     evento inerte sin Home Assistant conectado) en vez de inventar un gesto
     nuevo que pudiera chocar con los ya definidos. Se extiende con
     `id: !extend center_button` en vez de redefinir el sensor. `!extend`
     **concatena** listas (confirmado compilando), así que el bloque de
     fábrica sigue intacto y el nuestro se añade aparte: en el `!extend`
     va SOLO lo nuevo.
   - Crítico: `reboot_timeout: 0s` en `api:` y `wifi:` — de fábrica el
     dispositivo se reinicia solo a los 15 min sin cliente API o sin WiFi, lo
     que mataría cualquier partida en marcha en una casa sin mi red.
   - El número se dice con clips pregrabados (`espeak-ng` vía
     `audio/generar_numeros.py`) en vez de TTS en vivo — ver punto 5 para
     el detalle de las listas y del nombrado `snd_n<numero>`.
   - La intro de MacGyver (`audio/manual/macgyver_intro.mp3`, 67.6 s,
     suministrada por el usuario — no generada ni descargada por Claude)
     suena **al ganar**, recortada al tramo 19s-30s (~11 s,
     `sounds/macgyver_intro_recorte.mp3`). Uso privado en un dispositivo
     propio para una fiesta en casa, sin redistribuir.
   - **Ese audio NO está en el repo** (`github.com/eduherraiz/bombshot`,
     público): está en `.gitignore` junto con el original completo,
     porque subirlo sería redistribuirlo. Vive solo en local. La
     alternativa sintetizada sin copyright (`audio/generar_intro.py` →
     `sounds/intro.mp3`) sí viaja en el repo, y el propio
     `standalone.yaml` explica cómo cambiar de una a otra. Si algún día
     se clona el repo en limpio, hay que resolver eso antes de compilar.
   - **El aro de LEDs tiene dos dueños.** `led_ring` (la luz "de cara al
     usuario") y `voice_assistant_leds` (interna) son **dos particiones
     sobre las mismas 12 LEDs físicas**. Sin Home Assistant conectado, el
     `control_leds` de fábrica deja `voice_assistant_leds` encendido con
     su "Twinkle" rojo de *sin conexión*, que repinta por encima de
     nuestros efectos. Por eso el juego apaga `voice_assistant_leds` al
     entrar en cada fase **y** un `interval` de 500 ms lo mantiene apagado
     mientras hay partida (el firmware lo puede reencender en cualquier
     momento: cambios de volumen, pulsaciones, estado del media player).
   - El asistente de voz de fábrica no gasta CPU en la fiesta: en el YAML
     oficial `micro_wake_word.start` solo se dispara desde
     `api: on_client_connected`, así que sin Home Assistant nunca arranca.
   - **Verificado por compilación** (ver "Estado actual").

3. **Los dos cables van al puerto Grove** (base del aparato, bajo una pestaña
   que hay que romper — irreversible pero solo estética). Verificado contra
   `modules/grove-i2c.yaml` del repo oficial `esphome/home-assistant-voice-pe`
   (antes teníamos SCL/SDA cruzados en la etiqueta, aunque el pin GPIO ya
   era el correcto):
   - Hilo blanco = SDA = **GPIO1** → cable ROJO del juego → GND
   - Hilo amarillo = SCL = **GPIO2** → cable AZUL del juego → GND
   - Hilo rojo (5V) **no se usa**, se corta y se aísla.
   - Pull-up interno. Intacto = LOW. Cortado = HIGH.
   - No se incluye el paquete `grove-i2c.yaml` de fábrica (no queremos I2C en
     ese puerto, solo GPIO simple), así que no hay conflicto de uso del pin.
   - **CRÍTICO, encontrado tras mucho depurar en hardware real (2026-08-10):**
     el puerto Grove no lleva señal a menos que se encienda su interruptor
     de alimentación (`grove_port_power`, GPIO46 — módulo de fábrica
     `modules/grove-power.yaml`). Sin él, SDA/SCL se quedan a 0V pase lo
     que pase por fuera (el puerto tiene protección/adaptación de nivel de
     por medio que necesita ese riel). Costó varias horas de depuración
     con multímetro porque el síntoma (0V constante, sin reaccionar a
     nada) es indistinguible de un cable roto o un conector mal encajado.
     `standalone.yaml` ya lo enciende (`restore_mode: ALWAYS_ON`). Si se
     toca el cableado del Grove en el futuro y deja de responder: comprobar
     esto ANTES que el cableado físico.

4. **Toda la cuenta atrás es un solo fichero pregrabado** de 36.2 s
   (`sounds/cuenta_atras.flac`): 30 s de tic-tac acelerando + la explosión
   final ya incorporada. Así no hay nada que sincronizar. Generado por
   `audio/generar_audio.py --seg 30` (antes 60 s, acortado tras probarlo
   en fiesta real: 60 s se hacía largo entre rondas; el tic-tac acelera en
   función de la duración total, así que cambiar los segundos implica
   regenerar el audio **y** el `delay: 30s` del YAML).
   - **FLAC 48 kHz mono 16 bits, no MP3.** Es exactamente el formato del
     `announcement_pipeline` del firmware, así que el ESP32 no decodifica
     MP3 ni remuestrea de 44.1 a 48 kHz en el fichero más largo y pesado
     del juego. `generar_audio.py` lo saca en los dos formatos; el MP3
     queda como alternativa (una línea en el `audio_file:`).
   - Sonido de derrota "Has perdido." + "Bebe un chupito." tras la
     explosión, como **dos clips separados** (una frase larga sonaba mal
     en la primera mitad), `audio/generar_perdiste.py`, espeak-ng a
     135 wpm — es un juego de fiesta con alcohol, asúmelo como parte del
     diseño. Ese mismo script genera el aviso de "No se puede armar.
     Repara los cables antes de empezar." (`snd_no_armar`), que suena con
     el aro en amarillo si se intenta armar con un cable ya cortado.
   - **Explosión contundente**: `explosion_grande()` encadena tres
     detonaciones solapadas de intensidad creciente (~6,2 s), la gorda la
     última. Se usa tanto para el boom suelto (cable equivocado) como para
     el final de la pista de cuenta atrás.
   - **EL ALTAVOZ DEL VOICE PE NO TIENE GRAVES, y eso cambia cómo hay que
     sintetizar** (2026-08-12, medido). La primera explosión "sonaba a
     soplido" y el motivo era medible: tenía el **98,6 % de su energía por
     debajo de 400 Hz**, y este altavoz no baja de ~250 Hz. Todo el trabajo
     estaba en frecuencias que el aparato no radia. Lo que lo arregló:
     - Repartir la energía por la banda que sí reproduce (300 Hz - 8 kHz):
       un transitorio brillante de 1,2-9 kHz (el "algo ha reventado"), el
       cuerpo en 300-3000 Hz, el rugido en 150-1000 Hz y metralla
       (chasquidos sueltos) en 800-6000 Hz.
     - **Saturar y LUEGO filtrar el grave**, en ese orden: la saturación
       genera los armónicos del sub y el oído reconstruye la fundamental
       que falta, así que después se puede quitar el sub real (que solo se
       comía margen de volumen). Es la cadena clásica de realce de graves
       para altavoces pequeños, y aquí se nota mucho.
     - Reverb por convolución al final: una explosión seca suena a
       petardo; lo que la hace sonar grande es el eco del sitio.
     - Resultado: energía por encima de 300 Hz del 1,4 % al 76,7 %, y el
       "punch" audible (RMS de la banda >300 Hz en el primer segundo y
       medio) ×6.
     - **Regla general para futuros sonidos de este cacharro:** si suena
       flojo, antes de subir el volumen mira dónde está la energía. Los
       filtros están en `audio/generar_audio.py` (`filtro`, `saturar`,
       `reverberar`), en FFT y sin scipy, que en esta máquina no hay.

   **CÓMO SE MANEJA EL AUDIO (reescrito el 2026-08-11, esto es lo que da
   estabilidad — no volver al modelo anterior):**
   - Un único script toca el altavoz: **`bomba_sonar` para lo que suene y
     lanza el clip nuevo. Nunca encola.** Es el mismo patrón que el
     `play_sound` de fábrica con `priority: true`. Como no se encola
     nada, la cola de anuncios del media player no puede desbordarse
     ("Queue full, URI dropped", que era lo que hacía desaparecer sonidos
     enteros tras varias rondas).
   - **Las esperas son `delay:` fijos del tamaño real del fichero**, no
     sondeos de `is_announcing`. Las duraciones están medidas con ffprobe
     y anotadas al lado de cada delay en el YAML. Si cambias un fichero,
     cambia su delay.
   - Lo que había antes (`bomba_play` con `mode: queued`, parámetro
     `bloqueante`, `wait_until` sobre el media player, timeouts a ojo, y
     `wait_until !is_running()` sueltos para compensar que
     `script.execute` no espera al script llamado) era la fuente de casi
     todos los fallos de audio. Está eliminado entero.
   - **No hay cronómetro.** El tiempo de la partida es el `delay: 30s`
     dentro de `bomba_partida`; si alguien corta un cable, el sensor hace
     `script.stop: bomba_partida` y ahí muere. Esto sustituye al global
     `bomba_restante` + `interval: 1s`, que era el **bug que rompía la
     cuenta atrás**: el estado pasaba a "armada" antes de leer la serie
     pero el global no se recargaba hasta después, así que el interval
     veía el valor de la ronda anterior (0 tras una explosión), daba el
     tiempo por agotado al segundo de armar y disparaba la explosión en
     plena lectura de dígitos, matando el audio de cuenta atrás recién
     lanzado. Síntoma exacto: *"la cuenta atrás no se oye justo después
     de una ronda en la que sí se oyó entera"*, y "a veces sí va" (tras
     una victoria cómoda quedaba tiempo residual suficiente).
   - Al agotarse el tiempo **no se lanza ningún boom**: la explosión ya
     viene dentro del propio fichero de cuenta atrás, así que solo hay
     que dejarlo sonar. Antes se paraba el fichero y se lanzaba
     `snd_boom` encima, con las dos explosiones pisándose.
   - **Rearmar ya no reinicia el ESP32.** El triple clic siempre llama a
     `bomba_armar`, que para los tres scripts del juego, para el audio,
     apaga las luces y vuelve a empezar. El reinicio (que costaba ~10 s y
     obligaba a triple-clicar otra vez) era un parche para la fragilidad
     de la versión anterior; queda comentado en el YAML por si acaso.
   - **La rueda ya no ajusta la duración**, solo el volumen (lo de
     fábrica). El ajuste 20-180 s nunca pudo funcionar: el audio dura lo
     que dura, así que con 180 s la bomba estallaba en el audio a los 30
     y la partida seguía otros 150 s en silencio. Además movía el volumen
     a la vez, porque `!extend` concatena y la acción de fábrica se
     seguía ejecutando.
   - **La celebración dura lo que dura la canción.** `bomba_ganar` se queda
     vivo los ~11 s de la intro encadenando efectos, en vez de terminar
     nada más lanzarla. No es solo estético: el `interval` que devuelve la
     bomba a "espera" comprueba que no haya scripts en marcha, así que
     mientras el script vive nadie apaga el aro. Antes las LEDs se apagaban
     a mitad de canción en cuanto se reempalmaban los cables — o incluso
     sin tocarlos, si los dos extremos recién cortados se rozaban un
     instante (`delayed_off: 300ms` y el reset lo daba por "empalmado").
     Rearmar durante la celebración sigue funcionando: `bomba_armar` para
     el script y corta la música.
   - **Efectos de LED propios en `led_ring`** (`id: !extend led_ring`, de
     fábrica no trae ninguno). Ver en el punto 2 lo de apagar
     `voice_assistant_leds`: sin eso, el firmware de fábrica repinta el aro
     por encima.
     - `leyendo` — celeste/blanco alternando, mientras dice el número.
     - `tension` / `tension_rapida` / `tension_critica` — los tres tramos de
       la cuenta atrás. **No son arbitrarios: marcan los dos cambios de
       ritmo del tic-tac**, que salen de `intervalo()` en
       `audio/generar_audio.py` (tic cada 0,50 s hasta que quedan 10 s,
       cada 0,25 s hasta que quedan 5, y cada 0,12 s en los últimos 5). Van
       de pulso rojo tranquilo → parpadeo naranja/rojo al doble de
       velocidad → cometa girando a toda velocidad. El último es
       movimiento, no fogonazo a pantalla completa: se lee igual de urgente
       y es menos agresivo para la vista.
       **Los tres `delay` de `bomba_partida` tienen que sumar los 30 s de la
       pista de audio**; si se regenera el audio con otra duración, hay que
       recalcularlos.
     - `fiesta` / `arcoiris` / `chispas` — se encadenan durante la canción
       de victoria (ver punto 4, "la celebración dura lo que dura la
       canción").

5. **Mecánica del juego (modo regla, no azar puro):** al armar se sortea un
   número que se dice en voz alta, dos veces.
   - número **PRIMO** → cortar ROJO
   - número **NO primo** → cortar AZUL
   Hay que imprimir la regla en una tarjeta para los jugadores.
   - Antes era "último dígito par/impar" sobre un número de 4 dígitos, y
     resultó **demasiado obvio**: quien sabía la regla no tenía que pensar
     nada. Con primos hay que pararse un segundo, que es justo la gracia.
   - Los números salen de dos listas de 20 (`audio/generar_numeros.py`, que
     es la **fuente de la verdad**): los 20 primeros primos, y 20 compuestos
     elegidos a mano para que se vea a simple vista que no son primos
     (pares, acabados en 0 o 5, tabla del 3). Nada de 51, 57 o 91, que hacen
     dudar hasta al que sabe la regla — el juego es adivinar la regla, no
     hacer aritmética mental con alcohol encima.
   - Las dos listas están **repartidas por el mismo rango** (4 primos y 4
     compuestos por debajo de 10, 8 y 8 entre 11 y 40, 8 y 8 entre 41 y 71).
     Si los compuestos fuesen todos pequeños, "número grande = primo" sería
     un atajo que se carga el juego.
   - Se sortea primero **si la respuesta es primo** y luego qué número
     concreto, en vez de sortear entre los 40 de golpe: así cada cable sale
     exactamente el 50 % de las veces pase lo que pase con las listas.
   - El número se dice **entero** ("cuarenta y siete"), no dígito a dígito,
     porque la regla va del número completo. Y **dos veces**, porque en una
     fiesta con ruido una sola palabra corta se pierde.
   - Los 40 clips (`n2.flac`...`n71.flac`) se sintetizan pasándole la cifra
     ("47") a espeak-ng, que ya sabe decirla en español: así no hay que
     escribir 40 nombres a mano y no puede haber erratas. Son FLAC 48 kHz
     mono **16 bits** — la mitad de tamaño que 24 bits, que con 40 clips ya
     se nota (1,4 MB de flash).
   - **Ojo al tocar las listas:** el nombre del audio se construye
     concatenando (`"snd_n" + std::to_string(numero)`), así que un número en
     el array de C++ sin su `audio_file` correspondiente **no da error de
     compilación, da una ronda muda**. Por eso `generar_numeros.py --yaml`
     escupe los dos bloques ya listos para pegar.
   - Los clips de dígitos sueltos (`d0.flac`...`d9.flac`,
     `audio/generar_digitos.py`) ya no los usa el firmware. El script y los
     ficheros siguen en `audio/out/` por si alguna vez se quiere volver a
     leer un número largo cifra a cifra.

6. **Rearme entre partidas:** los cables van a una regleta de tornillo. Se
   pelan 5 mm y se vuelven a atornillar. Debe llevar menos de un minuto o la
   fiesta se muere entre rondas.

7. **Al terminar la fiesta se reflashea el firmware de stock.** Ver la
   sección "Plan: vuelta al estado stock" más abajo — el dispositivo vuelve
   conmigo y tiene que quedar funcionando como asistente de voz normal otra
   vez.

## Estado actual

- [x] Audio de cuenta atrás / boom / ok generado (`audio/out/*.mp3`)
- [x] Clips de dígitos generados (`audio/out/d0.flac`...`d9.flac`, español,
      voz "es" de espeak-ng, mono 48 kHz) — script `audio/generar_digitos.py`.
      Usa `libespeak-ng.so` por `ctypes` en vez del binario `espeak-ng`
      porque esta máquina no tenía permisos para instalarlo con apt; si en
      otra máquina sí está el binario, sirve igual sin tocar el script.
      Pendiente: escuchar los 10 clips y comprobar que se entienden bien en
      el altavoz real del Voice PE (por ahora solo verificados por duración).
- [x] Lógica autónoma completa escrita (`esphome/standalone.yaml`), montada
      sobre la base oficial vía `packages: github://...@dev`
- [x] **Probado en el hardware real** (2026-08-10): flasheado y jugado de
      verdad sobre un Voice PE con cables en breadboard. El hallazgo
      importante del día: hay que activar `grove_port_power` (punto 3).
- [x] **Reescritura completa de la lógica (2026-08-11)** buscando
      estabilidad, tras los fallos vistos jugando: "la cuenta atrás no
      suena cuando ya ha sonado antes" y rearmes poco fiables. Ver el
      punto 4 ("cómo se maneja el audio") para el diagnóstico y el
      diseño nuevo. Resumen: fuera el cronómetro global (era el bug),
      fuera la cola de audio y los `wait_until`, fuera el reinicio para
      rearmar, fuera el ajuste de duración con la rueda, y se apaga
      `voice_assistant_leds` para que el firmware de fábrica no repinte
      el aro por encima.
- [x] `esphome config` valida limpio y
      `esphome --toolchain platformio compile standalone.yaml` termina en
      SUCCESS con la versión nueva (2026-08-11, esphome 2026.7.4).
      Flash 56.7% (4.6MB/8.1MB), RAM 22.4%. `esphome` se instala sin root
      en un venv local (no persiste entre sesiones: `python3 -m venv
      --without-pip` + `get-pip.py` + `pip install esphome`, con el mismo
      truco a mano en `~/.platformio/penv` porque falta
      `python3.12-venv`/`ensurepip` del sistema y no hay sudo).
- [ ] **Volver a probar en hardware la versión reescrita** — está
      compilada y validada, pero todavía no jugada. Es lo siguiente que
      hay que hacer: `esphome run standalone.yaml --device /dev/ttyACM0`
      y 6 rondas seguidas (ver el ensayo de más abajo).
- [ ] Romper la pestaña Grove y soldar/crimpar los cables a la regleta
      (de momento probado con cables sueltos en breadboard, no en la
      regleta de tornillo definitiva)
- [ ] Ensayo completo: 6 rondas seguidas cronometrando el rearme
- [ ] Decorar la caja
- [ ] Resolver las dudas abiertas del plan de vuelta al estado stock (abajo)
- (Opción secundaria, no bloqueante) Paquete de Home Assistant ya escrito en
      `ha/packages/bomba.yaml` por si se usa la variante con HA

## Plan: vuelta al estado stock (al terminar la fiesta)

Plan todavía sin ejecutar — el dispositivo vuelve a mi casa después de la
fiesta y tiene que quedar otra vez como un Home Assistant Voice PE normal,
funcionando como asistente de voz.

1. **El YAML custom ya queda a salvo en este repo** (`esphome/standalone.yaml`
   + la base oficial de referencia), así que no hay nada que respaldar aparte
   — se puede reflashear sin miedo a perderlo, y reutilizar en otra fiesta.
2. **Desconectar los cables** de la regleta de tornillo. La pestaña rota del
   Grove es solo estética; GPIO1/GPIO2 no los usa el firmware de stock para
   nada crítico, así que dejarlos sueltos no rompe nada.
3. **Reflashear el firmware de stock** por USB-C con el instalador web
   oficial del Home Assistant Voice PE (el mismo que se usó en el setup
   inicial de fábrica, vía navegador con Web Serial — Chrome o Edge). Esto
   sobrescribe por completo el YAML custom.
4. **Re-emparejar el dispositivo**: reconectarlo a mi WiFi (Bluetooth /
   Improv-WiFi, igual que la primera vez) y volver a vincularlo a mi
   instancia de Home Assistant como asistente de voz normal.
5. **Verificar** que el asistente de voz responde, la wake word funciona y
   el aro de LEDs se comporta como antes de tocar nada.

Dudas abiertas antes de ejecutar esto:
- Confirmar en su momento la versión/canal correcto del instalador oficial
  (puede haber cambiado desde que se configuró el dispositivo por primera
  vez).
- Si ha habido actualizaciones automáticas de Home Assistant entre medias,
  revisar si el reflasheo deja el dispositivo en una versión más antigua de
  lo esperado y si hace falta forzar una actualización después.

## Ids que vienen del firmware oficial

Estos ids salen del YAML base de `home-assistant-voice-pe` (que se importa
como `packages:` desde la rama `dev`) y **pueden cambiar si el firmware
oficial cambia**. Todos están confirmados a día 2026-08-11 porque el
proyecto compila contra él; si un día deja de compilar, mirar aquí primero.
Una copia del YAML oficial resuelto queda cacheada en
`esphome/.esphome/packages/` — es la referencia más fiable para consultarlos.

- `led_ring` — partición "de cara al usuario" de las 12 LEDs
- `voice_assistant_leds` — la OTRA partición sobre las mismas 12 LEDs
  (interna; hay que apagarla para que no repinte, ver punto 2)
- `external_media_player` — media player del altavoz; `play_sound` es su
  script de fábrica y el patrón que imita `bomba_sonar`
- `center_button` (binary_sensor) y `dial` (rotary_encoder)
- `restart_button` — botón de reinicio, por si se recupera el rearme bruto

(Si en algún momento se usa la variante con Home Assistant en vez de la
autónoma, ahí las entidades a revisar son otras — ver las notas dentro de
`ha/packages/bomba.yaml`.)

## Convenciones

- Comunicación y comentarios en español.
- KISS: antes de añadir una capa, comprobar si el MP3 pregrabado ya lo resuelve.
- Nada de dependencias de nube ni de mi instancia de Home Assistant — el
  dispositivo tiene que funcionar solo, en otra casa.
