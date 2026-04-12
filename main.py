import pygame.mixer as mixer
import threading
import os

from time import sleep
from phone_control import get_call_state, pick_up, hang_up, PhoneState
from typing import Optional, Callable

# 模块导入
try:
    from audio_recorder import AudioRecorder
    import speech_recognition  # 直接用模块里的函数
    from ai_supervisor import AISupervisor, IntentExecutor
    from dtmf_detector import DTMFDetector
    from tts_engine import init_tts, speak
    SPEECH_ENABLED = True
    AI_ENABLED = True
    DTMF_ENABLED = True
    TTS_ENABLED = True
except ImportError as e:
    SPEECH_ENABLED = False
    AI_ENABLED = False
    DTMF_ENABLED = False
    TTS_ENABLED = False
    raise ImportError(f"模块未安装: {e}")


# 组件（延迟初始化）
recorder: Optional[AudioRecorder] = None
ai_supervisor: Optional[AISupervisor] = None
intent_executor: Optional[IntentExecutor] = None
dtmf_detector: Optional[DTMFDetector] = None

# 全局控制标志
should_stop_music = False


def init_speech():
    """初始化语音识别组件"""
    global recorder
    if not SPEECH_ENABLED or recorder is not None:
        return
    
    print("[初始化] 语音识别...")
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


def play_beep():
    """播放提示音"""
    try:
        if os.path.exists("beep.wav"):
            beep = mixer.Sound("beep.wav")
            beep.play()
    except:
        pass


def listen_for_speech(timeout: int = 100, should_stop_fn: Optional[Callable[[], bool]] = None) -> str:
    """监听用户语音 - 直接使用用户写的 keep_transcribing 逻辑"""
    if not SPEECH_ENABLED:
        print("[语音识别] 未启用")
        return ""
    
    init_speech()
    if recorder is None:
        print("[警告] 录音组件未初始化")
        return ""
    
    # 直接调用用户写的逻辑（传递挂断检测函数）
    result = speech_recognition.listen_for_speech(recorder, timeout=timeout, should_stop_fn=should_stop_fn)
    play_beep()
    
    print(f"[监听] 识别结果: {result}")
    return result


def play_music_with_interrupt(music_path: str, timeout: int = 600,
                               should_stop_fn: Optional[Callable[[], bool]] = None) -> bool:
    """
    播放音乐，支持挂断中断和 DTMF '#' 键停止
    
    Args:
        music_path: 音乐文件路径
        timeout: 最大播放时长
        should_stop_fn: 检查是否应该停止的函数（如挂断检测）
    
    Returns:
        True: 正常播放结束
        False: 被中断
    """
    global should_stop_music
    
    if not music_path:
        return True
    
    print(f"[音乐] 开始播放: {os.path.basename(music_path)}")
    print("[音乐] 提示：按 '#' 键可停止音乐")
    
    mixer.music.stop()
    mixer.music.load(music_path)
    mixer.music.play()
    
    should_stop_music = False
    import time
    start_time = time.time()
    
    # 启动麦克风用于 DTMF 检测（可能会有回声）
    if recorder:
        recorder.start()
    
    while mixer.music.get_busy():
        # 检查超时
        if time.time() - start_time > timeout:
            print("[音乐] 播放超时")
            break
        
        # 检查停止信号（全局标志）
        if should_stop_music:
            print("[音乐] 收到停止信号")
            mixer.music.stop()
            if recorder:
                recorder.stop()
            return False
        
        # 检查挂断（传入的函数）
        if should_stop_fn and should_stop_fn():
            print("[音乐] 检测到挂断，停止音乐")
            mixer.music.stop()
            if recorder:
                recorder.stop()
            return False
        
        # 检测 DTMF '#' 键（即使可能有回声）
        if dtmf_detector and recorder:
            try:
                audio_chunk = recorder.get_slice_for_recognition()
                if len(audio_chunk) > 800:
                    key = dtmf_detector.detect(audio_chunk[-800:])
                    if key == "#":
                        print("[DTMF] 检测到 '#' 键，停止音乐")
                        mixer.music.stop()
                        recorder.stop()
                        return False
            except:
                pass
        
        sleep(0.05)
    
    mixer.music.stop()
    if recorder:
        recorder.stop()
    print("[音乐] 播放结束")
    return True


def stop_music():
    """停止音乐"""
    global should_stop_music
    should_stop_music = True
    mixer.music.stop()


def handle_conversation(should_stop_fn: Callable[[], bool]) -> None:
    """
    处理多轮对话，直到用户说再见或挂断
    """
    round_num = 0
    
    while True:
        round_num += 1
        print(f"\n[对话] ===== 第 {round_num} 轮 =====")
        
        # 检查挂断
        if should_stop_fn():
            print("[对话] 用户已挂断")
            break
        
        # 1. 语音识别
        user_input = listen_for_speech(timeout=100, should_stop_fn=should_stop_fn)
        
        if not user_input:
            print("[对话] 未识别到输入，继续下一轮")
            continue
        
        if should_stop_fn():
            break
        
        # 2. AI 分析意图
        if not (ai_supervisor and intent_executor):
            print("[对话] AI 未初始化")
            break
        
        intent_data = ai_supervisor.understand(user_input)
        print(f"[AI主管] 意图: {intent_data['intent']}, 参数: {intent_data['params']}")
        
        # 3. 检查是否结束
        if intent_data['intent'] == 'goodbye':
            print("[AI主管] 用户要求结束通话")
            if TTS_ENABLED:
                speak(intent_data.get('response', '好的，再见！'), block=True)
            break
        
        # 4. 执行意图
        ai_response, music_path = intent_executor.execute(intent_data)
        print(f"[AI主管] 回复: {ai_response}")
        
        # 5. TTS 回复
        if TTS_ENABLED and ai_response:
            speak(ai_response, block=True)
        
        # 6. 执行动作（传入挂断检测函数，支持中断）
        if music_path:
            play_music_with_interrupt(music_path, timeout=600, should_stop_fn=should_stop_fn)
        
        # 7. 检查是否挂断（音乐播放后）
        if should_stop_fn():
            break
        
        # 8. 提示用户继续说
        if TTS_ENABLED:
            play_beep()
    
    print(f"[对话] ===== 对话结束（共 {round_num} 轮）=====")


def main():
    global should_stop_music
    
    print("[主程序] 程序开始运行...")
    print("[主程序] 支持多轮对话，说'再见'结束通话")
    
    
    # 初始化
    init_ai()
    init_dtmf()
    if TTS_ENABLED:
        init_tts("xiaoxiao")
    
    def check_hangup() -> bool:
        """检查用户是否挂断"""
        return get_call_state() == PhoneState.IDLE
    
    while True:
        phone_state = get_call_state()
        
        if phone_state == PhoneState.RINGING:
            # 接听
            sleep(1)
            pick_up()
            sleep(0.3)
            
            # 欢迎语
            if TTS_ENABLED:
                speak("您好，我是您的 AI 助手，请问有什么可以帮您？", block=True)
            
            # 处理多轮对话
            handle_conversation(check_hangup)
            
            # 结束通话
            print("[主程序] 结束通话")
            stop_music()
            hang_up()
        
        sleep(0.5)


if __name__ == "__main__":
    main()
