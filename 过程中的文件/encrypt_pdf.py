import os
from cryptography.fernet import Fernet
import base64

KEY = b'YOUR_SECRET_KEY_32BYTE_______'

def encrypt_file(src_path, dst_path):
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(src_path, 'rb') as f:
        data = f.read()
    fernet = Fernet(base64.urlsafe_b64encode(KEY[:32]))
    encrypted = fernet.encrypt(data)
    with open(dst_path, 'wb') as f:
        f.write(encrypted)
    print(f"✅ 加密完成: {dst_path}")

def encrypt_folder(src_dir, dst_dir='data'):
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                rel_path = os.path.relpath(os.path.join(root, file), src_dir)
                enc_path = os.path.join(dst_dir, rel_path + ".enc")
                encrypt_file(os.path.join(root, file), enc_path)

if __name__ == "__main__":
    src = "../pdfs"  # 原始PDF根目录
    encrypt_folder(src)