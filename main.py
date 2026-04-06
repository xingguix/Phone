import pygame.mixer as mixer

from time import sleep
from phone_control import get_call_state, pick_up, hang_up, PhoneState
from enum import Enum
from typing import Optional, Callable

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
    LISTENING = 2


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


def listen_for_speech(timeout: int = 30, should_stop_fn: Optional[Callable[[], bool]] = None) -> str:
    """
    监听用户语音，直到说出关键词或超时
    
    Args:
        timeout: 最大监听时长（秒）
        should_stop_fn: 可选，一个无参函数，返回 True 时立即停止识别
    
    Returns:
        识别到的完整文字（VAD分段后合并）
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
    
    def on_keyword(text):
        print(f"[监听] 关键词触发，停止监听")
    
    worker.on_keyword = on_keyword
    
    # 开始录音和识别
    print(f"[监听] 请说话，说'完毕'结束（最长{timeout}秒）...")
    recorder.start()
    worker.start(recorder, timeout=timeout, should_stop_fn=should_stop_fn)
    
    # 等待识别结束
    while worker.is_running:
        sleep(0.1)
    
    # 停止录音
    recorder.stop()
    
    # 返回结果 - VAD 分段后的完整识别结果
    print(f"[监听] VAD分段结果: {worker.all_texts}")
    return " ".join(worker.all_texts)


def main():
    global state
    print("[主程序] 程序开始运行...")
    
    def check_should_stop() -> bool:
        """检查是否应该停止语音识别（用户挂断了）"""
        return get_call_state() == PhoneState.IDLE
    
    while True:
        phone_state = get_call_state()
        
        match state:
            case BotState.IDLE:
                if phone_state == PhoneState.RINGING:
                    sleep(1)
                    pick_up()
                    sleep(0.3)
                    
                    user_input = listen_for_speech(timeout=30, should_stop_fn=check_should_stop)
                    print(f"[主程序] 用户说: {user_input}")
                    
                    play_music("Nicky Youre - Mile Away.mp3")
                    state = BotState.PLAYING
            
            case BotState.PLAYING:
                # 检测用户是否挂断
                if phone_state == PhoneState.IDLE:
                    hang_up()
                    stop_music()
                    state = BotState.IDLE
                elif phone_state == PhoneState.CALLING and not mixer.music.get_busy():
                    # 音乐放完了，正常结束
                    hang_up()
                    stop_music()
                    state = BotState.IDLE
        
        sleep(0.5)


if __name__ == "__main__":
    main()
