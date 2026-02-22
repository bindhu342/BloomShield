from flask import Flask, render_template, request, jsonify
import pandas as pd
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import os
from PyPDF2 import PdfReader
import random
import time

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- GLOBAL SESSION VARIABLES ---
# These MUST stay at the top level to persist across requests
current_file_path = None
file_expiry_time = 0 

# ==========================
# 🔐 ENCRYPTION & SEARCH LOGIC
# ==========================
password = "hackathon_secret"
key = hashlib.sha256(password.encode()).digest()

def encrypt_text(text):
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(str(text).encode(), AES.block_size))
    return base64.b64encode(encrypted).decode()

def search_csv(file_path, word):
    try:
        df = pd.read_csv(file_path)
        encrypted_word = encrypt_text(word.strip())
        for col in df.columns:
            for cell in df[col]:
                if str(cell).strip() == encrypted_word:
                    return "MATCH FOUND"
        return "NO MATCH"
    except: return "Error processing CSV"

def search_txt(file_path, word):
    try:
        encrypted_word = encrypt_text(word.strip())
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == encrypted_word:
                    return "MATCH FOUND"
        return "NO MATCH"
    except: return "Error processing TXT"

def search_pdf(file_path, word):
    try:
        encrypted_word = encrypt_text(word.strip())
        pdf_reader = PdfReader(file_path)
        for page in pdf_reader.pages:
            if encrypted_word in page.extract_text():
                return "MATCH FOUND"
        return "NO MATCH"
    except: return "Error reading PDF"

# =============================================
# 🌸 BLOOM FILTER LOGIC (3 INDICES)
# =============================================
BLOOM_SIZE = 10000
bloom = [0] * BLOOM_SIZE

def bloom_search(item):
    h1 = int(hashlib.md5(item.encode()).hexdigest(), 16) % BLOOM_SIZE
    h2 = int(hashlib.sha1(item.encode()).hexdigest(), 16) % BLOOM_SIZE
    h3 = int(hashlib.sha256(item.encode()).hexdigest(), 16) % BLOOM_SIZE
    return "Indices Computed", [h1, h2, h3]

# ==========================
# 🌐 ROUTES
# ==========================

@app.route("/dataset", methods=["GET", "POST"])
def dataset():
    global current_file_path, file_expiry_time
    dataset_result = None
    upload_indices = None
    
    # 1. AUTO-CLEANUP: If time is up, kill the session
    if current_file_path and time.time() > file_expiry_time:
        if os.path.exists(current_file_path): 
            try: os.remove(current_file_path)
            except: pass
        current_file_path = None
        file_expiry_time = 0

    if request.method == "POST":
        file = request.files.get("file")
        word = request.form.get("word")

        # 2. FILE HANDLING: Update session if a new file is uploaded
        if file and file.filename != '':
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)
            current_file_path = file_path
            file_expiry_time = time.time() + 120 # Start 2-minute timer

        # 3. SEARCH LOGIC: If we have a query and a valid session
        if word and current_file_path:
            # Important: We search using the stored current_file_path
            ext = current_file_path.lower()
            if ext.endswith(".csv"): dataset_result = search_csv(current_file_path, word)
            elif ext.endswith(".pdf"): dataset_result = search_pdf(current_file_path, word)
            elif ext.endswith(".txt"): dataset_result = search_txt(current_file_path, word)
            
            _, upload_indices = bloom_search(word.strip())
        elif word and not current_file_path:
            dataset_result = "SESSION EXPIRED: Please upload file again."

    # 4. PREPARE UI DATA
    remaining_time = max(0, int(file_expiry_time - time.time())) if file_expiry_time > 0 else 0
    return render_template("dataset.html", 
                           dataset_result=dataset_result, 
                           upload_indices=upload_indices, 
                           remaining_time=remaining_time, 
                           file_active=bool(current_file_path))

# Maintain your other routes (/, /attack, /graph) here...

@app.route("/", methods=["GET", "POST"])
def index():
    insert_bloom_result = None
    insert_indices = None
    if request.method == "POST":
        text = request.form.get("text")
        action = request.form.get("action")
        if text:
            if action == "insert":
                h1 = int(hashlib.md5(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                h2 = int(hashlib.sha1(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                h3 = int(hashlib.sha256(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                bloom[h1] = bloom[h2] = bloom[h3] = 1
                insert_bloom_result = "INSERTED"
                insert_indices = [h1, h2, h3]
            elif action == "search":
                h1 = int(hashlib.md5(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                h2 = int(hashlib.sha1(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                h3 = int(hashlib.sha256(text.encode()).hexdigest(), 16) % BLOOM_SIZE
                if bloom[h1] and bloom[h2] and bloom[h3]:
                    insert_bloom_result = "PROBABLY EXISTS"
                else:
                    insert_bloom_result = "DEFINITELY NOT EXISTS"
                insert_indices = [h1, h2, h3]
    return render_template("index.html", insert_bloom_result=insert_bloom_result, insert_indices=insert_indices)

@app.route("/graph")
def graph():
    active = sum(bloom)
    available = BLOOM_SIZE - active
    return jsonify({"active": active, "available": available})

@app.route("/attack")
def attack():
    words = ["password", "admin", "secret", "key", "token", "user", "data", "hash"]
    cracked = 0
    for word in words:
        h1 = int(hashlib.md5(word.encode()).hexdigest(), 16) % BLOOM_SIZE
        h2 = int(hashlib.sha1(word.encode()).hexdigest(), 16) % BLOOM_SIZE
        h3 = int(hashlib.sha256(word.encode()).hexdigest(), 16) % BLOOM_SIZE
        if bloom[h1] and bloom[h2] and bloom[h3]:
            cracked += 1
    return jsonify({"cracked": cracked, "total": len(words)})

if __name__ == "__main__":
    # threaded=False ensures that all requests use the SAME memory space
    app.run(debug=True, threaded=False)