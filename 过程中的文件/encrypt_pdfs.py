import os
import base64

SRC_FOLDER = "../pdfs"
ENC_FOLDER = "encrypted_files"
os.makedirs(ENC_FOLDER, exist_ok=True)

for root, dirs, files in os.walk(SRC_FOLDER):
    for fname in files:
        if fname.lower().endswith(".pdf"):
            full_path = os.path.join(root, fname)
            with open(full_path, "rb") as f:
                data = f.read()
            enc_data = base64.b64encode(data)

            # 保持目录结构
            rel_path = os.path.relpath(full_path, SRC_FOLDER)
            enc_path = os.path.join(ENC_FOLDER, rel_path + ".enc")
            os.makedirs(os.path.dirname(enc_path), exist_ok=True)

            with open(enc_path, "wb") as f:
                f.write(enc_data)

print("加密完成，生成的加密文件在 'encrypted_files' 文件夹中。")
