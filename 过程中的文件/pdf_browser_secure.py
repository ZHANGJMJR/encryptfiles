#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_browser_secure_auth.py
功能：
 - 启动时如果无有效 license → 显示授权对话框（含机器码，可复制）
 - 授权通过并在有效期内后保存 license.key
 - 支持过期检查（格式：LICENSECODE = 授权字符串）
 - PDF 加密 (AES-GCM) 与 浏览（放大/缩小/全屏）
依赖：PyQt5, PyMuPDF, cryptography
pip install PyQt5 PyMuPDF cryptography
"""
import sys
import os
import base64
import tempfile
import traceback
import secrets
import hashlib
import datetime
import uuid
import socket
import platform
from pathlib import Path
from typing import Tuple, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PyQt5 import QtCore, QtGui, QtWidgets
import fitz  # PyMuPDF

# ---------------- Config ----------------
APP_DIR = Path.cwd()
FILES_DIR = APP_DIR / "files"
ENC_DIR = APP_DIR / "encrypted_files"
KEY_FILE = APP_DIR / "key.key"
LOGO_FILE = APP_DIR / "logo.png"
LICENSE_FILE = APP_DIR / "license.key"

# SECRET_KEY: 你用于签发授权码的私密常量（仅在你生成授权码时使用）
# 请在部署前改成你自己的随机字符串并妥善保管
SECRET_KEY = "ReplaceWithYourVerySecretKey_ChangeMe"

# 嵌入小 logo 作为后备
_EMBED_LOGO_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsTAAALEwEAmpwYAAAA"
    "B3RJTUUH5AkPDzw2wq3S6gAAABl0RVh0Q29tbWVudABDcmVhdGVkIHdpdGggR0lNUFeBDhcAAABc"
    "SURBVHja7cExAQAAAMKg9U9tCF8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAID/AAGdAAGkAAGs0NnUAAAAAElFTkSuQmCC"
)

# ---------------- Utilities ----------------
def ensure_dirs_and_default_logo():
    FILES_DIR.mkdir(exist_ok=True)
    ENC_DIR.mkdir(exist_ok=True)
    if not LOGO_FILE.exists():
        try:
            with open(LOGO_FILE, "wb") as f:
                f.write(base64.b64decode(_EMBED_LOGO_BASE64))
        except Exception:
            pass

def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
        if len(key) != 32:
            key = secrets.token_bytes(32)
            KEY_FILE.write_bytes(key)
    else:
        key = secrets.token_bytes(32)
        KEY_FILE.write_bytes(key)
    return key

def encrypt_file(src_path: Path, dst_path: Path, key: bytes):
    data = src_path.read_bytes()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ct = aesgcm.encrypt(nonce, data, None)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "wb") as f:
        f.write(nonce + ct)

def decrypt_to_tempfile(enc_path: Path, key: bytes) -> Path:
    raw = enc_path.read_bytes()
    if len(raw) < 13:
        raise ValueError("Encrypted file too short / corrupted.")
    nonce = raw[:12]
    ct = raw[12:]
    aesgcm = AESGCM(key)
    data = aesgcm.decrypt(nonce, ct, None)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(data)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)

def relative_enc_path_for(src: Path) -> Path:
    rel = src.relative_to(FILES_DIR)
    return ENC_DIR / rel.parent / (rel.stem + ".enc")

def scan_and_encrypt_all(key: bytes, progress_callback=None) -> Tuple[int,int]:
    total = 0
    for root, _, files in os.walk(FILES_DIR):
        for fn in files:
            if fn.lower().endswith(".pdf"):
                total += 1
    count = 0
    changed = 0
    for root, _, files in os.walk(FILES_DIR):
        for fn in files:
            if not fn.lower().endswith(".pdf"):
                continue
            src = Path(root) / fn
            dst = relative_enc_path_for(src)
            need = False
            if not dst.exists():
                need = True
            else:
                if src.stat().st_mtime > dst.stat().st_mtime:
                    need = True
            if need:
                try:
                    encrypt_file(src, dst, key)
                    changed += 1
                except Exception as e:
                    print("Encrypt failed:", src, e)
            count += 1
            if progress_callback:
                progress_callback(count, total)
    return total, changed

# ---------------- License (生成/验证) ----------------
def get_machine_code() -> str:
    """
    生成可复制的机器码（字符串），由系统信息 + MAC 组成的 MD5 的前 16 个大写字符。
    该字符串长度 16，可方便复制粘贴。
    """
    try:
        mac = uuid.getnode()
        host = socket.gethostname()
        sysstr = f"{platform.system()}|{platform.machine()}|{mac}|{host}"
        h = hashlib.md5(sysstr.encode()).hexdigest().upper()
        return h[:16]
    except Exception:
        # 兜底
        fallback = hashlib.md5(os.urandom(16)).hexdigest().upper()
        return fallback[:16]

def verify_license_code(machine_code: str, license_code: str, secret: str = SECRET_KEY) -> Tuple[bool, str]:
    """
    license_code 预期格式：<HASH16><YYYYMMDD>
    其中 HASH16 = sha256(machine_code + "-" + expire + "-" + secret) 的前16位大写十六进制
    expire 用 YYYYMMDD 表示
    返回 (True, "有效期至 YYYYMMDD") 或 (False, "原因")
    """
    license_code = license_code.strip().upper()
    if len(license_code) < 24:  # 16 + 8
        return False, "授权码长度不正确"
    hash_part = license_code[:-8]
    date_part = license_code[-8:]
    try:
        expire_dt = datetime.datetime.strptime(date_part, "%Y%m%d")
    except Exception:
        return False, "授权码日期格式错误"
    now = datetime.datetime.now()
    if now.date() > expire_dt.date():
        return False, "授权已过期"
    raw = f"{machine_code}-{date_part}-{secret}"
    expected = hashlib.sha256(raw.encode()).hexdigest().upper()[:len(hash_part)]
    if expected != hash_part:
        return False, "授权码无效（签名不匹配）"
    return True, f"有效，至 {date_part}"

def save_license(license_code: str):
    LICENSE_FILE.write_text(license_code.strip())

def load_saved_license() -> str:
    if LICENSE_FILE.exists():
        return LICENSE_FILE.read_text().strip()
    return ""

# -------------------- Qt: 授权对话框 --------------------
class LicenseDialog(QtWidgets.QDialog):
    def __init__(self, machine_code: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权验证")
        self.setModal(True)
        self.machine_code = machine_code
        self.result_code = None

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("请将下面的机器码复制并发送给授权方以获取授权码：")
        layout.addWidget(label)

        # 可复制的 readonly QLineEdit + copy 按钮
        h = QtWidgets.QHBoxLayout()
        self.machine_line = QtWidgets.QLineEdit(machine_code)
        self.machine_line.setReadOnly(True)
        self.machine_line.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)  # 允许右键复制
        h.addWidget(self.machine_line)
        btn_copy = QtWidgets.QPushButton("复制机器码")
        btn_copy.clicked.connect(self.copy_machine_code)
        h.addWidget(btn_copy)
        layout.addLayout(h)

        layout.addWidget(QtWidgets.QLabel("请输入收到的授权码（24位以内，含到期日期）："))
        self.license_input = QtWidgets.QLineEdit()
        self.license_input.setPlaceholderText("例如：16HEXHASHYYYYMMDD")
        layout.addWidget(self.license_input)

        # 验证结果展示
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        btns = QtWidgets.QHBoxLayout()
        btn_verify = QtWidgets.QPushButton("验证并保存授权")
        btn_verify.clicked.connect(self.on_verify)
        btn_cancel = QtWidgets.QPushButton("退出")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_verify)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        # 允许用户右键复制机器码（也可选中复制）
        self.machine_line.selectAll()

    def copy_machine_code(self):
        cb = QtWidgets.QApplication.clipboard()
        cb.setText(self.machine_code)
        QtWidgets.QMessageBox.information(self, "已复制", "机器码已复制到剪贴板，可粘贴发送给授权方。")

    def on_verify(self):
        lic = self.license_input.text().strip()
        ok, msg = verify_license_code(self.machine_code, lic)
        if ok:
            save_license(lic)
            QtWidgets.QMessageBox.information(self, "授权成功", f"授权通过：{msg}")
            self.result_code = lic
            self.accept()
        else:
            self.status_label.setText(f"验证失败：{msg}")
            QtWidgets.QMessageBox.warning(self, "验证失败", msg)

# -------------------- 基于之前的浏览器（简化版） --------------------
class PDFViewer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc = None
        self.page_index = 0
        self.scale = 2.0
        self._temp_files: List[Path] = []

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.image_label)

        self.prev_btn = QtWidgets.QPushButton("上一页")
        self.next_btn = QtWidgets.QPushButton("下一页")
        self.zoom_in_btn = QtWidgets.QPushButton("放大")
        self.zoom_out_btn = QtWidgets.QPushButton("缩小")
        self.full_btn = QtWidgets.QPushButton("全屏")
        self.page_info = QtWidgets.QLabel("无文档")

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addWidget(self.zoom_in_btn)
        btn_layout.addWidget(self.zoom_out_btn)
        btn_layout.addWidget(self.full_btn)
        btn_layout.addWidget(self.page_info)
        btn_layout.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.scroll)
        layout.addLayout(btn_layout)

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.zoom_in_btn.clicked.connect(lambda: self.adjust_zoom(1.25))
        self.zoom_out_btn.clicked.connect(lambda: self.adjust_zoom(0.8))
        self.full_btn.clicked.connect(self.toggle_pdf_fullscreen)

    def load_pdf(self, pdf_path: Path):
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(str(pdf_path))
            self.page_index = 0
            if str(pdf_path).startswith(tempfile.gettempdir()):
                self._temp_files.append(pdf_path)
            self.update_page()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "打开失败", f"无法打开 PDF：{e}")
            traceback.print_exc()

    def update_page(self):
        if not self.doc:
            self.image_label.clear()
            self.page_info.setText("无文档")
            return
        try:
            page = self.doc.load_page(self.page_index)
            mat = fitz.Matrix(self.scale, self.scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            qimg = QtGui.QImage.fromData(pix.tobytes("png"))
            if qimg.isNull():
                self.image_label.setText("渲染失败")
                return
            self.image_label.setPixmap(QtGui.QPixmap.fromImage(qimg))
            self.page_info.setText(f"第 {self.page_index+1} / 共 {self.doc.page_count}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "渲染失败", f"{e}")
            traceback.print_exc()

    def prev_page(self):
        if not self.doc: return
        if self.page_index > 0:
            self.page_index -= 1
            self.update_page()

    def next_page(self):
        if not self.doc: return
        if self.page_index < self.doc.page_count - 1:
            self.page_index += 1
            self.update_page()

    def adjust_zoom(self, factor: float):
        self.scale *= factor
        # 限制 scale
        if self.scale < 0.25: self.scale = 0.25
        if self.scale > 6.0: self.scale = 6.0
        self.update_page()

    def toggle_pdf_fullscreen(self):
        if self.toggle_pdf_fullscreen:
            # 退出全屏
            self.left_widget.show()
            self.button_layout_widget.show()
            self.toggle_pdf_fullscreen = False
            self.full_btn.setText("全屏显示 PDF")
        else:
            # PDF 全屏
            self.left_widget.hide()
            self.button_layout_widget.hide()
            self.toggle_pdf_fullscreen = True
            self.full_btn.setText("退出 PDF 全屏")

    def cleanup_temp_files(self):
        for p in self._temp_files:
            try:
                if p.exists(): p.unlink()
            except: pass
        self._temp_files.clear()

    def closeEvent(self, event):
        try:
            if self.doc: self.doc.close()
        except: pass
        self.cleanup_temp_files()
        super().closeEvent(event)

# -------------------- 主窗口 --------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, key: bytes):
        super().__init__()
        self.key = key
        self.setWindowTitle("受限 PDF 浏览器")
        self.resize(1200, 800)

        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6,6,6,6)
        left_layout.setSpacing(8)

        # logo
        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignCenter)
        if LOGO_FILE.exists():
            pix = QtGui.QPixmap(str(LOGO_FILE))
            if not pix.isNull():
                pix = pix.scaledToWidth(160, QtCore.Qt.SmoothTransformation)
                logo_label.setPixmap(pix)
            else:
                logo_label.setText("PDF 浏览器")
        else:
            logo_label.setText("PDF 浏览器")
        left_layout.addWidget(logo_label)

        # file tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        left_layout.addWidget(self.tree, 1)

        btn_refresh = QtWidgets.QPushButton("刷新并加密")
        left_layout.addWidget(btn_refresh)

        # viewer
        self.viewer = PDFViewer()

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(self.viewer)
        splitter.setStretchFactor(1,1)
        splitter.setSizes([300,900])
        self.setCentralWidget(splitter)

        # status
        self.status = self.statusBar()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMaximumWidth(220)
        self.status.addPermanentWidget(self.progress)
        self.progress.hide()

        btn_refresh.clicked.connect(self.sync_and_refresh)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_tree_context_menu)

        QtCore.QTimer.singleShot(100, self.sync_and_refresh)

    def set_progress(self, c, t):
        self.progress.show()
        self.progress.setMaximum(t if t>0 else 1)
        self.progress.setValue(c)
        if c >= t:
            QtCore.QTimer.singleShot(600, self.progress.hide)

    def sync_and_refresh(self):
        self.status.showMessage("扫描并加密中...")
        # 简单同步（小文件集）以保持代码精简；可替换为线程池异步
        try:
            total, changed = scan_and_encrypt_all(self.key, progress_callback=lambda c,t: self.set_progress(c,t))
            self.status.showMessage(f"完成：{total} PDF，更新 {changed}")
        except Exception as e:
            self.status.showMessage("加密失败")
            traceback.print_exc()
        self.refresh_tree()

    def refresh_tree(self):
        self.tree.clear()
        if not FILES_DIR.exists(): return
        def add_dir(parent, path: Path):
            entries = sorted([p for p in path.iterdir()], key=lambda x: (not x.is_dir(), x.name.lower()))
            for p in entries:
                if p.is_dir():
                    item = QtWidgets.QTreeWidgetItem([p.name])
                    item.setData(0, QtCore.Qt.UserRole, str(p))
                    parent.addChild(item)
                    add_dir(item, p)
                elif p.is_file() and p.suffix.lower() == ".pdf":
                    item = QtWidgets.QTreeWidgetItem([p.name])
                    item.setData(0, QtCore.Qt.UserRole, str(p))
                    parent.addChild(item)
        root = QtWidgets.QTreeWidgetItem([str(FILES_DIR.name)])
        root.setData(0, QtCore.Qt.UserRole, str(FILES_DIR))
        self.tree.addTopLevelItem(root)
        add_dir(root, FILES_DIR)
        self.tree.expandItem(root)

    def on_tree_item_clicked(self, item, col):
        path_str = item.data(0, QtCore.Qt.UserRole)
        if not path_str: return
        src = Path(path_str)
        if src.is_file() and src.suffix.lower() == ".pdf":
            enc = relative_enc_path_for(src)
            if not enc.exists():
                QtWidgets.QMessageBox.warning(self, "未找到", "请先点击刷新并生成加密文件。")
                return
            try:
                tmp = decrypt_to_tempfile(enc, self.key)
                self.viewer.load_pdf(tmp)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "解密失败", str(e))
                traceback.print_exc()

    def on_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        path = Path(item.data(0, QtCore.Qt.UserRole))
        menu = QtWidgets.QMenu()
        if path.is_file():
            a_re = menu.addAction("重新加密")
            a_open = menu.addAction("打开文件夹")
            a = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if a == a_re:
                try:
                    encrypt_file(path, relative_enc_path_for(path), self.key)
                    QtWidgets.QMessageBox.information(self, "完成", "重新加密完成")
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "失败", str(e))
            elif a == a_open:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path.parent)))
        else:
            a_open = menu.addAction("打开此文件夹")
            a = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if a == a_open:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

# -------------------- main --------------------
def main():
    ensure_dirs_and_default_logo()
    key = load_or_create_key()

    app = QtWidgets.QApplication(sys.argv)

    # 首先检查已有 license
    saved = load_saved_license()
    machine_code = get_machine_code()
    licensed_ok = False
    if saved:
        ok, msg = verify_license_code(machine_code, saved)
        if ok:
            licensed_ok = True
        else:
            # 如果存在但无效，则提示并弹出授权框
            print("已保存的授权无效：", msg)

    if not licensed_ok:
        dlg = LicenseDialog(machine_code)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            # 用户取消或验证失败 -> 退出
            QtWidgets.QMessageBox.information(None, "未授权", "程序未获得授权，程序将退出。")
            return

    # 已授权 -> 打开主窗口
    w = MainWindow(key)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
