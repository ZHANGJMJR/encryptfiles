import os
import shutil
import subprocess

# 配置
MAIN_SCRIPT = "pdfviewer.py"
OUTPUT_NAME = "PDFViewer"
ENC_FOLDER = "encrypted_files"
LOGO_FILE = "logo.png"

def main():
    # 检查必要文件
    if not os.path.exists(MAIN_SCRIPT):
        print(f"错误：未找到主程序 {MAIN_SCRIPT}")
        return

    if not os.path.exists(ENC_FOLDER) or not os.listdir(ENC_FOLDER):
        print(f"错误：加密文件目录 {ENC_FOLDER} 为空或不存在")
        return

    # 清理旧文件
    for dir in ["build", "dist"]:
        if os.path.exists(dir):
            shutil.rmtree(dir, ignore_errors=True)
    if os.path.exists(f"{OUTPUT_NAME}.spec"):
        os.remove(f"{OUTPUT_NAME}.spec")

    # 构建打包命令
    cmd = [
        "pyinstaller",
        "--name", OUTPUT_NAME,
        "--onefile",
        "--windowed",
        # 确保路径分隔符兼容Windows
        f"--add-data={ENC_FOLDER}{os.pathsep}encrypted_files",
        "--hidden-import", "fitz",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "PyQt5.QtPrintSupport",  # 新增：解决潜在的打印支持依赖
    ]

    # 添加Logo
    if os.path.exists(LOGO_FILE):
        cmd.append(f"--add-data={LOGO_FILE}{os.pathsep}.")

    # 添加主程序
    cmd.append(MAIN_SCRIPT)

    # 执行打包
    try:
        subprocess.run(cmd, check=True, shell=True)  # shell=True确保Windows下路径正确
        print(f"\n✅ 打包成功！EXE位于：{os.path.abspath(f'dist/{OUTPUT_NAME}.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败：{e}")

if __name__ == "__main__":
    main()