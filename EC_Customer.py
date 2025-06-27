import socket
import json
import time
import sys
import threading
from kafka import KafkaProducer, KafkaConsumer


TOPIC_SOLICITUDES_TAXIS = 'solicitudes-taxis' 
TOPIC_RESPUESTAS_TAXIS = 'respuestas-taxis' 
TOPIC_TAXI_END_CLIENT = 'taxi-end-client'  

class ECCustomer:
    def __init__(self, kafka_ip_port, customer_id, destinations_file):
        self.kafka_ip_port = kafka_ip_port
        self.customer_id = customer_id
        self.destinations = self.load_destinations(destinations_file)
        self.current_destination_index = 0
        self.last_offset = -1
        self.last_offset_taxi_end = -1

        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_ip_port,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.consumer = KafkaConsumer(
            bootstrap_servers=kafka_ip_port,
            group_id=f"grupo_{self.customer_id}",
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        self.consumer.subscribe(topics=[TOPIC_RESPUESTAS_TAXIS, TOPIC_TAXI_END_CLIENT])
    

    def handle_response(self):
        """Recibe la respuesta de la central para el cliente a través de Kafka."""
        for msg in self.consumer:
            if msg is None:
                continue
            if msg.topic == TOPIC_RESPUESTAS_TAXIS:
                mensaje = msg.value
                clientID, aux = mensaje.split(": ")
                if self.customer_id == clientID:
                    print(f"Processing msg: {mensaje} with offset {msg.offset}")
                    return mensaje
                
    
    def load_destinations(self, filename):
        """Carga la lista de destinos desde un archivo."""
        with open(filename, 'r') as file:
            data = json.load(file)
            return [request['Id'] for request in data['Requests']]


    def request_taxi(self, destination):
        """Envía una solicitud de taxi con origen y destino a través de Kafka."""
        message = f"{self.customer_id} solicita {destination}"
        self.producer.send(TOPIC_SOLICITUDES_TAXIS, value=message)

    def wait_arrival(self):
        print("LISTENING")
        for msg in self.consumer:
            if msg is None:
                continue
            if msg.topic == TOPIC_TAXI_END_CLIENT:
                mensaje = msg.value
                print(f'THE MSG IS {mensaje}')
                mensajes = mensaje.split('#')
                if len(mensajes) >= 4:
                    client_id = mensajes[3]
                    if self.customer_id == client_id:
                        return "You have arrived at your destination"

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("PARÁMETROS INCORRECTOS USAGE: EC_Customer <KAFKA_IP_PORT> <CUSTOMER_ID> <REQUESTS FILE>")
        sys.exit(1)
    
    kafka_ip_port = sys.argv[1]
    customer_id = sys.argv[2]
    destinations_file = sys.argv[3]

    customer = ECCustomer(kafka_ip_port, customer_id, destinations_file)
    
    for destination in customer.destinations:
        print()
        print(f"Sending request to go to destination: {destination}")
        customer.request_taxi(destination)
        print()
        response = customer.handle_response()
        responseID, allOK = response.split(': ')
        print(f"RECIEVED Response for service with destination {destination} : {allOK}")
        
        if allOK == 'OK':
           taxi_response = customer.wait_arrival()
           print()
           print(taxi_response)
        else:
            print('no se ha recibido confirmación')
        time.sleep(4)
