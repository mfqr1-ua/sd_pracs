import socket
import sys
import threading
import re
import time
import json
from kafka import KafkaConsumer, KafkaProducer
import urllib3
import os
import requests
from PyInquirer import prompt
import ssl
import certifi
from cryptography.fernet import Fernet
from dotenv import load_dotenv
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


TOPIC_TAXI_UPDATES = 'taxi_updates' 
TOPIC_ASIGNACION_TAXIS = 'asignacion-taxis' 
TOPIC_TAXI_END_CLIENT = 'taxi-end-client' 
TOPIC_TAXI_END_CENTRAL = 'taxi-end-central' 
FORMAT = 'utf-8'
HEADER = 64

# Cargar variables de entorno desde .env
load_dotenv()

def create_ssl_context(cert_path):
    """Create SSL context with certificate validation"""
    context = ssl.create_default_context(cafile=cert_path)
    return context

def register_taxi(taxi_id, registry_url, cert_path):
    try:
        context = create_ssl_context(cert_path)
        response = requests.put(
            f"{registry_url}/register_taxi",
            json={"id": int(taxi_id)},
            verify=cert_path,  # Use certificate for verification
            headers={'Content-Type': 'application/json'}
        )
        print(response.json())
        return response.status_code == 201
    except Exception as e:
        print(f"Error registering taxi: {e}")
        return False

def deregister_taxi(taxi_id, registry_url, cert_path):
    try:
        context = create_ssl_context(cert_path)
        response = requests.delete(
            f"{registry_url}/deregister_taxi/{taxi_id}",
            verify=cert_path,
            headers={'Content-Type': 'application/json'}
        )
        print(response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"Error deregistering taxi: {e}")
        return False

def show_registry_menu(taxi_id, registry_url, cert_path):
    questions = [
        {
            'type': 'list',
            'name': 'action',
            'message': 'What would you like to do?',
            'choices': [
                'Register Taxi',
                'Deregister Taxi', 
                'Continue without changes'
            ]
        }
    ]
    
    action = prompt(questions)['action']
    
    if action == 'Register Taxi':
        if register_taxi(taxi_id, registry_url, cert_path):
            return True
        sys.exit(1)
    elif action == 'Deregister Taxi':
        if deregister_taxi(taxi_id, registry_url, cert_path):
            sys.exit(0)
        sys.exit(1)
    return True


class DigitalEngine:
    def __init__(self, ec_central_ip, ec_central_port, kafka_ip_port, ec_de_port, taxi_id, registry_ip, registry_port, cert_path):
        # Add certificate path
        self.cert_path = cert_path
        self.registry_url = f"https://{registry_ip}:{registry_port}"
        self.ec_central_addr = (ec_central_ip, ec_central_port)
        self.kafka_ip_port = kafka_ip_port
        self.de_addr = (socket.gethostbyname(socket.gethostname()), int(ec_de_port))
        self.taxi_id = taxi_id
        self.status = "OK"
        self.position = [1, 1]
        self.client_position = [1, 1]
        self.goal_position = [1, 1]
        self.available = True
        self.inTaxi = False
        self.ordered = False
        self.arrived = False
        self.client_id = ''
        self.producer = KafkaProducer(bootstrap_servers=kafka_ip_port, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
        self.sensor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.producer_end = KafkaProducer(bootstrap_servers=kafka_ip_port, value_serializer=lambda v: json.dumps(v).encode('utf-8'))       
        self.consumer = KafkaConsumer(
            TOPIC_ASIGNACION_TAXIS,
            bootstrap_servers=kafka_ip_port,
            group_id=f"taxi_{self.taxi_id}",
            auto_offset_reset='latest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        self.returning_to_base = False  # Indica si el taxi está regresando a la base


    def send(self, msg, client):
        message = msg.encode(FORMAT)
        msg_length = len(message)
        send_length = str(msg_length).encode(FORMAT)
        send_length += b' ' * (HEADER - len(send_length))
        client.send(send_length)
        client.send(message)

    def send_to_kafka(self, topic, message):
        try:
            self.producer.send(topic, value=message)
            self.producer.flush()
        except Exception as e:
            print(f"Error al enviar mensaje a Kafka: {e}")

    def update_client_coordinates(self, x, y):
        if x < self.client_position[0]:
            x+= 1
        elif x > self.client_position[0]:
            x -= 1
        elif y < self.client_position[1]:
            y += 1
        elif y > self.client_position[1]:
            y -= 1
        print(f"{x, y}")
        self.position = [x, y]
        return x, y

    def updateCoordinates(self):     
        if self.position[0] < self.goal_position[0]:
            self.position[0] += 1
        elif self.position[0] > self.goal_position[0]:
            self.position[0] -= 1
        elif self.position[1] < self.goal_position[1]:
            self.position[1] += 1
        elif self.position[1] > self.goal_position[1]:
            self.position[1] -= 1
        print(f"Actualizando posición: {self.position}")

    def connect_to_central(self):
        print(f"Establecida conexión en [{client_socket.getsockname()}]")
        

        print("Envio al servidor: ", self.taxi_id)
        self.send(str(self.taxi_id), client_socket)
        
        while True:
            response = client_socket.recv(2048).decode('utf-8')
            pattern = r"'x' ?: ?(\d+)[.,] ?'y' ?: ?(\d+)"
            aux = re.search(pattern, response)

            if aux:
                self.position = [int(aux.group(1)), int(aux.group(2))]
                print(f"Mi coordenada es {self.position}")
            if response == "ERROR taxi doesnt exist":
                print("ERROR: id not on our database, try again ")
                sys.exit(1)
            else:
                print(f"Taxi {self.taxi_id} autenticado correctamente.")
                break
        client_socket.close()

    def listen_asignacion_kafka(self):
        for msg in self.consumer:
            if msg is None:
                continue
            command = msg.value
            print(f"Command received from Central: {command}")
            auxArr = command.split("#")

            if len(auxArr) >= 2:
                command_type = auxArr[0]
                Tid = int(auxArr[1])
                if Tid == self.taxi_id:
                    if command_type == "RETURN_TO_BASE":
                        self.return_to_base()
                    elif command_type == "RESUME_OPERATIONS":
                        self.resume_operations()
                    elif command_type == "Taxi has to go to":
                        Gx = int(auxArr[2])
                        Gy = int(auxArr[3])
                        cliX = int(auxArr[4])
                        cliY = int(auxArr[5])
                        self.client_id = auxArr[6]
                        self.goal_position = [Gx, Gy]
                        self.client_position = [cliX, cliY]
                        self.ordered = True
                        self.arrived = False
                        print(f"RECOGER AL CLIENTE EN {self.client_position} PARA IR A {self.goal_position}")
                    else:
                        print(f"Unknown command: {command_type}")
            else:
                print(f"Received unrecognized message format: {command}")

    def handle_sensors(self):
        ok = False
        while True:
            try:
                msg = conn.recv(1024).decode('utf-8')
                if msg:
                    if msg == "KO":
                        self.status = "KO"
                        self.send_to_kafka(TOPIC_TAXI_UPDATES,f"{self.taxi_id}#{msg}#{self.position[0]}#{self.position[1]}")
                        continue
                    if self.position == self.client_position and self.ordered:
                        self.inTaxi = True
                    
                    if self.inTaxi == False:
                        self.update_client_coordinates(self.position[0], self.position[1])
                        self.send_to_kafka(TOPIC_TAXI_UPDATES, f"{self.taxi_id}#{msg}#{self.position[0]}#{self.position[1]}")
                    else:
                        print(f"Ordenado == {self.ordered} y arrived =={self.arrived}")
                        if self.ordered and not self.arrived and self.position == self.goal_position:
                            self.send_to_kafka(TOPIC_TAXI_UPDATES, f"{self.taxi_id}#{msg}#{self.position[0]}#{self.position[1]}#destino")
                            print("Service completed")
                            self.arrived = True
                            aux = f"taxi#{self.taxi_id}#cliente#{self.client_id}#ha llegado a su destino"
                            self.producer_end.send(TOPIC_TAXI_END_CENTRAL, value=aux)
                            self.producer_end.send(TOPIC_TAXI_END_CLIENT, value=aux)

                            if ok == False:
                                ok = True
                                self.position[0] -= 1
                            self.inTaxi = False
                            self.ordered = False
                        
                        else:
                            self.updateCoordinates()
                            self.send_to_kafka(TOPIC_TAXI_UPDATES,f"{self.taxi_id}#{msg}#{self.position[0]}#{self.position[1]}#recogido")
            except socket.error as error:
                print(f"Error al recibir mensaje del Sensor: {error}") 
                break

    def resume_operations(self):
        print("Recibido comando RESUME_OPERATIONS. Reanudando operaciones y cambiando estado a 'OK'.")
        self.status = 'OK'           # Cambiar el estado a 'OK'
        self.available = True          # Marcar como disponible
        self.returning_to_base = False
        # Notificar a la central del cambio de estado
        self.send_to_kafka(TOPIC_TAXI_UPDATES, f"{self.taxi_id}#OK#{self.position[0]}#{self.position[1]}")
        print(f"Taxi {self.taxi_id} disponible para nuevos servicios.")

    def return_to_base(self):
        print("Recibido comando RETURN_TO_BASE. Regresando a la base.")
        self.goal_position = [1, 1]       # Establecer la posición objetivo en (1,1)
        self.available = False            # Marcar como no disponible
        self.ordered = False              # No tiene orden asignada
        self.client_id = ''               # Sin cliente asignado
        self.returning_to_base = True     # Indicar que está regresando a la base
        # Iniciar un hilo para supervisar la llegada a la base
        monitor_thread = threading.Thread(target=self.monitor_return_to_base)
        monitor_thread.start()

    def monitor_return_to_base(self):
        while self.returning_to_base:
            if self.position == [1, 1]:
                print("Taxi ha llegado a la base.")
                self.status = 'KO'             # Cambiar el estado a 'KO'
                self.returning_to_base = False # Dejar de supervisar
                self.send_to_kafka(TOPIC_TAXI_UPDATES, f"{self.taxi_id}#KO#{self.position[0]}#{self.position[1]}")
                print("Estado del taxi cambiado a 'KO'.")
            else:
                self.updateCoordinates()  # Mover el taxi hacia la base
                self.send_to_kafka(TOPIC_TAXI_UPDATES, f"{self.taxi_id}#OK#{self.position[0]}#{self.position[1]}")
            time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 9:
        print("Usage: python digital_engine.py <EC_Central_IP> <EC_Central_Port> <Kafka_IP_Port> <EC_DE_Port> <Taxi_ID> <Registry_IP> <Registry_Port> <Cert_Path>")
        sys.exit(1)
    
    registry_url = f"https://{sys.argv[6]}:{sys.argv[7]}"
    cert_path = sys.argv[8]
    
    # Verify certificate exists
    if not os.path.exists(cert_path):
        print(f"Certificate not found at {cert_path}")
        sys.exit(1)
    
    # Show initial registry menu with cert path
    if not show_registry_menu(int(sys.argv[5]), registry_url, cert_path):
        sys.exit(1)
        
    # Create Digital Engine instance with cert path
    DE = DigitalEngine(
        sys.argv[1], 
        int(sys.argv[2]), 
        sys.argv[3], 
        sys.argv[4], 
        int(sys.argv[5]),
        sys.argv[6],
        sys.argv[7],
        cert_path
    )
    
    DE.recogido = False
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(DE.ec_central_addr)
    DE.connect_to_central()

    try:
        DE.sensor_socket.bind((DE.de_addr[0], DE.de_addr[1]))
        DE.sensor_socket.listen(1)
        print("Data engine up and listening at ", DE.de_addr[0], " ", DE.de_addr[1])
        conn, addr = DE.sensor_socket.accept()
        print("NUEVA CONEXION: ", addr)
    except socket.error as e:
        print(f"Error connecting to sensors: {e}")
        sys.exit(1)

    sensor_thread = threading.Thread(target=DE.handle_sensors)
    sensor_thread.start()

    kafka_thread = threading.Thread(target=DE.listen_asignacion_kafka)
    kafka_thread.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("Closing Conn...")
    finally:
        DE.sensor_socket.close()
        DE.producer.flush()
        DE.consumer.close()