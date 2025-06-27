from PyInquirer import prompt
import requests
import ssl
import socket

BASE_URL = "https://localhost:5002"

# Disable SSL warnings (for testing purposes only)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CERT_PATH = "C:/Users/Ginés/Desktop/SD-2425/cert.pem"  # Ruta al certificado autofirmado del servidor

def register_taxi():
    taxi_id = input("Introduce el ID del taxi a registrar: ")
    try:
        response = requests.put(f"{BASE_URL}/register_taxi", json={"id": int(taxi_id)}, verify=False)
        print(response.json())
    except Exception as e:
        print(f"Error al registrar el taxi: {e}")

def deregister_taxi():
    taxi_id = input("Introduce el ID del taxi a dar de baja: ")
    try:
        response = requests.delete(f"{BASE_URL}/deregister_taxi/{taxi_id}", verify=False)
        print(response.json())
    except Exception as e:
        print(f"Error al dar de baja el taxi: {e}")

def test_ssl_encryption():
    try:
        # Crear un contexto SSL que confíe explícitamente en el certificado autofirmado
        context = ssl.create_default_context(cafile=CERT_PATH)
        with socket.create_connection(("localhost", 5002)) as sock:
            with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                print("Conexión SSL establecida exitosamente. El cifrado está funcionando correctamente.")
                print(f"Usando protocolo: {ssock.version()} con cifrado: {ssock.cipher()}")
    except Exception as e:
        print(f"Error al verificar el cifrado SSL: {e}")

def menu():
    questions = [
        {
            'type': 'list',
            'name': 'action',
            'message': '¿Qué acción deseas realizar?',
            'choices': [
                'Registrar Taxi',
                'Dar de baja Taxi',
                'Probar cifrado SSL',
                'Salir'
            ]
        }
    ]
    return prompt(questions)['action']

if __name__ == "__main__":
    while True:
        action = menu()

        if action == 'Registrar Taxi':
            register_taxi()
        elif action == 'Dar de baja Taxi':
            deregister_taxi()
        elif action == 'Probar cifrado SSL':
            test_ssl_encryption()
        elif action == 'Salir':
            print("Saliendo del menú...")
            break
        else:
            print("Opción no válida.")
