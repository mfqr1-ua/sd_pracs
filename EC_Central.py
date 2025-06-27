import socket
import threading
import sys
import json
import time
import logging
from datetime import datetime
import requests
from kafka import KafkaProducer, KafkaConsumer
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation
from flask import Flask, jsonify, render_template, request
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Constantes de los tópicos de Kafka
TOPIC_SOLICITUDES_TAXIS = 'solicitudes-taxis' #consume solicitudes de clientes para que les recojan
TOPIC_RESPUESTAS_TAXIS = 'respuestas-taxis' #produce una respuesta para los clientes
TOPIC_ASIGNACION_TAXIS = 'asignacion-taxis' #produce una respuesta para los taxis cuando se le asigna un cliente
TOPIC_TAXI_UPDATES = 'taxi_updates' #consume para obtener el estado y posicion de los taxis
TOPIC_TAXI_END_CENTRAL = 'taxi-end-central' #envia a central el fin de servicio 

TAXIS_FILE = "taxis.json" #esto no es buen codigo pero es una solucion temporal

logging.basicConfig(
    filename='LOGS/central.log',  # Archivo donde se guardarán los logs
    level=logging.INFO,    # Nivel de registro
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

app = Flask(__name__)

#FRONT/GRAPHICS

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/get_taxis')
def get_taxis():
    with open('taxis.json') as f:
        taxis = json.load(f)
    return jsonify(taxis)

@app.route('/get_map')
def get_map():
    with open('mapa.json') as f:
        mapa = json.load(f)
    return jsonify(mapa)

#A BIT OF REGISTRY LOGIC

@app.route('/get_all_taxis', methods=['GET'])
def get_all_taxis():
    """Devuelve el JSON actual de taxis."""
    try:
        with open(TAXIS_FILE, 'r') as file:
            taxis = json.load(file)
    except FileNotFoundError:
        taxis = []  # Si el archivo no existe, devuelve una lista vacía
    return jsonify(taxis), 200

@app.route('/update_taxis', methods=['POST'])
def update_taxis():
    """Actualiza el JSON de taxis con los datos recibidos."""
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'El formato del JSON no es válido'}), 400

    try:
        with open(TAXIS_FILE, 'w') as file:
            json.dump(data, file, indent=4)
        return jsonify({'message': 'Taxis actualizados correctamente'}), 200
    except IOError as e:
        return jsonify({'error': f'Error al guardar los datos: {e}'}), 500

class ECCentral:
    def __init__(self, port, kafka_ip_port, taxi_bd, CTC_ipPort, front_port):
        self.port = int(port)
        self.kafka_ip_port = kafka_ip_port
        self.taxi_bd = taxi_bd
        self.offset_taxi_end = -1
        self.ctcApi = 'http://' + CTC_ipPort
        self.front_port = int(front_port)
        
        self.kafka_consumer_taxi = KafkaConsumer(
            TOPIC_TAXI_UPDATES, 
            bootstrap_servers=self.kafka_ip_port,
            group_id='central_taxi_group',
            auto_offset_reset='latest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        
        self.producer_taxicommands = KafkaProducer(
            bootstrap_servers=kafka_ip_port, 
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

        self.producer_customer = KafkaProducer(
            bootstrap_servers=kafka_ip_port,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        self.consumer_customer = KafkaConsumer(
            TOPIC_SOLICITUDES_TAXIS,
            bootstrap_servers=kafka_ip_port,
            group_id='central_customer_group',
            auto_offset_reset='latest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

        self.consumer_taxi_end = KafkaConsumer(
            TOPIC_TAXI_END_CENTRAL,
            bootstrap_servers=kafka_ip_port,
            group_id='taxi_end_group',
            auto_offset_reset='latest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

    #ok
    def save_taxis_to_json(self, filename, taxis):
        try:    
            with open(filename, 'w') as file:
                json.dump(taxis, file, indent=4)
            # print(f"Archivo {filename} actualizado correctamente.")
        except IOError as e:
            print(f"Error al escribir en {filename}: {e}")

    #ok
    def load_file(self, filename):
        try:
            with open(filename, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"{filename} not found.")
            return []
        except json.JSONDecodeError:
            print(f"Error decoding {filename}.")
            return []
    
    #ok
    def update_taxi_status(self, id_taxi, status, taxis):
        for taxi in taxis:
            if taxi["id"] == id_taxi:
                taxi["estado"] = "verde" if status == "OK" else "rojo"
                return True
        return False

    #ok
    def check_id(self, taxis, id_taxi):
        for taxi in taxis:
            if taxi["id"] == id_taxi:
                return True
        return False
    

    def listen_taxi_updates(self):
        for msg in self.kafka_consumer_taxi:
            if msg.value is None:
                continue
            data = msg.value
            print(f"Received taxi update: {data}")
            parts = data.split('#')
            if len(parts) >= 4:
                taxi_id = int(parts[0])
                status = parts[1]
                taxiX = int(parts[2])
                taxiY = int(parts[3])
                taxis = self.load_file(self.taxi_bd)
                for taxi in taxis:
                    if taxi['id'] == taxi_id:
                        taxi['estado'] = 'verde' if status == 'OK' else 'rojo'
                        taxi['coordenada_origen'] = {'x': taxiX, 'y': taxiY}
                        taxi['status'] = status  # Update status if necessary
                        self.save_taxis_to_json(self.taxi_bd, taxis)
                        print(f"Updated taxi {taxi_id} status to {status}, estado to {taxi['estado']}")
                        break
                else:
                    print(f"Taxi {taxi_id} not found in taxis database.")
            else:
                print(f"Invalid taxi update message format: {data}")

    def listen_customer_services(self):
        try:
            for msg in self.consumer_customer:

                mensaje_cliente = msg.value
                print(f"Mensaje recibido del cliente: {mensaje_cliente}")

                servicios = mensaje_cliente.split(" ")
                
                if len(servicios) != 3:
                    print("ERROR WRONG FORMAT.")
                    continue
                
                client, aux, destination = servicios
                
                taxi_available = self.check_taxi_availability(destination, client)

                if taxi_available:
                    response = f"{client}: OK"
                else:
                    response = f"{client}: KO"

                # Enviar la respuesta al customer
                self.producer_customer.send(TOPIC_RESPUESTAS_TAXIS, value=response)
                self.producer_customer.flush()
                print(f"Response sent: {response}")
        except Exception as e:
            print(f"Error al escuchar servicios de clientes: {e}")
    
    #ok
    def listen_taxi_end(self):
        try:
            for msg in self.consumer_taxi_end:
                if msg is None:
                    continue
                
                if msg.offset > self.offset_taxi_end:
                    mensaje = msg.value
                    print(f"el mensaje es {mensaje}")
                    self.offset_taxi_end = msg.offset
                    
                    mensajes = mensaje.split('#')
                    taxi_id = int(mensajes[1])
                    cliente_id = mensajes[3]
                    taxis = self.load_file(self.taxi_bd)
                    mapa = self.load_file('Mapa.json')
                    
                    for taxi in taxis:
                        if taxi['id'] == taxi_id:
                            taxi['disponible'] = True
                            taxi['recogido'] = False
                            taxi['cliente']['id_cliente'] = ""
                            taxi['cliente']['x'] = None
                            taxi['cliente']['y'] = None
                            taxi['coordenada_destino']['x'] = None
                            taxi['coordenada_destino']['y'] = None
                            taxi['coordenada_destino']['id'] = ""
                            print(f"taxi {taxi_id} has arrived")

                            corx = taxi['coordenada_origen']['x']
                            cory = taxi['coordenada_origen']['y']
                            mapa[cliente_id] = [corx, cory]

                            self.save_taxis_to_json(self.taxi_bd, taxis)
                            self.save_taxis_to_json('Mapa.json', mapa)
        except Exception as e:
            print(f"Error al escuchar el fin del servicio del taxi: {e}")

    #ok
    def send_coordinates(self, producer, taxi_id, kafka_topic):
        taxis = self.load_file(self.taxi_bd)
        for taxi in taxis:
            if taxi['id'] == taxi_id:
                coordenada_destino = taxi['coordenada_destino']
                cliente = taxi['cliente']
                mensaje = f"Taxi has to go to#{taxi_id}#{coordenada_destino['x']}#{coordenada_destino['y']}#{cliente['x']}#{cliente['y']}#{cliente['id_cliente']}"
                print(f"sent to EC_DE: {mensaje}")
                
                producer.send(kafka_topic, value=mensaje)
                producer.flush()
                return True
        return False

    #ok
    def get_coordinates(self, destino, client):
        coordinates = self.load_file('Mapa.json')
        if destino in coordinates:
            destX, destY = coordinates[destino]
        if client in coordinates:
            clientXpos, clientYpos = coordinates[client]
            print(f"Client coordinates are {clientXpos}, {clientYpos}")
        return clientXpos, clientYpos, destX, destY
    
    #ok
    def socket_taxi(self, conn, addr):
        print(f"[NEW CONN] {addr} connected.")
    
        while True:
            msg_length = conn.recv(64).decode('utf-8')
            if not msg_length:
                break
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode('utf-8')
            taxis = self.load_file(self.taxi_bd)
            id_taxi = int(msg)
            exists = self.check_id(taxis, id_taxi)
            for taxi in taxis:
                if taxi["id"] == id_taxi:
                    coordinates = taxi["coordenada_origen"]
                    taxi['verificado'] = True 
                    
                    print(f"my taxi ID is: {msg} and my coordinates are {coordinates}")
            
            self.save_taxis_to_json(self.taxi_bd, taxis)

            response = ""
            if exists:
                response += f"your coordinates are {coordinates}"
            else:
                response += "ERROR taxi doesnt exist"
            conn.send(response.encode('utf-8'))
        
        conn.close()

    #ok
    def check_taxi_availability(self, destino, client):
        taxis = self.load_file(self.taxi_bd)

        for taxi in taxis:
            if taxi['disponible'] and taxi['verificado']:  # Verifica si el campo 'disponible' es True
                print(f"Taxi disponible: ID {taxi['id']}, Estado: {taxi['estado']}, Coordenada origen: {taxi['coordenada_origen']}")
                taxi['disponible'] = False
                taxi['coordenada_destino']['id'] = destino
                clientX, clientY, destX, destY = self.get_coordinates(destino, client)
                taxi['coordenada_destino']['x'] = destX
                taxi['coordenada_destino']['y'] = destY
                taxi['cliente']['x'] = clientX
                print(f"la coor x es {taxi['coordenada_destino']['x']}")
                taxi['cliente']['y'] = clientY
                taxi['cliente']['id_cliente'] = client
                print(f"el cliente está en {clientX},{clientY} y quiere ir a {destX},{destY}")
                self.save_taxis_to_json(self.taxi_bd, taxis)
                
                self.send_coordinates(self.producer_taxicommands, taxi['id'], TOPIC_ASIGNACION_TAXIS)

                return True  
        print("No available taxis.")
        return False

#--------------------------DEPRECATED GRAPHICS---------------------------   
    #ok
    def actualizar_mapa(self, frame, taxis, ubicaciones, ax, size):
        ax.clear()

 
        mapa_colores = np.zeros((size, size))


        cmap = mcolors.ListedColormap(['white', 'yellow', 'blue', 'green', 'red'])
        bounds = [0, 1, 2, 3, 4, 5]  
        norm = mcolors.BoundaryNorm(bounds, cmap.N)
        ubicaciones = self.load_file('Mapa.json')

        for cliente, pos in ubicaciones.items():
            if cliente.islower():  
                mapa_colores[pos[1] - 1, pos[0] - 1] = 1 


        for destino, pos in ubicaciones.items():
            if destino.isupper(): 
                mapa_colores[pos[1] - 1, pos[0] - 1] = 2  


        taxisact = self.load_file(self.taxi_bd)
        xtaxi1 = None
        ytaxi1 = None
        xtaxi2 = None
        ytaxi2 = None

        for ta in taxisact:
            if ta['id'] == 1:
                xtaxi1 = ta['coordenada_origen']['x']
                ytaxi1 = ta['coordenada_origen']['y']
            if ta['id'] == 2:
                xtaxi2 = ta['coordenada_origen']['x']
                ytaxi2 = ta['coordenada_origen']['y']

        for taxi in taxis:
            if taxi['id'] == 1:
                taxi['coordenada_origen']['x'] = xtaxi1
                taxi['coordenada_origen']['y'] = ytaxi1
            if taxi['id'] == 2:
                taxi['coordenada_origen']['x'] = xtaxi2
                taxi['coordenada_origen']['y'] = ytaxi2


        
        for taxi in taxisact:
            taxi_pos = taxi['coordenada_origen']
            status = taxi['estado']

            if status == "verde":  
                mapa_colores[taxi_pos['y'] - 1, taxi_pos['x'] - 1] = 3
            else: 
                mapa_colores[taxi_pos['y'] - 1, taxi_pos['x'] - 1] = 4

    

        ax.imshow(mapa_colores, cmap=cmap, norm=norm, extent=[0, size, 0, size], origin='lower')



    
        for cliente, pos in ubicaciones.items():
            if cliente.islower():
                ax.text(pos[0] - 0.5, pos[1] - 0.5, cliente, color='black', fontsize=12, ha='left', va='center')           


        for destino, pos in ubicaciones.items():
            if destino.isupper():
                ax.text(pos[0] - 0.5, pos[1] - 0.5, destino, color='black', fontsize=12, ha='center', va='center')


        for taxi in taxisact:
            taxi_pos = taxi['coordenada_origen']
            if taxi['recogido'] == True:
                taxi_id = str(taxi['id'])
            else:
                taxi_id = taxi['id']
            ax.text(taxi_pos['x'] - 0.5, taxi_pos['y'] - 0.5, str(taxi_id), color='black', fontsize=12, ha='right', va='center')


        ax.set_xticks(np.arange(0, size))
        ax.set_yticks(np.arange(0, size))
        ax.set_xticklabels(np.arange(1, size + 1))
        ax.set_yticklabels(np.arange(1, size + 1))


        ax.grid(True, color='black', linestyle='-', linewidth=0.5)
        ax.set_xlim(0, size)
        ax.set_ylim(0, size)

        plt.gca().invert_yaxis() 

    #ok
    def iniciar_grafico(self, taxis, ubicaciones):
        fig, ax = plt.subplots()
        size = 20
        ani = FuncAnimation(fig, self.actualizar_mapa, fargs=(taxis, ubicaciones, ax, size), interval=1000, cache_frame_data=False)
        plt.show()

#------------------------------------NEW RELEASE---------------------------------------------
    #ok
    def get_traffic_status(self):
        """
        Realiza una solicitud GET al endpoint /get_traffic_status y muestra el estado del tráfico.
        """
        try:
            response = requests.get(self.ctcApi + '/get_traffic_status')
            response.raise_for_status()  # Lanza una excepción para códigos de estado HTTP 4xx/5xx
            data = response.json()
            status = data.get('status', 'Desconocido')
            city = data.get('city', 'Desconocida')
            logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error al obtener el estado del tráfico: {e}")
            status = 'Desconocido'
            city = 'Desconocida'
        return status, city

    def periodic_city_status(self):
        print("Iniciando test.py para monitorear el estado del tráfico cada 10 segundos...")
        logging.info("test.py iniciado para monitorear el estado del tráfico.")
        try:
            status, city = self.get_traffic_status()
            while True:
                try:
                    prevStatus = status
                    prevCity  = city
                    status, city = self.get_traffic_status()

                    if prevCity != city:
                        print(f"CIUDAD CAMBIADA DE {prevCity} A {city}")

                    if prevStatus == 'OK' and status == 'KO':
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}. VOLVER A LA BASE!")
                        self.return_taxis_to_base()

                    elif prevStatus == 'KO' and status == 'OK':
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Estado del tráfico: {status} en {city}. REANUDAR LA MARCHA!")
                        #LOGICA VUELTA A HACER PEDIDOS
                        self.resume_taxi_operations()

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


    def return_taxis_to_base(self):
        taxis = self.load_file(self.taxi_bd)
        for taxi in taxis:
            if taxi['disponible'] and taxi['estado'] == 'verde':
                command = f"RETURN_TO_BASE#{taxi['id']}"
                self.producer_taxicommands.send(TOPIC_ASIGNACION_TAXIS, value=command)
                print(f"Sent command to taxi {taxi['id']}: {command}")

    def resume_taxi_operations(self):
        taxis = self.load_file(self.taxi_bd)
        for taxi in taxis:
            if taxi['estado'] == 'rojo':
                command = f"RESUME_OPERATIONS#{taxi['id']}"
                self.producer_taxicommands.send(TOPIC_ASIGNACION_TAXIS, value=command)
                print(f"Sent command to taxi {taxi['id']}: {command}")
    
    def startFrontGraphics(self):
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # Show only errors
        print(f"Starting server at {socket.gethostbyname(socket.gethostname())}:{self.front_port}")
        app.run(host = socket.gethostbyname(socket.gethostname()), port = self.front_port)

#--------------------------------------------------------------------------------------------------------
    #ok
    def start(self):
        server.listen()
        print(f"[LISTENING] Servidor a la escucha en el puerto {self.port}")

        while True:

            conn, addr = server.accept()
            print(f"[NEW CONNECTION] {addr}")
            

            thread = threading.Thread(target=self.socket_taxi, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    if len(sys.argv) != 6:
        print('USAGE: EC_Central.py <CENTRAL_PORT> <KAFKA_IP_PORT> <taxis.json> <CTC_IP:PORT> <WEB PORT>')
        sys.exit(1)

    
    # Parámetros de ejemplo, deben ser ajustados según los argumentos de línea de comandos
    central = ECCentral(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((socket.gethostbyname(socket.gethostname()), central.port))

    taxis = central.load_file(central.taxi_bd)
    ubis = central.load_file('Mapa.json')


    kafka_thread_taxis = threading.Thread(target=central.listen_taxi_updates)
    kafka_thread_taxis.start()
    kafka_thread_customer = threading.Thread(target=central.listen_customer_services)
    kafka_thread_customer.start()
    thread_socket = threading.Thread(target=central.start)
    thread_socket.start()
    kafka_thread_end_taxi = threading.Thread(target=central.listen_taxi_end)
    kafka_thread_end_taxi.start()
    periodic_status_thread = threading.Thread(target=central.periodic_city_status)
    periodic_status_thread.start()
    #GRAFICOS ANTIGUOS   
    #central.iniciar_grafico(taxis, ubis)
    central.startFrontGraphics()