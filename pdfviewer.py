import sys, os, hashlib, datetime, uuid, json, base64, tempfile
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QMessageBox, QLineEdit, QSplitter, QDialog, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
import fitz  # PyMuPDF

# ---------------- 配置参数 ----------------
SECRET_KEY = "MySecretKey123"
CODE_LENGTH = 24
AUTH_FILE = "auth_info.json"
# 新增：记录最近运行时间的文件
LAST_RUN_FILE = "last_run_time.json"
LOGO_FILE_NAME = "logo.png"  # Logo文件名


# 获取资源路径（兼容所有环境）
def get_resource_path(relative_path):
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(base_path, relative_path))
    except Exception as e:
        QMessageBox.critical(None, "路径错误", f"获取资源路径失败: {str(e)}")
        return ""


# 加密文件目录
ENC_FOLDER = get_resource_path("encrypted_files")


# 获取Logo路径
def get_logo_path():
    return get_resource_path(LOGO_FILE_NAME)


# ---------------- 时间防篡改逻辑（核心新增） ----------------
def get_last_run_time():
    """获取最近一次运行的时间戳（精确到分钟）"""
    try:
        user_dir = os.path.expanduser("~")
        last_run_path = os.path.join(user_dir, LAST_RUN_FILE)
        if os.path.exists(last_run_path):
            with open(last_run_path, "r") as f:
                data = json.load(f)
            # 验证文件未被篡改
            expected_checksum = hashlib.sha256(f"{data['timestamp']}{SECRET_KEY}".encode()).hexdigest()
            if data["checksum"] == expected_checksum:
                return data["timestamp"]
    except Exception as e:
        print(f"读取最近运行时间失败: {str(e)}")  # 不弹窗，内部处理
    return None


def update_last_run_time():
    """更新最近运行时间（精确到分钟，避免频繁写入）"""
    try:
        # 精确到分钟（减少写入次数，同时保留防篡改精度）
        current_ts = int(datetime.datetime.now().timestamp() // 60 * 60)
        user_dir = os.path.expanduser("~")
        last_run_path = os.path.join(user_dir, LAST_RUN_FILE)
        # 加密存储（防止直接修改文件）
        data = {
            "timestamp": current_ts,
            "checksum": hashlib.sha256(f"{current_ts}{SECRET_KEY}".encode()).hexdigest()
        }
        with open(last_run_path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"更新最近运行时间失败: {str(e)}")


def check_time_tampering():
    """检查系统时间是否被倒退（防篡改核心）"""
    current_ts = int(datetime.datetime.now().timestamp())
    last_ts = get_last_run_time()

    if last_ts is None:
        # 首次运行，直接记录当前时间
        update_last_run_time()
        return True

    # 允许1分钟误差（系统时间同步可能有微小偏差）
    if current_ts < last_ts - 60:
        # 系统时间比上次运行时间早，判定为被篡改
        return False
    else:
        # 时间正常，更新最近运行时间
        update_last_run_time()
        return True


# ---------------- 授权函数（集成时间防篡改） ----------------
def get_machine_code():
    try:
        return f"{uuid.getnode():012X}"
    except Exception as e:
        QMessageBox.critical(None, "机器码错误", f"获取机器码失败: {str(e)}")
        return "ERROR_MACHINE_CODE"


def generate_auth_code(machine_code, valid_days=1):
    # 生成授权码前先检查时间是否正常
    if not check_time_tampering():
        raise ValueError("系统时间异常，可能被篡改")

    expire_date = datetime.datetime.now() + datetime.timedelta(days=valid_days)
    expire_str = expire_date.strftime("%Y%m%d")
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    return digest[:CODE_LENGTH].upper(), expire_str


def verify_auth_code(machine_code, auth_code_input, expire_str):
    # 验证授权前先检查时间是否正常
    if not check_time_tampering():
        return False, "系统时间异常，可能被篡改"

    today_str = datetime.datetime.now().strftime("%Y%m%d")
    if today_str > str(expire_str):
        return False, "授权码已过期"
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    expected = digest[:CODE_LENGTH].upper()
    return (expected == auth_code_input.upper(),
            "授权码有效" if expected == auth_code_input.upper() else "授权码不匹配")


def save_auth_info(machine_code, auth_code, expire_str):
    try:
        info = {"machine_code": machine_code, "auth_code": auth_code, "expire": expire_str}
        user_dir = os.path.expanduser("~")
        auth_path = os.path.join(user_dir, AUTH_FILE)
        with open(auth_path, "w") as f:
            json.dump(info, f)
    except Exception as e:
        QMessageBox.warning(None, "保存失败", f"授权信息保存失败: {str(e)}")


def load_auth_info():
    try:
        user_dir = os.path.expanduser("~")
        auth_path = os.path.join(user_dir, AUTH_FILE)
        if os.path.exists(auth_path):
            with open(auth_path, "r") as f:
                return json.load(f)
        return None
    except Exception as e:
        QMessageBox.warning(None, "加载失败", f"授权信息加载失败: {str(e)}")
        return None


def is_auth_valid():
    # 检查授权有效性前先验证时间
    if not check_time_tampering():
        QMessageBox.critical(None, "时间异常", "系统时间可能被篡改，授权验证失败")
        return False

    machine_code = get_machine_code()
    auth_info = load_auth_info()
    if auth_info and auth_info.get("machine_code") == machine_code:
        valid, _ = verify_auth_code(machine_code, auth_info["auth_code"], auth_info["expire"])
        return valid
    return False


# ---------------- 解密函数 ----------------
def decrypt_file(encrypted_path):
    try:
        if not os.path.exists(encrypted_path):
            raise FileNotFoundError(f"加密文件不存在: {encrypted_path}")
        with open(encrypted_path, "rb") as f:
            enc_data = f.read()
        return base64.b64decode(enc_data)
    except Exception as e:
        raise ValueError(f"解密失败: {str(e)}")


# ---------------- 授权窗口 ----------------
class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setModal(True)
        self.resize(700, 520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Logo
        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            try:
                pix = QPixmap(logo_path)
                self.logo_label.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception as e:
                QMessageBox.warning(self, "Logo错误", f"加载Logo失败: {str(e)}")
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)

        # 机器码
        self.label_mc = QLabel(f"机器码: {get_machine_code()}")
        layout.addWidget(self.label_mc, alignment=Qt.AlignCenter)

        # 复制按钮
        self.copy_btn = QPushButton("复制机器码")
        self.copy_btn.clicked.connect(self.copy_machine_code)
        layout.addWidget(self.copy_btn, alignment=Qt.AlignCenter)

        # 授权码输入
        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("请输入授权码")
        self.input_code.setMinimumHeight(70)
        layout.addWidget(self.input_code)

        # 验证按钮
        self.ok_btn = QPushButton("验证")
        self.ok_btn.clicked.connect(self.check_code)
        layout.addWidget(self.ok_btn)

        self.setLayout(layout)

    def copy_machine_code(self):
        try:
            QApplication.clipboard().setText(get_machine_code())
            QMessageBox.information(self, "成功", "机器码已复制到剪贴板")
        except Exception as e:
            QMessageBox.warning(self, "复制失败", f"无法复制: {str(e)}")

    def check_code(self):
        machine_code = get_machine_code()
        code_input = self.input_code.text().strip()
        if not code_input:
            QMessageBox.warning(self, "输入错误", "请输入授权码")
            return

        try:
            # 验证前先检查时间
            if not check_time_tampering():
                QMessageBox.critical(self, "时间异常", "系统时间可能被篡改，验证失败")
                return

            expire_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y%m%d")
            valid, msg = verify_auth_code(machine_code, code_input, expire_str)
            if valid:
                save_auth_info(machine_code, code_input, expire_str)
                QMessageBox.information(self, "成功", msg)
                self.accept()
            else:
                QMessageBox.warning(self, "失败", msg)
        except Exception as e:
            QMessageBox.critical(self, "验证错误", f"验证过程出错: {str(e)}")


# ---------------- PDF 浏览器 ----------------
class PDFBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.temp_pdf = None  # 临时文件路径
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("加密 PDF 浏览器")
        self.resize(1200, 800)

        main_layout = QVBoxLayout()

        # 顶部区域
        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_widget.setLayout(top_layout)

        # Logo
        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            try:
                pix = QPixmap(logo_path)
                self.logo_label.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception as e:
                QMessageBox.warning(self, "Logo错误", f"加载Logo失败: {str(e)}")
        top_layout.addWidget(self.logo_label)

        # 全屏按钮
        self.fullscreen_btn = QPushButton("全屏/退出全屏")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_layout.addWidget(self.fullscreen_btn)
        top_layout.addStretch()
        main_layout.addWidget(top_widget)

        # 分割器
        self.splitter = QSplitter(Qt.Horizontal)

        # 左侧目录树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.splitter.addWidget(self.tree)
        self.tree.itemClicked.connect(self.open_encrypted_pdf)

        # 右侧PDF显示
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

        # 加载目录
        self.load_encrypted_tree()

        # 初始化变量
        self.doc = None
        self.zoom = 1.0
        self.fullscreen_flag = False

    def load_encrypted_tree(self):
        self.tree.clear()
        enc_folder = get_resource_path("encrypted_files")
        if not enc_folder or not os.path.exists(enc_folder):
            QMessageBox.warning(self, "目录错误", f"加密文件目录不存在: {enc_folder}")
            return

        try:
            if not os.listdir(enc_folder):
                QMessageBox.information(self, "提示", "加密文件目录为空")
                return

            # 递归添加目录
            def add_items(parent, path):
                for f in sorted(os.listdir(path)):
                    fp = os.path.join(path, f)
                    if os.path.isdir(fp):
                        dir_item = QTreeWidgetItem([f])
                        parent.addChild(dir_item)
                        add_items(dir_item, fp)
                    elif f.lower().endswith(".enc"):
                        display_name = f[:-4] if f.endswith(".enc") else f
                        file_item = QTreeWidgetItem([display_name])
                        parent.addChild(file_item)

            # 加载根目录
            for f in sorted(os.listdir(enc_folder)):
                fp = os.path.join(enc_folder, f)
                if os.path.isdir(fp):
                    dir_item = QTreeWidgetItem([f])
                    self.tree.addTopLevelItem(dir_item)
                    add_items(dir_item, fp)
                elif f.lower().endswith(".enc"):
                    display_name = f[:-4] if f.endswith(".enc") else f
                    file_item = QTreeWidgetItem([display_name])
                    self.tree.addTopLevelItem(file_item)

            self.tree.expandAll()
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"加载目录失败: {str(e)}")

    def open_encrypted_pdf(self, item, column):
        # 打开文件前先检查时间是否正常
        if not check_time_tampering():
            QMessageBox.critical(self, "时间异常", "系统时间可能被篡改，无法打开文件")
            return

        # 清理之前的临时文件
        self.clean_temp_file()

        try:
            # 获取加密文件路径
            enc_path = self.get_encrypted_item_path(item)
            if not enc_path or not os.path.exists(enc_path) or not enc_path.lower().endswith(".enc"):
                QMessageBox.warning(self, "文件错误", "未找到有效的加密文件")
                return

            # 解密文件
            decrypted_data = decrypt_file(enc_path)
            if not decrypted_data:
                QMessageBox.warning(self, "解密错误", "解密后文件为空")
                return

            # 在系统临时目录创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', mode='wb') as f:
                f.write(decrypted_data)
                self.temp_pdf = f.name

            # 打开PDF
            self.doc = fitz.open(self.temp_pdf)
            self.show_all_pages()

        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"无法打开文件: {str(e)}")
            self.clean_temp_file()

    def get_encrypted_item_path(self, item):
        names = []
        current_item = item
        while current_item:
            names.insert(0, current_item.text(0))
            current_item = current_item.parent()

        if not names:
            return ""

        # 补全.enc后缀
        enc_filename = names[-1] if names[-1].endswith(".enc") else f"{names[-1]}.enc"
        names[-1] = enc_filename
        return get_resource_path(os.path.join("encrypted_files", *names))

    def show_all_pages(self):
        # 清空现有页面
        for i in reversed(range(self.pdf_layout.count())):
            widget = self.pdf_layout.itemAt(i).widget()
            if widget:
                self.pdf_layout.removeWidget(widget)
                widget.deleteLater()

        if not self.doc:
            return

        try:
            # 自适应宽度
            container_width = self.scroll_area.viewport().width() - 20
            for page_idx in range(self.doc.page_count):
                page = self.doc.load_page(page_idx)
                zoom = container_width / page.rect.width
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                lbl = QLabel()
                lbl.setPixmap(QPixmap.fromImage(img))
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.pdf_layout.addWidget(lbl)
            self.pdf_layout.addStretch()
        except Exception as e:
            QMessageBox.warning(self, "显示错误", f"无法显示PDF页面: {str(e)}")

    def wheelEvent(self, event):
        if not self.doc:
            return
        angle = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            self.zoom *= 1.1 if angle > 0 else 0.9
            self.show_all_pages_with_zoom()
        else:
            super().wheelEvent(event)

    def show_all_pages_with_zoom(self):
        for i in reversed(range(self.pdf_layout.count())):
            widget = self.pdf_layout.itemAt(i).widget()
            if widget:
                self.pdf_layout.removeWidget(widget)
                widget.deleteLater()

        if not self.doc:
            return

        try:
            for page_idx in range(self.doc.page_count):
                page = self.doc.load_page(page_idx)
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                lbl = QLabel()
                lbl.setPixmap(QPixmap.fromImage(img))
                lbl.setAlignment(Qt.AlignCenter)
                self.pdf_layout.addWidget(lbl)
            self.pdf_layout.addStretch()
        except Exception as e:
            QMessageBox.warning(self, "缩放错误", f"缩放页面失败: {str(e)}")

    def toggle_fullscreen(self):
        if self.fullscreen_flag:
            self.showNormal()
            self.splitter.widget(0).show()
            self.fullscreen_flag = False
        else:
            self.showFullScreen()
            self.splitter.widget(0).hide()
            self.fullscreen_flag = True

    def clean_temp_file(self):
        """清理临时PDF文件"""
        if hasattr(self, 'temp_pdf') and self.temp_pdf and os.path.exists(self.temp_pdf):
            try:
                os.remove(self.temp_pdf)
            except Exception as e:
                print(f"清理临时文件失败: {str(e)}")
        self.temp_pdf = None
        self.doc = None

    def closeEvent(self, event):
        self.clean_temp_file()
        event.accept()


# ---------------- 入口函数 ----------------
def main():
    try:
        # 程序启动时先检查时间是否正常
        if not check_time_tampering():
            QMessageBox.critical(None, "时间异常", "系统时间可能被篡改，程序无法启动")
            sys.exit(1)

        app = QApplication(sys.argv)
        # 确保中文显示正常
        font = app.font()
        font.setFamily("SimHei")
        app.setFont(font)

        main_win = PDFBrowser()
        if is_auth_valid():
            main_win.showMaximized()
        else:
            auth_dialog = AuthDialog(parent=main_win)
            if auth_dialog.exec_() == QDialog.Accepted:
                main_win.showMaximized()
            else:
                sys.exit(0)
        sys.exit(app.exec_())
    except Exception as e:
        QMessageBox.critical(None, "程序错误", f"程序启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()