import hashlib
import datetime
import uuid
import argparse  # 用于解析命令行参数

SECRET_KEY = "MySecretKey123"
CODE_LENGTH = 24


def get_machine_code():
    """默认    生成默认机器码（基于设备MAC地址）
    仅在未通过命令行传入machine_code时使用
    """
    return f"{uuid.getnode():012X}"


def generate_auth_code(machine_code, valid_days=1):
    """
    返回:
        auth_code: 24位授权码
        expire_str: YYYYMMDD 字符串
    """
    expire_date = datetime.datetime.now() + datetime.timedelta(days=valid_days)
    expire_str = expire_date.strftime("%Y%m%d")  # 年月日
    data = f"{machine_code}|{expire_str}"
    digest = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    auth_code = digest[:CODE_LENGTH].upper()
    return auth_code, expire_str


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="生成授权码")
    parser.add_argument("machine_code", nargs='?', default=None,
                        help="机器码（如未提供，将自动生成）")
    parser.add_argument("valid_days", nargs='?', type=int, default=1,
                        help="有效期天数（默认1天）")

    args = parser.parse_args()

    # 获取机器码（优先使用命令行传入的，否则自动生成）
    machine_code = args.machine_code if args.machine_code else get_machine_code()
    valid_days = args.valid_days

    # 生成授权码
    auth_code, expire_str = generate_auth_code(machine_code, valid_days)

    # 输出结果
    print(f"机器码: {machine_code}")
    print(f"授权码: {auth_code}")
    print(f"有效期到: {expire_str}")