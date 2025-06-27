# app.py (servidor Flask)
from flask import Flask, jsonify, render_template
import json
import logging
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/get_taxis')
def get_taxis():
    with open('taxis.json') as f:
        taxis = json.load(f)
    return jsonify(taxis)

@app.route('/get_map')
def get_map():
    with open('mapa.json') as f:
        mapa = json.load(f)
    return jsonify(mapa)

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)  # Show only errors
    app.run()
