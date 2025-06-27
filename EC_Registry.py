import ipaddress
from flask import Flask, request, jsonify
import json
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import requests
import sys
import socket

app = Flask(__name__)

EC_CENTRAL_URL = ""

def get_taxis_from_central():
    """
    Obtener el JSON actual de taxis desde EC_Central.
    """
    try:
        response = requests.get(f"{EC_CENTRAL_URL}/get_all_taxis")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al obtener taxis de EC_Central: {response.text}")
            return None
    except Exception as e:
        print(f"Error al conectarse a EC_Central: {e}")
        return None
    
def update_taxis_in_central(taxis):
    """
    Enviar el JSON actualizado de taxis a EC_Central.
    """
    try:
        response = requests.post(f"{EC_CENTRAL_URL}/update_taxis", json=taxis)
        if response.status_code == 200:
            print("Taxis actualizados en EC_Central correctamente.")
        else:
            print(f"Error al actualizar taxis en EC_Central: {response.text}")
    except Exception as e:
        print(f"Error al conectarse a EC_Central: {e}")

def generate_certificates():
    """
    Genera un certificado autofirmado y una clave privada si no existen.
    """
    if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
       
        server_ip = socket.gethostbyname(socket.gethostname())
        # Generar clave privada
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Crear certificado autofirmado
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My Company"),
            x509.NameAttribute(NameOID.COMMON_NAME, server_ip),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost"),
            x509.IPAddress(ipaddress.IPv4Address(server_ip))]),
            critical=False,
        ).sign(key, hashes.SHA256())

        # Guardar clave privada
        with open("key.pem", "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Guardar certificado
        with open("cert.pem", "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

@app.route('/register_taxi', methods=['PUT'])
def register_taxi():
    """Endpoint to register a taxi."""
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({'error': 'Taxi ID is required'}), 400

    taxis = get_taxis_from_central()
    taxi_id = data['id']

    # Check if taxi is already registered
    if any(taxi['id'] == taxi_id for taxi in taxis):
        return jsonify({'message': f'Taxi {taxi_id} is already registered'}), 200

    # Add the new taxi
    new_taxi = {
        "id": taxi_id,
        "coordenada_origen": {"x": 1, "y": 1},
        "coordenada_destino": {"x": None, "y": None, "id": ""},
        "estado": "verde",
        "disponible": True,
        "verificado": False,
        "recogido": False,
        "returning_to_base": False,
        "cliente": {"x": None, "y": None, "id_cliente": ""}
    }
    taxis.append(new_taxi)
    update_taxis_in_central(taxis)

    return jsonify({'message': f'Taxi {taxi_id} registered successfully'}), 201

@app.route('/deregister_taxi/<int:taxi_id>', methods=['DELETE'])
def deregister_taxi(taxi_id):
    """Endpoint to deregister a taxi."""
    taxis = get_taxis_from_central()

    # Check if taxi exists
    taxi = next((taxi for taxi in taxis if taxi['id'] == taxi_id), None)
    if not taxi:
        return jsonify({'error': f'Taxi {taxi_id} not found'}), 404

    # Remove the taxi
    taxis.remove(taxi)
    update_taxis_in_central(taxis)

    return jsonify({'message': f'Taxi {taxi_id} deregistered successfully'}), 200

@app.route('/is_registered/<int:taxi_id>', methods=['GET'])
def is_registered(taxi_id):
    """Endpoint to check if a taxi is registered."""
    taxis = get_taxis_from_central()
    if any(taxi['id'] == taxi_id for taxi in taxis):
        return jsonify({'registered': True}), 200
    return jsonify({'registered': False}), 404

if __name__ == '__main__':
        # Validar argumentos
    if len(sys.argv) != 4:
        print("Usage: python EC_Registry.py <IP_CENTRAL> <PORT_CENTRAL> [<PORT_REGISTRY>]")
        sys.exit(1)

    # Obtener los argumentos
    central_ip = sys.argv[1]
    central_port = sys.argv[2]
    registry_port = int(sys.argv[3])
    registry_ip = socket.gethostbyname(socket.gethostname())

    # Configurar la URL de EC_Central
    EC_CENTRAL_URL = f"http://{central_ip}:{central_port}"
    
    # Generar certificados si no existen
    generate_certificates()
    
    print(f"registry API working on {registry_ip}:{registry_port} sending and getting bd data from central with API at {EC_CENTRAL_URL}")
    print()

    # Ensure HTTPS by running the app with SSL certificates
    app.run(host=registry_ip, port=registry_port, ssl_context=('cert.pem', 'key.pem'))