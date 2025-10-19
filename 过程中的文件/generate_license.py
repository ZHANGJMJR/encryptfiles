#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_license.py
用法：
 python generate_license.py <MACHINE_CODE> <DAYS_VALID>
示例：
 python generate_license.py ABCDEF1234567890 1
输出一个授权码（含到期日期），请把该授权码发给第三方用户。
"""
import sys
import hashlib
import datetime

# 与主程序一致的 SECRET_KEY（务必保密）
SECRET_KEY = "ReplaceWithYourVerySecretKey_ChangeMe"

def generate_for(machine_code: str, days_valid: int = 1) -> str:
    expire_dt = datetime.datetime.now() + datetime.timedelta(days=days_valid)
    date_str = expire_dt.strftime("%Y%m%d")
    raw = f"{machine_code.upper()}-{date_str}-{SECRET_KEY}"
    hash16 = hashlib.sha256(raw.encode()).hexdigest().upper()[:16]
    license_code = f"{hash16}{date_str}"
    return license_code

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_license.py <MACHINE_CODE> [DAYS_VALID]")
        return
    mc = sys.argv[1].strip()
    days = int(sys.argv[2]) if len(sys.argv) >= 3 else 1
    lic = generate_for(mc, days)
    print("Machine code:", mc)
    print("Days valid:", days)
    print("License code:", lic)

if __name__ == "__main__":
    main()
