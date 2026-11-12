# Application VOLONTAIREMENT vulnérable (cible pour SAST / SCA du lab)
import sqlite3
import subprocess

import yaml
from flask import Flask, request

app = Flask(__name__)
SECRET_KEY = "dev-secret-key-123"          # secret en dur


@app.route("/user")
def user():
    name = request.args.get("name", "")
    conn = sqlite3.connect("app.db")
    query = "SELECT * FROM users WHERE name = '%s'" % name   # injection SQL
    return str(conn.execute(query).fetchall())


@app.route("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    return subprocess.check_output("ping -c1 " + host, shell=True)  # injection de commande


@app.route("/load", methods=["POST"])
def load():
    return str(yaml.load(request.data))      # désérialisation YAML non sûre


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)      # debug activé
