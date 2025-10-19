import os
import base64
import hashlib
import datetime
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pyperclip


class PDFEncryptorAndAuthTool:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF加密与授权码工具")
        self.root.geometry("650x500")
        self.root.resizable(True, True)

        # 设置中文字体支持
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        self.style.configure("TNotebook", font=("SimHei", 10))
        self.style.configure("TEntry", font=("SimHei", 10))

        # 创建标签页
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # PDF加密标签页
        self.encrypt_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.encrypt_frame, text="PDF加密")

        # 授权码生成标签页
        self.auth_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.auth_frame, text="授权码生成")

        # 初始化PDF加密界面
        self.init_encrypt_tab()

        # 初始化授权码生成界面
        self.init_auth_tab()

    def init_encrypt_tab(self):
        # 源目录选择
        ttk.Label(self.encrypt_frame, text="源PDF目录:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)

        self.src_dir_var = tk.StringVar()
        ttk.Entry(self.encrypt_frame, textvariable=self.src_dir_var, width=50).grid(row=0, column=1, padx=5, pady=10)

        ttk.Button(
            self.encrypt_frame,
            text="浏览...",
            command=self.select_src_dir
        ).grid(row=0, column=2, padx=5, pady=10)

        # 加密目录选择
        ttk.Label(self.encrypt_frame, text="加密文件保存目录:").grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)

        self.enc_dir_var = tk.StringVar(value="encrypted_files")
        ttk.Entry(self.encrypt_frame, textvariable=self.enc_dir_var, width=50).grid(row=1, column=1, padx=5, pady=10)

        ttk.Button(
            self.encrypt_frame,
            text="浏览...",
            command=self.select_enc_dir
        ).grid(row=1, column=2, padx=5, pady=10)

        # 状态显示区域
        ttk.Label(self.encrypt_frame, text="处理状态:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.NW)

        self.status_text = tk.Text(self.encrypt_frame, height=15, width=60)
        self.status_text.grid(row=2, column=1, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(
            self.encrypt_frame,
            command=self.status_text.yview
        )
        scrollbar.grid(row=2, column=2, sticky=tk.NS)
        self.status_text.config(yscrollcommand=scrollbar.set)

        # 加密按钮
        ttk.Button(
            self.encrypt_frame,
            text="开始加密",
            command=self.start_encryption
        ).grid(row=3, column=1, padx=5, pady=20)

    def init_auth_tab(self):
        # 机器码输入
        ttk.Label(self.auth_frame, text="机器码:").grid(row=0, column=0, padx=5, pady=10, sticky=tk.W)

        self.machine_code_var = tk.StringVar()
        ttk.Entry(self.auth_frame, textvariable=self.machine_code_var, width=50).grid(row=0, column=1, padx=5, pady=10)

        ttk.Button(
            self.auth_frame,
            text="生成默认机器码",
            command=self.generate_default_machine_code
        ).grid(row=0, column=2, padx=5, pady=10)

        # 有效期设置
        ttk.Label(self.auth_frame, text="有效期(天):").grid(row=1, column=0, padx=5, pady=10, sticky=tk.W)

        self.valid_days_var = tk.StringVar(value="1")
        ttk.Entry(self.auth_frame, textvariable=self.valid_days_var, width=10).grid(row=1, column=1, padx=5, pady=10,
                                                                                    sticky=tk.W)

        # 授权码显示
        ttk.Label(self.auth_frame, text="生成的授权码:").grid(row=2, column=0, padx=5, pady=10, sticky=tk.W)

        self.auth_code_var = tk.StringVar()
        ttk.Entry(self.auth_frame, textvariable=self.auth_code_var, width=50, state="readonly").grid(row=2, column=1,
                                                                                                     padx=5, pady=10)

        ttk.Button(
            self.auth_frame,
            text="复制授权码",
            command=self.copy_auth_code
        ).grid(row=2, column=2, padx=5, pady=10)

        # 有效期到显示
        ttk.Label(self.auth_frame, text="有效期至:").grid(row=3, column=0, padx=5, pady=10, sticky=tk.W)

        self.expire_date_var = tk.StringVar()
        ttk.Entry(self.auth_frame, textvariable=self.expire_date_var, width=50, state="readonly").grid(row=3, column=1,
                                                                                                       padx=5, pady=10)

        # 生成按钮
        ttk.Button(
            self.auth_frame,
            text="生成授权码",
            command=self.generate_auth_code
        ).grid(row=4, column=1, padx=5, pady=20)

    def select_src_dir(self):
        dir_path = filedialog.askdirectory(title="选择源PDF目录")
        if dir_path:
            self.src_dir_var.set(dir_path)

    def select_enc_dir(self):
        dir_path = filedialog.askdirectory(title="选择加密文件保存目录")
        if dir_path:
            self.enc_dir_var.set(dir_path)

    def log(self, message):
        """在状态区域显示消息"""
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()

    def start_encryption(self):
        """开始加密PDF文件"""
        src_folder = self.src_dir_var.get()
        enc_folder = self.enc_dir_var.get()

        if not src_folder:
            messagebox.showerror("错误", "请选择源PDF目录")
            return

        if not os.path.exists(src_folder):
            messagebox.showerror("错误", f"源目录不存在: {src_folder}")
            return

        # 清空状态区域
        self.status_text.delete(1.0, tk.END)
        self.log(f"开始加密，源目录: {src_folder}")
        self.log(f"加密文件将保存到: {enc_folder}")

        try:
            # 创建加密目录
            os.makedirs(enc_folder, exist_ok=True)

            pdf_count = 0
            # 遍历源目录
            for root, dirs, files in os.walk(src_folder):
                for fname in files:
                    if fname.lower().endswith(".pdf"):
                        pdf_count += 1
                        full_path = os.path.join(root, fname)
                        self.log(f"处理文件: {full_path}")

                        # 读取文件内容
                        with open(full_path, "rb") as f:
                            data = f.read()

                        # Base64加密
                        enc_data = base64.b64encode(data)

                        # 保持目录结构
                        rel_path = os.path.relpath(full_path, src_folder)
                        enc_path = os.path.join(enc_folder, rel_path + ".enc")
                        os.makedirs(os.path.dirname(enc_path), exist_ok=True)

                        # 保存加密文件
                        with open(enc_path, "wb") as f:
                            f.write(enc_data)

            self.log(f"加密完成，共处理 {pdf_count} 个PDF文件")
            messagebox.showinfo("成功", f"加密完成，共处理 {pdf_count} 个PDF文件")
        except Exception as e:
            error_msg = f"加密过程出错: {str(e)}"
            self.log(error_msg)
            messagebox.showerror("错误", error_msg)

    def generate_default_machine_code(self):
        """生成默认机器码（基于设备MAC地址）"""
        machine_code = f"{uuid.getnode():012X}"
        self.machine_code_var.set(machine_code)

    def generate_auth_code(self):
        """生成授权码"""
        machine_code = self.machine_code_var.get().strip()
        if not machine_code:
            messagebox.showerror("错误", "请输入或生成机器码")
            return

        try:
            valid_days = int(self.valid_days_var.get().strip())
            if valid_days <= 0:
                raise ValueError("有效期必须为正整数")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的有效期天数（正整数）")
            return

        # 生成授权码
        SECRET_KEY = "MySecretKey123"
        CODE_LENGTH = 24

        expire_date = datetime.datetime.now() + datetime.timedelta(days=valid_days)
        expire_str = expire_date.strftime("%Y%m%d")
        data = f"{machine_code}|{expire_str}"
        digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
        auth_code = digest[:CODE_LENGTH].upper()

        # 更新界面显示
        self.auth_code_var.set(auth_code)
        self.expire_date_var.set(expire_str)

    def copy_auth_code(self):
        """复制授权码到剪贴板"""
        auth_code = self.auth_code_var.get()
        if auth_code:
            pyperclip.copy(auth_code)
            messagebox.showinfo("成功", "授权码已复制到剪贴板")
        else:
            messagebox.showwarning("提示", "没有可复制的授权码，请先生成")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFEncryptorAndAuthTool(root)
    root.mainloop()