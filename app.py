from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timezone
import uuid
import os
import requests

app = Flask(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo-connections:27017/")
client = MongoClient(MONGO_URI)
db = client['sistema_de_transacoes']
transacoes_collection = db['transacoes']

USER_API_URL = os.environ.get("USER_API_URL", "http://18.228.48.67/users")


@app.route('/transacao', methods=['GET'])
def get_transacoes():
    cliente_id = request.args.get('id')
    filtro = {"cliente_id": cliente_id} if cliente_id else {}

    transacoes = list(transacoes_collection.find(filtro, {"_id": 0}))
    return jsonify(transacoes), 200


@app.route('/transacao', methods=['POST'])
def create_transacao():
    data = request.json or {}

    cliente_id = data.get("cliente_id") 
    codigo_acao = data.get("codigo_acao")
    quantidade = data.get("quantidade")
    preco_unitario = data.get("preco_unitario")

    if not (cliente_id and codigo_acao and quantidade and preco_unitario):
        return jsonify({"Erro": "Problema nos campos"}), 400

    try:
        response = requests.get(f"{USER_API_URL}/{cliente_id}", timeout=5)
        
        if response.status_code != 200:
             return jsonify({"Erro": "Cliente não encontrado"}), 404
        
        dados_usuario = response.json() 
        email_cliente = dados_usuario.get("email") 
        
    except requests.exceptions.RequestException:
        return jsonify({"Erro": "Falha na consulta de api"}), 500


    nova_transacao = {
        "id": str(uuid.uuid4()),
        "cliente_id": cliente_id,
        "email_cliente": email_cliente,
        "codigo_acao": str(codigo_acao).upper(),
        "quantidade": quantidade,
        "preco_unitario": preco_unitario,
        "valor_total": quantidade * preco_unitario,
        "data_transacao": datetime.now(timezone.utc).isoformat()
    }

    transacoes_collection.insert_one(nova_transacao)
    nova_transacao.pop('_id', None)
    
    return jsonify(nova_transacao), 201


@app.route('/transacao/<id>', methods=['DELETE'])
def delete_transacao(id):
    resultado = transacoes_collection.delete_one({"id": id})

    if resultado.deleted_count == 0:
        return jsonify({"Erro": "Transação não encontrada"}), 404

    return jsonify({"Erro": "Transação removida"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)