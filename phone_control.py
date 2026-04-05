import subprocess
import re
from enum import Enum

class PhoneState(Enum):
    IDLE = 0
    RINGING = 1
    CALLING = 2



def get_call_state() -> PhoneState:
    output = subprocess.check_output('adb shell dumpsys telephony.registry | findstr "mCallState"', shell=True)
    #     会输出两个
    #     mCallState=1 <- 取这个
    #     mCallState=0
    output = output.decode('utf-8')
    result = re.search(r'mCallState=(\d)', output)
    if result:
        return PhoneState(int(result.group(1)))
    else:
        raise RuntimeError('未找到mCallState')

def pick_up():
    subprocess.run('adb shell input keyevent 5')

def hang_up():
    subprocess.run('adb shell input keyevent 4')