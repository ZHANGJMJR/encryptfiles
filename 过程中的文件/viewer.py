import os
import base64
import hashlib
import datetime
import tempfile
import platform, uuid
from cryptography.fernet import Fernet
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QMessageBox, QSplitter, QLabel, QVBoxLayout, QWidget, QScrollArea
import fitz  # PyMuPDF

KEY = b'YOUR_SECRET_KEY_32BYTE_______'
SECRET = "SecureViewerKey"
LICENSE_FILE = "license.key"
DATA_DIR = "data"

def get_machine_code():
    raw = platform.node() + str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def verify_license():
    if not os.path.exists(LICENSE_FILE):
        return False, "未激活，请输入激活码。"
    try:
        with open(LICENSE_FILE, "r") as f:
            license_code = f.read().strip()
        expire, license_hash = license_code.split("-")[0], license_code.split("-")[1]
        data = f"{get_machine_code()}-{expire}-{SECRET}"
        valid_hash = hashlib.sha256(data.encode()).hexdigest()[:24]
        if valid_hash != license_hash:
            return False, "激活码无效。"
        if datetime.datetime.now() > datetime.datetime.strptime(expire, "%Y%m%d"):
            return False, "激活码已过期。"
        return True, "激活成功。"
    except:
        return False, "激活码解析失败。"

def decrypt_file(filepath):
    with open(filepath, 'rb') as f:
        encrypted_data = f.read()
    fernet = Fernet(base64.urlsafe_b64encode(KEY[:32]))
    return fernet.decrypt(encrypted_data)

class Viewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure PDF Viewer")
        self.resize(1000, 700)

        splitter = QSplitter(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("文件目录")
        self.tree.itemDoubleClicked.connect(self.open_pdf)
        splitter.addWidget(self.tree)

        self.viewer = QScrollArea()
        splitter.addWidget(self.viewer)
        self.setCentralWidget(splitter)

        valid, msg = verify_license()
        if not valid:
            self.ask_for_activation(msg)

        self.load_directory(DATA_DIR, self.tree.invisibleRootItem())

    def load_directory(self, path, parent_item):
        entries = sorted(os.listdir(path))
        for entry in entries:
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                folder_item = QTreeWidgetItem([entry])
                parent_item.addChild(folder_item)
                self.load_directory(full_path, folder_item)
            elif entry.endswith(".enc"):
                QTreeWidgetItem(parent_item, [entry])

    def ask_for_activation(self, msg):
        code = get_machine_code()
        QMessageBox.warning(self, "激活提示", f"{msg}\n\n机器码：{code}")
        code_input, ok = QtWidgets.QInputDialog.getText(self, "输入激活码", "请输入激活码：")
        if ok:
            with open(LICENSE_FILE, "w") as f:
                f.write(code_input)
            QtWidgets.QMessageBox.information(self, "提示", "激活码已保存，请重新启动程序。")
            exit(0)
        else:
            exit(0)

    def open_pdf(self, item):
        path_list = []
        p = item
        while p:
            path_list.insert(0, p.text(0))
            p = p.parent()
        enc_path = os.path.join(DATA_DIR, *path_list)
        if not os.path.isfile(enc_path):
            return
        data = decrypt_file(enc_path)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(data)
        tmp.close()
        self.display_pdf(tmp.name)

    def display_pdf(self, pdf_path):
        doc = fitz.open(pdf_path)
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            qimg = QtGui.QImage(pix.samples, pix.width, pix.height, pix.stride, QtGui.QImage.Format_RGB888)
            label = QLabel()
            label.setPixmap(QtGui.QPixmap.fromImage(qimg))
            vbox.addWidget(label)
        self.viewer.setWidget(widget)

if __name__ == "__main__":
    app = QApplication([])
    v = Viewer()
    v.show()
    app.exec_()