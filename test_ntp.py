import socket
import struct
import datetime
import time

# 国内常用NTP服务器列表
NTP_SERVERS = [
    "ntp.aliyun.com",  # 阿里云
    "ntp.tencent.com",  # 腾讯云
    "cn.pool.ntp.org",  # 中国NTP池
    "time1.aliyun.com",  # 阿里云节点1
    "time2.aliyun.com",  # 阿里云节点2
    "ntp1.baidu.com",  # 百度
    "ntp2.baidu.com"  # 百度节点2
]

NTP_PORT = 123
NTP_PACKET_FORMAT = "!12I"
NTP_DELTA = 2208988800  # 1970-01-01到1900-01-01的秒数
BEIJING_TIME_DELTA = datetime.timedelta(hours=8)  # 北京时间UTC+8


def test_ntp_server(server):
    """测试单个NTP服务器是否可用"""
    try:
        # 创建UDP socket
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(3)  # 3秒超时

        # 构建NTP请求包
        data = b'\x1b' + 47 * b'\0'
        client.sendto(data, (server, NTP_PORT))

        # 接收响应
        start_time = time.time()
        response, _ = client.recvfrom(1024)
        end_time = time.time()
        client.close()

        # 计算延迟（毫秒）
        delay = (end_time - start_time) * 1000

        # 解析NTP响应
        unpacked = struct.unpack(NTP_PACKET_FORMAT, response[0:48])
        transmit_timestamp = unpacked[10] + float(unpacked[11]) / 2 ** 32
        utc_time = datetime.datetime.utcfromtimestamp(transmit_timestamp - NTP_DELTA)
        beijing_time = utc_time + BEIJING_TIME_DELTA

        return {
            "server": server,
            "available": True,
            "delay_ms": round(delay, 2),
            "beijing_time": beijing_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        }

    except socket.timeout:
        return {"server": server, "available": False, "error": "超时"}
    except Exception as e:
        return {"server": server, "available": False, "error": str(e)}


def main():
    print("开始测试国内NTP服务器可用性...\n")
    results = []

    for server in NTP_SERVERS:
        print(f"测试 {server} ...", end=" ")
        result = test_ntp_server(server)
        results.append(result)

        if result["available"]:
            print(f"可用 | 延迟: {result['delay_ms']}ms | 时间: {result['beijing_time']}")
        else:
            print(f"不可用 | 原因: {result['error']}")

    # 汇总可用服务器
    available_servers = [r for r in results if r["available"]]
    if available_servers:
        print("\n可用服务器列表（按延迟排序）:")
        for r in sorted(available_servers, key=lambda x: x["delay_ms"]):
            print(f"- {r['server']} (延迟: {r['delay_ms']}ms)")
    else:
        print("\n没有可用的NTP服务器")


if __name__ == "__main__":
    main()