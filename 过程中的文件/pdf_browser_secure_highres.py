# pdf_browser_secure_final_sidebar.py

import sys, os, hashlib, datetime, uuid, json
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QListWidget, QMessageBox,
                             QLineEdit, QSplitter)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
import fitz  # PyMuPDF

SECRET_KEY = "MySecretKey123"
CODE_LENGTH = 24
AUTH_FILE = "../auth_info.json"
LOGO_FILE = "../logo.png"  # 可替换

# ---------------- 授权函数 ----------------
def get_machine_code():
    return f"{uuid.getnode():012X}"

def generate_auth_code(machine_code, valid_days=1):
    expire_date = datetime.datetime.now() + datetime.timedelta(days=valid_days)
    expire_str = expire_date.strftime("%Y%m%d")
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    auth_code = digest[:CODE_LENGTH].upper()
    return auth_code, expire_str

def verify_auth_code(machine_code, auth_code_input, expire_str):
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    if today_str > str(expire_str):
        return False, "授权码已过期"
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    expected = digest[:CODE_LENGTH].upper()
    if expected == auth_code_input.upper():
        return True, "授权码有效"
    else:
        return False, "授权码不匹配"

def save_auth_info(machine_code, auth_code, expire_str):
    info = {"machine_code": machine_code, "auth_code": auth_code, "expire": expire_str}
    with open(AUTH_FILE, "w") as f:
        json.dump(info, f)

def load_auth_info():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            return json.load(f)
    return None

# ---------------- 授权窗口 ----------------
class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("授权验证")
        self.resize(400, 220)
        layout = QVBoxLayout()

        self.label_mc = QLabel(f"机器码: {get_machine_code()}")
        layout.addWidget(self.label_mc)

        self.copy_btn = QPushButton("复制机器码")
        self.copy_btn.clicked.connect(self.copy_machine_code)
        layout.addWidget(self.copy_btn)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("请输入授权码")
        layout.addWidget(self.input_code)

        self.ok_btn = QPushButton("验证")
        self.ok_btn.clicked.connect(self.check_code)
        layout.addWidget(self.ok_btn)

        self.setLayout(layout)

    def copy_machine_code(self):
        QApplication.clipboard().setText(get_machine_code())
        QMessageBox.information(self, "复制", "机器码已复制到剪贴板")

    def check_code(self):
        machine_code = get_machine_code()
        code_input = self.input_code.text().strip()
        auth_info = load_auth_info()
        if auth_info and auth_info.get("machine_code") == machine_code:
            valid, msg = verify_auth_code(machine_code, auth_info["auth_code"], auth_info["expire"])
            if valid:
                self.accept()
                return
        expire_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
        valid, msg = verify_auth_code(machine_code, code_input, expire_str)
        if valid:
            save_auth_info(machine_code, code_input, expire_str)
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "失败", msg)

    def accept(self):
        self.close()
        self.main_window = PDFBrowser()
        self.main_window.show()

# ---------------- PDF 浏览器 ----------------
class PDFBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("加密 PDF 浏览器")
        self.resize(1200, 800)

        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        # 顶部按钮
        self.fullscreen_btn = QPushButton("全屏/退出全屏")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_layout.addWidget(self.fullscreen_btn)

        # Logo
        self.logo_label = QLabel()
        if os.path.exists(LOGO_FILE):
            pix = QPixmap(LOGO_FILE)
            self.logo_label.setPixmap(pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top_layout.addWidget(self.logo_label)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # 左右分割
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧 PDF 文件列表
        self.pdf_list = QListWidget()
        self.splitter.addWidget(self.pdf_list)
        self.pdf_list.itemClicked.connect(self.open_pdf)

        # 右侧 PDF 显示区域
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.pdf_label.setMinimumSize(800, 600)
        self.splitter.addWidget(self.pdf_label)

        self.splitter.setSizes([300, 900])  # 默认左侧宽度
        main_layout.addWidget(self.splitter, 1)

        self.setLayout(main_layout)

        self.pdf_dir = os.path.join(os.getcwd(), "pdfs")
        self.load_pdf_list()

        self.doc = None
        self.page_index = 0
        self.zoom = 1.0
        self.fullscreen_flag = False

    def load_pdf_list(self):
        files = []
        for root, dirs, filenames in os.walk(self.pdf_dir):
            for f in filenames:
                if f.lower().endswith(".pdf"):
                    files.append(os.path.join(root, f))
        self.pdf_list.clear()
        self.pdf_paths = files
        for path in files:
            self.pdf_list.addItem(os.path.splitext(os.path.basename(path))[0])

    def open_pdf(self, item):
        index = self.pdf_list.currentRow()
        path = self.pdf_paths[index]
        try:
            self.doc = fitz.open(path)
            self.page_index = 0
            self.zoom = 1.0
            self.show_page()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开失败: {e}")

    def show_page(self):
        if not self.doc:
            return
        page = self.doc.load_page(self.page_index)
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        self.pdf_label.setPixmap(QPixmap.fromImage(img))

    def toggle_fullscreen(self):
        if self.fullscreen_flag:
            self.showNormal()
            self.splitter.widget(0).show()  # 显示列表
            self.fullscreen_flag = False
        else:
            self.showFullScreen()
            self.splitter.widget(0).hide()  # 隐藏列表
            self.fullscreen_flag = True

    def wheelEvent(self, event):
        if self.doc:
            angle = event.angleDelta().y()
            factor = 1.1 if angle > 0 else 0.9
            self.zoom *= factor
            self.show_page()

    def keyPressEvent(self, event):
        if not self.doc:
            return
        if event.key() == Qt.Key_Right:
            if self.page_index < self.doc.page_count - 1:
                self.page_index += 1
                self.show_page()
        elif event.key() == Qt.Key_Left:
            if self.page_index > 0:
                self.page_index -= 1
                self.show_page()

# ----------------- 入口 -----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    auth_win = AuthWindow()
    auth_win.show()
    sys.exit(app.exec_())
