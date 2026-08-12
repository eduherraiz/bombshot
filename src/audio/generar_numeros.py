#!/usr/bin/env python3
"""
Genera los 40 numeros hablados del juego: los 20 primeros primos y 20
compuestos "evidentes". La bomba dice uno de ellos al armar y la regla es
"si es primo corta el ROJO, si no el AZUL".

POR QUE ESTAS LISTAS
--------------------
Los primos son los 20 primeros, sin mas. Los compuestos estan elegidos a
mano con dos condiciones:

  1. Que se vea a simple vista que NO son primos: pares, acabados en 0 o
     5, o de la tabla del 3 / del 9. Nada de 51, 57 o 91, que hacen dudar
     hasta al que sabe la regla.
  2. Que esten repartidos por el mismo rango que los primos. Si los
     compuestos fuesen todos pequenos, "numero grande = primo" seria un
     atajo que se carga el juego. Por eso hay 4 primos y 4 compuestos por
     debajo de 10, 8 y 8 entre 11 y 40, y 8 y 8 entre 41 y 71.

Los numeros se sintetizan pasandole la cifra ("47") a espeak-ng, que ya
sabe decirla en espanol ("cuarenta y siete"); asi no hay que escribir 40
nombres a mano y no puede haber erratas.

Usa el mismo motor que el resto de locuciones (espeak-ng via ctypes, ver
generar_digitos.py para el porque de ctypes en vez del binario).

Salida (en ./out/): n2.flac, n3.flac, ... n71.flac
FLAC 48 kHz mono **16 bits**: es el formato exacto del pipeline de
anuncios del Voice PE (ni remuestreo ni conversion) y ademas ocupa la
mitad que el de 24 bits, que con 40 clips ya se nota en la flash.

Uso:
  python3 generar_numeros.py
  python3 generar_numeros.py --velocidad 150
  python3 generar_numeros.py --yaml      # solo imprime lo que va en el YAML
"""

import argparse
import ctypes
import ctypes.util
import os
import subprocess
import wave

AUDIO_OUTPUT_RETRIEVAL = 1
ESPEAK_CHARS_UTF8 = 1
ESPEAK_RATE = 1  # id del parametro "velocidad" en espeak-ng

# FUENTE DE LA VERDAD de las dos listas. Si tocas esto, vuelve a ejecutar
# el script con --yaml y pega la salida en esphome/standalone.yaml: alli
# hay que tener un `audio_file:` por numero Y el mismo numero en el array
# de C++, o la bomba se quedara muda al sortear el que falte.
PRIMOS = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
          31, 37, 41, 43, 47, 53, 59, 61, 67, 71]

COMPUESTOS = [4, 6, 8, 9, 12, 15, 18, 21, 25, 27,
              33, 36, 44, 48, 50, 55, 60, 63, 66, 70]


def cargar_libreria():
    nombre = ctypes.util.find_library("espeak-ng") or "libespeak-ng.so.1"
    lib = ctypes.CDLL(nombre)
    lib.espeak_Synth.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
    ]
    return lib


def sintetizar(lib, texto):
    muestras = bytearray()

    CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                 ctypes.c_int, ctypes.c_void_p)

    def on_audio(wav, numsamples, events):
        if numsamples > 0 and wav:
            muestras.extend(ctypes.string_at(wav, numsamples * 2))
        return 0

    sintetizar.cb = CALLBACK(on_audio)
    lib.espeak_SetSynthCallback(sintetizar.cb)

    texto_c = texto.encode("utf-8") + b"\0"
    uid = ctypes.c_uint(0)
    lib.espeak_Synth(texto_c, len(texto_c), 0, 0, 0, ESPEAK_CHARS_UTF8,
                      ctypes.byref(uid), None)
    lib.espeak_Synchronize()
    return bytes(muestras)


def guardar_flac(pcm, sample_rate, ruta_wav, ruta_flac):
    with wave.open(ruta_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", ruta_wav,
            "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "apad=pad_dur=0.10",
            "-ar", "48000", "-ac", "1", "-sample_fmt", "s16", ruta_flac,
        ],
        check=True,
    )
    os.remove(ruta_wav)


def imprimir_yaml():
    """Escupe los dos trozos que hay que tener en standalone.yaml."""
    print("# ---- audio_file: (pegar en el bloque audio_file de standalone.yaml)")
    for n in sorted(PRIMOS + COMPUESTOS):
        print(f"  - id: snd_n{n}\n    file: sounds/n{n}.flac")
    print()
    print("// ---- arrays (pegar en el lambda de bomba_partida)")
    def fila(nums):
        return ", ".join(str(n) for n in nums)
    print(f"static const int PRIMOS[20]     = {{{fila(PRIMOS)}}};")
    print(f"static const int COMPUESTOS[20] = {{{fila(COMPUESTOS)}}};")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--velocidad", type=int, default=135,
                     help="palabras por minuto (espeak-ng, defecto ~175)")
    ap.add_argument("--voz", default="es")
    ap.add_argument("--out", default="out")
    ap.add_argument("--yaml", action="store_true",
                     help="no genera audio, solo imprime lo que va en el YAML")
    args = ap.parse_args()

    if args.yaml:
        imprimir_yaml()
        return

    # Red de seguridad: que las listas sigan siendo lo que dicen ser.
    def es_primo(n):
        return n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))
    assert len(PRIMOS) == 20 and all(es_primo(n) for n in PRIMOS), "PRIMOS mal"
    assert len(COMPUESTOS) == 20 and not any(es_primo(n) for n in COMPUESTOS), "COMPUESTOS mal"
    assert not (set(PRIMOS) & set(COMPUESTOS)), "un numero esta en las dos listas"

    os.makedirs(args.out, exist_ok=True)

    lib = cargar_libreria()
    sample_rate = lib.espeak_Initialize(AUDIO_OUTPUT_RETRIEVAL, 0, None, 0)
    if sample_rate <= 0:
        raise RuntimeError("No se pudo inicializar espeak-ng")
    if lib.espeak_SetVoiceByName(args.voz.encode()) != 0:
        raise RuntimeError(f"Voz '{args.voz}' no encontrada")
    lib.espeak_SetParameter(ESPEAK_RATE, args.velocidad, 0)

    total = 0
    for n in sorted(PRIMOS + COMPUESTOS):
        pcm = sintetizar(lib, str(n))
        wav_tmp = os.path.join(args.out, f"n{n}.wav")
        flac_out = os.path.join(args.out, f"n{n}.flac")
        guardar_flac(pcm, sample_rate, wav_tmp, flac_out)
        total += os.path.getsize(flac_out)
        print(f"  {flac_out}  ({os.path.getsize(flac_out) // 1024} kB)")

    lib.espeak_Terminate()
    print(f"\n40 clips, {total // 1024} kB en total (van dentro del firmware).")
    print("Copialos a esphome/sounds/ y ejecuta --yaml si has cambiado las listas.")


if __name__ == "__main__":
    main()
