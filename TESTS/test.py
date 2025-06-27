# test.py

import requests
import time
import logging
from datetime import datetime
import sys

# Configuración de logging
logging.basicConfig(
    filename='test.log',  # Archivo donde se guardarán los logs
    level=logging.INFO,    # Nivel de registro
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

BASE_URL = 'http://192.168.23.1:6761'

def get_traffic_status():
    """
    Realiza una solicitud GET al endpoint /get_traffic_status y muestra el estado del tráfico.
    """
    url = f'{BASE_URL}/get_traffic_status'
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción para códigos de estado HTTP 4xx/5xx
    data = response.json()
    status = data.get('status', 'Desconocido')
    city = data.get('city', 'Desconocida')
    logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}")
    return status, city


def main():
    print("Iniciando test.py para monitorear el estado del tráfico cada 10 segundos...")
    logging.info("test.py iniciado para monitorear el estado del tráfico.")
    try:
        status, city = get_traffic_status()
        while True:
            try:
                prevStatus = status
                prevCity  = city
                status, city = get_traffic_status()

                if prevCity != city:
                    print(f"CIUDAD CAMBIADA DE {prevCity} A {city}")

                if prevStatus == 'OK' and status == 'KO':
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}. VOLVER A LA BASE!")
                    #LOGICA DE LOS TAXIS VUELTA A BASE

                elif prevStatus == 'KO' and status == 'OK':
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}. REANUDAR LA MARCHA!")
                    #LOGICA VUELTA A HACER PEDIDOS

            except requests.exceptions.RequestException as e:
                # Manejo de excepciones relacionadas con la solicitud HTTP
                logging.error(f"Excepción al obtener el estado del tráfico: {e}")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Excepción al obtener el estado del tráfico: {e}")
                print("El servidor no está disponible. Saliendo del programa.")
                sys.exit(1)  # Termina el programa con un código de salida no cero
            time.sleep(10)
    
    except KeyboardInterrupt:
        print("\nDeteniendo test.py...")
        logging.info("test.py detenido por el usuario.")

if __name__ == '__main__':
    main()