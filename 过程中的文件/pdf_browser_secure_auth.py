import sys
import os
import hashlib
import base64
import tempfile
import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QLineEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView

# ------------------- 配置 -------------------
EXPIRE_DAYS = 1  # 程序过期天数，可修改
ENCRYPTED_FOLDER = "encrypted_files"  # 打包的加密文件夹
# -----------------------------------------

def get_machine_code():
    """生成可复制的机器码"""
    import uuid
    mac = uuid.getnode()
    return f"{mac:012X}"

def check_expired():
    """检查程序是否过期"""
    install_file = os.path.join(tempfile.gettempdir(), "pdf_secure_install_date.txt")
    if os.path.exists(install_file):
        with open(install_file, "r") as f:
            date_str = f.read().strip()
        install_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    else:
        install_date = datetime.datetime.now()
        with open(install_file, "w") as f:
            f.write(install_date.strftime("%Y-%m-%d"))
    return (datetime.datetime.now() - install_date).days > EXPIRE_DAYS

def verify_code(machine_code, code_input):
    """简单示例验证码验证（可自行修改算法）"""
    # 例如用 SHA256(machine_code + secret) 截取前24位
    SECRET_KEY = "MySecretKey123"
    digest = hashlib.sha256((machine_code + SECRET_KEY).encode()).hexdigest()
    return digest[:24].upper() == code_input.upper()

# ------------------- GUI -------------------
# 授权窗口部分
class AuthWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 浏览器授权")
        self.resize(500, 250)  # 窗口更大
        layout = QVBoxLayout()

        self.machine_label = QLabel("机器码（可复制）：")
        self.machine_code_edit = QLineEdit(get_machine_code())
        self.machine_code_edit.setReadOnly(True)
        self.copy_btn = QPushButton("复制")
        self.copy_btn.clicked.connect(self.copy_code)

        self.code_label = QLabel("请输入授权码：")
        self.code_edit = QLineEdit()
        self.ok_btn = QPushButton("确认")
        self.ok_btn.clicked.connect(self.check_code)

        machine_layout = QHBoxLayout()
        machine_layout.addWidget(self.machine_code_edit)
        machine_layout.addWidget(self.copy_btn)

        code_layout = QHBoxLayout()
        code_layout.addWidget(self.code_edit)
        code_layout.addWidget(self.ok_btn)

        layout.addWidget(self.machine_label)
        layout.addLayout(machine_layout)
        layout.addWidget(self.code_label)
        layout.addLayout(code_layout)
        self.setLayout(layout)

        self.accepted = False  # 默认未通过验证

    def copy_code(self):
        self.machine_code_edit.selectAll()
        self.machine_code_edit.copy()

    def check_code(self):
        if check_expired():
            QMessageBox.critical(self, "错误", "程序已过期，无法使用")
            sys.exit()
        code_input = self.code_edit.text()
        if verify_code(get_machine_code(), code_input):
            self.accepted = True
            self.close()  # 关闭授权窗口，但程序继续运行
        else:
            QMessageBox.warning(self, "错误", "授权码不正确")

class PDFViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("加密 PDF 浏览器")
        self.resize(1000, 700)
        self._pdf_fullscreen = False

        # 文件列表区域
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("PDF 文件")
        self.tree.itemClicked.connect(self.open_pdf)
        self.left_widget = self.tree

        # PDF 显示区域
        self.pdf_view = QWebEngineView()

        # 按钮
        self.full_btn = QPushButton("全屏显示 PDF")
        self.full_btn.clicked.connect(self.toggle_pdf_fullscreen)
        self.zoom_in_btn = QPushButton("放大")
        self.zoom_out_btn = QPushButton("缩小")
        self.zoom_in_btn.clicked.connect(lambda: self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() + 0.1))
        self.zoom_out_btn.clicked.connect(lambda: self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() - 0.1))

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.full_btn)
        button_layout.addWidget(self.zoom_in_btn)
        button_layout.addWidget(self.zoom_out_btn)
        self.button_layout_widget = QWidget()
        self.button_layout_widget.setLayout(button_layout)

        # 布局
        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.pdf_view)
        splitter.setStretchFactor(1, 5)

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.button_layout_widget)
        self.setLayout(main_layout)

        self.load_encrypted_files()

    def load_encrypted_files(self):
        """加载内置加密 PDF 文件到文件树"""
        if hasattr(sys, "_MEIPASS"):
            base_path = os.path.join(sys._MEIPASS, ENCRYPTED_FOLDER)
        else:
            base_path = ENCRYPTED_FOLDER

        for root, dirs, files in os.walk(base_path):
            for fname in files:
                if fname.endswith(".enc"):
                    rel_path = os.path.relpath(os.path.join(root, fname), base_path)
                    display_name = os.path.splitext(rel_path)[0]  # 去掉扩展名
                    item = QTreeWidgetItem([display_name])
                    item.full_path = os.path.join(root, fname)
                    self.tree.addTopLevelItem(item)

    def open_pdf(self, item):
        """解密并显示 PDF"""
        enc_path = item.full_path
        with open(enc_path, "rb") as f:
            data = f.read()
        # 简单解密示例：base64 解码
        try:
            pdf_bytes = base64.b64decode(data)
        except:
            QMessageBox.warning(self, "错误", "无法解密 PDF")
            return
        tmp_pdf = os.path.join(tempfile.gettempdir(), "tmp.pdf")
        with open(tmp_pdf, "wb") as f:
            f.write(pdf_bytes)
        self.pdf_view.load(f"file:///{tmp_pdf}")

    def toggle_pdf_fullscreen(self):
        if self._pdf_fullscreen:
            self.left_widget.show()
            self.button_layout_widget.show()
            self._pdf_fullscreen = False
            self.full_btn.setText("全屏显示 PDF")
        else:
            self.left_widget.hide()
            self.button_layout_widget.hide()
            self._pdf_fullscreen = True
            self.full_btn.setText("退出 PDF 全屏")

# ------------------- 主程序 -------------------
def main():
    app = QApplication(sys.argv)

    auth = AuthWindow()
    auth.accepted = False
    auth.show()
    app.exec_()
    if not getattr(auth, "accepted", False):
        sys.exit()

    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
