"""语音识别模块 - 直接使用用户写的 recognizer

提供与 main.py 兼容的接口，但核心逻辑使用用户写的 keep_transcribing
"""

from recognizer import Recognizer, merge
from config import STOP_KEYWORDS, MAX_RECORD_SECONDS, AUDIO_SAMPLE_RATE
import numpy as np
import threading
import time
import re
from typing import Callable, Optional, List


# 兼容别名
SpeechRecognizer = Recognizer


class RecognitionWorker:
    """
    识别工作器 - 直接封装 keep_transcribing
    
    兼容原 API，但内部使用用户写的 keep_transcribing 逻辑
    """
    
    def __init__(self, recognizer: Recognizer):
        self.recognizer = recognizer
        self.is_running = False
        self.thread = None
        
        # 回调（兼容原 API）
        self.on_text: Optional[Callable[[str], None]] = None
        self.on_keyword: Optional[Callable[[str], None]] = None
        
        # 结果
        self.all_texts: List[str] = []
        self.keyword_detected = False
        self.full_transcript = ""
    
    def start(self, recorder, timeout=MAX_RECORD_SECONDS, should_stop_fn=None):
        """开始识别 - 直接使用 keep_transcribing"""
        if self.is_running:
            return
        
        self.is_running = True
        self.keyword_detected = False
        self.all_texts = []
        self.full_transcript = ""
        self.should_stop_fn = should_stop_fn
        
        def run():
            # 使用用户写的 keep_transcribing 逻辑
            chunks: list = []
            keyword = STOP_KEYWORDS[0] if STOP_KEYWORDS else "完毕"
            
            for chunk in recorder.stream():
                # 🛡️ 检查挂断信号
                if self.should_stop_fn and self.should_stop_fn():
                    print("[识别] 检测到挂断，停止录音")
                    break
                
                chunks.append(chunk)
                
                # 用最后两个 chunk 识别（重叠）
                if len(chunks) == 1:
                    result = self.recognizer.transcribe(chunk)
                else:
                    result = self.recognizer.transcribe(merge(chunks[-2:]))
                
                print(f"[识别] {result}")
                
                # 更新完整转录
                if result:
                    self.full_transcript = result
                    self.all_texts = [result]
                
                # 检查关键词
                if keyword in result:
                    self.keyword_detected = True
                    if self.on_keyword:
                        self.on_keyword(result)
                    break
            
            # 最终识别所有 chunks
            if not self.keyword_detected and chunks:
                final_result = self.recognizer.transcribe(merge(chunks))
                if final_result:
                    self.full_transcript = final_result
                    self.all_texts = [final_result]
            
            self.is_running = False
            print("[识别] 循环结束")
        
        self.thread = threading.Thread(target=run)
        self.thread.start()
    
    def stop(self):
        """停止识别"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_all_text(self) -> str:
        """获取所有识别到的文字"""
        return "".join(self.all_texts)


# 保留原来的函数签名，方便 main.py 直接调用
def listen_for_speech(recorder, timeout: int = 100, should_stop_fn: Callable[[], bool] = None) -> str:
    """
    监听用户语音 - 直接使用用户写的逻辑
    
    Args:
        recorder: AudioRecorder 实例
        timeout: 超时时间
        should_stop_fn: 检查是否挂断的函数
    
    Returns:
        识别的文字
    """
    recognizer = Recognizer()
    chunks: list = []
    keyword = STOP_KEYWORDS[0] if STOP_KEYWORDS else "完毕"
    
    print(f"[监听] 请说话，说'{keyword}'结束...")
    
    for chunk in recorder.stream():
        # 🛡️ 检查挂断信号 - 保护你的安全！
        if should_stop_fn and should_stop_fn():
            print("[监听] 检测到挂断，停止录音！")
            break
        
        chunks.append(chunk)
        
        # 用最后两个 chunk 识别（重叠）
        if len(chunks) == 1:
            result = recognizer.transcribe(chunk)
        else:
            result = recognizer.transcribe(merge(chunks[-2:]))
        
        print(f"[识别] {result}")
        
        if keyword in result:
            break
    
    # 最终识别所有 chunks
    if chunks:
        final_result = recognizer.transcribe(merge(chunks))
        print(f"[监听] 识别结果: {final_result}")
        return final_result
    
    return ""


def test_recognition():
    """测试语音识别"""
    from audio_recorder import AudioRecorder
    
    recorder = AudioRecorder()
    
    # 测试时不要调用 recorder.start()，因为 stream() 会自己启动
    
    # 直接使用用户写的逻辑
    result = listen_for_speech(recorder, timeout=30)
    print(f"\n最终识别结果: {result}")


if __name__ == "__main__":
    test_recognition()
