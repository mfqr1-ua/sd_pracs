import socket
import sys
import threading
import time

# Función para enviar mensaje al EC_DE
def send_message(client_socket, message):
    try:
        client_socket.sendall(message.encode('utf-8'))
        print(f"Mensaje enviado: {message}")
    except socket.error as e:
        print(f"Error al enviar mensaje: {e}")

# Función que captura eventos de la terminal (barra espaciadora para cambiar estado)
def listen_for_input(client_socket, estado):
    while True:
        user_input = input("")
        if user_input == " ":
            # Cambiar estado de OK a KO y viceversa
            estado['value'] = "KO" if estado['value'] == "OK" else "OK"
            print(f"Estado cambiado a {estado['value']}")

# Función principal de conexión al EC_DE
def main():
    if len(sys.argv) != 3:
        print("Uso: python EC_S.py <IP_EC_DE> <PUERTO_EC_DE>")
        sys.exit(1)

    # IP y puerto del EC_DE recibidos como argumentos
    ip_de = sys.argv[1]
    puerto_de = int(sys.argv[2])

    # Crear socket para conectarse con el EC_DE
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip_de, puerto_de))
        print(f"Conectado al EC_DE en {ip_de}:{puerto_de}")
    except socket.error as e:
        print(f"Error al conectarse a EC_DE: {e}")
        sys.exit(1)

    # Estado inicial del sensor: "OK"
    estado = {'value': 'OK'}  # Usamos un diccionario para mutabilidad en hilos

    # Crear un hilo para escuchar los eventos del sensor (entrada por teclado)
    input_thread = threading.Thread(target=listen_for_input, args=(client_socket, estado))
    input_thread.start()

    # Simulación constante de mensajes basados en el estado (OK/KO) cada segundo
    try:
        while True:
            send_message(client_socket, estado['value'])  # Enviar el estado actual
            time.sleep(1)  # Simula el envío del estado cada segundo
    except KeyboardInterrupt:
        print("Cerrando conexión...")
    finally:
        client_socket.close()

if __name__ == "__main__":
    main()
