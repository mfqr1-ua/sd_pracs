@echo off

rmdir /s /q C:\tmp\kafka-logs
rmdir /s /q C:\tmp\zookeeper

start "Zookeeper" cmd /k "C:\kafka\bin\windows\zookeeper-server-start.bat C:\kafka\config\zookeeper.properties"
timeout /t 10

start "Kafka" cmd /k "C:\kafka\bin\windows\kafka-server-start.bat C:\kafka\config\server.properties"
timeout /t 10

start "Crear Tópico solicitudes-taxis" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic solicitudes-taxis --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
start "Crear Tópico respuestas-taxis" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic respuestas-taxis --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
start "Crear Tópico asignacion-taxis" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic asignacion-taxis --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
start "Crear Tópico taxi_updates" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic taxi_updates --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
start "Crear Tópico taxi-end-central" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic taxi-end-central --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"
start "Crear Tópico taxi-end-client" cmd /c "C:\kafka\bin\windows\kafka-topics.bat --create --topic taxi-end-client --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1"

echo Kafka y los tópicos se han iniciado correctamente.
pause
