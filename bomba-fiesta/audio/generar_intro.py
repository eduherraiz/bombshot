#!/usr/bin/env python3
"""
Genera un jingle de intro sintetizado (bajo pulsante + arpegio, estilo
synth de accion/espionaje de los 80) para sonar al armar el juego.

Es una composicion propia generada por sintesis, no una copia ni un cover
de ninguna melodia con derechos de autor.

Salida (en ./out/): intro.mp3

Uso:
  python3 generar_intro.py
  python3 generar_intro.py --bpm 160
"""

import argparse
import os
import subprocess
import numpy as np

SR = 44100

NOTAS = {
    "E2": 82.41, "G2": 98.00, "B2": 123.47,
    "E3": 164.81, "G3": 196.00, "B3": 246.94,
    "E4": 329.63,
}


def onda(freq, n, forma="saw"):
    t = np.arange(n) / SR
    if forma == "square":
        return np.sign(np.sin(2 * np.pi * freq * t))
    # diente de sierra
    return 2 * (t * freq - np.floor(0.5 + t * freq))


def nota(freq, dur, forma="saw", decay=8.0, vol=1.0):
    n = int(dur * SR)
    x = onda(freq, n, forma)
    env = np.exp(-decay * np.arange(n) / SR)
    ataque = max(1, int(0.003 * SR))
    env[:ataque] *= np.linspace(0, 1, ataque)
    return x * env * vol


def mezclar(destino, muestra, pos):
    ini = int(pos * SR)
    fin = min(ini + len(muestra), len(destino))
    if ini >= len(destino):
        return
    destino[ini:fin] += muestra[: fin - ini]


def bajo_pulsante(total_s, bpm):
    beat = 60.0 / bpm
    paso = beat / 2  # corcheas
    out = np.zeros(int(total_s * SR))
    patron = ["E2", "E2", "G2", "E2", "E2", "E2", "B2", "E2"]
    t, i = 0.0, 0
    while t < total_s - 0.3:
        f = NOTAS[patron[i % len(patron)]]
        mezclar(out, nota(f, paso * 0.9, forma="square", decay=6.0, vol=0.6), t)
        t += paso
        i += 1
    return out


def arpegio(total_s, bpm):
    beat = 60.0 / bpm
    paso = beat / 4  # semicorcheas
    out = np.zeros(int(total_s * SR))
    patron = ["E3", "G3", "B3", "E4", "B3", "G3", "E3", "G3"]
    t, i = beat, 0  # entra medio compas despues del bajo
    while t < total_s - 0.15:
        f = NOTAS[patron[i % len(patron)]]
        mezclar(out, nota(f, paso * 0.85, forma="saw", decay=10.0, vol=0.35), t)
        t += paso
        i += 1
    return out


def golpe_final(dur=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    acorde = sum(np.sin(2 * np.pi * NOTAS[nombre] * t) for nombre in ("E2", "B2", "E3", "G3"))
    acorde /= 4
    env = np.exp(-4.0 * t)
    return acorde * env


def generar(bpm):
    total = 3.6
    out = np.zeros(int((total + 0.8) * SR))
    mezclar(out, bajo_pulsante(total, bpm), 0.0)
    mezclar(out, arpegio(total, bpm), 0.0)
    mezclar(out, golpe_final(0.8) * 0.9, total - 0.05)
    return out


def guardar(nombre, datos, outdir):
    pico = np.max(np.abs(datos))
    if pico > 0:
        datos = datos / pico * 0.89
    pcm = (datos * 32767).astype(np.int16)

    wav = os.path.join(outdir, nombre + ".wav")
    mp3 = os.path.join(outdir, nombre + ".mp3")

    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "128k", mp3],
        check=True,
    )
    os.remove(wav)
    print(f"  {mp3}  ({len(datos)/SR:.1f} s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm", type=int, default=140, help="tempo del jingle")
    ap.add_argument("--out", default="out", help="carpeta de salida")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    print("Generando intro...")
    guardar("intro", generar(args.bpm), args.out)
    print("Listo.")


if __name__ == "__main__":
    main()
