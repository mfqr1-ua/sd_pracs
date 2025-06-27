CENTRAL_IP=localhost
CENTRAL_PORT=1515

TAXI_IP=localhost
TAXI_PORT=1616
TAXI_ID=1

KAFKA_IP=localhost
KAFKA_PORT=9092

kafka:
	docker run -d -p $(KAFKA_PORT):9092 --name kafka apache/kafka:latest

central:
	python3 EC_Central.py $(CENTRAL_PORT) $(KAFKA_IP):$(KAFKA_PORT) taxisDefault.json

taxi:
	python3 EC_DE.py $(CENTRAL_IP) $(CENTRAL_PORT) $(KAFKA_IP):$(KAFKA_PORT) $(TAXI_PORT) $(TAXI_ID)

cliente:
	python3 EC_Customer.py $(KAFKA_IP):$(KAFKA_PORT) a Customer_services.json

sensor:
	python3 EC_S.py $(TAXI_IP) $(TAXI_PORT)

espiar.SOLICITUDES_TAXIS:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'solicitudes-taxis'
espiar.RESPUESTAS_TAXIS:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'respuestas-taxis'
espiar.ASIGNACION_TAXIS:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'asignacion-taxis'
espiar.TAXI_UPDATES:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'taxi_updates'
espiar.TAXI_END_CENTRAL:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'taxi-end-central'
espiar.TAXI_END_CLIENT:
	docker exec -ti kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server $(KAFKA_IP):$(KAFKA_PORT) --topic 'taxi-end-client'