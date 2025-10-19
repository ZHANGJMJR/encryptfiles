import os
import sys
import base64
import hashlib
import tempfile
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFileDialog, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyPDF2 import PdfReader
from cryptography.fernet import Fernet

# ======== 工具函数 ========
def generate_key(password: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

def decrypt_file(enc_path, password, output_path):
    key = generate_key(password)
    fernet = Fernet(key)
    with open(enc_path, 'rb') as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    with open(output_path, 'wb') as f:
        f.write(decrypted_data)

def machine_code():
    import uuid
    return str(uuid.getnode())

def verify_auth_code(machine_id, code, expire_timestamp):
    # 模拟授权验证
    try:
        if not code or code != hashlib.sha256(machine_id.encode()).hexdigest()[:8].upper():
            return False, "授权码不匹配"
        if datetime.now().timestamp() > expire_timestamp:
            return False, "授权码已过期"
        return True, "验证成功"
    except Exception as e:
        return False, str(e)

# ======== 授权验证窗口 ========
class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedSize(420, 400)

        layout = QVBoxLayout()

        self.logo_label = QLabel()
        if os.path.exists("../logo.png"):
            pixmap = QPixmap("../logo.png")
            self.logo_label.setPixmap(pixmap.scaledToWidth(180, Qt.SmoothTransformation))
            self.logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_label)

        self.machine_label = QLabel("机器码：")
        layout.addWidget(self.machine_label)

        self.machine_code = QLineEdit(machine_code())
        self.machine_code.setReadOnly(True)
        layout.addWidget(self.machine_code)

        self.auth_label = QLabel("请输入授权码：")
        layout.addWidget(self.auth_label)

        self.auth_code = QLineEdit()
        self.auth_code.setFixedHeight(40)
        layout.addWidget(self.auth_code)

        self.btn_verify = QPushButton("验证")
        layout.addWidget(self.btn_verify)

        self.btn_verify.clicked.connect(self.check_code)
        self.setLayout(layout)
        self.verified = False

    def check_code(self):
        code = self.auth_code.text().strip().upper()
        mcode = self.machine_code.text().strip()
        valid, msg = verify_auth_code(mcode, code, datetime.now().timestamp() + 86400)
        if valid:
            with open("auth.dat", "w") as f:
                f.write(code)
            self.verified = True
            QMessageBox.information(self, "成功", "授权验证通过！")
            self.accept()
        else:
            QMessageBox.warning(self, "错误", msg)

# ======== 主窗口 ========
class PDFBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全PDF浏览器")
        self.setGeometry(100, 100, 1200, 800)

        # 临时目录
        self.temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(self.temp_dir, exist_ok=True)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧文件树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMaximumWidth(int(self.width() / 10))
        splitter.addWidget(self.tree)

        # 右侧PDF显示区
        self.viewer = QLabel("请选择一个加密PDF文件")
        self.viewer.setAlignment(Qt.AlignCenter)
        splitter.addWidget(self.viewer)
        self.setCentralWidget(splitter)

        # Logo
        if os.path.exists("../logo.png"):
            self.logo_label = QLabel(self)
            pixmap = QPixmap("../logo.png")
            self.logo_label.setPixmap(pixmap.scaledToWidth(120))
            self.logo_label.move(20, 10)

        # 加载文件
        self.load_pdf_tree()
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        # 滚轮缩放控制
        self.scale_factor = 1.2

    def load_pdf_tree(self):
        root_dir = os.path.join(os.getcwd(), "encrypted_files")
        if not os.path.exists(root_dir):
            return
        for subdir, _, files in os.walk(root_dir):
            relative = os.path.relpath(subdir, root_dir)
            if relative == ".":
                parent = self.tree
            else:
                parent = QTreeWidgetItem(self.tree, [relative])
            for file in files:
                if file.endswith(".pdf.enc"):
                    child = QTreeWidgetItem([file])
                    parent.addChild(child)

    def on_item_double_clicked(self, item, _):
        filename = item.text(0)
        enc_path = os.path.join("../encrypted_files", filename)
        if not os.path.exists(enc_path):
            return
        temp_pdf = os.path.join(self.temp_dir, filename.replace(".enc", ""))
        decrypt_file(enc_path, "MyPassword123", temp_pdf)
        self.show_pdf(temp_pdf)

    def show_pdf(self, path):
        try:
            reader = PdfReader(path)
            page = reader.pages[0]
            text = page.extract_text() or "(PDF内容为空)"
            self.viewer.setText(text)
        except Exception as e:
            self.viewer.setText(f"打开失败：{e}")

# ======== 主程序入口 ========
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 检查授权文件
    verified = False
    if os.path.exists("auth.dat"):
        with open("auth.dat") as f:
            code = f.read().strip()
        valid, _ = verify_auth_code(machine_code(), code, datetime.now().timestamp() + 86400)
        verified = valid

    if not verified:
        dialog = AuthDialog()
        if not dialog.exec_():
            sys.exit(0)

    window = PDFBrowser()
    window.showMaximized()
    sys.exit(app.exec_())
