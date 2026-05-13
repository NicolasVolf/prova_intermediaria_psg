from enum import Enum
from functools import wraps

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, g, jsonify, request
from pymongo import MongoClient
from jose import JWTError, jwt
from datetime import datetime, timezone
import os
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo-connections:27017/")
client = MongoClient(MONGO_URI)
db = client['ecommerce']
produtos_collection = db['produtos']

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
ROLES_CLAIM = "https://api.pf/roles"


class Status(str, Enum):
    DISPONIVEL = "DISPONIVEL"
    INDISPONIVEL = "INDISPONIVEL"


def auth_required(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify({"error": "Token ausente"}), 401
            try:
                token = header.removeprefix("Bearer ")
                jwks = requests.get(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json", timeout=5).json()
                kid = jwt.get_unverified_header(token).get("kid")
                key = next(k for k in jwks["keys"] if k["kid"] == kid)
                payload = jwt.decode(token, key, algorithms=["RS256"],
                                     audience=AUTH0_AUDIENCE, issuer=f"https://{AUTH0_DOMAIN}/")
            except (JWTError, StopIteration):
                return jsonify({"error": "Token inválido"}), 401

            if roles and not any(r in payload.get(ROLES_CLAIM, []) for r in roles):
                return jsonify({"error": "Permissão insuficiente"}), 403

            g.email = payload.get("email", "")
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/products", methods=["POST"])
@auth_required(roles=["admin"])
def create_product():
    data = request.get_json() or {}

    missing = [f for f in ("codigo", "nome", "preco") if f not in data]
    if missing:
        return jsonify({"error": f"Campos obrigatórios: {', '.join(missing)}"}), 400
    if not isinstance(data["preco"], (int, float)) or data["preco"] < 0:
        return jsonify({"error": "Preço inválido"}), 400
    if db.products.find_one({"codigo": data["codigo"]}):
        return jsonify({"error": "Código já existe"}), 409

    doc = {
        "codigo": data["codigo"],
        "nome": data["nome"],
        "preco": data["preco"],
        "data_cadastro": datetime.now(timezone.utc),
        "status": data.get("status", Status.DISPONIVEL),
        "email_admin": g.email,
    }
    inserted_id = db.products.insert_one(doc).inserted_id
    doc["id"] = str(inserted_id)
    doc.pop("_id", None)
    doc["data_cadastro"] = doc["data_cadastro"].isoformat()
    return jsonify(doc), 201


@app.route("/products", methods=["GET"])
@auth_required(roles=["admin", "user"])
def list_products():
    query = {"status": request.args["status"]} if "status" in request.args else {}
    result = [
        {
            "id": str(d["_id"]),
            "codigo": d["codigo"],
            "nome": d["nome"],
            "preco": d["preco"],
            "data_cadastro": d["data_cadastro"].isoformat(),
            "status": d["status"],
            "email_admin": d["email_admin"],
        }
        for d in db.products.find(query)
    ]
    return jsonify(result), 200


@app.route("/products/<product_id>", methods=["DELETE"])
@auth_required(roles=["admin"])
def delete_product(product_id):
    try:
        result = db.products.delete_one({"_id": ObjectId(product_id)})
    except InvalidId:
        return jsonify({"error": "ID inválido"}), 400
    if result.deleted_count == 0:
        return jsonify({"error": "Produto não encontrado"}), 404
    return jsonify({"message": "Produto deletado"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)