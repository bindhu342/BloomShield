from flask import Flask, render_template, request, jsonify
import pandas as pd
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import os
from PyPDF2 import PdfReader
import random

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==========================
# 🔐 ENCRYPTION SECTION
# ==========================

password = "hackathon_secret"
key = hashlib.sha256(password.encode()).digest()

def encrypt_text(text):
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(str(text).encode(), AES.block_size))
    return base64.b64encode(encrypted).decode()

def search_csv(file_path, word):
    df = pd.read_csv(file_path)
    encrypted_word = encrypt_text(word.strip())

    for col in df.columns:
        for cell in df[col]:
            if str(cell).strip() == encrypted_word:
                return "FOUND"

    return "NOT FOUND"


def search_txt(file_path, word):
    encrypted_word = encrypt_text(word.strip())

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        if line.strip() == encrypted_word:
            return "FOUND"

    return "NOT FOUND"

def search_pdf(file_path, word):
    encrypted_word = encrypt_text(word.strip())
    
    try:
        pdf_reader = PdfReader(file_path)
        for page in pdf_reader.pages:
            text = page.extract_text()
            if encrypted_word in text:
                return "FOUND"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
    
    return "NOT FOUND"

# ==========================
# 🌸 BLOOM FILTER SECTION
# ==========================

BLOOM_SIZE = 10000
bloom = [0] * BLOOM_SIZE
inserted_items = set()

def hash1(item):
    return int(hashlib.md5(item.encode()).hexdigest(), 16) % BLOOM_SIZE

def hash2(item):
    return int(hashlib.sha1(item.encode()).hexdigest(), 16) % BLOOM_SIZE

def bloom_insert(item):
    h1 = hash1(item)
    h2 = hash2(item)
    bloom[h1] = 1
    bloom[h2] = 1
    inserted_items.add(item)
    return [h1, h2]

def bloom_search(item):
    h1 = hash1(item)
    h2 = hash2(item)

    if bloom[h1] == 1 and bloom[h2] == 1:
        return "Found!", [h1, h2]
    else:
        return "Not Found!", [h1, h2]

# ==========================
# 🌐 ROUTES
# ==========================

@app.route("/", methods=["GET", "POST"])
def index():

    dataset_result = None
    upload_bloom_result = None
    upload_indices = None

    insert_bloom_result = None
    insert_indices = None

    if request.method == "POST":

        # 🔐 FILE UPLOAD SEARCH
        file = request.files.get("file")
        word = request.form.get("word")

        if file and word:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)

            filename = file.filename.lower()

            if filename.endswith(".csv"):
                dataset_result = search_csv(file_path, word)

            elif filename.endswith(".pdf"):
                dataset_result = search_pdf(file_path, word)

            elif filename.endswith(".txt"):
                dataset_result = search_txt(file_path, word)

            else:
                dataset_result = "Unsupported File Format"

            # Only search bloom (NO INSERT)
            upload_bloom_result, upload_indices = bloom_search(word.strip())


        # 🌸 BLOOM SECTION
        text = request.form.get("text")
        action = request.form.get("action")

        if text and action:

            if action == "insert":
                insert_indices = bloom_insert(text.strip())
                insert_bloom_result = "Inserted into Bloom"

            elif action == "search":
                insert_bloom_result, insert_indices = bloom_search(text.strip())

    return render_template(
        "index.html",
        dataset_result=dataset_result,
        upload_bloom_result=upload_bloom_result,
        upload_indices=upload_indices,
        insert_bloom_result=insert_bloom_result,
        insert_indices=insert_indices
    )
# ==========================
# 🚨 ATTACK SIMULATION
# ==========================

@app.route("/attack")
def attack():
    attempts = 2
    false_positive = 0

    for i in range(attempts):
        test = "random" + str(random.randint(1, 10000))
        if test not in inserted_items:
            res, _ = bloom_search(test)
            if res == "Found!":
                false_positive += 1

    return jsonify({
        "false_positive": false_positive,
        "attempts": attempts
    })

# ==========================
# 📊 GRAPH DATA
# ==========================

@app.route("/graph")
def graph():
    bits_set = sum(bloom)
    return jsonify({
        "bits_set": bits_set,
        "size": BLOOM_SIZE
    })

# ==========================

if __name__ == "__main__":
    app.run(debug=True)