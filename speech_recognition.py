"""语音识别模块 - SenseVoice (FunASR)"""

from phone_control import get_call_state
from phone_control import PhoneState
import numpy as np
import threading
import time
import os
import re
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
        
        # 关键词检测用：轻量快速，无VAD
        self.model_fast = AutoModel(
            model=model_dir,
            device="cuda" if WHISPER_DEVICE == "cuda" else "cpu",
        )
        
        # 完整识别用：带VAD，准确分段
        self.model_full = AutoModel(
            model=model_dir,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda" if WHISPER_DEVICE == "cuda" else "cpu",
        )
        
        print(f"[SenseVoice] 模型加载完成！")
    
    def _clean_text(self, text: str) -> str:
        """清洗 SenseVoice 输出的标签"""
        text = re.sub(r'<\|[^|]+\|>', '', text)
        text = ' '.join(text.split())
        return text.strip()
    
    def transcribe_fast(self, audio_data: np.ndarray) -> str:
        """
        快速识别（用于关键词检测）
        无VAD，直接识别整个音频片段
        
        Returns:
            识别出的文字（单段）
        """
        if len(audio_data) < AUDIO_SAMPLE_RATE * 0.3:
            return ""
        
        result = self.model_fast.generate(
            input=audio_data,
            language="zh",
            use_itn=True,
        )
        
        if result and len(result) > 0:
            text = result[0].get("text", "").strip()
            return self._clean_text(text)
        return ""
    
    def transcribe_full(self, audio_data: np.ndarray) -> list:
        """
        完整识别（用于最终结果）
        带VAD，自动分段，返回所有段落
        
        Returns:
            识别出的文字列表（多段）
        """
        if len(audio_data) < AUDIO_SAMPLE_RATE * 0.3:
            return []
        
        result = self.model_full.generate(
            input=audio_data,
            language="zh",
            use_itn=True,
        )
        
        texts = []
        if result:
            for item in result:
                text = item.get("text", "").strip()
                text = self._clean_text(text)
                if text:
                    texts.append(text)
        return texts
    
    def check_keyword(self, text: str) -> bool:
        """检查文本中是否包含停止关键词"""
        text = text.lower().replace(" ", "").replace(",", "").replace("，", "")
        for keyword in STOP_KEYWORDS:
            if keyword in text:
                return True
        return False


class RecognitionWorker:
    """
    识别工作器
    - 用 2s 叠加切片快速检测关键词
    - 检测到关键词后，用 VAD 完整识别全部音频
    """
    
    def __init__(self, recognizer: SpeechRecognizer):
        self.recognizer = recognizer
        self.is_running = False
        self.thread = None
        
        # 回调
        self.on_text: Optional[Callable[[str], None]] = None
        self.on_keyword: Optional[Callable[[str], None]] = None
        
        # 结果
        self.all_texts = []
        self.keyword_detected = False
    
    def start(self, recorder, timeout=MAX_RECORD_SECONDS, should_stop_fn=None):
        """
        开始识别工作循环
        
        Args:
            should_stop_fn: 可选，一个无参函数，返回 True 时立即停止识别
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.keyword_detected = False
        self.all_texts = []
        
        self.thread = threading.Thread(
            target=self._recognize_loop,
            args=(recorder, timeout, should_stop_fn)
        )
        self.thread.start()
    
    def _recognize_loop(self, recorder, timeout, should_stop_fn):
        """识别循环"""
        start_time = time.time()
        last_recognize_time = 0
        
        print("[识别] 开始监听...")
        
        while self.is_running and not self.keyword_detected:
            # 检查外部停止信号
            if should_stop_fn and should_stop_fn():
                print("[识别] 收到停止信号，立即结束")
                break
            
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"[识别] 超时 ({timeout}秒)，强制停止")
                break
            
            # 每 1 秒用 2s 切片快速检测关键词
            if elapsed - last_recognize_time >= RECOGNIZE_INTERVAL:
                last_recognize_time = elapsed
                
                # 获取 2s 切片（叠加）
                audio_slice = recorder.get_slice_for_recognition()
                
                if len(audio_slice) >= AUDIO_SAMPLE_RATE * 0.5:
                    # 快速识别
                    text = self.recognizer.transcribe_fast(audio_slice)
                    
                    if text:
                        print(f"[识别] {text}")
                        
                        # 检查关键词
                        if self.recognizer.check_keyword(text):
                            print(f"[识别] 🎯 检测到关键词！")
                            self.keyword_detected = True
                            
                            # 用 VAD 完整识别全部音频
                            full_audio = recorder.get_full_audio()
                            self.all_texts = self.recognizer.transcribe_full(full_audio)
                            print(f"[识别] 完整结果: {self.all_texts}")
                            
                            if self.on_keyword:
                                self.on_keyword(text)
                            break
            
            time.sleep(0.05)
        
        # 如果没检测到关键词但超时/停止了，也做一次完整识别
        if not self.keyword_detected and self.all_texts == []:
            full_audio = recorder.get_full_audio()
            self.all_texts = self.recognizer.transcribe_full(full_audio)
        
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
    
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    worker = RecognitionWorker(recognizer)
    
    def on_keyword(text):
        print(f"  → 🎉 关键词触发！")
    
    worker.on_keyword = on_keyword
    
    recorder.start()
    worker.start(recorder, timeout=30)
    
    while worker.is_running:
        time.sleep(0.1)
    
    worker.stop()
    recorder.cleanup()
    
    print(f"\n全部识别结果: {worker.get_all_text()}")


if __name__ == "__main__":
    test_recognition()
