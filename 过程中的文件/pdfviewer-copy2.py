import sys, os, hashlib, datetime, uuid, json, base64
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QMessageBox, QLineEdit, QSplitter, QDialog, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
import fitz  # PyMuPDF

# ---------------- 配置参数 ----------------
SECRET_KEY = "MySecretKey123"
CODE_LENGTH = 24
AUTH_FILE = "../auth_info.json"
LOGO_FILE = "../logo.png"  # 可替换

# ENC_FOLDER = "encrypted_files"  # 加密文件目录
def get_resource_path(relative_path):
    """获取资源路径（兼容开发环境和打包后的EXE）"""
    if getattr(sys, 'frozen', False):
        # 打包后：资源位于sys._MEIPASS临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：资源位于当前工作目录
        base_path = os.path.abspath("..")
    return os.path.join(base_path, relative_path)
ENC_FOLDER = get_resource_path("../encrypted_files")

# if os.path.exists(LOGO_FILE):
#     # 改为
#     LOGO_PATH = get_resource_path(LOGO_FILE)
#     if os.path.exists(LOGO_PATH):
#         pix = QPixmap(LOGO_PATH)
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


def is_auth_valid():
    machine_code = get_machine_code()
    auth_info = load_auth_info()
    if auth_info and auth_info.get("machine_code") == machine_code:
        valid, msg = verify_auth_code(machine_code, auth_info["auth_code"], auth_info["expire"])
        return valid
    return False


# ---------------- 解密函数 ----------------
def decrypt_file(encrypted_path):
    """解密base64加密的文件"""
    try:
        with open(encrypted_path, "rb") as f:
            enc_data = f.read()
        # 解密base64数据（与加密逻辑对应）
        decrypted_data = base64.b64decode(enc_data)
        return decrypted_data
    except Exception as e:
        raise ValueError(f"解密失败: {str(e)}")





# ---------------- 授权窗口 ----------------
class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setModal(True)  # 阻塞主窗口
        self.resize(700, 520)
        layout = QVBoxLayout()

        # Logo
        self.logo_label = QLabel()
        if os.path.exists(LOGO_FILE):
            pix = QPixmap(LOGO_FILE)
            self.logo_label.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)

        self.label_mc = QLabel(f"机器码: {get_machine_code()}")
        layout.addWidget(self.label_mc, alignment=Qt.AlignCenter)

        self.copy_btn = QPushButton("复制机器码")
        self.copy_btn.clicked.connect(self.copy_machine_code)
        layout.addWidget(self.copy_btn, alignment=Qt.AlignCenter)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("请输入授权码")
        self.input_code.setMinimumHeight(70)
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
        expire_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
        valid, msg = verify_auth_code(machine_code, code_input, expire_str)
        if valid:
            save_auth_info(machine_code, code_input, expire_str)
            QMessageBox.information(self, "成功", msg)
            if self.parent():
                self.parent().showMaximized()
            self.accept()
        else:
            QMessageBox.warning(self, "失败", msg)


# ---------------- PDF 浏览器（支持解密） ----------------
class PDFBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("加密 PDF 浏览器")
        self.resize(1200, 800)

        main_layout = QVBoxLayout()

        # 顶部 Logo + 按钮
        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_widget.setLayout(top_layout)

        self.logo_label = QLabel()
        if os.path.exists(LOGO_FILE):
            pix = QPixmap(LOGO_FILE)
            self.logo_label.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top_layout.addWidget(self.logo_label)

        self.fullscreen_btn = QPushButton("全屏/退出全屏")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_layout.addWidget(self.fullscreen_btn)
        top_layout.addStretch()
        main_layout.addWidget(top_widget)

        # 左右分割
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧目录树（显示加密文件）
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.splitter.addWidget(self.tree)
        self.tree.itemClicked.connect(self.open_encrypted_pdf)  # 改为解密打开

        # 右侧 PDF 显示
        self.scroll_area = QScrollArea()
        self.pdf_container = QWidget()
        self.pdf_layout = QVBoxLayout()
        self.pdf_container.setLayout(self.pdf_layout)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.pdf_container)
        self.splitter.addWidget(self.scroll_area)

        self.splitter.setSizes([120, 1080])
        main_layout.addWidget(self.splitter, 1)
        self.setLayout(main_layout)

        # 加载加密文件目录（关键修改）
        self.load_encrypted_tree()

        self.doc = None
        self.zoom = 1.0
        self.fullscreen_flag = False
        self.current_page = 0

    def load_encrypted_tree(self):
        """加载encrypted_files目录下的加密文件结构"""
        self.tree.clear()
        # if not os.path.exists(ENC_FOLDER):
        #     QMessageBox.warning(self, "提示", f"未找到加密文件目录: {ENC_FOLDER}")
        #     return
        enc_folder = get_resource_path("../encrypted_files")
        if not os.path.exists(enc_folder) or not os.listdir(enc_folder):
            QMessageBox.warning(self, "提示", f"未找到加密文件目录: {enc_folder}")
            return

        # 递归添加加密文件目录结构
        def add_items(parent, path):
            for f in sorted(os.listdir(path)):
                fp = os.path.join(path, f)
                if os.path.isdir(fp):
                    # 目录节点
                    dir_item = QTreeWidgetItem([f])
                    parent.addChild(dir_item)
                    add_items(dir_item, fp)
                elif f.lower().endswith(".enc"):
                    # 加密文件节点（去掉.enc后缀显示）
                    display_name = f[:-4] if f.endswith(".enc") else f
                    file_item = QTreeWidgetItem([display_name])
                    parent.addChild(file_item)

        # 加载根目录
        for f in sorted(os.listdir(ENC_FOLDER)):
            fp = os.path.join(ENC_FOLDER, f)
            if os.path.isdir(fp):
                dir_item = QTreeWidgetItem([f])
                self.tree.addTopLevelItem(dir_item)
                add_items(dir_item, fp)
            elif f.lower().endswith(".enc"):
                display_name = f[:-4] if f.endswith(".enc") else f
                file_item = QTreeWidgetItem([display_name])
                self.tree.addTopLevelItem(file_item)

        self.tree.expandAll()

    def open_encrypted_pdf(self, item, column):
        """解密并打开选中的加密PDF文件"""
        # 获取加密文件的完整路径
        enc_path = self.get_encrypted_item_path(item)
        if not enc_path or not enc_path.lower().endswith(".enc"):
            return

        try:
            # 1. 解密文件
            decrypted_data = decrypt_file(enc_path)

            # 2. 保存为临时PDF文件
            temp_pdf = os.path.join(os.path.dirname(enc_path), f"temp_{os.path.basename(enc_path)[:-4]}.pdf")
            with open(temp_pdf, "wb") as f:
                f.write(decrypted_data)

            # 3. 打开临时PDF
            self.doc = fitz.open(temp_pdf)
            self.current_page = 0
            self.show_all_pages()

            # 4. 注册程序退出时删除临时文件
            self.temp_pdf = temp_pdf

        except Exception as e:
            QMessageBox.warning(self, "错误", f"处理失败: {str(e)}")

    def get_encrypted_item_path(self, item):
        """获取加密文件在encrypted_files中的完整路径"""
        names = []
        while item:
            names.insert(0, item.text(0))
            item = item.parent()
        # 拼接路径时补回.enc后缀
        enc_filename = names[-1] if names[-1].endswith(".enc") else f"{names[-1]}.enc"
        names[-1] = enc_filename
        # return os.path.join(ENC_FOLDER, *names)
        return get_resource_path(os.path.join("../encrypted_files", *names))

    def show_all_pages(self):
        """显示PDF所有页面"""
        if not self.doc:
            return
        # 清空现有页面
        for i in reversed(range(self.pdf_layout.count())):
            widget_to_remove = self.pdf_layout.itemAt(i).widget()
            if widget_to_remove:
                self.pdf_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

        # 自适应宽度显示
        container_width = self.scroll_area.viewport().width() - 20  # 留边距
        for page_index in range(self.doc.page_count):
            page = self.doc.load_page(page_index)
            zoom_x = container_width / page.rect.width
            mat = fitz.Matrix(zoom_x, zoom_x)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            lbl = QLabel()
            lbl.setPixmap(QPixmap.fromImage(img))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.pdf_layout.addWidget(lbl)

        self.pdf_layout.addStretch()

    def wheelEvent(self, event):
        """处理滚轮缩放"""
        if not self.doc:
            return
        angle = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.1 if angle > 0 else 0.9
            self.zoom *= factor
            self.show_all_pages_with_zoom()
        else:
            # 普通滚动
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - angle
            )

    def show_all_pages_with_zoom(self):
        """按缩放比例显示页面"""
        if not self.doc:
            return
        for i in reversed(range(self.pdf_layout.count())):
            widget_to_remove = self.pdf_layout.itemAt(i).widget()
            if widget_to_remove:
                self.pdf_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

        for page_index in range(self.doc.page_count):
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            lbl = QLabel()
            lbl.setPixmap(QPixmap.fromImage(img))
            lbl.setAlignment(Qt.AlignCenter)
            self.pdf_layout.addWidget(lbl)

        self.pdf_layout.addStretch()

    def toggle_fullscreen(self):
        """切换全屏模式"""
        if self.fullscreen_flag:
            self.showMaximized()
            self.splitter.widget(0).show()
            self.fullscreen_flag = False
        else:
            self.showFullScreen()
            self.splitter.widget(0).hide()
            self.fullscreen_flag = True

    def closeEvent(self, event):
        """程序退出时清理临时文件"""
        if hasattr(self, 'temp_pdf') and os.path.exists(self.temp_pdf):
            try:
                os.remove(self.temp_pdf)
            except:
                pass
        event.accept()


# ---------------- 入口 -----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = PDFBrowser()

    if is_auth_valid():
        main_win.showMaximized()  # 已验证直接显示
    else:
        auth_dialog = AuthDialog(parent=main_win)
        if auth_dialog.exec_() == QDialog.Accepted:
            main_win.showMaximized()
        else:
            sys.exit(0)

    sys.exit(app.exec_())
