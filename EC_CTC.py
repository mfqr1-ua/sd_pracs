# ec_ctc.py
import socket
import threading
import time
import requests
from flask import Flask, jsonify, request
from datetime import datetime, timezone
import json
import sys
import logging  # Importar el módulo logging
from dotenv import load_dotenv
import os
from PyInquirer import prompt

# Cargar variables de entorno desde .env
load_dotenv()
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
if not OPENWEATHER_API_KEY:
    print("Por favor, proporciona una API Key válida en el archivo .env con la clave OPENWEATHER_API_KEY.")
    sys.exit(1)

# Configuración
DEFAULT_CITY = 'Madrid'  # Ciudad por defecto
TEMPERATURE_THRESHOLD = 0  # °C

app = Flask(__name__)

# Configuración de logging
logging.basicConfig(
    filename='LOGS/ec_ctc.log',  # Archivo donde se guardarán los logs
    level=logging.INFO,     # Nivel de registro
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

current_city = DEFAULT_CITY
traffic_status = 'OK'  # Estado inicial del tráfico

def get_current_temperature(city):
    """
    Obtiene la temperatura actual de la ciudad especificada utilizando la API de OpenWeather.
    """
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&appid={OPENWEATHER_API_KEY}'
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            temp = data['main']['temp']
            logging.info(f"Temperatura en {city}: {temp}°C")
            return temp
        else:
            logging.error(f"Error al obtener la temperatura: {data.get('message', 'Error desconocido')}")
            return None
    except Exception as e:
        logging.error(f"Excepción al obtener la temperatura: {e}")
        return None

def determine_traffic_status(temp):
    """
    Determina el estado del tráfico basado en la temperatura.
    """
    if temp is not None:
        return 'OK' if temp >= TEMPERATURE_THRESHOLD else 'KO'
    return 'KO'  # Por defecto, si no se puede obtener la temperatura

@app.route('/get_traffic_status', methods=['GET'])
def get_traffic_status_route():
    """
    Endpoint para obtener el estado actual del tráfico.
    """
    global traffic_status
    return jsonify({
        'status': traffic_status,
        'city': current_city,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/set_city', methods=['POST'])
def set_city():
    """
    Endpoint para cambiar la ciudad actual.
    """
    global current_city, traffic_status
    data = request.get_json()
    if not data or 'city' not in data:
        return jsonify({'error': 'Se requiere el nombre de la ciudad'}), 400
    new_city = data['city']
    logging.info(f"Cambiando ciudad de {current_city} a {new_city}")
    current_city = new_city
    # Actualizar el estado del tráfico inmediatamente después de cambiar la ciudad
    temp = get_current_temperature(current_city)
    traffic_status = determine_traffic_status(temp)
    return jsonify({'message': f'Ciudad actualizada a {current_city}', 'new_status': traffic_status}), 200

@app.route('/get_temperature', methods=['GET'])
def get_temperature_route():
    """
    Endpoint para obtener la temperatura actual de la ciudad.
    """
    temp = get_current_temperature(current_city)
    if temp is not None:
        return jsonify({
            'city': current_city,
            'temperature': temp,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    else:
        return jsonify({'error': 'No se pudo obtener la temperatura'}), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    Endpoint para detener el servidor Flask.
    """
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        return jsonify({'error': 'No se puede cerrar el servidor'}), 500
    func()
    return jsonify({'message': 'Servidor cerrado'}), 200

def run_flask(ip, port):
    """
    Ejecuta el servidor Flask.
    """
    app.run(host=ip, port=port, debug=False, use_reloader=False)

def cli_menu():
    """
    Menú de línea de comandos para interactuar con el usuario.
    """
    global current_city, traffic_status
    while True:
        questions = [
            {
                'type': 'list',
                'name': 'action',
                'message': 'Selecciona una acción:',
                'choices': [
                    'Cambiar ciudad',
                    'Ver estado actual del tráfico',
                    'Ver temperatura actual',
                    'Salir'
                ]
            }
        ]
        answers = prompt(questions)
        if not answers:
            continue
        action = answers['action']
        if action == 'Cambiar ciudad':
            questions = [
                {
                    'type': 'input',
                    'name': 'new_city',
                    'message': 'Introduce el nombre de la nueva ciudad:'
                }
            ]
            answers = prompt(questions)
            if not answers or 'new_city' not in answers:
                print("No se proporcionó una ciudad válida.")
                continue
            new_city = answers['new_city'].strip()
            if new_city:
                try:
                    response = requests.post(f'http://{ip}:{port}/set_city', json={'city': new_city})
                    if response.status_code == 200:
                        data = response.json()
                        print(f"Ciudad cambiada a {data['message']}. Estado del tráfico: {data['new_status']}")
                    else:
                        data = response.json()
                        print(f"Error al cambiar la ciudad: {data.get('error', 'Error desconocido')}")
                except Exception as e:
                    print(f"Error al comunicar con el servidor: {e}")
        elif action == 'Ver estado actual del tráfico':
            try:
                response = requests.get(f'http://{ip}:{port}/get_traffic_status')
                if response.status_code == 200:
                    data = response.json()
                    print(f"Ciudad: {data['city']}")
                    print(f"Estado del Tráfico: {data['status']}")
                else:
                    print(f"Error al obtener el estado del tráfico: {response.text}")
            except Exception as e:
                print(f"Error al comunicar con el servidor: {e}")
        elif action == 'Ver temperatura actual':
            try:
                response = requests.get(f'http://{ip}:{port}/get_temperature')
                if response.status_code == 200:
                    data = response.json()
                    print(f"Temperatura actual en {data['city']}: {data['temperature']}°C")
                    print(f"Timestamp: {data['timestamp']}")
                else:
                    data = response.json()
                    print(f"Error al obtener la temperatura: {data.get('error', 'Error desconocido')}")
            except Exception as e:
                print(f"Error al comunicar con el servidor: {e}")
        elif action == 'Salir':
            print("Saliendo del menú de EC_CTC...")
            print("Cerrando aplicación...")
            try:
                requests.post(f'http://{ip}:{port}/shutdown')
            except Exception:
                pass
            break
        time.sleep(1)

def periodic_temperature_check():
    """
    Función que verifica la temperatura cada 10 segundos y actualiza el estado del tráfico.
    """
    global traffic_status
    while True:
        temp = get_current_temperature(current_city)
        new_status = determine_traffic_status(temp)
        if new_status != traffic_status:
            logging.info(f"Estado del tráfico cambiado de {traffic_status} a {new_status}")
            traffic_status = new_status
        time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Uso: python EC_CTC.py <puerto>")
        sys.exit(1)
    ip = socket.gethostbyname(socket.gethostname())
    port = sys.argv[1]

    print(f"Iniciando EC_CTC... en {ip}:{port}")
    flask_thread = threading.Thread(target=run_flask, args=(ip, port), daemon=True)
    flask_thread.start()

    temperature_thread = threading.Thread(target=periodic_temperature_check, daemon=True)
    temperature_thread.start()

    cli_menu()

    print("EC_CTC ha sido cerrado.")