"""
Instituto Tecnológico de Costa Rica
Escuela de Ingeniería en Computadores
Introducción a la programación
2026
Grupo 4
Python 3.14.3
Emanuel Rojas Benavides y Diego Andrés Herrrera Rivera
Proyecto 1
Descripción: El código de la PC controla el juego, las ventanas, las frases, la conexión WiFi y los puntajes.
Versión del programa: 1.0.0
Requerimientos del sistema: Python 3
"""

# Librerias usadas por la interfaz
import tkinter as tk
from tkinter import messagebox
import random
import time
import threading
import queue
import socket

# Diccionario principal: cada letra o numero tiene su codigo Morse.
MORSE = {
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

# Diccionario inverso: sirve para pasar de Morse a texto.
MORSE_INV = {v: k for k, v in MORSE.items()}
# Lista inicial de frases. Deben existir al iniciar el juego.
FRASES_INICIALES = ["SOS", "SI", "NO", "AYUDA", "MORSE", "TEC", "LUZ", "AMIGO", "MUNDO", "CODIGO"]
# Tiempo base del Morse. Un punto dura una unidad.
UNIDAD_FIJA = 0.2


# Limpia la frase y deja solo caracteres permitidos.
def limpiar_frase(frase):
    salida = ""
    for c in frase.upper():
        if c in MORSE or c == " ":
            salida += c
    return salida[:16]


# Convierte una frase normal a codigo Morse.
def texto_a_morse(frase):
    palabras = []
    for palabra in limpiar_frase(frase).split(" "):
        letras = []
        for c in palabra:
            if c in MORSE:
                letras.append(MORSE[c])
        palabras.append(" ".join(letras))
    return " / ".join(palabras)


# Convierte un codigo Morse escrito a texto normal.
def morse_a_texto(codigo):
    codigo = codigo.strip()
    if codigo == "":
        return ""

    texto = ""
    palabras = codigo.split("/")
    for p, palabra in enumerate(palabras):
        for letra in palabra.strip().split():
            texto += MORSE_INV.get(letra, "?")
        if p < len(palabras) - 1:
            texto += " "
    return texto


# Deja solo puntos y rayas para comparar la secuencia.
def solo_señales(codigo):
    salida = ""
    for c in codigo:
        if c in ".-":
            salida += c
    return salida


# Compara dos textos posicion por posicion y cuenta aciertos.
def comparar_posicion(esperado, recibido):
    puntos = 0
    for i, c in enumerate(esperado):
        if i < len(recibido) and recibido[i] == c:
            puntos += 1
    return puntos, len(esperado)


# Calcula el puntaje de un intento del jugador.
def evaluar_intento(frase, codigo_morse):
    frase_limpia = limpiar_frase(frase)
    texto_esperado = frase_limpia.replace(" ", "")
    texto_recibido = morse_a_texto(codigo_morse).replace(" ", "")
    morse_esperado = solo_señales(texto_a_morse(frase_limpia))
    morse_recibido = solo_señales(codigo_morse)

    puntos_caracteres, total_caracteres = comparar_posicion(texto_esperado, texto_recibido)
    puntos_morse, total_morse = comparar_posicion(morse_esperado, morse_recibido)

    return {
        "texto": texto_recibido,
        "morse": codigo_morse,
        "caracteres": puntos_caracteres,
        "total_caracteres": total_caracteres,
        "secuencia": puntos_morse,
        "total_secuencia": total_morse,
        "puntaje": puntos_caracteres + puntos_morse
    }


# Clase encargada de hablar con la maqueta por WiFi.
class ConexionPico:
    # Crea los valores iniciales de la clase.
    def __init__(self):
        self.ser = None
        self.servidor = None
        self.udp = None
        self.cola = queue.Queue()
        self.activa = False
        self.tcp_port = 5000
        self.discovery_port = 5001

    # Inicia los hilos que esperan la conexion de la maqueta.
    def iniciar(self):
        self.activa = True
        threading.Thread(target=self.responder_descubrimiento, daemon=True).start()
        threading.Thread(target=self.esperar_pico, daemon=True).start()

    # Responde cuando la maqueta busca la PC por la red.
    def responder_descubrimiento(self):
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp.bind(("", self.discovery_port))

            while self.activa:
                try:
                    datos, addr = self.udp.recvfrom(128)
                    if datos.decode(errors="ignore").strip() == "MORSE_DISCOVER":
                        self.udp.sendto(("MORSE_PC:" + str(self.tcp_port)).encode(), addr)
                except Exception:
                    pass

        except Exception as e:
            self.cola.put("WIFI_ERROR:" + str(e))

    # Espera a que la maqueta se conecte por TCP.
    def esperar_pico(self):
        try:
            self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.servidor.bind(("", self.tcp_port))
            self.servidor.listen(1)
            conn, addr = self.servidor.accept()
            self.ser = conn
            self.cola.put("WIFI_CONNECTED:" + addr[0])
            threading.Thread(target=self.leer, daemon=True).start()
        except Exception as e:
            self.cola.put("WIFI_ERROR:" + str(e))

    # Lee los mensajes que llegan desde la maqueta.
    def leer(self):
        buffer = ""

        while self.activa and self.ser:
            try:
                datos = self.ser.recv(128)

                if not datos:
                    self.cola.put("WIFI_ERROR:Maqueta desconectada")
                    self.ser = None
                    break

                buffer += datos.decode(errors="ignore")

                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    linea = linea.strip()
                    if linea:
                        self.cola.put(linea)

            except Exception as e:
                self.cola.put("WIFI_ERROR:" + str(e))
                self.ser = None
                break

    # Envia un mensaje a la maqueta.
    def enviar(self, texto):
        try:
            if self.ser:
                self.ser.sendall((texto + "\n").encode())
        except Exception as e:
            self.cola.put("WIFI_ERROR:" + str(e))

    # Cierra la conexion y libera los sockets.
    def cerrar(self):
        self.activa = False

        for s in (self.ser, self.servidor, self.udp):
            try:
                if s:
                    s.close()
            except Exception:
                pass

        self.ser = None
        self.servidor = None
        self.udp = None


# Clase principal de la aplicacion de la PC.
class App:
    # Crea los valores iniciales de la clase.
    def __init__(self):
        # Se crea la raiz de Tkinter, pero se oculta porque se usan ventanas Toplevel.
        self.root = tk.Tk()
        self.root.withdraw()

        # Variables principales del juego y de la conexion.
        self.pico = ConexionPico()
        self.win = None
        self.modo = "ESCUCHA"
        self.unidad = UNIDAD_FIJA
        self.salida = "BOTH"
        self.frase = "SOS"
        self.frases = FRASES_INICIALES.copy()
        self.puntos = {"A": 0, "B": 0}
        self.detalles = {"A": [], "B": []}
        self.callback = None
        self.ultima_consulta = 0
        self.pantalla = ""

        # Abre la primera pantalla y deja activo el ciclo de Tkinter.
        self.abrir_inicio()
        self.root.after(200, self.revisar)
        self.root.mainloop()

    # Crea una ventana nueva y cierra la anterior.
    def abrir(self, titulo, w=620, h=430):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass

        self.win = tk.Toplevel(self.root)
        self.win.title(titulo)
        self.win.geometry(f"{w}x{h}")
        self.win.protocol("WM_DELETE_WINDOW", self.salir)
        return self.win

    # Muestra un titulo centrado en la ventana.
    def titulo(self, texto):
        tk.Label(self.win, text=texto, wraplength=560, justify="center").pack(pady=12)

    # Muestra texto simple en la ventana.
    def texto(self, texto):
        tk.Label(self.win, text=texto, wraplength=560, justify="center").pack(pady=4)

    # Crea un boton basico con una accion.
    def boton(self, texto, cmd):
        tk.Button(self.win, text=texto, width=24, command=cmd).pack(pady=5)

    # Cierra la conexion y termina el programa.
    def salir(self):
        self.pico.cerrar()
        self.root.destroy()

    # Devuelve el nombre visible del modo actual.
    def nombre_modo(self):
        if self.modo == "ESCUCHA":
            return "Escucha y transmision"
        return "Transmision simple"

    # Forma el texto del puntaje de A y B.
    def texto_marcador(self):
        return "A: " + str(self.puntos["A"]) + "   B: " + str(self.puntos["B"])

    # Muestra el marcador en la ventana.
    def marcador(self):
        tk.Label(self.win, text=self.texto_marcador()).pack(pady=4)

    # Revisa mensajes de la maqueta sin congelar la ventana.
    def revisar(self):
        # Procesa todos los mensajes pendientes de la maqueta.
        while not self.pico.cola.empty():
            linea = self.pico.cola.get()

            # La maqueta ya se conecto correctamente.
            if linea.startswith("WIFI_CONNECTED:"):
                if hasattr(self, "estado_var"):
                    self.estado_var.set("Maqueta conectada")
                self.pico.enviar("PING")
                self.pico.enviar("MODE?")
                if self.pantalla == "INICIO":
                    self.abrir_modo()

            # Muestra errores de conexion en la pantalla inicial.
            elif linea.startswith("WIFI_ERROR:"):
                if hasattr(self, "estado_var") and self.pantalla == "INICIO":
                    self.estado_var.set(linea.split(":", 1)[1].strip())

            # Actualiza el modo si el DIP switch cambio.
            elif linea.startswith("MODE:"):
                nuevo = linea.split(":", 1)[1].strip()
                if nuevo in ("ESCUCHA", "SIMPLE") and nuevo != self.modo:
                    self.modo = nuevo
                    if self.pantalla not in ("CAPTURA", "PC_MORSE", "PRESENTANDO"):
                        self.abrir_modo()

            elif self.callback:
                self.callback(linea)

        ahora = time.time()
        # Pregunta el modo cada segundo para detectar cambios.
        if self.pico.ser and ahora - self.ultima_consulta > 1:
            self.pico.enviar("MODE?")
            self.ultima_consulta = ahora

        self.root.after(200, self.revisar)

    # Muestra la primera pantalla de conexion.
    def abrir_inicio(self):
        self.pantalla = "INICIO"
        self.callback = None
        self.abrir("Morse", 520, 250)
        self.titulo("Morse")
        self.estado_var = tk.StringVar(value="Iniciando...")
        tk.Label(self.win, textvariable=self.estado_var).pack(pady=10)
        self.texto("Conecte la maqueta a la misma red.")
        self.win.after(500, self.iniciar_wifi)

    # Reinicia la conexion WiFi y espera la maqueta.
    def iniciar_wifi(self):
        try:
            self.pico.cerrar()
            self.pico = ConexionPico()
            self.pico.iniciar()
            self.estado_var.set("Esperando maqueta...")
        except Exception as e:
            self.estado_var.set("Error")
            self.texto(str(e))
            self.boton("Reintentar", self.abrir_inicio)

    # Muestra el menu segun el modo del DIP switch.
    def abrir_modo(self):
        self.pantalla = "MODO"
        self.callback = None
        self.abrir("Modo", 520, 280)
        self.titulo("Modo: " + self.nombre_modo())
        self.boton("Configurar", self.abrir_config_escucha if self.modo == "ESCUCHA" else self.abrir_config_simple)
        self.boton("Frases", self.abrir_frases)
        self.boton("Probar LEDs", lambda: self.pico.enviar("DEMO"))
        self.boton("Salir", self.salir)

    # Actualiza la lista visual de frases.
    def actualizar_lista(self, lista):
        lista.delete(0, tk.END)
        for f in self.frases:
            lista.insert(tk.END, f)

    # Abre la pantalla para agregar o borrar frases.
    def abrir_frases(self):
        self.pantalla = "FRASES"
        self.callback = None
        self.abrir("Frases", 520, 520)
        self.titulo("Frases")

        lista = tk.Listbox(self.win, height=10, width=28)
        lista.pack(pady=6)
        self.actualizar_lista(lista)

        entrada_var = tk.StringVar(value="")
        tk.Entry(self.win, textvariable=entrada_var, width=28, justify="center").pack(pady=6)

        # Copia la frase seleccionada en la caja de texto.
        def seleccionar(event=None):
            sel = lista.curselection()
            if sel:
                entrada_var.set(self.frases[sel[0]])

        # Agrega una frase nueva si es valida.
        def agregar():
            frase = limpiar_frase(entrada_var.get())
            if frase == "":
                messagebox.showwarning("Error", "Frase vacia")
                return
            if len(self.frases) >= 10:
                messagebox.showwarning("Error", "Maximo 10 frases")
                return
            self.frases.append(frase)
            entrada_var.set("")
            self.actualizar_lista(lista)

        # Elimina una frase seleccionada si se permite.
        def eliminar():
            sel = lista.curselection()
            if not sel:
                messagebox.showwarning("Error", "Seleccione una frase")
                return
            if len(self.frases) <= 3:
                messagebox.showwarning("Error", "Deben quedar 3 frases")
                return
            frase = self.frases[sel[0]]
            if frase in ("SOS", "SI", "NO"):
                messagebox.showwarning("Error", "No elimine SOS, SI o NO")
                return
            self.frases.pop(sel[0])
            entrada_var.set("")
            self.actualizar_lista(lista)

        # Verifica que existan las 10 frases antes de volver.
        def volver():
            for f in ("SOS", "SI", "NO"):
                if f not in self.frases:
                    messagebox.showwarning("Error", "Faltan SOS, SI o NO")
                    return
            self.abrir_modo()
        lista.bind("<<ListboxSelect>>", seleccionar)

        frame = tk.Frame(self.win)
        frame.pack(pady=6)
        tk.Button(frame, text="Agregar", width=12, command=agregar).grid(row=0, column=0, padx=4)
        tk.Button(frame, text="Eliminar", width=12, command=eliminar).grid(row=0, column=1, padx=4)
        tk.Button(frame, text="Limpiar", width=12, command=lambda: entrada_var.set("")).grid(row=0, column=2, padx=4)

        self.boton("Guardar", volver)

    # Configura el modo de escucha y transmision.
    def abrir_config_escucha(self):
        self.pantalla = "CONFIG"
        self.callback = None
        self.abrir("Configurar", 520, 430)
        self.titulo("Configurar")

        self.unidad_var = tk.StringVar(value=str(self.unidad))
        self.salida_var = tk.StringVar(value=self.salida)

        self.texto("Unidad")
        tk.Radiobutton(self.win, text="0.2 s", variable=self.unidad_var, value="0.2").pack()
        tk.Radiobutton(self.win, text="0.3 s", variable=self.unidad_var, value="0.3").pack()

        self.texto("Salida")
        tk.Radiobutton(self.win, text="Luz", variable=self.salida_var, value="LIGHT").pack()
        tk.Radiobutton(self.win, text="Sonido", variable=self.salida_var, value="SOUND").pack()
        tk.Radiobutton(self.win, text="Ambos", variable=self.salida_var, value="BOTH").pack()

        self.boton("Iniciar", self.iniciar_escucha)
        self.boton("Volver", self.abrir_modo)

    # Guarda la configuracion y elige una frase al azar.
    def iniciar_escucha(self):
        self.unidad = float(self.unidad_var.get())
        self.salida = self.salida_var.get()
        self.frase = random.choice(self.frases)
        self.reiniciar_puntos()
        self.abrir_presentacion()

    # Configura el modo de transmision simple.
    def abrir_config_simple(self):
        self.pantalla = "CONFIG"
        self.callback = None
        self.abrir("Configurar", 520, 500)
        self.titulo("Configurar")

        self.unidad_var = tk.StringVar(value=str(self.unidad))
        self.texto("Unidad")
        tk.Radiobutton(self.win, text="0.2 s", variable=self.unidad_var, value="0.2").pack()
        tk.Radiobutton(self.win, text="0.3 s", variable=self.unidad_var, value="0.3").pack()

        self.texto("Frase")
        lista = tk.Listbox(self.win, height=9, width=26)
        lista.pack(pady=6)
        for f in self.frases:
            lista.insert(tk.END, f)
        lista.selection_set(0)

        # Inicia el modo simple con la frase seleccionada.
        def iniciar():
            sel = lista.curselection()
            if not sel:
                messagebox.showwarning("Error", "Seleccione una frase")
                return
            self.unidad = float(self.unidad_var.get())
            self.frase = self.frases[sel[0]]
            self.reiniciar_puntos()
            self.abrir_pico_capture("A", "simple", lambda: self.abrir_pico_capture("B", "simple", self.abrir_resultados))

        self.boton("Iniciar", iniciar)
        self.boton("Volver", self.abrir_modo)

    # Ordena a la maqueta mostrar la frase en Morse.
    def abrir_presentacion(self):
        self.pantalla = "PRESENTANDO"
        self.callback = None
        self.abrir("Mensaje", 520, 300)
        self.titulo("Mensaje")
        self.marcador()
        self.texto("La maqueta mostrara la frase.")

        estado_var = tk.StringVar(value="Esperando...")
        tk.Label(self.win, textvariable=estado_var).pack(pady=10)

        # Recibe respuestas de la maqueta para esta pantalla.
        def recibir(linea):
            if linea == "DONE:SHOW":
                estado_var.set("Listo")
                self.callback = None
                self.win.after(900, self.turno_escucha_1)

        self.callback = recibir
        self.pico.enviar(f"SHOW:{self.unidad}:{self.salida}:{self.frase}")
        estado_var.set("Mostrando...")

    # Primer turno del modo escucha.
    def turno_escucha_1(self):
        self.abrir_pc_morse("A", lambda: self.abrir_pico_capture("B", "escucha", self.abrir_cambio_turno))

    # Pantalla corta para cambiar los jugadores.
    def abrir_cambio_turno(self):
        self.pantalla = "CAMBIO"
        self.callback = None
        self.abrir("Cambio", 520, 260)
        self.titulo("Cambio de turno")
        self.marcador()
        self.texto("Ahora cambian los jugadores.")
        self.win.after(1200, self.turno_escucha_2)

    # Segundo turno del modo escucha.
    def turno_escucha_2(self):
        self.abrir_pc_morse("B", lambda: self.abrir_pico_capture("A", "escucha", self.abrir_resultados))

    # Captura Morse desde la tecla M en la PC.
    def abrir_pc_morse(self, jugador, despues):
        self.pantalla = "PC_MORSE"
        self.callback = None
        self.abrir("PC", 620, 430)
        self.titulo("Jugador " + jugador + " en PC")
        self.marcador()
        self.texto("Use la tecla M.")
        self.texto("Corto = punto. Largo = raya.")

        codigo_var = tk.StringVar(value="")
        texto_var = tk.StringVar(value="Texto: ")
        estado_var = tk.StringVar(value="Esperando")

        inicio_press = {"t": 0, "down": False, "ultima_suelta": time.time()}
        control = {"empezo": False, "fin": False, "timer": None}

        tk.Label(self.win, textvariable=estado_var).pack(pady=4)
        tk.Label(self.win, textvariable=codigo_var, width=50, height=3).pack(pady=8)
        tk.Label(self.win, textvariable=texto_var).pack(pady=4)

        # Actualiza el texto traducido mientras el jugador escribe Morse.
        def actualizar():
            texto_var.set("Texto: " + morse_a_texto(codigo_var.get()))

        # Cancela el cierre automatico si el jugador sigue escribiendo.
        def cancelar_timer():
            if control["timer"] is not None:
                try:
                    self.root.after_cancel(control["timer"])
                except Exception:
                    pass
                control["timer"] = None

        # Quita eventos del teclado y pasa a la siguiente parte.
        def pasar():
            try:
                self.win.unbind("<KeyPress>")
                self.win.unbind("<KeyRelease>")
            except Exception:
                pass
            despues()

        # Termina el intento, evalua y guarda los puntos.
        def terminar():
            if control["fin"]:
                return

            control["fin"] = True
            cancelar_timer()
            estado_var.set("Terminado")
            datos = evaluar_intento(self.frase, codigo_var.get().strip())
            self.guardar_puntos(jugador, "PC", datos)
            self.root.after(300, pasar)

        # Termina automaticamente tras unos segundos sin escribir.
        def programar_fin():
            cancelar_timer()
            control["timer"] = self.root.after(4000, terminar)

        # Detecta cuando el jugador presiona la tecla M.
        def tecla_down(event):
            if event.keysym.lower() != "m" or inicio_press["down"] or control["fin"]:
                return

            cancelar_timer()
            ahora = time.time()

            if control["empezo"]:
                pausa = ahora - inicio_press["ultima_suelta"]
                if pausa >= 7 * self.unidad:
                    codigo_var.set(codigo_var.get() + " / ")
                elif pausa >= 3 * self.unidad:
                    codigo_var.set(codigo_var.get() + " ")
                actualizar()

            inicio_press["down"] = True
            inicio_press["t"] = ahora
            control["empezo"] = True
            estado_var.set("Presionando")

        # Detecta cuando el jugador suelta la tecla M.
        def tecla_up(event):
            if event.keysym.lower() != "m" or not inicio_press["down"] or control["fin"]:
                return

            inicio_press["down"] = False
            duracion = time.time() - inicio_press["t"]
            codigo_var.set(codigo_var.get() + ("." if duracion < 2 * self.unidad else "-"))
            inicio_press["ultima_suelta"] = time.time()
            estado_var.set("Registrado")
            actualizar()
            programar_fin()

        self.win.bind("<KeyPress>", tecla_down)
        self.win.bind("<KeyRelease>", tecla_up)
        self.win.focus_force()

    # Captura Morse desde el boton fisico de la maqueta.
    def abrir_pico_capture(self, jugador, tipo, despues):
        self.pantalla = "CAPTURA"
        self.callback = None
        self.abrir("Maqueta", 620, 450)
        self.titulo("Jugador " + jugador + " en maqueta")
        self.marcador()
        self.texto("Use el boton fisico.")
        self.texto("Corto = punto. Largo = raya.")

        if tipo == "simple":
            self.texto("Frase: " + self.frase)
        else:
            self.texto("Repita la frase.")

        estado_var = tk.StringVar(value="Esperando")
        codigo_var = tk.StringVar(value="Morse: ")
        texto_var = tk.StringVar(value="Texto: ")
        tiempo_var = tk.StringVar(value="Tiempo: ")

        tk.Label(self.win, textvariable=estado_var).pack(pady=4)
        tk.Label(self.win, textvariable=codigo_var, width=50, height=2).pack(pady=6)
        tk.Label(self.win, textvariable=texto_var).pack(pady=4)
        tk.Label(self.win, textvariable=tiempo_var).pack(pady=4)

        datos = {"morse": "", "texto": "", "tiempo": 0}

        # Recibe respuestas de la maqueta para esta pantalla.
        def recibir(linea):
            if linea == "CAPTURE_START":
                estado_var.set("Capturando")
            elif linea == "BUTTON:DOWN":
                estado_var.set("Presionando")
            elif linea.startswith("BUTTON:UP:"):
                estado_var.set("Registrado")
            elif linea == "GAP:LETTER":
                estado_var.set("Letra")
            elif linea == "GAP:WORD":
                estado_var.set("Palabra")
            elif linea.startswith("LIVE_MORSE:"):
                datos["morse"] = linea.split(":", 1)[1]
                codigo_var.set("Morse: " + datos["morse"])
            elif linea.startswith("LIVE_TEXT:"):
                datos["texto"] = linea.split(":", 1)[1]
                texto_var.set("Texto: " + datos["texto"])
            elif linea.startswith("MORSE:"):
                datos["morse"] = linea.split(":", 1)[1]
                codigo_var.set("Morse: " + datos["morse"])
            elif linea.startswith("TEXT:"):
                datos["texto"] = linea.split(":", 1)[1]
                texto_var.set("Texto: " + datos["texto"])
            elif linea.startswith("TIME:"):
                try:
                    datos["tiempo"] = float(linea.split(":", 1)[1])
                except Exception:
                    datos["tiempo"] = 0
                tiempo_var.set("Tiempo: " + str(datos["tiempo"]) + " s")
            elif linea == "DONE:CAPTURE":
                self.callback = None
                evaluacion = evaluar_intento(self.frase, datos["morse"])

                if tipo == "simple":
                    extra = self.puntos_velocidad(datos["tiempo"])
                    evaluacion["puntaje"] += extra
                    evaluacion["extra_velocidad"] = extra
                    evaluacion["tiempo"] = datos["tiempo"]

                self.guardar_puntos(jugador, "Maqueta", evaluacion)
                despues()

        self.callback = recibir
        self.pico.enviar(f"CAPTURE:25:{self.unidad}")

    # Da puntos extra segun el tiempo usado.
    def puntos_velocidad(self, tiempo_seg):
        if tiempo_seg <= 8:
            return 3
        if tiempo_seg <= 14:
            return 2
        return 1

    # Limpia puntos y detalles para una nueva ronda.
    def reiniciar_puntos(self):
        self.puntos = {"A": 0, "B": 0}
        self.detalles = {"A": [], "B": []}

    # Guarda el puntaje de un jugador.
    def guardar_puntos(self, jugador, medio, datos):
        self.puntos[jugador] += datos["puntaje"]
        datos["medio"] = medio
        self.detalles[jugador].append(datos)

    # Prepara el resumen de puntos de un jugador.
    def texto_detalles(self, jugador):
        lineas = []
        for d in self.detalles[jugador]:
            linea = (
                d["medio"] + ": " +
                str(d["puntaje"]) + " pts | " +
                str(d["caracteres"]) + "/" + str(d["total_caracteres"]) +
                " letras | " +
                str(d["secuencia"]) + "/" + str(d["total_secuencia"]) +
                " señales"
            )
            if "extra_velocidad" in d:
                linea += " | +" + str(d["extra_velocidad"])
            lineas.append(linea)
        return "\n".join(lineas)

    # Muestra los resultados finales de la ronda.
    def abrir_resultados(self):
        self.pantalla = "RESULTADOS"
        self.callback = None
        self.abrir("Resultados", 620, 500)
        self.titulo("Resultados")

        # Decide quien gano con base en los puntos.
        if self.puntos["A"] > self.puntos["B"]:
            ganador = "A"
        elif self.puntos["B"] > self.puntos["A"]:
            ganador = "B"
        else:
            ganador = "Empate"

        self.texto("Modo: " + self.nombre_modo())
        self.texto("Frase: " + self.frase)
        self.texto("Morse: " + texto_a_morse(self.frase))
        self.texto("Jugador A: " + str(self.puntos["A"]))
        self.texto(self.texto_detalles("A"))
        self.texto("Jugador B: " + str(self.puntos["B"]))
        self.texto(self.texto_detalles("B"))
        self.texto("Ganador: " + ganador)

        self.boton("Nueva ronda", self.abrir_modo)
        self.boton("Salir", self.salir)


# Inicia todo el programa.
App()
