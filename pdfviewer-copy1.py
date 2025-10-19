import sys, os, hashlib, datetime, uuid, json, base64, tempfile, socket, struct, requests, time
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QMessageBox, QLineEdit, QSplitter, QDialog, QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
import fitz  # PyMuPDF

# ---------------- 配置参数 ----------------
SECRET_KEY = "MySecretKey123"
CODE_LENGTH = 24
AUTH_FILE = "auth_info.json"
# 新增：存储多重时间基准的文件
TIME_BASE_FILE = "time_base.json"
LOGO_FILE_NAME = "logo.png"

# NTP服务器（按延迟排序）
NTP_SERVERS = [
    "cn.pool.ntp.org",  # 延迟: 44.5ms
    "ntp.tencent.com",  # 延迟: 60.26ms
    "time1.aliyun.com",  # 延迟: 67.54ms
    "ntp.aliyun.com",  # 延迟: 74.03ms
    "time2.aliyun.com"  # 延迟: 77.92ms
]
NTP_PORT = 123
NTP_PACKET_FORMAT = "!12I"
NTP_DELTA = 2208988800  # 1970-01-01到1900-01-01的秒数
BEIJING_TIME_DELTA = datetime.timedelta(hours=8)  # UTC+8

# HTTP时间接口（备用）
HTTP_TIME_APIS = [
    {
        "url": "http://api.m.taobao.com/rest/api3.do?api=mtop.common.getTimestamp",
        "parser": lambda resp: datetime.datetime.fromtimestamp(int(resp.json()["data"]["t"]) / 1000)
    },
    {
        "url": "https://time.tencent.com/",
        "parser": lambda resp: datetime.datetime.strptime(resp.text.strip(), "%Y-%m-%d %H:%M:%S")
    }
]


# ---------------- 资源路径函数 ----------------
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


# 新增：获取程序主文件（自身）的路径
def get_main_executable_path():
    if getattr(sys, 'frozen', False):
        return sys.executable  # 打包后的EXE路径
    else:
        return os.path.abspath(__file__)  # 开发环境下的脚本路径


ENC_FOLDER = get_resource_path("encrypted_files")


def get_logo_path():
    return get_resource_path(LOGO_FILE_NAME)


# ---------------- 时间基准初始化（核心改进） ----------------
def init_time_base():
    """初始化时间基准：记录程序文件修改时间和初始单调时钟"""
    time_base_path = os.path.join(os.path.expanduser("~"), TIME_BASE_FILE)
    if os.path.exists(time_base_path):
        return

    try:
        # 1. 获取程序主文件的最后修改时间（操作系统维护，难以篡改）
        main_file_path = get_main_executable_path()
        file_mtime = os.path.getmtime(main_file_path)  # 时间戳（秒）
        file_mtime_dt = datetime.datetime.fromtimestamp(file_mtime)

        # 2. 获取系统单调时钟（从启动到现在的累计时间，不受日期影响）
        monotonic_initial = time.monotonic()

        # 3. 获取首次网络时间（作为辅助基准）
        trusted_time, _ = get_trusted_time()
        network_time_ts = trusted_time.timestamp() if trusted_time else None

        # 加密存储时间基准
        data = {
            "file_mtime": file_mtime,
            "monotonic_initial": monotonic_initial,
            "network_time_ts": network_time_ts,
            "checksum": hashlib.sha256(f"{file_mtime}|{monotonic_initial}|{SECRET_KEY}".encode()).hexdigest()
        }

        with open(time_base_path, "w") as f:
            json.dump(data, f)

    except Exception as e:
        QMessageBox.critical(None, "时间基准初始化失败", f"程序关键验证机制初始化失败: {str(e)}", QMessageBox.Ok)
        sys.exit(1)


def verify_time_base():
    """验证时间基准是否有效，防止通过修改系统时间绕过"""
    time_base_path = os.path.join(os.path.expanduser("~"), TIME_BASE_FILE)
    if not os.path.exists(time_base_path):
        init_time_base()
        return True

    try:
        with open(time_base_path, "r") as f:
            data = json.load(f)

        # 1. 校验时间基准文件未被篡改
        expected_checksum = hashlib.sha256(
            f"{data['file_mtime']}|{data['monotonic_initial']}|{SECRET_KEY}".encode()).hexdigest()
        if data["checksum"] != expected_checksum:
            raise ValueError("时间基准文件已被篡改")

        # 2. 验证程序文件修改时间未变（防止替换旧版本程序）
        main_file_path = get_main_executable_path()
        current_file_mtime = os.path.getmtime(main_file_path)
        if abs(current_file_mtime - data["file_mtime"]) > 30:  # 允许30秒误差（文件复制耗时）
            raise ValueError("程序文件已被修改或替换，授权失效")

        # 3. 验证单调时钟是否合理（累计时间不能减少）
        current_monotonic = time.monotonic()
        if current_monotonic < data["monotonic_initial"] - 5:  # 允许5秒误差（系统休眠唤醒）
            raise ValueError("系统时间异常（可能通过重启或修改时钟绕过）")

        # 4. 若存在网络时间基准，验证当前时间与历史网络时间的逻辑合理性
        if data["network_time_ts"]:
            trusted_time, _ = get_trusted_time()
            current_network_ts = trusted_time.timestamp()
            # 允许网络时间±2天误差（考虑离线情况），但不能早于历史网络时间太多
            if current_network_ts < data["network_time_ts"] - 86400 * 2:
                raise ValueError("当前时间早于历史记录，可能被篡改")

        return True

    except Exception as e:
        QMessageBox.critical(None, "时间验证失败", f"检测到时间异常或程序被篡改: {str(e)}", QMessageBox.Ok)
        sys.exit(1)


# ---------------- 时间获取核心逻辑 ----------------
class TimeFetcherThread(QThread):
    time_fetched = pyqtSignal(datetime.datetime, str)  # (北京时间, 来源/错误信息)

    def run(self):
        # 1. 尝试NTP服务器
        for server in NTP_SERVERS:
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                data = b'\x1b' + 47 * b'\0'
                client.sendto(data, (server, NTP_PORT))
                client.settimeout(3)
                data, _ = client.recvfrom(1024)
                client.close()

                unpacked = struct.unpack(NTP_PACKET_FORMAT, data[0:48])
                transmit_timestamp = unpacked[10] + float(unpacked[11]) / 2 ** 32
                utc_time = datetime.datetime.utcfromtimestamp(transmit_timestamp - NTP_DELTA)
                beijing_time = utc_time + BEIJING_TIME_DELTA
                self.time_fetched.emit(beijing_time, f"NTP({server})")
                return
            except:
                continue

        # 2. 尝试HTTP接口
        for api in HTTP_TIME_APIS:
            try:
                response = requests.get(api["url"], timeout=3, verify=False)
                beijing_time = api["parser"](response)
                self.time_fetched.emit(beijing_time, f"HTTP({api['url']})")
                return
            except:
                continue

        # 3. 所有方式失败，返回本地时间
        local_time = datetime.datetime.now()
        self.time_fetched.emit(local_time, f"本地时间（网络时间获取失败）")


def get_trusted_time():
    thread = TimeFetcherThread()
    result = [None, ""]

    def on_time_fetched(time, source):
        result[0] = time
        result[1] = source

    thread.time_fetched.connect(on_time_fetched)
    thread.start()
    thread.wait(5000)

    if result[0] is not None:
        if "本地时间" in result[1]:
            QMessageBox.warning(None, "时间警告",
                                "无法获取网络时间，将使用本地时间。\n"
                                "请注意：本地时间可能被篡改，导致授权校验不准确。")
        return result[0], result[1]
    else:
        local_time = datetime.datetime.now()
        QMessageBox.critical(None, "时间获取失败", "无法通过网络获取时间，强制使用本地时间！")
        return local_time, "强制本地时间"


# ---------------- 授权函数（强化校验） ----------------
def get_machine_code():
    try:
        return f"{uuid.getnode():012X}"
    except Exception as e:
        QMessageBox.critical(None, "机器码错误", f"获取机器码失败: {str(e)}")
        return "ERROR_MACHINE_CODE"


def generate_auth_code(machine_code, valid_days=1):
    verify_time_base()  # 生成授权码前先验证时间基准
    trusted_time, _ = get_trusted_time()
    expire_date = trusted_time + datetime.timedelta(days=valid_days)
    expire_str = expire_date.strftime("%Y%m%d")
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    return digest[:CODE_LENGTH].upper(), expire_str


def verify_auth_code(machine_code, auth_code_input, expire_str):
    # 核心改进：验证授权前先校验时间基准
    if not verify_time_base():
        return False, "时间基准验证失败"

    trusted_time, time_source = get_trusted_time()
    today_str = trusted_time.strftime("%Y%m%d")

    if today_str > str(expire_str):
        return False, f"授权码已过期（当前北京时间：{today_str}，有效期至：{expire_str}）"

    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    expected = digest[:CODE_LENGTH].upper()
    return (expected == auth_code_input.upper(),
            "授权码有效" if expected == auth_code_input.upper() else "授权码不匹配")


def save_auth_info(machine_code, auth_code, expire_str):
    try:
        info = {"machine_code": machine_code, "auth_code": auth_code, "expire": expire_str,
                "save_time": datetime.datetime.now().timestamp()}  # 记录保存时的时间戳
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
    # 每次验证授权前先校验时间基准
    if not verify_time_base():
        return False

    machine_code = get_machine_code()
    auth_info = load_auth_info()
    if auth_info and auth_info.get("machine_code") == machine_code:
        # 额外验证：授权保存时间不能晚于当前时间（防止修改时间后保存的授权）
        try:
            save_time = datetime.datetime.fromtimestamp(auth_info.get("save_time", 0))
            if save_time > datetime.datetime.now() + datetime.timedelta(hours=1):
                raise ValueError("授权信息保存时间异常，可能被篡改")
        except:
            return False

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

        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            try:
                pix = QPixmap(logo_path)
                self.logo_label.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception as e:
                QMessageBox.warning(self, "Logo错误", f"加载Logo失败: {str(e)}")
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
            # 验证前先校验时间基准
            verify_time_base()
            trusted_time, _ = get_trusted_time()
            expire_str = (trusted_time + datetime.timedelta(days=1)).strftime("%Y%m%d")
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
        self.temp_pdf = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("加密 PDF 浏览器")
        self.resize(1200, 800)

        main_layout = QVBoxLayout()

        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_widget.setLayout(top_layout)

        self.logo_label = QLabel()
        logo_path = get_logo_path()
        if os.path.exists(logo_path):
            try:
                pix = QPixmap(logo_path)
                self.logo_label.setPixmap(pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception as e:
                QMessageBox.warning(self, "Logo错误", f"加载Logo失败: {str(e)}")
        top_layout.addWidget(self.logo_label)

        self.fullscreen_btn = QPushButton("全屏/退出全屏")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        top_layout.addWidget(self.fullscreen_btn)
        top_layout.addStretch()
        main_layout.addWidget(top_widget)

        self.splitter = QSplitter(Qt.Horizontal)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.splitter.addWidget(self.tree)
        self.tree.itemClicked.connect(self.open_encrypted_pdf)

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

        self.load_encrypted_tree()

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
        # 打开文件前先校验时间基准
        if not verify_time_base():
            return

        self.clean_temp_file()

        try:
            enc_path = self.get_encrypted_item_path(item)
            if not enc_path or not os.path.exists(enc_path) or not enc_path.lower().endswith(".enc"):
                QMessageBox.warning(self, "文件错误", "未找到有效的加密文件")
                return

            decrypted_data = decrypt_file(enc_path)
            if not decrypted_data:
                QMessageBox.warning(self, "解密错误", "解密后文件为空")
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', mode='wb') as f:
                f.write(decrypted_data)
                self.temp_pdf = f.name

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

        enc_filename = names[-1] if names[-1].endswith(".enc") else f"{names[-1]}.enc"
        names[-1] = enc_filename
        return get_resource_path(os.path.join("encrypted_files", *names))

    def show_all_pages(self):
        for i in reversed(range(self.pdf_layout.count())):
            widget = self.pdf_layout.itemAt(i).widget()
            if widget:
                self.pdf_layout.removeWidget(widget)
                widget.deleteLater()

        if not self.doc:
            return

        try:
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
        app = QApplication(sys.argv)
        font = app.font()
        font.setFamily("SimHei")
        app.setFont(font)

        # 程序启动时立即初始化并验证时间基准（核心改进）
        init_time_base()
        verify_time_base()

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