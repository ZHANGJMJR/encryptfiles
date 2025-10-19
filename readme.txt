pip install PyQt5 PyMuPDF cryptography

python pdf_browser_secure.py


使用流程：

第三方打开你的 EXE/程序，授权窗口显示机器码（可复制）。

第三方把机器码发给你（或粘贴到邮件/聊天里）。

你在本地运行：
python generate_license.py ABCDEF1234567890 1
将生成一个授权码（例如：A1B2C3D4E5F67890YYYYMMDD）。

把该授权码发回给第三方，第三方在授权窗口粘贴并点击“验证并保存授权”。

验证成功后程序会把授权码写入 license.key，下次启动自动通过验证（直到到期）。

安全与注意事项（请务必阅读）

SECRET_KEY 必须由你来替换为一段安全、不与人共享的随机字符串。泄露 SECRET_KEY 会导致任何人能伪造授权。

license.key 是明文存储授权码；若被第三方修改可能绕过授权（不过签名会验证）。可以考虑对 license.key 再用签名或加密包装（后续可加）。

如果要打包为 EXE（使用 PyInstaller），请在打包前确保 SECRET_KEY 已替换并且 generate_license.py 也使用相同 SECRET_KEY（或者你直接在服务器/本地生成并不发布该脚本）。

过期检查使用客户端本地时间，可能被用户篡改系统时间。若要防篡改，需在线验证（搭建授权服务器）。

pyinstaller --onefile --noconsole  --add-data "encrypted_files;encrypted_files"   pdf_browser_secure_auth.py

pip install PyQt5 PyQtWebEngine

pyinstaller --onefile --noconsole    pdf_browser_secure_final.py

pyinstaller --onefile --noconsole    pdf_browser_secure_final_pymupdf.py

pyinstaller --onefile --noconsole   pdf_browser_secure_highres.py

请输入机器码（复制自用户程序）：38A74637ABC5
生成的授权码（24位）：B97691A1DD30AE827C26FE11

=== 授权码生成结果 ===
机器码:
38A74637ABC5
授权码: D6D0610BB64C458310C1698F
有效期至: 2025-10-20 17:15:54.116367 （1760951754 时间戳）

pyinstaller --onefile --noconsole --add-data "logo.png;."  --add-data "encrypted_files;encrypted_files"   pdf_browser_secure_with_logo.py
pyinstaller --noconsole --onefile  --add-data "logo.png;."   --add-data "encrypted_files;encrypted_files"  pdf_browser_secure_with_logo.py

pyinstaller --noconsole --onefile  --add-data "logo.png;."   --add-data "encrypted_files;encrypted_files"  pdfviewer.py


# 审计法务部，小马，限制转发、文件加密及设置有效期限程序   最终状态如下：================
=== 授权码生成结果 ===
机器码:
38A74637ABC5
授权码: D6D0610BB64C458310C1698F
有效期至: 2025-10-20 17:15:54.116367 （1760951754 时间戳）

#运行，执行程序，体验功能
python pdfviewer.py
# 生成exe文件，该文件用于发送给第三方
python build.py

# 生成exe文件，用于生成验证码及加密文件的
pyinstaller -F -w   generate_gui.py