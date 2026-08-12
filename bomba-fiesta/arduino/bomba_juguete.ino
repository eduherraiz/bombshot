/*
  ============================================================
  MINI-BOMBA DE JUGUETE — juego de desactivación de cables
  ============================================================
  Placa   : Arduino Nano / Uno (ESP32 -> solo cambia los pines)
  Display : TM1637 4 dígitos
  Librería: "TM1637Display" de Avishay Orpaz
            (Gestor de librerías -> buscar TM1637)

  CABLEADO
  --------
  TM1637 CLK -> D2      TM1637 DIO -> D3      VCC 5V / GND
  Cable A (rojo) : D4 -----[cable]----- GND
  Cable B (azul) : D5 -----[cable]----- GND
  LED rojo   : D6 -> R220 -> GND
  LED verde  : D7 -> R220 -> GND
  Buzzer pasivo : D8 -> GND
  Interruptor armado : D9 -> GND (cerrado = armado)
  A0 queda al aire a propósito (ruido para la semilla aleatoria)
*/

#include <TM1637Display.h>

// ---------------- CONFIGURACIÓN ----------------
const uint16_t TIEMPO_SEG   = 60;    // duración de la partida
const bool     MODO_REGLA   = true;  // true = deducible, false = 50/50 puro
const uint16_t SEG_MOSTRAR_SERIE = 2; // segundos mostrando el nº de serie

// ---------------- PINES ----------------
const uint8_t PIN_CLK     = 2;
const uint8_t PIN_DIO     = 3;
const uint8_t PIN_CABLE_A = 4;   // rojo
const uint8_t PIN_CABLE_B = 5;   // azul
const uint8_t PIN_LED_R   = 6;
const uint8_t PIN_LED_G   = 7;
const uint8_t PIN_BUZZER  = 8;
const uint8_t PIN_ARM     = 9;

TM1637Display display(PIN_CLK, PIN_DIO);

enum Estado { ESPERA, MOSTRANDO_SERIE, ARMADA, DESACTIVADA, EXPLOTADA };
Estado estado = ESPERA;

unsigned long tRef      = 0;   // marca de tiempo del estado actual
unsigned long tUltBeep   = 0;
unsigned long tUltBlink  = 0;
bool          blinkOn    = false;

uint8_t  cableCorrecto = 0;    // 0 = A (rojo), 1 = B (azul)
uint16_t numeroSerie   = 0;

const uint8_t SEG_OFF[]  = {0, 0, 0, 0};
const uint8_t SEG_BOOM[] = {0x7f, 0x7f, 0x7f, 0x7f};          // todo encendido
const uint8_t SEG_OK[]   = {0x3f, 0x3f, 0x00, 0x00};          // "OO"

// ---------------- HELPERS ----------------
bool cableCortado(uint8_t pin) { return digitalRead(pin) == HIGH; }
bool armado()                  { return digitalRead(PIN_ARM) == LOW; }

void leds(bool rojo, bool verde) {
  digitalWrite(PIN_LED_R, rojo);
  digitalWrite(PIN_LED_G, verde);
}

// ---------------- SETUP ----------------
void setup() {
  pinMode(PIN_CABLE_A, INPUT_PULLUP);
  pinMode(PIN_CABLE_B, INPUT_PULLUP);
  pinMode(PIN_ARM,     INPUT_PULLUP);
  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  display.setBrightness(7);
  randomSeed(analogRead(A0) * millis());

  irAEspera();
}

// ---------------- TRANSICIONES ----------------
void irAEspera() {
  estado = ESPERA;
  leds(false, false);
  noTone(PIN_BUZZER);
  display.setSegments(SEG_OFF);
}

void armar() {
  numeroSerie = random(1000, 10000);

  if (MODO_REGLA) {
    // REGLA DEL JUEGO (imprímela en una tarjeta):
    // último dígito PAR   -> cortar cable ROJO  (A)
    // último dígito IMPAR -> cortar cable AZUL  (B)
    cableCorrecto = (numeroSerie % 2 == 0) ? 0 : 1;
    display.showNumberDec(numeroSerie, true);
    estado = MOSTRANDO_SERIE;
  } else {
    cableCorrecto = random(0, 2);
    estado = ARMADA;
  }

  leds(true, false);
  tone(PIN_BUZZER, 1200, 120);
  tRef = millis();
  tUltBeep = millis();
}

void desactivar() {
  estado = DESACTIVADA;
  noTone(PIN_BUZZER);
  leds(false, true);
  display.setSegments(SEG_OK);
  tone(PIN_BUZZER, 880, 150);  delay(180);
  tone(PIN_BUZZER, 1320, 400);
}

void explotar() {
  estado = EXPLOTADA;
  display.setSegments(SEG_BOOM);
  leds(true, false);

  // barrido descendente = "pfffboom"
  for (int f = 1800; f > 80; f -= 12) {
    tone(PIN_BUZZER, f + random(-40, 40));
    digitalWrite(PIN_LED_R, (f / 60) % 2);
    delay(4);
  }
  // coletazo de ruido
  for (int i = 0; i < 60; i++) {
    tone(PIN_BUZZER, random(60, 300));
    delay(12);
  }
  noTone(PIN_BUZZER);
  digitalWrite(PIN_LED_R, HIGH);
}

// ---------------- BUCLE ----------------
void loop() {
  unsigned long ahora = millis();

  switch (estado) {

    case ESPERA:
      // arranca solo si el interruptor está armado y los dos cables intactos
      if (armado() && !cableCortado(PIN_CABLE_A) && !cableCortado(PIN_CABLE_B)) {
        armar();
      }
      break;

    case MOSTRANDO_SERIE:
      if (ahora - tRef >= SEG_MOSTRAR_SERIE * 1000UL) {
        estado = ARMADA;
        tRef = ahora;          // el cronómetro empieza aquí
        tUltBeep = ahora;
      }
      break;

    case ARMADA: {
      // abortar si se baja el interruptor
      if (!armado()) { irAEspera(); break; }

      long transcurrido = (ahora - tRef) / 1000;
      long restante = (long)TIEMPO_SEG - transcurrido;

      if (restante <= 0) { explotar(); break; }

      // ---- cuenta atrás MM:SS con dos puntos ----
      int mm = restante / 60;
      int ss = restante % 60;
      display.showNumberDecEx(mm * 100 + ss, 0b01000000, true);

      // ---- tic-tac que acelera ----
      unsigned int intervalo = 1000;
      if      (restante <= 5)  intervalo = 120;
      else if (restante <= 10) intervalo = 250;
      else if (restante <= 30) intervalo = 500;

      if (ahora - tUltBeep >= intervalo) {
        tUltBeep = ahora;
        tone(PIN_BUZZER, restante <= 10 ? 1600 : 1000, 45);
        blinkOn = !blinkOn;
        digitalWrite(PIN_LED_R, blinkOn);
      }

      // ---- lectura de cables ----
      if (cableCortado(PIN_CABLE_A)) {
        (cableCorrecto == 0) ? desactivar() : explotar();
      } else if (cableCortado(PIN_CABLE_B)) {
        (cableCorrecto == 1) ? desactivar() : explotar();
      }
      break;
    }

    case DESACTIVADA:
    case EXPLOTADA:
      // rearme: bajar el interruptor y volver a empalmar los dos cables
      if (!armado()) {
        if (estado == EXPLOTADA && ahora - tUltBlink > 400) {
          tUltBlink = ahora;
          digitalWrite(PIN_LED_R, !digitalRead(PIN_LED_R));
        }
        if (!cableCortado(PIN_CABLE_A) && !cableCortado(PIN_CABLE_B)) {
          irAEspera();
        }
      }
      break;
  }
}
