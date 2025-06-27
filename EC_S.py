
import socket
import sys
import threading
import time

#ARREGLAR QUE CUANDO HAGA UN KEYBOARD INTERRUPT 

def wait_input(status):
    print("Presione 'k' para KO, 'o' para OK")
    while True:
        user_input = input()
        if user_input.lower() == 'k':
            status['value'] = "KO"
            print(f"Estado cambiado a {status['value']}")
        elif user_input.lower() == 'o':
            status['value'] = "OK"
            print(f"Estado cambiado a {status['value']}")

def send_message(client_socket, message):
    try:
        client_socket.sendall(message.encode('utf-8'))
        print(f"Mensaje enviado: {message}")
    except socket.error as e:
        print(f"Error al enviar mensaje: {e}")

def run():
    if len(sys.argv) != 3:
        print("Uso: python EC_S.py <IP_EC_DE> <PUERTO_EC_DE>")
        sys.exit(1)

    ip_de = sys.argv[1]
    de_port = int(sys.argv[2])

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip_de, de_port))
        print(f"Connected to Data Engine: {ip_de}:{de_port}")
    except socket.error as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    status = {'value': 'OK'}

    input_thread = threading.Thread(target=wait_input, args=(status,))
    input_thread.start()

    try:
        while True:
            send_message(client_socket, status['value'])  
            time.sleep(1)  
    except KeyboardInterrupt:
        print("Cerrando conexión...")
    finally:
        client_socket.close()

if __name__ == "__main__":
    run()
