import os
import firebase_admin
import hashlib
import hmac
import re

from flask import *
from datetime import datetime, timezone, timedelta
from flask_paginate import Pagination, get_page_parameter
from firebase_admin import credentials
from firebase_admin import firestore

# Obtener la ruta del directorio donde se encuentra app.py
dir_path = os.path.dirname(os.path.realpath(__file__))

# Concatenar la ruta relativa al archivo key.json
key_path = os.path.join(dir_path, 'key.json')

# Crear la credencial con la ruta al archivo key.json
cred = credentials.Certificate(key_path)
firebase_admin.initialize_app(cred)

app = Flask(__name__)
app.secret_key = "TestingAsegurandoLaExcelencia"


