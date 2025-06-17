import sys
from confluent_kafka import Producer, Consumer, KafkaError 
import time 

last_offset = -1
last_offset_taxi_end = -1
##########  MAIN  #########

#leer el fichero de los servicios 
def read_services(file):
    with open(file, 'r') as f:
        services = f.readlines()
    return [s.strip() for s in services]

def recibir_respuesta(consumer, ID_customer):
    global last_offset
    
    while True:
        msg = consumer.poll(timeout=0.5)
        
        
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(msg.error())
                return None #error demasiado critico que requiere parar la ejecución 
        if msg.offset() > last_offset:
            
            mensaje = msg.value().decode('utf-8')
            id, confirmacion = mensaje.split(": ")
            if ID_customer == id:
                print(f"Procesando mensaje: {mensaje} con offset {msg.offset()}")
                # Actualizar el último offset procesado
                last_offset = msg.offset()
                # Confirmar manualmente el offset
                consumer.commit(asynchronous=False)
                return mensaje
            else:
                continue

                

        else: 
            print(f"Ignorando mensaje antiguo con offset {msg.offset()}")
        



#solicitud para producir mensajes en kafka 
def send_request(producer, service, customer_id):
    message = f"{customer_id} solicita {service}" # aqui PASARLE LA COORDENADA ORIGEN, DESTINO 
    producer.produce('service', message.encode('utf-8')) #topic name = service 
    producer.flush() #para que no se produzcan envios por lotes 

def esperar_llegada_taxi(consumer, ID_customer):
    global last_offset_taxi_end
    while True:
        print("HE ENTRADO A ESCUCHAR")
        msg = consumer.poll(timeout=0.5)
        
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(msg.error())
                return None #error demasiado critico que requiere parar la ejecución 
    
        if msg.offset() > last_offset_taxi_end:
            
            mensaje = msg.value().decode('utf-8')
            print(f'EL MENSAJE ES {mensaje}')
            print(f"el mensaje es {mensaje}")
            last_offset_taxi_end = msg.offset()
            #FORMATO mensaje TAXI --> f"taxi#taxi_id#cliente#cliente#ha llegado a su destino"
            # Extraemos taxi_id y cliente usando split y strip
            # Encuentra las posiciones de las llaves
            mensajes = mensaje.split('#') 
            taxi_id = mensajes[1]
            cliente_id = mensajes[3]
        
            if ID_customer == cliente_id:
                return "has llegado a tu destino"
            else:
                continue
        else:
            continue
                

        


######################### MAIN #######################
if(len(sys.argv) == 5):
    IP_kafka = sys.argv[1] 
    PORT_kafka = sys.argv[2] 
    ID_customer = sys.argv[3]
    Services_File = sys.argv[4]

    #Configuración de EC_Customer 
    kafka_server = f"{IP_kafka}:{PORT_kafka}" #puerto e ip de kafka 
    producer_conf = {'bootstrap.servers': kafka_server}
    consumer_conf = {
        'bootstrap.servers': kafka_server,
        'group.id': f'grupo_{ID_customer}',
        'auto.offset.reset': 'latest'

    }
    

    producer = Producer(producer_conf)
    consumer = Consumer(consumer_conf)
    consumer.subscribe(['central_replay']) #el customer se suscribe al topic de central donde se le responde la solicitud 
    consumer_taxi = Consumer(consumer_conf)
    consumer_taxi.subscribe(['taxi_end'])
    services = read_services(Services_File)

    for service in services: #Para cada uno de los servicios que el cliente quiere y se encuentran en el archivo...
        print('                                                 ')
        print(f"Enviando solicitud para ir al destino: {service}")
        send_request(producer, service, ID_customer) # producimos un mensaje en kafka con el servicio requerido 

        # Esperar la respuesta de la central
        print('                               ')
        respuesta = recibir_respuesta(consumer, ID_customer)
        id_respuesta, confirmacion = respuesta.split(': ')
      
        print(f"Respuesta recibida para el servicio con destino {service} : {confirmacion}")
        if confirmacion == 'OK':
        
           respuesta_taxi = esperar_llegada_taxi(consumer_taxi, ID_customer)
           print('                           ')
           print(respuesta_taxi)
        else:
            print('no se recibio confirmacion')
        
    

        # Esperar 4 segundos antes de la siguiente solicitud
        time.sleep(4)

else:
    print("Formato: python EC_Customer.py <IP_kafka> <Port_kafka> <ID_customer> servicesCustomer1.json")

    
