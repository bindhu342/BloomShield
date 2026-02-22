import pandas as pd
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

password = "hackathon_secret"
key = hashlib.sha256(password.encode()).digest()

def encrypt_text(text):
    cipher = AES.new(key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(str(text).encode(), AES.block_size))
    return base64.b64encode(encrypted).decode()

# Read original dataset
df = pd.read_csv("dataset.csv")

# Encrypt everything and save as TXT
with open("encrypted_dataset.txt", "w", encoding="utf-8") as f:
    for col in df.columns:
        for value in df[col]:
            encrypted_value = encrypt_text(value)
            f.write(encrypted_value + "\n")

# Encrypt and save as CSV (preserving structure)
encrypted_df = df.map(lambda x: encrypt_text(x) if pd.notna(x) else x)
encrypted_df.to_csv("encrypted_dataset.csv", index=False)

print("✅ Encrypted TXT file created successfully!")
print("✅ Encrypted CSV file created successfully!")