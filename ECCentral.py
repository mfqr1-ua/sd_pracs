from MapaCiudad import MapaCiudad
from kafka import KafkaConsumer
import json

# Configuración de Kafka
TOPIC_REQUESTS = "taxi_requests"
BOOTSTRAP_SERVERS = "localhost:9092"
GROUP_ID = "taxi_assignment_group"

# Función principal del servidor central
def main():
    # Inicializar el mapa de la ciudad
    ciudad = MapaCiudad()
    ciudad.cargar_localizaciones("EC_locations.json") 
    ciudad.cargar_taxis("taxis.json") 
    ciudad.mostrar_mapa()

    # Configurar el consumidor de Kafka para escuchar solicitudes
    consumer = KafkaConsumer(
        TOPIC_REQUESTS,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print("Esperando solicitudes de taxis...")

    # Procesar solicitudes entrantes
    for message in consumer:
        solicitud = message.value
        cliente_id = solicitud['Id']
        destino = solicitud['Destino']

        # Mostrar en consola la solicitud recibida
        print(f"Solicitud de taxi recibida de Cliente {cliente_id} hacia {destino}")

        # Lógica para asignar el taxi (puede ser avanzada)
        # Para simplificar, solo muestra la solicitud en el mapa (puedes expandir esto)
        
        ciudad.mostrar_mapa()

if __name__ == "__main__":
    main()
