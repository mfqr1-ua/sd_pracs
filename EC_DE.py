import socket
import sys
import threading
import time
import re
from confluent_kafka import Producer, Consumer, KafkaException
HEADER = 64
PORT = 5050 #puerto al que se conectará el cliente, debe coincidir con el del servidor 
FORMAT = 'utf-8'
FIN = "FIN"
coordenadax = 1
coordenaday = 1
destinox = 1
destinoy = 1
clientex =1
clientey = 1
recogido = False
ordenado = False
llegado = False
cliente = ''


def send(msg, client):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    client.send(send_length)
    client.send(message)

# Función para enviar mensaje a Kafka usando Confluent Producer
def send_to_kafka(producer, topic, message):
    try:
        producer.produce(topic, message.encode('utf-8'))
        producer.flush()
        print(f"Mensaje enviado a Kafka: {message}")
    except KafkaException as e:
        print(f"Error al enviar mensaje a Kafka: {e}")

#funcion para actualizar coordenada del cliente
def actualizar_coordenadacliente(cordix, cordiy):
    if cordix < clientex:
         cordix+= 1
    elif cordix > clientex:
        cordix -= 1
    elif cordiy < clientey:
        cordiy += 1
    elif cordiy > clientey:
        cordiy -= 1
    print(f"{cordix, cordiy}")
    return cordix, cordiy

def actualizar_coordenadadestino():
    global coordenadax, clientex, clientey, destinox, destinoy, coordenaday
    if coordenadax < destinox:
         coordenadax += 1
    elif coordenadax > destinox:
        coordenadax -= 1
    elif coordenaday < destinoy:
        coordenaday += 1
    elif coordenaday > destinoy:
        coordenaday -= 1
    print(f"{coordenadax, coordenaday}")


# Función para recibir mensajes de EC_S (sensor)
def listen_to_sensor(sensor_socket, producer, producer_servicio_completado, kafka_topic_status, taxi_id):
    global coordenaday, recogido, ordenado, llegado
    global coordenadax, clientex, clientey
    avanzado = False
    while True:
        try:
            mensaje = sensor_socket.recv(1024).decode('utf-8')
            if mensaje:
                #print(f"Mensaje recibido de Sensor: {message}")
                # Enviar el mensaje recibido del sensor a Kafka
                #send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#RUN#Taxi en movimiento")
                if mensaje == "KO":
                    send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#{mensaje}#{coordenadax}#{coordenaday}")
                    continue
                if coordenadax == clientex and coordenaday == clientey and ordenado:
                    recogido = True
                if recogido == False:
                    print(recogido)
                    coordenadax, coordenaday = actualizar_coordenadacliente(coordenadax, coordenaday)
                    send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#{mensaje}#{coordenadax}#{coordenaday}")
                else:
                    print(recogido)
                    print(f"Ordenado == {ordenado} y llegado =={llegado}")
                    if coordenadax == destinox and coordenaday == destinoy and ordenado== True and llegado == False:
                        send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#{mensaje}#{coordenadax}#{coordenaday}#destino")
                        print("Servicio completado")
                        llegado = True
                        m = f"taxi#{taxi_id}#cliente#{cliente}#ha llegado a su destino"
                        send_to_kafka(producer_servicio_completado, 'taxi_end2', m)
                        send_to_kafka(producer_servicio_completado, 'taxi_end', m)
                        if avanzado == False:
                            avanzado = True
                            coordenadax -= 1
                        recogido = False
                        ordenado = False  
                    else:
                        actualizar_coordenadadestino()
                        send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#{mensaje}#{coordenadax}#{coordenaday}#recogido")
        except socket.error as e:
            print(f"Error al recibir mensaje del Sensor: {e}")
            break


# Función para recibir instrucciones de EC_Central a través de Kafka
def listen_to_kafka_commands(consumer, taxi_id):
    global clientey, clientex, destinox, destinoy, ordenado, cliente, llegado
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Error en Kafka: {msg.error()}")
            continue

        command = msg.value().decode('utf-8')
        print(f"Comando recibido de EC_Central: {command}")
        # Procesar el comando recibido
        partes = command.split("#")
        if len(partes) == 7:
            id = int(partes[1])
            cx = int(partes[2])
            cy = int(partes[3])
            clix = int(partes[4])
            cliy = int(partes[5])
            cliente = partes[6]
            taxi_idi = int(taxi_id)
            if taxi_idi == id:
                destinox = cx
                destinoy = cy
                clientex = clix
                clientey = cliy
                ordenado = True
                llegado = False
                print(f"TENGO QUE RECOGER AL CLIENTE EN {clientex}, {clientey} Y LUEGO IR A {destinox}, {destinoy}")



def socket_check_id(client, taxi_id):
    global coordenadax, coordenaday
    print(f"Establecida conexión en [{client.getsockname()}]")

    print("Envio al servidor: ", taxi_id)
    send(taxi_id, client)
    
    while True:  #mientras el id no sea correcto
        replay = client.recv(2048).decode(FORMAT)
        patron = r"'x' ?: ?(\d+)[.,] ?'y' ?: ?(\d+)"
        resultado = re.search(patron, replay)

        if resultado:
            # Extraer los valores
            x = int(resultado.group(1))
            y = int(resultado.group(2))

            # Almacenar como tupla
            coordenadax = x
            coordenaday = y
            print(f"Mi coordenada es {coordenadax}, {coordenaday}")
        if replay == "El taxi no existe":
            taxi_id = input("Introduce un ID valido: ")
            send(taxi_id, client)  # Reenviar el mensaje
        else:
            break  # Rompe el bucle si el ID es válido

    client.close()
    return taxi_id

# Función principal de conexión con EC_Central y autenticación por socket
def main():
    if len(sys.argv) != 8:
        print("Uso: python EC_DE.py <IP_EC_Central> <PUERTO_EC_Central> <IP_KAFKA> <PUERTO_KAFKA> <IP_EC_S> <PUERTO_EC_S> <ID_TAXI>")
        sys.exit(1)

    ip_central = sys.argv[1]
    puerto_central = int(sys.argv[2])
    ip_kafka = sys.argv[3]
    puerto_kafka = int(sys.argv[4])
    ip_sensor = sys.argv[5]
    puerto_sensor = int(sys.argv[6])
    taxi_id = sys.argv[7]
    #comunicación sockets cofirmación ID 

    global recogido
    recogido =False

    ADDR = (ip_central, puerto_central)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(ADDR)
    taxi_id = socket_check_id(client, taxi_id)
  
    # Configuración de Kafka (usando Confluent Kafka)
    kafka_broker = f'{ip_kafka}:{puerto_kafka}'  # IP y puerto de Kafka
    kafka_topic_status = 'taxi_status'  # Tópico para enviar el estado del taxi
    kafka_topic_commands = 'taxi_commands'  # Tópico para recibir comandos de EC_Central

    # Inicializar el productor de Kafka
    producer_conf = {'bootstrap.servers': kafka_broker}
    producer = Producer(producer_conf)
    producer_servicio_consumido = Producer(producer_conf)
    
    # Inicializar el consumidor de Kafka
    consumer_conf = {
        'bootstrap.servers': kafka_broker,
        'group.id': f"taxi_{taxi_id}",
        'auto.offset.reset': 'latest'
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe([kafka_topic_commands])
 


    # Conexión con EC_S (Sensor)
    try:
        sensor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sensor_socket.bind((ip_sensor, puerto_sensor))
        sensor_socket.listen(1)
        print(f"Esperando conexión del sensor en {ip_sensor}:{puerto_sensor}...")
        connection, address = sensor_socket.accept()
        print(f"Sensor conectado desde {address}")
    except socket.error as e:
        print(f"Error al conectarse al Sensor: {e}")
        sys.exit(1)

    # Crear hilos para manejar los mensajes del sensor y de Kafka
    sensor_thread = threading.Thread(target=listen_to_sensor, args=(connection, producer, producer_servicio_consumido, kafka_topic_status, taxi_id))
    sensor_thread.start()

    kafka_thread = threading.Thread(target=listen_to_kafka_commands, args=(consumer, taxi_id))
    kafka_thread.start()


    # Mantener la ejecución para enviar mensajes de estado periódicamente
    try:
        while True:
            # Enviar mensaje de estado periódico a Kafka
            #send_to_kafka(producer, kafka_topic_status, f"{taxi_id}#RUN#Taxi en movimiento")
            time.sleep(5)  # Enviar estado cada 5 segundos
    except KeyboardInterrupt:
        print("Cerrando conexiones...")
    finally:
        sensor_socket.close()
        producer.flush()
        consumer.close()

if __name__ == "__main__":
    main()
