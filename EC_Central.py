import socket
import threading
import sys
import json
from confluent_kafka import Producer, Consumer, KafkaError
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation

HEADER = 64  # longitud del mensaje
PORT = None  # puerto en el que el servidor escucha
IP_kafka = None
PORT_kafka = None
consumer = None
producer = None
def get_local_ip():
    # Crea un socket temporal y se conecta a una dirección externa
    # Esto ayuda a determinar cuál es la IP de salida del sistema
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No envía datos reales, solo se conecta a una IP pública de ejemplo para obtener la IP local
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = "127.0.0.1"  # Fallback a localhost en caso de error
    finally:
        s.close()
    return ip_address

# Usar esta IP en tu configuración de socket
SERVER = get_local_ip()
print(f"Servidor configurado para la IP local: {SERVER}")
FORMAT = 'utf-8'
MAX_CONEXIONES = 2  # limita el número de conexiones simultáneas
offset_taxi_end = -1
# Cargar taxis desde un archivo JSON
def cargar_fichero(taxi_file):
    try:
        with open(taxi_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Archivo {taxi_file} no encontrado.")
        return []
    except json.JSONDecodeError:
        print(f"Error al decodificar el archivo {taxi_file}.")
        return []

# Guardar cambios en el archivo JSON de taxis
def guardar_taxis(taxi_file, taxis):
    try:
        with open(taxi_file, 'w') as f:
            json.dump(taxis, f, indent=4)
    except IOError as e:
        print(f"Error al guardar el archivo {taxi_file}: {e}")

# Comprobar si un taxi con el id existe
def comprobar_id(taxis, id_taxi):
    for taxi in taxis:
        if taxi["id"] == id_taxi:
            return True
    return False

# Actualizar el estado del taxi en función de los mensajes de Kafka
def actualizar_estado_taxi(id_taxi, estado, taxis):
    for taxi in taxis:
        if taxi["id"] == id_taxi:
            taxi["estado"] = "verde" if estado == "OK" else "rojo"
            return True
    return False
# Escuchar mensajes desde Kafka (los estados OK o KO) cambioooo
def escuchar_kafka_estado_taxis(consumer_taxi):
    while True:
        msg = consumer_taxi.poll(timeout=0.5)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Kafka Error: {msg.error()}")
                break

        # Proceso del mensaje de estado recibido desde EC_DE
        estado_mensaje = msg.value().decode(FORMAT)
        # Esperamos un formato tipo "taxi_id#estado"
        partes = estado_mensaje.split("#")
        taxis = cargar_fichero('taxis.json')
        mapa = cargar_fichero('Mapa.json')
        if len(partes) == 4: #si todavía no lo ha recogido 
            taxi_id = int(partes[0])
            estado = partes[1]
            coor_taxix = int(partes[2])
            coor_taxiy = int(partes[3])
            
            for taxi in taxis:
                if taxi['id'] == taxi_id:
                    taxi['coordenada_origen']['x'] = coor_taxix
                    taxi['coordenada_origen']['y'] = coor_taxiy
                    guardar_taxis('taxis.json', taxis)

            if actualizar_estado_taxi(taxi_id, estado, taxis):
                guardar_taxis('taxis.json', taxis)
                #print(f"El taxi {taxi_id} está en estado {estado}")          
            else:
                print(f"Taxi {taxi_id} no encontrado en el archivo.")
        else: #si lo ha recogido 
            taxi_id = int(partes[0])
            estado = partes[1]
            coor_taxix = int(partes[2])
            coor_taxiy = int(partes[3])
            destorec = partes[4] #destino o recogido
     
            for taxi in taxis:
                if taxi['id'] == taxi_id:
                    taxi['coordenada_origen']['x'] = coor_taxix
                    taxi['coordenada_origen']['y'] = coor_taxiy
                    
                    if destorec == "recogido":
                        taxi['recogido'] = True
                        taxi['cliente']['x'] = coor_taxix
                        taxi['cliente']['y'] = coor_taxiy
                        idcliente = taxi['cliente']['id_cliente']
                        mapa[idcliente] = [coor_taxix, coor_taxiy]
                    else:
                        taxi['recogido'] = False
                    guardar_taxis('taxis.json', taxis)
                    guardar_taxis('Mapa.json', mapa)


# Nueva función: Enviar coordenadas de destino del taxi a EC_DE vía Kafka
def enviar_coordenada_destino(producer, taxi_id, kafka_topic):
    taxis = cargar_fichero('taxis.json')
    
    for taxi in taxis:
        if taxi['id'] == taxi_id:
            coordenada_destino = taxi['coordenada_destino']
            cliente = taxi['cliente']
            mensaje = f"Taxi tiene que ir a#{taxi_id}#{coordenada_destino['x']}#{coordenada_destino['y']}#{cliente['x']}#{cliente['y']}#{cliente['id_cliente']}"
            print(f"Enviando a EC_DE: {mensaje}")
            
            # Enviar mensaje a EC_DE a través de Kafka
            producer.produce(kafka_topic, value=mensaje.encode('utf-8'))
            producer.flush()
            return True

    print(f"Taxi {taxi_id} no encontrado en el archivo taxis.json.")
    return False

# Función para manejar las conexiones del taxi
def socket_taxi(conn, addr): #hilo que maneja las peticiones de un cliente específico
    print(f"[NUEVA CONEXION] {addr} connected.")
 
    while True:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if not msg_length:
            break
        msg_length = int(msg_length)
        msg = conn.recv(msg_length).decode(FORMAT) #con la longitud del mensaje que se encuentra en HEADER obtenemos el mensaje
        taxis = cargar_fichero('taxis.json')
        id_taxi = int(msg)
        existe = comprobar_id(taxis, id_taxi)
        for taxi in taxis:
            if taxi["id"] == id_taxi:
                coordenada = taxi["coordenada_origen"]
                taxi['verificado'] = True 
                
        print(f"El ID de mi taxi es: {msg} y mi coordenada es {coordenada}")
        
        guardar_taxis('taxis.json', taxis)

        respuesta = ""
        if existe:
            respuesta += f"Tu coordenada es {coordenada}"
        else:
            respuesta += "El taxi no existe"
        conn.send(respuesta.encode(FORMAT))
      
        
    conn.close()


def obtener_coordenadas(destino, cliente):
    coordenadas = cargar_fichero('Mapa.json')
    if destino in coordenadas:
        x_destino, y_destino = coordenadas[destino]
    if cliente in coordenadas:
        x_cliente, y_cliente = coordenadas[cliente]
        print(f"la coordenada del cliente es{x_cliente},{y_cliente}" )
    return x_cliente, y_cliente, x_destino, y_destino

def escuchar_kafka_servicios_customer(consumer_customer, producer_customer, producer_taxicommands):
    while True:
        # Escuchar nuevos mensajes
        msg = consumer_customer.poll(timeout=0.5)  # Polling de 1 segundo para obtener mensajes
        
        if msg is None:  # Si no hay mensajes, continuar
            continue
        if msg.error():  # Manejo de errores
            print(f"Error: {msg.error()}")
            continue
        
        # Obtener el contenido del mensaje
        mensaje_cliente = msg.value().decode('utf-8')
        print(f"Mensaje recibido del cliente: {mensaje_cliente}")
        print('                                                ')
        # Procesar el mensaje para determinar el servicio solicitado
        servicio_solicitado = mensaje_cliente.split(" ")  # Suponiendo el formato "Q solicita F"
        
        if len(servicio_solicitado) != 3:
            print("Mensaje en un formato incorrecto.")
            continue
        
        cliente, accion, destino = servicio_solicitado
        
        # Verificar disponibilidad de taxis (aquí deberías implementar la lógica real)
        taxi_disponible = verificar_disponibilidad_taxis(destino, cliente, producer_taxicommands)  # Función ficticia para verificar disponibilidad

        # Preparar la respuesta
        if taxi_disponible:
            respuesta = f"{cliente}: OK"
        else:
            respuesta = f"{cliente}: KO"

        # Enviar la respuesta al customer
        producer_customer.produce('central_replay', value=respuesta.encode('utf-8'))
        producer_customer.flush()  # Asegurarse de que el mensaje se envía inmediatamente
        print(f"Respuesta enviada: {respuesta}")

def escuchar_taxi_end(consumer_taxi_end, producer_taxi_end):
    global offset_taxi_end
    while True:
        msg = consumer_taxi_end.poll(timeout=0.5)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(msg.error())
                return None #error demasiado critico que requiere parar la ejecución 
    
        if msg.offset() > offset_taxi_end:
            mensaje = msg.value().decode('utf-8')
            print(f"el mensaje es {mensaje}")
            offset_taxi_end = msg.offset()
            
            #FORMATO mensaje TAXI --> f"taxi#taxi_id#cliente#cliente#ha llegado a su destino"
        
            mensajes = mensaje.split('#') 
            taxi_id = int(mensajes[1])
            cliente_id = mensajes[3]
            taxis = cargar_fichero('taxis.json')
            mapa = cargar_fichero('Mapa.json')
            
            for taxi in taxis:
            #HE MODIFICADO ESTO BORRAR SI NO VA y si va el mensaje 
                if taxi['id'] == taxi_id:
                    taxi['disponible'] = True
                    taxi['recogido'] = False
                    taxi['cliente']['id_cliente'] = ""
                    taxi['cliente']['x'] = None
                    taxi['cliente']['y'] = None
                    taxi['coordenada_destino']['x'] = None
                    taxi['coordenada_destino']['y'] = None
                    taxi['coordenada_destino']['id'] = ""
                    print(f"El taxi {taxi_id} ha llegado a su destino")
                    #cambio en el mapa.json el origen del cliente 
                    corx =  taxi['coordenada_origen']['x']
                    cory = taxi['coordenada_origen']['y']
                    mapa[cliente_id] = [corx, cory]

                    print(f"HE PUESTO RECOGIDO A {taxi['recogido']}")
                    guardar_taxis('taxis.json', taxis)
                    guardar_taxis('Mapa.json', mapa)
        else:
            continue




def verificar_disponibilidad_taxis(destino, cliente, producer_taxicommands):
    # Suponiendo que el archivo JSON se llama 'taxis.json'
    with open('taxis.json', 'r') as file:
        taxis = json.load(file)

    # Verifica si hay algún taxi disponible
    for taxi in taxis:
        if taxi['disponible'] and taxi['verificado']:  # Verifica si el campo 'disponible' es True
            print(f"Taxi disponible: ID {taxi['id']}, Estado: {taxi['estado']}, Coordenada origen: {taxi['coordenada_origen']}")
            taxi['disponible'] = False
            taxi['coordenada_destino']['id'] = destino
            x_cliente, y_cliente, x_destino, y_destino = obtener_coordenadas(destino, cliente)
            taxi['coordenada_destino']['x'] = x_destino
            taxi['coordenada_destino']['y'] = y_destino
            taxi['cliente']['x'] = x_cliente
            print(f"la coor x es {taxi['coordenada_destino']['x']}")
            taxi['cliente']['y'] = y_cliente
            taxi['cliente']['id_cliente'] = cliente
            print(f"el cliente está en {x_cliente},{y_cliente} y quiere ir a {x_destino},{y_destino}")
            guardar_taxis('taxis.json', taxis)
            
            enviar_coordenada_destino(producer_taxicommands, taxi['id'], 'taxi_commands')

            return True  # Hay al menos un taxi disponible

    # Si llegamos aquí, no hay taxis disponibles
    print("No hay taxis disponibles.")
    return False

# Función para generar el mapa gráfico con matplotlib
def actualizar_mapa(frame, taxis, ubicaciones, ax, size):
    ax.clear()  # Limpiar el gráfico actual para redibujar

    # Crear una matriz para los colores de fondo de cada celda (números en lugar de nombres de colores)
    mapa_colores = np.zeros((size, size))

    # Definir un mapa de colores personalizado
    cmap = mcolors.ListedColormap(['white', 'yellow', 'blue', 'green', 'red'])
    bounds = [0, 1, 2, 3, 4, 5]  # Limites para cada color
    norm = mcolors.BoundaryNorm(bounds, cmap.N)
    ubicaciones = cargar_fichero('Mapa.json')
    # Colocar los clientes en el mapa (letras minúsculas, fondo amarillo -> valor 1)
    for cliente, pos in ubicaciones.items():
        if cliente.islower():  # Clientes
            mapa_colores[pos[1] - 1, pos[0] - 1] = 1 # Fondo amarillo para clientes

    # Colocar los destinos en el mapa (letras mayúsculas, fondo azul -> valor 2)
    for destino, pos in ubicaciones.items():
        if destino.isupper():  # Destinos
            mapa_colores[pos[1] - 1, pos[0] - 1] = 2  # Fondo azul para destinos

    # Simulación: actualizando posiciones de taxis para la animación
    # Puedes reemplazar esta lógica para hacer que se lea desde un archivo o una API
    taxisact = cargar_fichero('taxis.json')
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

    # Colocar los taxis en el mapa (estado verde -> valor 3, rojo -> valor 4)
    
    for taxi in taxisact:
        taxi_pos = taxi['coordenada_origen']
        estado = taxi['estado']
       #############################################
        if estado == "verde":  # Taxis disponibles (verde -> valor 3)
            mapa_colores[taxi_pos['y'] - 1, taxi_pos['x'] - 1] = 3
        else:  # Taxis ocupados (rojo -> valor 4)
            mapa_colores[taxi_pos['y'] - 1, taxi_pos['x'] - 1] = 4

   
    # Crear el mapa de colores con casillas alineadas
    ax.imshow(mapa_colores, cmap=cmap, norm=norm, extent=[0, size, 0, size], origin='lower')

    # Colocar el texto de las identificaciones después de colocar las casillas
    # Colocar identificaciones de clientes
   
    for cliente, pos in ubicaciones.items():
        if cliente.islower():
            ax.text(pos[0] - 0.5, pos[1] - 0.5, cliente, color='black', fontsize=12, ha='left', va='center')           

    # Colocar identificaciones de destinos
    for destino, pos in ubicaciones.items():
        if destino.isupper():
            ax.text(pos[0] - 0.5, pos[1] - 0.5, destino, color='black', fontsize=12, ha='center', va='center')

    # Colocar identificaciones de taxis
    for taxi in taxisact:
        taxi_pos = taxi['coordenada_origen']
        if taxi['recogido'] == True:
            taxi_id = str(taxi['id']) #+"-" + taxi['cliente']['id_cliente']
        else:
            taxi_id = taxi['id']
        ax.text(taxi_pos['x'] - 0.5, taxi_pos['y'] - 0.5, str(taxi_id), color='black', fontsize=12, ha='right', va='center')

    # Configurar los ejes para que vayan de 1 a 20
    ax.set_xticks(np.arange(0, size))
    ax.set_yticks(np.arange(0, size))
    ax.set_xticklabels(np.arange(1, size + 1))
    ax.set_yticklabels(np.arange(1, size + 1))

    # Configurar cuadrícula
    ax.grid(True, color='black', linestyle='-', linewidth=0.5)
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)

    plt.gca().invert_yaxis()  # Invertir el eje Y para que (1,1) esté en la esquina inferior izquierda

# Iniciar el gráfico con la animación
def iniciar_grafico(taxis, ubicaciones):
    fig, ax = plt.subplots()
    size = 20
    ani = FuncAnimation(fig, actualizar_mapa, fargs=(taxis, ubicaciones, ax, size), interval=1000, cache_frame_data=False)
    plt.show()

# Configuración de Kafka
def kafka_settings(kafka_server, topic, group_id):
    conf_producer = {'bootstrap.servers': kafka_server}
    conf_consumer = {
        'bootstrap.servers': kafka_server,
        'group.id': group_id,
        'auto.offset.reset': 'latest'
    }

    producer = Producer(conf_producer)
    consumer = Consumer(conf_consumer)
    consumer.subscribe([topic])  # Suscribirse al topic

    return producer, consumer



# Iniciar el servidor de sockets
def start():
    server.listen()
    print(f"[LISTENING] Servidor a la escucha en {SERVER}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=socket_taxi, args=(conn, addr))
        thread.start()
        print(f"[CONEXIONES ACTIVAS] {threading.active_count() - 1}")

# Función principal para iniciar los hilos y el gráfico
if __name__ == "__main__":
    if len(sys.argv) == 5:
        PORT = int(sys.argv[1])
        IP_kafka = sys.argv[2]
        PORT_kafka = int(sys.argv[3])
        fichero = sys.argv[4]
    
        # Configuración de sockets
        ADDR = (SERVER, PORT)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(ADDR)

        # Configuración de Kafka
        kafka_server = f"{IP_kafka}:{PORT_kafka}"
        producer_taxi, consumer_taxi = kafka_settings(kafka_server, 'taxi_status', 'central_taxi_group')
        producer_taxicommands, consumer_taxicommands = kafka_settings(kafka_server, 'taxi_commands', 'central_taxicommands_group')
        producer_customer, consumer_customer = kafka_settings(kafka_server, 'service', 'central_customer_group')
        producer_taxi_end, consumer_taxi_end = kafka_settings(kafka_server, 'taxi_end2', 'taxi_end_group')
        # Cargar taxis y ubicaciones desde archivos JSON
        taxis = cargar_fichero('taxis.json')
        ubicaciones = cargar_fichero('Mapa.json')

        # Iniciar hilo de Kafka para escuchar estados de taxis
        kafka_thread_taxis = threading.Thread(target=escuchar_kafka_estado_taxis, args=(consumer_taxi,))
        kafka_thread_taxis.start()
        kafka_thread_customer = threading.Thread(target=escuchar_kafka_servicios_customer, args=(consumer_customer, producer_customer, producer_taxicommands))
        kafka_thread_customer.start()
        thread_socket = threading.Thread(target=start)
        thread_socket.start()
        kafka_thread_end_taxi = threading.Thread(target=escuchar_taxi_end, args=(consumer_taxi_end, producer_taxi_end))
        kafka_thread_end_taxi.start()
        # Iniciar el gráfico en el hilo principal
        
        iniciar_grafico(taxis, ubicaciones)
    else:
        print('Los argumentos son: <puerto_socket> <IP_kafka> <PUERTO_kafka> <taxis.json>')
        exit()
