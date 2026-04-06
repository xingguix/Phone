import pygame.mixer as mixer
import threading
import os

from time import sleep
from phone_control import get_call_state, pick_up, hang_up, PhoneState
from enum import Enum
from typing import Optional, Callable

# 模块导入
try:
    from audio_recorder import AudioRecorder
    from speech_recognition import SpeechRecognizer, RecognitionWorker, preload_speech_models
    from ai_supervisor import AISupervisor, IntentExecutor
    from dtmf_detector import DTMFDetector
    SPEECH_ENABLED = True
    AI_ENABLED = True
    DTMF_ENABLED = True
except ImportError as e:
    SPEECH_ENABLED = False
    AI_ENABLED = False
    DTMF_ENABLED = False
    raise ImportError(f"模块未安装: {e}")


class BotState(Enum):
    IDLE = 0      # 空闲等待
    LISTENING = 1 # 语音识别中
    PLAYING = 2   # 播放音乐/回复中


mixer.init()
state: BotState = BotState.IDLE

# 组件（延迟初始化）
recognizer: Optional[SpeechRecognizer] = None
recorder: Optional[AudioRecorder] = None
ai_supervisor: Optional[AISupervisor] = None
intent_executor: Optional[IntentExecutor] = None
dtmf_detector: Optional[DTMFDetector] = None

# 全局控制标志
should_stop_music = False  # 用于通知音乐播放线程停止


def init_speech():
    """初始化语音识别组件"""
    global recognizer, recorder
    if not SPEECH_ENABLED or recognizer is not None:
        return
    
    print("[初始化] 语音识别...")
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    print("[初始化] 语音识别完成！")


def init_ai():
    """初始化 AI 主管"""
    global ai_supervisor, intent_executor
    if not AI_ENABLED or ai_supervisor is not None:
        return
    
    print("[初始化] AI 主管...")
    ai_supervisor = AISupervisor()
    intent_executor = IntentExecutor()
    print("[初始化] AI 主管完成！")


def init_dtmf():
    """初始化 DTMF 检测器"""
    global dtmf_detector
    if not DTMF_ENABLED or dtmf_detector is not None:
        return
    
    print("[初始化] DTMF 检测器...")
    dtmf_detector = DTMFDetector()
    print("[初始化] DTMF 检测器完成！")


def play_music_with_dtmf_stop(music_path: str, timeout: int = 300) -> bool:
    """
    播放音乐，同时检测 DTMF '#' 键停止
    
    Returns:
        True: 正常播放结束
        False: 被 DTMF 中断
    """
    global should_stop_music
    
    if not music_path or not mixer:
        return True
    
    print(f"[音乐] 开始播放: {music_path}")
    mixer.music.stop()
    mixer.music.load(music_path)
    mixer.music.play()
    
    should_stop_music = False
    start_time = sleep(0) or 0  # 只是为了语法
    start_time = 0
    import time
    start_time = time.time()
    
    # 播放循环，检测 DTMF
    while mixer.music.get_busy():
        # 检查是否超时
        if time.time() - start_time > timeout:
            print("[音乐] 播放超时")
            break
        
        # 检查 DTMF 停止信号
        if should_stop_music:
            print("[音乐] 收到停止信号")
            mixer.music.stop()
            return False
        
        # 读取音频检测 DTMF（如果检测器已初始化）
        if dtmf_detector and recorder:
            try:
                # 非阻塞读取一小段音频
                audio_chunk = recorder.get_slice_for_recognition()
                if len(audio_chunk) > 800:  # 至少 50ms
                    key = dtmf_detector.detect(audio_chunk[-800:])  # 只检测最后 50ms
                    if key == "#":
                        print("[DTMF] 检测到 '#' 键，停止音乐")
                        mixer.music.stop()
                        return False
            except:
                pass
        
        sleep(0.05)  # 50ms 检查一次
    
    mixer.music.stop()
    print("[音乐] 播放结束")
    return True


def stop_music():
    """停止音乐"""
    global should_stop_music
    should_stop_music = True
    mixer.music.stop()


def play_beep():
    """播放提示音"""
    try:
        if os.path.exists("beep.wav"):
            beep = mixer.Sound("beep.wav")
            beep.play()
    except Exception as e:
        pass  # 提示音播放失败不影响主流程


def listen_for_speech(timeout: int = 30, should_stop_fn: Optional[Callable[[], bool]] = None) -> str:
    """
    监听用户语音，直到说出关键词或超时
    """
    if not SPEECH_ENABLED:
        print("[语音识别] 未启用")
        return ""
    
    init_speech()
    if recognizer is None or recorder is None:
        print("[警告] 语音识别组件未初始化")
        return ""
    
    worker = RecognitionWorker(recognizer)
    
    def on_keyword(text):
        print(f"[监听] 关键词触发，停止监听")
    
    worker.on_keyword = on_keyword
    
    print(f"[监听] 请说话，说'完毕'结束（最长{timeout}秒）...")
    recorder.start()
    worker.start(recorder, timeout=timeout, should_stop_fn=should_stop_fn)
    
    while worker.is_running:
        sleep(0.1)
    
    recorder.stop()
    
    # 播放提示音表示检测结束
    play_beep()
    
    print(f"[监听] VAD分段结果: {worker.all_texts}")
    return " ".join(worker.all_texts)


def main():
    global state, should_stop_music
    
    print("[主程序] 程序开始运行...")
    
    # 预加载模型（只加载一次）
    print("[初始化] 预加载语音模型...")
    preload_speech_models()
    
    init_ai()
    init_dtmf()
    
    def check_should_stop() -> bool:
        """检查是否应该停止语音识别"""
        return get_call_state() == PhoneState.IDLE
    
    while True:
        phone_state = get_call_state()
        
        match state:
            case BotState.IDLE:
                if phone_state == PhoneState.RINGING:
                    sleep(1)
                    pick_up()
                    sleep(0.3)
                    
                    state = BotState.LISTENING
            
            case BotState.LISTENING:
                # 1. 语音识别
                user_input = listen_for_speech(timeout=30, should_stop_fn=check_should_stop)
                print(f"[主程序] 用户说: {user_input}")
                
                # 检查是否挂断
                if get_call_state() == PhoneState.IDLE:
                    state = BotState.IDLE
                    continue
                
                # 2. AI 主管分析意图
                if ai_supervisor and intent_executor:
                    intent_data = ai_supervisor.understand(user_input)
                    print(f"[AI主管] 意图: {intent_data['intent']}, 参数: {intent_data['params']}")
                    
                    # 3. 执行意图
                    ai_response, music_path = intent_executor.execute(intent_data)
                    print(f"[AI主管] 回复: {ai_response}")
                    
                    # 4. 播放音乐（支持 DTMF 停止）
                    if music_path:
                        state = BotState.PLAYING
                        # 在后台线程播放，主循环继续检测挂断
                        music_thread = threading.Thread(
                            target=play_music_with_dtmf_stop,
                            args=(music_path, 300)
                        )
                        music_thread.start()
                    else:
                        # 没有音乐，直接结束
                        hang_up()
                        state = BotState.IDLE
                else:
                    # AI 不可用，播放默认音乐
                    state = BotState.PLAYING
                    music_thread = threading.Thread(
                        target=play_music_with_dtmf_stop,
                        args=("music/Nicky Youre - Mile Away.mp3", 300)
                    )
                    music_thread.start()
            
            case BotState.PLAYING:
                # 检测挂断或音乐结束
                if phone_state == PhoneState.IDLE:
                    # 用户挂断
                    should_stop_music = True
                    hang_up()
                    mixer.music.stop()
                    state = BotState.IDLE
                elif not mixer.music.get_busy():
                    # 音乐放完了
                    hang_up()
                    state = BotState.IDLE
        
        sleep(0.5)


if __name__ == "__main__":
    main()
