import json
from kafka import KafkaProducer
import time

class ECCustomer:
    def __init__(self, kafka_broker="localhost:9092"):
        # Configuración del productor de Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_broker,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = "taxi_requests"  # Tópico donde se publicarán las solicitudes

    def cargar_peticiones(self, archivo):
        # Cargar las peticiones de localización desde el archivo JSON
        with open(archivo) as f:
            data = json.load(f)
            return [request["Id"] for request in data["Requests"]]

    def enviar_peticiones(self, localizaciones):
        # Enviar cada localización como una petición al servidor central
        for destino in localizaciones:
            print(f"Enviando solicitud de taxi a {destino}")
            self.producer.send(self.topic, {"destino": destino})
            time.sleep(1)  # Pausa para simular envío secuencial
        self.producer.flush()  # Asegurarse de que todos los mensajes se envían

if __name__ == "__main__":
    customer = ECCustomer()

    # Cargar destinos desde el archivo de peticiones
    destinos = customer.cargar_peticiones("EC_Requests.json")

    # Enviar cada destino como una petición al servidor central
    customer.enviar_peticiones(destinos)
