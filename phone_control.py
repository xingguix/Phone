import subprocess
import re
import os
import platform
from enum import Enum

class PhoneState(Enum):
    IDLE = 0
    RINGING = 1
    CALLING = 2


def check_adb() -> bool:
    """检查ADB是否已安装"""
    try:
        subprocess.check_output('adb version', shell=True)
        return True
    except:
        return False


def install_adb() -> bool:
    """根据操作系统自动安装ADB"""
    system = platform.system()
    
    print("[ADB] 未检测到ADB，正在尝试安装...")
    
    try:
        if system == 'Windows':
            # Windows安装ADB
            print("[ADB] Windows系统: 请手动安装Android SDK Platform Tools")
            print("[ADB] 下载地址: https://developer.android.com/studio/releases/platform-tools")
            print("[ADB] 下载后解压并将adb.exe所在目录添加到系统PATH")
            return False
        elif system == 'Linux':
            # Linux安装ADB
            if platform.dist()[0] in ['Ubuntu', 'Debian']:
                print("[ADB] Ubuntu/Debian系统: 正在安装ADB...")
                subprocess.run('sudo apt update && sudo apt install -y adb', shell=True, check=True)
                return True
            elif platform.dist()[0] in ['CentOS', 'RHEL']:
                print("[ADB] CentOS/RHEL系统: 正在安装ADB...")
                subprocess.run('sudo yum install -y android-tools', shell=True, check=True)
                return True
            else:
                print("[ADB] 未知Linux发行版，请手动安装ADB")
                return False
        else:
            print("[ADB] 不支持的操作系统")
            return False
    except Exception as e:
        print(f"[ADB] 安装失败: {e}")
        return False




def get_call_state() -> PhoneState:
    # 执行 adb 命令获取通话状态
    adb_command = ['adb', 'shell', 'dumpsys', 'telephony.registry']
    output = subprocess.check_output(adb_command)
    output = output.decode('utf-8')
    result = re.search(r'mCallState=(\d)', output)
    if result:
        return PhoneState(int(result.group(1)))
    else:
        raise RuntimeError('未找到mCallState')

def pick_up():
    # 确保命令在不同操作系统上都能正确执行
    subprocess.run(['adb', 'shell', 'input', 'keyevent', '5'])

def hang_up():
    # 确保命令在不同操作系统上都能正确执行
    subprocess.run(['adb', 'shell', 'input', 'keyevent', '4'])