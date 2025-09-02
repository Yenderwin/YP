# c:\Users\ypalomino\Documents\Estudia\Inventario\server.py
import os
import datetime
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit

# --- CONFIGURACIÓN ---
app = Flask(__name__)

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
# Render proporciona la URL de la base de datos en una variable de entorno.
# Si no la encuentra, usa una base de datos SQLite local para desarrollo.
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    # SQLAlchemy v1.4+ ya no necesita este truco, pero por compatibilidad lo dejamos.
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///inventario_central.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# --- MODELOS DE LA BASE DE DATOS ---
class Articulo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    cantidad = db.Column(db.Integer, default=0)
    proveedor = db.Column(db.String(100))

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    unidad_medicion = db.Column(db.String(50))
    imagen_path = db.Column(db.String(255))

class Entrada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey('articulo.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    proveedor = db.Column(db.String(100))
    destino = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    articulo = db.relationship('Articulo', backref=db.backref('entradas', lazy=True))

class Salida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey('articulo.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    destino = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    articulo = db.relationship('Articulo', backref=db.backref('salidas', lazy=True))

# --- LÓGICA DE NOTIFICACIÓN ---
def notificar_actualizacion():
    """Emite eventos a todos los clientes para que recarguen sus datos."""
    socketio.emit('actualizacion_servidor', {'data': 'updated'})

# --- RUTAS DE LA API (ENDPOINTS) ---
@app.route('/inventario', methods=['GET'])
def get_inventario():
    articulos = db.session.query(Articulo, Material.unidad_medicion).outerjoin(Material, Articulo.nombre == Material.nombre).all()
    return jsonify([{'nombre': art.nombre, 'cantidad': art.cantidad, 'unidad_medicion': unidad} for art, unidad in articulos])

@app.route('/historial', methods=['GET'])
def get_historial():
    entradas = db.session.query(Entrada, Articulo.nombre, Material.unidad_medicion).join(Articulo, Entrada.articulo_id == Articulo.id).outerjoin(Material, Articulo.nombre == Material.nombre).all()
    salidas = db.session.query(Salida, Articulo.nombre, Material.unidad_medicion).join(Articulo, Salida.articulo_id == Articulo.id).outerjoin(Material, Articulo.nombre == Material.nombre).all()
    historial = []
    for entrada, nombre, unidad in entradas:
        historial.append({'Articulo': nombre, 'Tipo': 'Entrada', 'cantidad': entrada.cantidad, 'Unidad': unidad, 'Ubicacion': entrada.destino, 'Proveedor': entrada.proveedor, 'fecha': entrada.fecha.isoformat()})
    for salida, nombre, unidad in salidas:
        historial.append({'Articulo': nombre, 'Tipo': 'Salida', 'cantidad': salida.cantidad, 'Unidad': unidad, 'Ubicacion': salida.destino, 'Proveedor': None, 'fecha': salida.fecha.isoformat()})
    return jsonify(historial)

@app.route('/registrar_entrada', methods=['POST'])
def registrar_entrada():
    data = request.get_json()
    # --- MEJORA: Validación y Normalización de Datos ---
    if not data or 'nombre' not in data or 'cantidad' not in data:
        return jsonify({'status': 'error', 'message': 'Faltan datos (nombre, cantidad)'}), 400
    
    try:
        cantidad = int(data['cantidad'])
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva.")
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'La cantidad debe ser un número entero positivo.'}), 400

    nombre_articulo = data['nombre'].strip().upper()
    proveedor = (data.get('proveedor') or '').strip().upper()
    destino = (data.get('destino') or '').strip().upper()

    articulo = Articulo.query.filter_by(nombre=nombre_articulo).first()
    if not articulo:
        articulo = Articulo(nombre=nombre_articulo, cantidad=0, proveedor=proveedor)
        db.session.add(articulo)
    
    try:
        articulo.cantidad += cantidad
        nueva_entrada = Entrada(articulo=articulo, cantidad=cantidad, proveedor=proveedor, destino=destino, fecha=datetime.datetime.utcnow())
        db.session.add(nueva_entrada)
        db.session.commit()
        notificar_actualizacion()
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error de base de datos: {e}'}), 500

    return jsonify({'status': 'success'}), 201

@app.route('/registrar_salida', methods=['POST'])
def registrar_salida():
    data = request.get_json()
    # --- MEJORA: Validación y Normalización de Datos ---
    if not data or 'nombre' not in data or 'cantidad' not in data:
        return jsonify({'status': 'error', 'message': 'Faltan datos (nombre, cantidad)'}), 400

    try:
        cantidad = int(data['cantidad'])
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva.")
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'La cantidad debe ser un número entero positivo.'}), 400

    nombre_articulo = data['nombre'].strip().upper()
    destino = (data.get('destino') or '').strip().upper()

    articulo = Articulo.query.filter_by(nombre=nombre_articulo).first()
    if not articulo or articulo.cantidad < cantidad:
        return jsonify({'status': 'error', 'message': 'Stock insuficiente o artículo no existe'}), 400
    
    try:
        articulo.cantidad -= cantidad
        nueva_salida = Salida(articulo=articulo, cantidad=cantidad, destino=destino, fecha=datetime.datetime.utcnow())
        db.session.add(nueva_salida)
        db.session.commit()
        notificar_actualizacion()
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error de base de datos: {e}'}), 500

    return jsonify({'status': 'success'}), 201

# --- EVENTOS DE WEBSOCKET ---
@socketio.on('connect')
def handle_connect():
    print('Cliente conectado!')

@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado.')

# --- INICIO DEL SERVIDOR ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
