# Bomba de juguete — Voice PE

Juego de desactivación de cables para una fiesta. Lee `CLAUDE.md` para el
contexto completo y las decisiones tomadas.

## Estructura

    audio/generar_audio.py    genera cuenta atras/boom/ok (numpy + ffmpeg)
                               la cuenta atras sale tambien en FLAC 48k/mono,
                               que es el formato nativo del Voice PE
    audio/generar_digitos.py  genera d0..d9 hablados (espeak-ng via ctypes)
    audio/generar_perdiste.py genera las locuciones cortas (perdiste,
                               chupito, no_armar)
    audio/out/                audios ya generados, listos para usar
    esphome/standalone.yaml   PLAN A: YAML completo y autoconclusivo, listo
                               para compilar (importa el firmware oficial
                               como `packages:`, no hace falta clonar nada)
    esphome/sounds/           copia de audio/out/ que usa standalone.yaml
    esphome/grove_cables.yaml snippet de los binary_sensor del Grove, solo
                               para la variante con Home Assistant
    ha/packages/bomba.yaml    variante opcional con Home Assistant
    arduino/bomba_juguete.ino version alternativa con Arduino Nano

## Puesta en marcha (plan A: autonomo, sin Home Assistant)

1. `cd audio && python3 generar_audio.py` y `python3 generar_digitos.py`
   (o usar los audios ya generados; ya están copiados en `esphome/sounds/`)
2. `esphome config esphome/standalone.yaml` para validar, luego
   `esphome compile` / `esphome run` (o subirlo al Device Builder de
   Home Assistant como dashboard genérico, sin necesidad de que el
   dispositivo esté ya adoptado por ningún HA)
3. Cablear el puerto Grove según `CLAUDE.md`

`standalone.yaml` valida y compila (último SUCCESS: 2026-08-11, esphome
2026.7.4, flash 56.7%). La cabecera del propio fichero explica por qué está
escrito así — merece la pena leerla antes de tocarlo, porque la mayoría de
las decisiones raras son cicatrices de fallos reales en la fiesta.

## Cómo se juega

1. **Triple clic** en el botón central: la bomba se arma y lee un número de
   serie de 4 dígitos.
2. Regla (imprímela en una tarjeta): **último dígito PAR → cortar ROJO;
   IMPAR → cortar AZUL**.
3. Hay 30 segundos de tic-tac. Aciertas y se desactiva; fallas o se acaba
   el tiempo y explota (y alguien bebe un chupito).
4. Para la ronda siguiente: reempalmar los dos cables en la regleta (el aro
   se apaga solo cuando detecta que están puestos) y triple clic otra vez.
   El triple clic rearma desde cualquier punto, también a media partida.

Variante con Home Assistant (opcional, solo si el dispositivo se queda en
una casa con HA propio): copiar `audio/out/*.mp3` a `config/www/`, copiar
`ha/packages/bomba.yaml` a `config/packages/` ajustando las entidades, y
añadir `esphome/grove_cables.yaml` al YAML del Voice PE.

## El audio de la intro (por qué no compila recién clonado)

Al ganar suena un trozo de la sintonía de MacGyver. Ese fichero **no está
en el repo**: es material de terceros, aquí se usa en privado en un
dispositivo propio y este repo es público. Está en `.gitignore` junto con
el original completo (`audio/manual/`).

Recién clonado, `esphome compile` fallará diciendo que no encuentra
`sounds/macgyver_intro_recorte.mp3`. Dos salidas, las dos de una línea:

- **Usar el jingle libre que sí viene incluido**: en `standalone.yaml`,
  cambiar el `file:` de `snd_intro` a `sounds/intro.mp3` (generado por
  `audio/generar_intro.py`, sin copyright).
- **Poner tu propio audio** en `esphome/sounds/macgyver_intro_recorte.mp3`.
  Para recortar un trozo de una canción tuya:

      ffmpeg -i cancion.mp3 -ss 19 -to 30 -c copy \
             esphome/sounds/macgyver_intro_recorte.mp3

## Regenerar el audio con otra duración

    python3 audio/generar_audio.py --seg 90

Si cambias los segundos hay que cambiar también el `delay: 30s` de
`bomba_partida` en `standalone.yaml`: el audio y el juego tienen que durar
lo mismo.
