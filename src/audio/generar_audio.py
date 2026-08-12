#!/usr/bin/env python3
"""
Genera los ficheros de audio de la bomba de juguete.

Salida (en ./out/):
  bomba_60.mp3   tic-tac acelerando durante 60 s + explosión final
  bomba_boom.mp3 explosión suelta (corte del cable equivocado)
  bomba_ok.mp3   sonido de desactivada

Uso:
  python3 generar_audio.py            # 60 segundos por defecto
  python3 generar_audio.py --seg 90   # otra duración

Requisitos: numpy y ffmpeg en el PATH.
"""

import argparse
import os
import subprocess
import numpy as np

SR = 44100


# ---------------------------------------------------------------- utilidades
def envolvente(n, ataque=0.002, decay=25.0):
    """Envolvente percusiva: ataque muy corto y caída exponencial."""
    t = np.arange(n) / SR
    env = np.exp(-decay * t)
    na = max(1, int(ataque * SR))
    env[:na] *= np.linspace(0, 1, na)
    return env


def filtro(x, lo=None, hi=None, orden=4):
    """Paso banda en el dominio de la frecuencia (magnitud Butterworth).

    En vez de un filtro de un polo aplicado muestra a muestra: es exacto,
    vectorizado, y permite decir "de 250 a 2500 Hz" en vez de pelearse con
    una constante alpha. Sin scipy, que aqui no hay.
    """
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    mascara = np.ones_like(f)
    if lo:
        mascara /= np.sqrt(1.0 + (lo / np.maximum(f, 1e-9)) ** (2 * orden))
    if hi:
        mascara /= np.sqrt(1.0 + (f / hi) ** (2 * orden))
    return np.fft.irfft(X * mascara, n)


def saturar(x, drive=2.0):
    """Saturacion suave, como la de una grabacion que se pasa de nivel.

    Hace dos cosas a la vez: sube el volumen percibido (aplasta los picos,
    sube la energia media) y genera armonicos de los graves. Lo segundo es
    lo importante aqui: el altavoz del Voice PE no reproduce 50 Hz, pero si
    sus armonicos, y el oido reconstruye el grave que falta (fundamental
    ausente). Una explosion saturada suena MAS grave en un altavoz pequeno
    que la misma explosion limpia.
    """
    return np.tanh(x * drive) / np.tanh(drive)


def reverberar(x, rng, dur_cola=1.1, mezcla=0.28):
    """Reverb por conviolucion con ruido que decae: da sensacion de tamano.

    Una explosion seca suena a petardo; lo que la hace sonar "grande" es el
    eco del sitio donde ocurre. La respuesta al impulso es ruido filtrado
    con caida exponencial, y la convolucion se hace por FFT para que no
    tarde una eternidad.
    """
    n_ir = int(dur_cola * SR)
    ir = rng.standard_normal(n_ir) * np.exp(-4.5 * np.arange(n_ir) / SR)
    ir = filtro(ir, 200, 4000)
    ir /= np.max(np.abs(ir)) + 1e-9

    n = len(x) + n_ir - 1
    nfft = 1 << int(np.ceil(np.log2(n)))
    humedo = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:n]
    humedo /= np.max(np.abs(humedo)) + 1e-9

    seco = np.zeros(n)
    seco[: len(x)] = x
    return (1.0 - mezcla) * seco + mezcla * humedo


def ruido_marron(n, rng):
    """Ruido marrón = ruido blanco integrado. Da el 'rumble' grave."""
    x = np.cumsum(rng.standard_normal(n))
    x -= np.linspace(x[0], x[-1], n)   # quita la deriva DC
    return x / (np.max(np.abs(x)) + 1e-9)


def mezclar(destino, muestra, pos):
    """Suma `muestra` sobre `destino` a partir de la posición `pos`."""
    ini = int(pos * SR)
    fin = min(ini + len(muestra), len(destino))
    if ini >= len(destino):
        return
    destino[ini:fin] += muestra[: fin - ini]


# ---------------------------------------------------------------- sonidos
def click(f0=1500.0, dur=0.05, decay=55.0, rng=None):
    """Tic mecánico: sinusoide percusiva + pizca de ruido en el ataque."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * f0 * 2.7 * t)
    transitorio = np.zeros(n)
    nt = int(0.004 * SR)
    if rng is not None:
        transitorio[:nt] = rng.standard_normal(nt) * 0.8
    return (cuerpo + transitorio) * envolvente(n, decay=decay) * 0.5


def explosion(dur=3.5, rng=None, brillo=1.0):
    """Una detonación, montada en cuatro capas + metralla.

    EL PROBLEMA QUE RESUELVE (medido, no intuido): la versión anterior tenía
    el 98,6 % de su energía por debajo de 400 Hz. En un equipo con graves
    eso suena impresionante, pero el altavoz del Voice PE es pequeño y no
    baja de ~250 Hz, así que casi todo lo que sonaba era... nada. Se oía un
    soplido sordo en vez de una explosión.

    Así que aquí la energía se reparte a propósito por la banda que el
    aparato SÍ reproduce (300 Hz - 8 kHz), y el grave se sugiere con
    saturación en vez de intentar radiarlo.
    """
    n = int(dur * SR)
    t = np.arange(n) / SR

    # 1) GOLPE. Transitorio brillante y cortísimo. Es lo que el oído lee
    #    como "algo ha reventado"; sin esto, cualquier ruido grave suena a
    #    viento. Se apaga en ~70 ms.
    golpe = rng.standard_normal(n) * np.exp(-45.0 * t)
    golpe = filtro(golpe, 1200, 9000) * brillo

    # 2) CUERPO. La capa principal, justo en la banda del altavoz.
    cuerpo = filtro(ruido_marron(n, rng), 300, 3000)
    cuerpo *= np.exp(-3.0 * t)

    # 3) RUGIDO. Cola grave-media larga con un temblor lento, para que no
    #    decaiga como una nota limpia sino como algo que sigue ardiendo.
    rugido = filtro(ruido_marron(n, rng), 150, 1000)
    rugido *= np.exp(-1.1 * t) * (1.0 + 0.30 * np.sin(2 * np.pi * 6.5 * t + rng.random() * 6.0))

    # 4) SUB. Barrido descendente, a nivel bajo: no se va a oír tal cual en
    #    este altavoz, pero la saturación de más abajo convierte su energía
    #    en armónicos que sí se oyen y el oído reconstruye el grave.
    f = 160.0 * np.exp(-4.0 * t) + 40.0
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-2.0 * t)

    # 5) METRALLA. Chasquidos sueltos, más densos al principio: cascotes.
    #    Es el detalle que separa "explosión" de "golpe de bombo".
    metralla = np.zeros(n)
    for _ in range(int(30 * dur)):
        pos = (rng.random() ** 1.7) * dur * 0.85
        largo = int(0.02 * SR)
        cascote = rng.standard_normal(largo) * np.exp(-90.0 * np.arange(largo) / SR)
        mezclar(metralla, cascote * (0.35 + 0.65 * rng.random()), pos)
    metralla = filtro(metralla, 800, 6000)

    mix = (1.25 * golpe + 1.15 * cuerpo + 0.85 * rugido
           + 0.35 * sub + 0.60 * metralla)
    return mix / (np.max(np.abs(mix)) + 1e-9) * 0.95


def explosion_grande(rng):
    """Tres detonaciones encadenadas (boom... boom-BOOM), saturadas y con
    reverb, en ~6,2 s. La gorda va la última: así la secuencia crece en vez
    de desinflarse, que es lo que hace que suene a catástrofe y no a
    petardo.

    La duración total está atada a `cola` en pista_cuenta_atras() y a los
    delays de standalone.yaml: si la alargas, hay que tocar los dos.
    """
    partes = [
        # (duracion, intensidad, cuando empieza, brillo)
        (1.4, 0.45, 0.00, 1.2),
        (1.8, 0.65, 0.30, 1.0),
        (4.2, 1.00, 0.85, 0.9),
    ]
    total = np.zeros(int((partes[-1][2] + partes[-1][0]) * SR))
    for dur, inten, off, brillo in partes:
        mezclar(total, explosion(dur=dur, rng=rng, brillo=brillo) * inten, off)

    # Orden importante:
    #  1. saturar genera los armónicos del sub (el grave "imaginario"),
    #  2. y ENTONCES se quita el sub real con un paso alto: ya ha hecho su
    #     trabajo y lo único que hacía era comerse el margen de volumen sin
    #     que este altavoz pudiera radiarlo. Es la cadena clásica de
    #     realce de graves en altavoces pequeños.
    #  3. la reverb va al final, así recoge también los armónicos nuevos.
    total = saturar(total, drive=3.2)
    total = filtro(total, lo=110)
    total = reverberar(total, rng, dur_cola=1.15, mezcla=0.28)

    pico = np.max(np.abs(total))
    if pico > 0:
        total = total / pico * 0.95
    return total


def desactivada(rng):
    """Dos pitidos ascendentes: 'a salvo'."""
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate((660.0, 990.0)):
        n = int(0.28 * SR)
        t = np.arange(n) / SR
        tono = np.sin(2 * np.pi * f * t) * 0.45
        tono *= np.minimum(1.0, np.exp(-4.0 * (t - 0.20).clip(0)))
        na = int(0.01 * SR)
        tono[:na] *= np.linspace(0, 1, na)
        mezclar(out, tono, 0.05 + i * 0.32)
    return out


# ---------------------------------------------------------------- cadencia
def intervalo(restante):
    """Cada cuánto suena el tic según los segundos que quedan."""
    if restante > 30:
        return 1.00
    if restante > 10:
        return 0.50
    if restante > 5:
        return 0.25
    return 0.12


def pista_cuenta_atras(segundos, rng):
    cola = 6.2  # explosion_grande dura mas que la explosion suelta
    total = np.zeros(int((segundos + cola) * SR))

    # --- tics ---
    t = 0.0
    alterna = False
    while t < segundos:
        restante = segundos - t
        # el tono sube un poco conforme aprieta el tiempo
        agudo = restante <= 10
        f0 = (1900.0 if agudo else 1400.0) * (1.08 if alterna else 1.0)
        mezclar(total, click(f0=f0, rng=rng), t)
        t += intervalo(restante)
        alterna = not alterna

    # --- drone de tensión en los últimos 12 s ---
    ini = max(0.0, segundos - 12.0)
    n = int((segundos - ini) * SR)
    td = np.arange(n) / SR
    f = 55.0 + 25.0 * (td / max(td[-1], 1e-9))
    drone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    drone *= np.linspace(0.0, 0.28, n)
    mezclar(total, drone, ini)

    # --- explosión justo al agotarse el tiempo ---
    mezclar(total, explosion_grande(rng), segundos)

    return total


# ---------------------------------------------------------------- export
def guardar(nombre, datos, outdir, flac=False):
    """Escribe el sonido como MP3 y, si `flac`, tambien como FLAC 48 kHz
    mono 16 bits.

    El FLAC no es un capricho: es EXACTAMENTE el formato del
    `announcement_pipeline` del firmware del Voice PE (FLAC / 48000 / 1
    canal), asi que el ESP32 lo reproduce sin decodificar MP3 ni
    remuestrear de 44.1 a 48. Para la pista de cuenta atras -- 36 s, el
    fichero mas largo y el que daba problemas -- esa diferencia importa.
    Para los clips cortos el MP3 sobra.
    """
    pico = np.max(np.abs(datos))
    if pico > 0:
        datos = datos / pico * 0.89          # normaliza dejando headroom
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
    print(f"  {mp3}  ({len(datos)/SR:.1f} s)")

    if flac:
        dst = os.path.join(outdir, nombre + ".flac")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
             "-ac", "1", "-ar", "48000", "-sample_fmt", "s16", "-c:a", "flac",
             dst],
            check=True,
        )
        print(f"  {dst}  ({len(datos)/SR:.1f} s)")

    os.remove(wav)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", type=int, default=60, help="duración de la partida")
    ap.add_argument("--out", default="out", help="carpeta de salida")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    print("Generando audio...")
    # La cuenta atras se llama siempre igual (cuenta_atras.*) porque es el
    # nombre que espera esphome/standalone.yaml; los segundos van en el log.
    guardar("cuenta_atras", pista_cuenta_atras(args.seg, rng), args.out, flac=True)
    # El boom también en FLAC: es de los sonidos importantes y así va en el
    # formato nativo del pipeline de anuncios, sin decodificar MP3.
    guardar("bomba_boom", explosion_grande(rng), args.out, flac=True)
    guardar("bomba_ok", desactivada(rng), args.out)
    print()
    print("Listo. Copia cuenta_atras.flac y los mp3 a esphome/sounds/.")
    if args.seg != 30:
        print(f"OJO: has generado una cuenta atras de {args.seg} s. Cambia tambien")
        print("     el `delay: 30s` de bomba_partida en esphome/standalone.yaml,")
        print("     o el juego y el audio iran cada uno por su lado.")


if __name__ == "__main__":
    main()
