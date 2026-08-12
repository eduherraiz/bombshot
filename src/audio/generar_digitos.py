#!/usr/bin/env python3
"""
Genera los clips de audio con los digitos hablados en espanol (cero..nueve)
para que la bomba en modo autonomo (esphome/standalone.yaml) pueda leer el
numero de serie sin depender de Home Assistant ni de TTS en la nube.

Usa la libreria libespeak-ng.so directamente via ctypes en vez del binario
`espeak-ng`: esta maquina no tiene privilegios de root para instalarlo con
apt, pero la libreria .so ya viene con el sistema (paquete libespeak-ng1).

Salida (en ./out/): d0.flac ... d9.flac -- mono, 48 kHz, silencios de los
bordes recortados.

Uso:
  python3 generar_digitos.py
  python3 generar_digitos.py --voz es+f3   # otra variante de voz de espeak-ng
"""

import argparse
import ctypes
import ctypes.util
import os
import subprocess
import wave

PALABRAS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]

AUDIO_OUTPUT_RETRIEVAL = 1
ESPEAK_CHARS_UTF8 = 1


def cargar_libreria():
    nombre = ctypes.util.find_library("espeak-ng") or "libespeak-ng.so.1"
    lib = ctypes.CDLL(nombre)
    lib.espeak_Synth.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
    ]
    return lib


def sintetizar(lib, texto):
    """Habla `texto` y devuelve el PCM mono 16 bit resultante."""
    muestras = bytearray()

    CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                 ctypes.c_int, ctypes.c_void_p)

    def on_audio(wav, numsamples, events):
        if numsamples > 0 and wav:
            muestras.extend(ctypes.string_at(wav, numsamples * 2))
        return 0

    # ctypes necesita mantener viva la referencia al callback mientras se usa
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

    # recorta silencio de ambos bordes (silenceremove + areverse dos veces)
    # y deja un pequeno colchon al final para que no corte en seco
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", ruta_wav,
            "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
            "areverse,"
            "apad=pad_dur=0.05",
            "-ar", "48000", "-ac", "1", ruta_flac,
        ],
        check=True,
    )
    os.remove(ruta_wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", default="es", help="voz de espeak-ng (es, es-419, es+f3...)")
    ap.add_argument("--out", default="out", help="carpeta de salida")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    lib = cargar_libreria()
    sample_rate = lib.espeak_Initialize(AUDIO_OUTPUT_RETRIEVAL, 0, None, 0)
    if sample_rate <= 0:
        raise RuntimeError("No se pudo inicializar espeak-ng (libespeak-ng.so no disponible)")
    if lib.espeak_SetVoiceByName(args.voz.encode()) != 0:
        raise RuntimeError(f"Voz '{args.voz}' no encontrada en espeak-ng")

    print(f"Generando digitos con espeak-ng (voz={args.voz}, sr={sample_rate})...")
    for i, palabra in enumerate(PALABRAS):
        pcm = sintetizar(lib, palabra)
        wav_tmp = os.path.join(args.out, f"d{i}.wav")
        flac_out = os.path.join(args.out, f"d{i}.flac")
        guardar_flac(pcm, sample_rate, wav_tmp, flac_out)
        print(f"  {flac_out}  ('{palabra}')")

    lib.espeak_Terminate()
    print("Listo. Copia d0.flac..d9.flac junto al YAML de ESPHome (carpeta sounds/).")


if __name__ == "__main__":
    main()
