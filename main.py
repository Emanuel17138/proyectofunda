"""
Instituto Tecnológico de Costa Rica
Escuela de Ingeniería en Computadores
Introducción a la programación
2026
Grupo 4
Python 3.14.3
Emanuel Rojas Benavides y Diego Andrés Herrrera Rivera
Proyecto 1 y 2
Descripción: El código de la Raspberry Pi Pico W controla la maqueta, el botón Morse, el buzzer, los LEDs, el DIP switch, el circuito incrementador en 5 y la conexión con la PC.
Versión del programa: 2.0.0
Requerimientos del sistema: MicroPython
"""

# Librerias de MicroPython para pines, tiempo, WiFi y sockets.
from machine import Pin
import time
import network
import socket

# Datos de la red WiFi usada por la maqueta.
WIFI_SSID = "Goated"
WIFI_PASSWORD = "AuraLaura67"
TCP_PORT = 5000
DISCOVERY_PORT = 5001

# Pines fisicos conectados a cada parte de la maqueta.
buzzer = Pin(5, Pin.OUT)
boton = Pin(16, Pin.IN, Pin.PULL_UP)
dip = Pin(17, Pin.IN, Pin.PULL_UP)

# Nuevo circuito del Proyecto II. El switch de habilitacion esta en GPIO 18.
# Las entradas del circuito incrementador en 5 usan GPIO 19 a GPIO 22.
# GPIO 19 es el bit menos significativo (LSB) y GPIO 22 es el bit mas significativo (MSB).
switch_inc5 = Pin(18, Pin.IN, Pin.PULL_UP)
inc5_pines = [Pin(19, Pin.OUT), Pin(20, Pin.OUT), Pin(21, Pin.OUT), Pin(22, Pin.OUT)]
INC5_SWITCH_ACTIVO_EN_BAJO = True

clk = Pin(26, Pin.OUT)
data = Pin(27, Pin.OUT)

# Pines que activan cada fila del panel de letras y numeros.
fila_num = Pin(13, Pin.OUT)
fila_b = Pin(14, Pin.OUT)
fila_a = Pin(15, Pin.OUT)

# Ajustes del panel. Se cambian si el cableado trabaja al reves.
FILA_ACTIVA_EN_ALTO = True
INVERTIR_COLUMNAS = False
COLUMNAS = 16

# Diccionario principal: texto a codigo Morse.
morse = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..",
    "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....",
    "6": "-....", "7": "--...", "8": "---..", "9": "----.", "0": "-----",
    "+": ".-.-.", "-": "-....-"
}

# Diccionario inverso: codigo Morse a texto.
morse_inv = {morse[k]: k for k in morse}

# Letras o simbolos que pertenecen a cada fila del panel.
fila_a_chars = "ACEGIKMOQSUWY"
fila_b_chars = "BDFHJLNPRTVXZ"
fila_num_chars = "0123456789-+"

# Relaciona cada caracter con su fila y columna del panel.
mapa_led = {}
for i, c in enumerate(fila_a_chars):
    mapa_led[c] = (fila_a, i)
for i, c in enumerate(fila_b_chars):
    mapa_led[c] = (fila_b, i)
for i, c in enumerate(fila_num_chars):
    mapa_led[c] = (fila_num, i)

# Variables globales de la conexion con la PC.
sock_pc = None
rx_buffer = ""


# Devuelve el valor electrico para encender o apagar una fila.
def valor_fila(activa):
    if FILA_ACTIVA_EN_ALTO:
        return 1 if activa else 0
    return 0 if activa else 1


# Apaga todas las filas del panel.
def apagar_filas():
    fila_a.value(valor_fila(False))
    fila_b.value(valor_fila(False))
    fila_num.value(valor_fila(False))


# Hace un pulso para mover datos en el 74LS164.
def pulso_clock():
    clk.value(0)
    time.sleep_us(2)
    clk.value(1)
    time.sleep_us(2)
    clk.value(0)
    time.sleep_us(2)


# Envia los bits de columnas al registro 74LS164.
def enviar_74ls164(valor):
    for i in range(COLUMNAS - 1, -1, -1):
        data.value((valor >> i) & 1)
        pulso_clock()


# Apaga todo el panel de LEDs.
def limpiar_panel():
    apagar_filas()
    enviar_74ls164(0)


# Enciende el LED que representa un caracter.
def led_on(caracter):
    caracter = caracter.upper()

    # Si el caracter no existe en el panel, se apaga todo.
    if caracter not in mapa_led:
        limpiar_panel()
        return

    pin_fila, columna = mapa_led[caracter]
    apagar_filas()

    # Corrige la posicion si las columnas estan al reves.
    if INVERTIR_COLUMNAS:
        columna = (COLUMNAS - 1) - columna

    enviar_74ls164(1 << columna)
    pin_fila.value(valor_fila(True))


# Apaga los LEDs.
def led_off():
    limpiar_panel()


# Enciende un caracter por un tiempo corto.
def mostrar_caracter(caracter, duracion=0.3):
    led_on(caracter)
    time.sleep(duracion)
    led_off()


# Enciende el buzzer.
def buzzer_on():
    buzzer.value(1)


# Apaga el buzzer.
def buzzer_off():
    buzzer.value(0)


# Lee el DIP switch y devuelve el modo actual.
def modo_actual():
    # Con pull-up, valor 0 significa que el DIP esta cerrado a GND.
    if dip.value() == 0:
        return "SIMPLE"
    return "ESCUCHA"


# Devuelve True cuando el switch nuevo habilita el incrementador en 5.
def inc5_switch_activo():
    valor = switch_inc5.value()

    # Con pull-up, lo normal es que el switch activo cierre a GND y lea 0.
    if INC5_SWITCH_ACTIVO_EN_BAJO:
        return valor == 0

    return valor == 1


# Convierte un valor de 0 a 15 a una cadena binaria de 4 bits.
def inc5_bin4(valor):
    valor = valor & 0x0F
    salida = ""

    for bit in range(3, -1, -1):
        salida += "1" if ((valor >> bit) & 1) else "0"

    return salida


# Limpia las 4 entradas enviadas al circuito incrementador.
def inc5_limpiar_entradas():
    for pin in inc5_pines:
        pin.value(0)


# Escribe los 4 bits menos significativos en los pines 19, 20, 21 y 22.
def inc5_escribir_entradas(valor):
    valor = valor & 0x0F

    # bit 0 -> GPIO 19 (LSB), bit 1 -> GPIO 20, bit 2 -> GPIO 21, bit 3 -> GPIO 22 (MSB).
    for bit, pin in enumerate(inc5_pines):
        pin.value((valor >> bit) & 1)


# Procesa una letra para el Proyecto II: ASCII, 4 LSB y resultado esperado de sumar 5.
def inc5_procesar_caracter(caracter, origen="PICO"):
    if not caracter:
        return

    caracter = caracter[0].upper()

    if caracter == "?" or caracter == " ":
        return

    if not inc5_switch_activo():
        inc5_limpiar_entradas()
        enviar("INC5_SWITCH:OFF")
        return

    codigo_ascii = ord(caracter)
    entrada = codigo_ascii & 0x0F
    salida = (entrada + 5) & 0x0F

    inc5_escribir_entradas(entrada)

    # Formato: caracter, ASCII decimal, entrada de 4 bits, salida de 4 bits y salida decimal.
    enviar("INC5_SWITCH:ON")
    enviar(
        "INC5_RESULT:" + caracter + ":" +
        str(codigo_ascii) + ":" +
        inc5_bin4(entrada) + ":" +
        inc5_bin4(salida) + ":" +
        str(salida)
    )


# Limpia la frase y deja solo caracteres validos.
def normalizar_frase(frase):
    salida = ""
    for c in frase.upper():
        if c in morse or c == " ":
            salida += c
    return salida[:16]


# Convierte texto normal a Morse.
def texto_a_morse(frase):
    partes = []
    for palabra in normalizar_frase(frase).split(" "):
        letras = []
        for c in palabra:
            if c in morse:
                letras.append(morse[c])
        partes.append(" ".join(letras))
    return " / ".join(partes)


# Convierte Morse a texto normal.
def morse_a_texto(codigo):
    texto = ""
    palabras = codigo.strip().split("/")

    for p, palabra in enumerate(palabras):
        for letra in palabra.strip().split():
            texto += morse_inv.get(letra, "?")
        if p < len(palabras) - 1:
            texto += " "

    return texto


# Muestra una frase usando luz, sonido o ambos.
def mostrar_frase(frase, unidad=0.2, salida="BOTH"):
    frase = normalizar_frase(frase)
    salida = salida.upper()
    codigo_mostrado = ""

    # Recorre cada caracter de la frase.
    for caracter in frase:
        # Un espacio en texto se representa como pausa larga.
        if caracter == " ":
            if codigo_mostrado != "" and not codigo_mostrado.endswith("/ "):
                codigo_mostrado += "/ "
                enviar("SHOW_LIVE_MORSE:" + codigo_mostrado.strip())
                enviar("SHOW_LIVE_TEXT:" + morse_a_texto(codigo_mostrado))
            time.sleep(7 * unidad)
            continue

        if caracter not in morse:
            continue

        codigo = morse[caracter]
        parcial = ""

        # Recorre cada punto o raya de la letra.
        for i, simbolo in enumerate(codigo):
            duracion = unidad if simbolo == "." else 3 * unidad
            parcial += simbolo

            enviar("SHOW_LIVE_MORSE:" + (codigo_mostrado + parcial).strip())
            enviar("SHOW_LIVE_TEXT:" + morse_a_texto((codigo_mostrado + parcial).strip()))

            # Activa la luz si ese modo fue escogido.
            if salida in ("LIGHT", "BOTH"):
                led_on(caracter)
            # Activa el sonido si ese modo fue escogido.
            if salida in ("SOUND", "BOTH"):
                buzzer_on()

            time.sleep(duracion)

            buzzer_off()
            led_off()

            if i < len(codigo) - 1:
                time.sleep(unidad)

        codigo_mostrado += codigo + " "
        enviar("SHOW_LIVE_MORSE:" + codigo_mostrado.strip())
        enviar("SHOW_LIVE_TEXT:" + morse_a_texto(codigo_mostrado))
        time.sleep(3 * unidad)


# Revisa si el boton fisico esta presionado.
def boton_presionado():
    return boton.value() == 0


# Envia a la PC el Morse y el texto que se llevan hasta ahora.
def enviar_estado_morse(codigo, letra):
    actual = (codigo + letra).strip()
    enviar("LIVE_MORSE:" + actual)
    enviar("LIVE_TEXT:" + morse_a_texto(actual))


# Lee el boton y arma el codigo Morse del jugador.
def capturar_morse(limite=25, unidad=0.2):
    enviar("CAPTURE_START")
    codigo = ""
    letra = ""
    inicio_total = time.ticks_ms()
    ultima_suelta = time.ticks_ms()
    empezo = False

    # Captura hasta que se acabe el tiempo o haya silencio largo.
    while time.ticks_diff(time.ticks_ms(), inicio_total) < int(limite * 1000):
        # Si se presiona el boton, se mide cuanto dura.
        if boton_presionado():
            ahora = time.ticks_ms()

            # Si ya habia datos, revisa si hubo pausa de letra o palabra.
            if empezo:
                pausa = time.ticks_diff(ahora, ultima_suelta) / 1000

                if pausa >= 7 * unidad:
                    if letra != "":
                        inc5_procesar_caracter(morse_inv.get(letra, "?"), "PICO")
                        codigo += letra + " / "
                        letra = ""
                        enviar("GAP:WORD")
                        enviar_estado_morse(codigo, letra)

                elif pausa >= 3 * unidad:
                    if letra != "":
                        inc5_procesar_caracter(morse_inv.get(letra, "?"), "PICO")
                        codigo += letra + " "
                        letra = ""
                        enviar("GAP:LETTER")
                        enviar_estado_morse(codigo, letra)

            enviar("BUTTON:DOWN")
            inicio = time.ticks_ms()
            buzzer_on()

            while boton_presionado():
                time.sleep_ms(5)

            buzzer_off()
            fin = time.ticks_ms()
            duracion = time.ticks_diff(fin, inicio) / 1000

            # Presion corta es punto; presion larga es raya.
            if duracion < 2 * unidad:
                simbolo = "."
            else:
                simbolo = "-"

            letra += simbolo
            enviar("BUTTON:UP:" + simbolo)
            enviar("PRESS:" + simbolo)
            enviar_estado_morse(codigo, letra)

            ultima_suelta = time.ticks_ms()
            empezo = True

        # Si no se presiona, revisa si ya se debe terminar.
        else:
            # Si ya habia datos, revisa si hubo pausa de letra o palabra.
            if empezo:
                silencio = time.ticks_diff(time.ticks_ms(), ultima_suelta) / 1000
                if silencio > 4:
                    break
            time.sleep_ms(10)

    # Agrega la ultima letra si quedo pendiente.
    if letra != "":
        inc5_procesar_caracter(morse_inv.get(letra, "?"), "PICO")
        codigo += letra

    tiempo_total = time.ticks_diff(time.ticks_ms(), inicio_total) / 1000
    codigo = codigo.strip()
    texto = morse_a_texto(codigo)

    enviar("MORSE:" + codigo)
    enviar("TEXT:" + texto)
    enviar("TIME:" + str(round(tiempo_total, 2)))
    enviar("DONE:CAPTURE")


# Envia un mensaje de texto a la PC.
def enviar(texto):
    global sock_pc

    try:
        if sock_pc:
            sock_pc.send((str(texto) + "\n").encode())
    except Exception:
        pass


# Conecta la Pico W a la red WiFi.
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Solo intenta conectar si todavia no hay WiFi.
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        inicio = time.ticks_ms()

        # Espera la conexion, pero no para siempre.
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), inicio) > 20000:
                return None
            time.sleep_ms(250)

    return wlan.ifconfig()[0]


# Busca la PC usando un mensaje UDP.
def buscar_pc():
    try:
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass

        udp.settimeout(1)

        # Prueba varias veces porque la red puede tardar.
        for intento in range(10):
            try:
                udp.sendto(b"MORSE_DISCOVER", ("255.255.255.255", DISCOVERY_PORT))
                datos, addr = udp.recvfrom(64)
                mensaje = datos.decode().strip()

                if mensaje.startswith("MORSE_PC:"):
                    puerto = int(mensaje.split(":", 1)[1])
                    udp.close()
                    return addr[0], puerto

            except Exception:
                time.sleep_ms(500)

        udp.close()

    except Exception:
        pass

    return None, None


# Intenta conectar la maqueta con la PC.
def conectar_pc():
    global sock_pc, rx_buffer

    while True:
        ip = conectar_wifi()

        if ip is not None:
            pc_ip, puerto = buscar_pc()

            if pc_ip is not None:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((pc_ip, puerto))
                    s.setblocking(False)
                    sock_pc = s
                    rx_buffer = ""
                    return
                except Exception:
                    try:
                        s.close()
                    except Exception:
                        pass

        time.sleep(2)


# Lee una linea recibida desde la PC.
def leer_linea_wifi():
    global sock_pc, rx_buffer

    # Si no hay conexion, no hay nada que leer.
    if not sock_pc:
        return None

    try:
        datos = sock_pc.recv(128)

        if not datos:
            return "__DESCONECTADO__"

        rx_buffer += datos.decode()

        if "\n" in rx_buffer:
            linea, rx_buffer = rx_buffer.split("\n", 1)
            return linea.strip()

    except Exception:
        return None

    return None


# Ejecuta el comando que mando la PC.
def procesar_comando(linea):
    if not linea:
        return

    # Prueba simple para saber si la conexion responde.
    if linea == "PING":
        enviar("PONG")
        return

    # La PC pregunta que modo tiene el DIP switch.
    if linea == "MODE?":
        enviar("MODE:" + modo_actual())
        return

    # La PC pregunta si el switch del incrementador en 5 esta activo.
    if linea == "INC5_STATUS?":
        enviar("INC5_SWITCH:" + ("ON" if inc5_switch_activo() else "OFF"))
        return

    # La PC envia una letra capturada con el teclado para alimentar el circuito incrementador.
    if linea.startswith("INC5_CHAR:"):
        caracter = linea.split(":", 1)[1].strip().upper()
        inc5_procesar_caracter(caracter, "PC")
        enviar("DONE:INC5")
        return

    # Permite probar manualmente una entrada de 4 bits desde la PC.
    if linea.startswith("INC5_TEST:"):
        valor_texto = linea.split(":", 1)[1].strip()

        try:
            if len(valor_texto) == 4 and all(c in "01" for c in valor_texto):
                entrada = int(valor_texto, 2)
            else:
                entrada = int(valor_texto)
        except Exception:
            enviar("ERROR:INC5_VALOR_NO_VALIDO")
            return

        if entrada < 0 or entrada > 15:
            enviar("ERROR:INC5_VALOR_NO_VALIDO")
            return

        if not inc5_switch_activo():
            inc5_limpiar_entradas()
            enviar("INC5_SWITCH:OFF")
            return

        salida = (entrada + 5) & 0x0F
        inc5_escribir_entradas(entrada)
        enviar("INC5_SWITCH:ON")
        enviar("INC5_RESULT:TEST:-:" + inc5_bin4(entrada) + ":" + inc5_bin4(salida) + ":" + str(salida))
        enviar("DONE:INC5_TEST")
        return

    # Limpia luces y sonido.
    if linea == "CLEAR":
        limpiar_panel()
        buzzer_off()
        inc5_limpiar_entradas()
        enviar("DONE:CLEAR")
        return

    # Muestra una sola letra en el panel.
    if linea.startswith("LETTER:"):
        caracter = linea.split(":", 1)[1].strip().upper()
        mostrar_caracter(caracter, 0.4)
        enviar("DONE:LETTER")
        return

    # Muestra una frase completa en Morse.
    if linea.startswith("SHOW:"):
        partes = linea.split(":", 3)

        if len(partes) == 4:
            try:
                unidad = float(partes[1])
            except Exception:
                unidad = 0.2

            salida = partes[2]
            frase = partes[3]
            mostrar_frase(frase, unidad, salida)
            enviar("DONE:SHOW")

        return

    # Empieza a capturar lo que el jugador haga con el boton.
    if linea.startswith("CAPTURE:"):
        partes = linea.split(":")

        try:
            limite = float(partes[1])
        except Exception:
            limite = 25

        try:
            unidad = float(partes[2])
        except Exception:
            unidad = 0.2

        capturar_morse(limite, unidad)
        return

    # Prueba todos los LEDs del panel.
    if linea == "DEMO":
        for c in fila_a_chars + fila_b_chars + fila_num_chars:
            mostrar_caracter(c, 0.1)
        enviar("DONE:DEMO")
        return

    enviar("ERROR:COMANDO_NO_VALIDO")


# Estado inicial: todo apagado.
limpiar_panel()
buzzer_off()
inc5_limpiar_entradas()

# Bucle principal: si se desconecta, vuelve a conectar.
while True:
    conectar_pc()

    # Avisa a la PC que la maqueta esta lista y manda el modo actual.
    ultimo_modo = modo_actual()
    ultimo_inc5 = inc5_switch_activo()
    enviar("READY")
    enviar("MODE:" + ultimo_modo)
    enviar("INC5_SWITCH:" + ("ON" if ultimo_inc5 else "OFF"))

    # Bucle interno: ya conectado, escucha comandos de la PC.
    while True:
        modo = modo_actual()
        estado_inc5 = inc5_switch_activo()

        # Si cambia el DIP switch, se avisa a la PC.
        if modo != ultimo_modo:
            ultimo_modo = modo
            enviar("MODE:" + modo)

        # Si cambia el switch del incrementador, se avisa a la PC.
        if estado_inc5 != ultimo_inc5:
            ultimo_inc5 = estado_inc5
            if not estado_inc5:
                inc5_limpiar_entradas()
            enviar("INC5_SWITCH:" + ("ON" if estado_inc5 else "OFF"))

        comando = leer_linea_wifi()

        if comando == "__DESCONECTADO__":
            try:
                sock_pc.close()
            except Exception:
                pass
            sock_pc = None
            break

        # Si llego un comando valido, se ejecuta.
        if comando:
            procesar_comando(comando)

        time.sleep_ms(50)
