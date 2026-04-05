"""语音识别模块 - SenseVoice (FunASR)"""

import numpy as np
import threading
import time
import os
from typing import Callable, Optional
from config import *

# 尝试导入 SenseVoice
try:
    from funasr import AutoModel
    SENSEVOICE_AVAILABLE = True
except ImportError:
    SENSEVOICE_AVAILABLE = False
    raise ImportError("FunASR 未安装，运行: pip install funasr modelscope")


class SpeechRecognizer:
    """语音识别器 - 使用 SenseVoice"""
    
    def __init__(self):
        if not SENSEVOICE_AVAILABLE:
            raise RuntimeError("FunASR 未安装")
        
        print(f"[SenseVoice] 正在加载模型...")
        
        # 模型会下载到本地缓存
        model_dir = "iic/SenseVoiceSmall"
        
        self.model = AutoModel(
            model=model_dir,
            vad_model="fsmn-vad",  # 内置 VAD，可以自动检测语音结束
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda" if WHISPER_DEVICE == "cuda" else "cpu",
        )
        
        print(f"[SenseVoice] 模型加载完成！")
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        将音频转换为文字
        
        Args:
            audio_data: float32 数组，范围 [-1, 1]，采样率 16kHz
        
        Returns:
            识别出的文字
        """
        if len(audio_data) < AUDIO_SAMPLE_RATE * 0.3:  # 少于0.3秒
            return ""
        
        # SenseVoice 需要 float32 格式（内部会自动处理）
        # 直接用 float32 数组
        
        # 识别
        result = self.model.generate(
            input=audio_data,
            language="zh",  # 中文
            use_itn=True,   # 使用逆文本规范化
        )
        
        if result and len(result) > 0:
            text = result[0].get("text", "").strip()
            # 去掉语言标签，比如 "<|zh|>"
            if text.startswith("<") and "|>" in text:
                text = text.split("|>", 1)[-1].strip()
            return text
        return ""
    
    def check_keyword(self, text: str) -> bool:
        """
        检查文本中是否包含停止关键词
        """
        text = text.lower().replace(" ", "").replace(",", "").replace("，", "")
        for keyword in STOP_KEYWORDS:
            if keyword in text:
                return True
        return False


class RecognitionWorker:
    """
    识别工作器
    定时从录音器获取音频切片，进行识别，检测关键词
    """
    
    def __init__(self, recognizer: SpeechRecognizer):
        self.recognizer = recognizer
        self.is_running = False
        self.thread = None
        
        # 识别结果回调
        self.on_text: Optional[Callable[[str], None]] = None
        self.on_keyword: Optional[Callable[[str], None]] = None
        
        # 记录已识别的文字（去重）
        self.last_text = ""
        self.all_texts = []
    
    def start(self, recorder, timeout=MAX_RECORD_SECONDS):
        """
        开始识别工作循环
        
        Args:
            recorder: AudioRecorder 实例
            timeout: 最大运行时间（秒）
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(
            target=self._recognize_loop,
            args=(recorder, timeout)
        )
        self.thread.start()
    
    def _recognize_loop(self, recorder, timeout):
        """识别循环（在后台线程运行）"""
        start_time = time.time()
        last_recognize_time = 0
        keyword_found = False
        
        print("[识别] 开始监听...")
        
        while self.is_running and not keyword_found:
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"[识别] 超时 ({timeout}秒)，强制停止")
                break
            
            # 检查是否应该进行识别
            if elapsed - last_recognize_time >= RECOGNIZE_INTERVAL:
                last_recognize_time = elapsed
                
                # 获取音频切片
                audio_slice = recorder.get_slice_for_recognition()
                
                if len(audio_slice) >= AUDIO_SAMPLE_RATE * 0.3:  # 至少0.3秒
                    # 识别
                    text = self.recognizer.transcribe(audio_slice)
                    
                    if text and text != self.last_text:
                        self.last_text = text
                        self.all_texts.append(text)
                        print(f"[识别] {text}")
                        
                        if self.on_text:
                            self.on_text(text)
                        
                        # 检查关键词
                        if self.recognizer.check_keyword(text):
                            print(f"[识别] 🎯 检测到关键词！")
                            keyword_found = True
                            if self.on_keyword:
                                self.on_keyword(text)
                            break
            
            time.sleep(0.05)
        
        self.is_running = False
        print("[识别] 循环结束")
    
    def stop(self):
        """停止识别"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_all_text(self) -> str:
        """获取所有识别到的文字（合并）"""
        return "".join(self.all_texts)


def test_recognition():
    """测试语音识别"""
    from audio_recorder import AudioRecorder
    
    # 初始化
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    worker = RecognitionWorker(recognizer)
    
    # 设置回调
    def on_text(text):
        print(f"  → 文字: {text}")
    
    def on_keyword(text):
        print(f"  → 🎉 关键词触发！")
    
    
    worker.on_text = on_text
    worker.on_keyword = on_keyword
    
    # 开始
    recorder.start()
    worker.start(recorder, timeout=30)
    
    # 等待结束
    while worker.is_running:
        time.sleep(0.1)
    
    # 清理
    worker.stop()
    recorder.cleanup()
    
    print(f"\n全部识别结果: {worker.get_all_text()}")


if __name__ == "__main__":
    test_recognition()
