import pygame.mixer as mixer

from time import sleep
from phone_control import get_call_state, pick_up, hang_up, PhoneState
from enum import Enum
from typing import Optional

# 语音识别模块（延迟导入，避免未安装时报错）
try:
    from audio_recorder import AudioRecorder
    from speech_recognition import SpeechRecognizer, RecognitionWorker
    SPEECH_ENABLED = True
except ImportError:
    SPEECH_ENABLED = False
    raise ImportError("语音识别模块未安装，运行: pip install -r requirements.txt")



class BotState(Enum):
    IDLE = 0
    PLAYING = 1
    LISTENING = 2  # 新增：正在听用户说话


mixer.init()
state: BotState = BotState.IDLE

# 语音识别组件（延迟初始化）
recognizer: Optional[SpeechRecognizer] = None
recorder: Optional[AudioRecorder] = None


def init_speech():
    """初始化语音识别组件"""
    global recognizer, recorder
    if not SPEECH_ENABLED or recognizer is not None:
        return
    
    print("[初始化] 语音识别...")
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    print("[初始化] 完成！")


def play_music(path: str):
    mixer.music.stop()
    mixer.music.load(path)
    mixer.music.play()


def stop_music():
    mixer.music.stop()


def listen_for_speech(timeout: int = 30) -> str:
    """
    监听用户语音，直到说出关键词或超时
    
    Returns:
        识别到的完整文字
    """
    if not SPEECH_ENABLED:
        print("[语音识别] 未启用")
        return ""
    
    init_speech()
    if recognizer is None or recorder is None:
        print("[警告] 语音识别组件未初始化")
        return ""
    # 创建工作器
    worker = RecognitionWorker(recognizer)
    
    # 设置回调（可以在这里添加其他逻辑）
    recognized_texts = []
    
    def on_text(text):
        recognized_texts.append(text)
    
    def on_keyword(text):
        print(f"[监听] 关键词触发，停止监听")
    
    worker.on_text = on_text
    worker.on_keyword = on_keyword
    
    # 开始录音和识别
    print(f"[监听] 请说话，说'完毕'结束（最长{timeout}秒）...")
    recorder.start()
    worker.start(recorder, timeout=timeout)
    
    # 等待识别结束
    while worker.is_running:
        sleep(0.1)
    
    # 停止录音
    recorder.stop()
    
    # 返回结果
    full_text = "".join(recognized_texts)
    print(f"[监听] 结果: {full_text}")
    return full_text


def main():
    global state
    
    while True:
        phone_state = get_call_state()
        
        match state:
            case BotState.IDLE:
                if phone_state == PhoneState.RINGING:
                    sleep(1)
                    pick_up()
                    sleep(0.3)
                    
                    user_input = listen_for_speech(timeout=30)
                    print(f"[主程序] 用户说: {user_input}")
                    
                    play_music("Nicky Youre - Mile Away.mp3")
                    state = BotState.PLAYING
            
            case BotState.PLAYING:
                if phone_state == PhoneState.IDLE \
                or (phone_state == PhoneState.CALLING and not mixer.music.get_busy()):
                    hang_up()
                    stop_music()
                    state = BotState.IDLE
        
        sleep(0.5)


if __name__ == "__main__":
    main()
