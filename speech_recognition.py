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


# 全局模型缓存
_model = None


def preload_speech_models():
    """预加载语音模型（程序启动时调用一次）"""
    global _model
    
    if _model is not None:
        return
    
    if not SENSEVOICE_AVAILABLE:
        raise RuntimeError("FunASR 未安装")
    
    print(f"[SenseVoice] 正在加载模型...")
    
    model_dir = "iic/SenseVoiceSmall"
    
    # 只用基础模型，不用VAD
    _model = AutoModel(
        model=model_dir,
        device="cuda" if WHISPER_DEVICE == "cuda" else "cpu",
        disable_update=True,
    )
    
    print(f"[SenseVoice] 模型加载完成！")


class SpeechRecognizer:
    """语音识别器 - 使用 SenseVoice"""
    
    def __init__(self):
        if not SENSEVOICE_AVAILABLE:
            raise RuntimeError("FunASR 未安装")
        
        global _model
        
        if _model is None:
            preload_speech_models()
        
        self.model = _model
    
    def _clean_text(self, text: str) -> str:
        """清洗 SenseVoice 输出的标签"""
        text = re.sub(r'<\|[^|]+\|>', '', text)
        text = ' '.join(text.split())
        return text.strip()
    
    def transcribe(self, audio_data: np.ndarray) -> str:
        """
        识别音频
        
        Returns:
            识别出的文字
        """
        if len(audio_data) < AUDIO_SAMPLE_RATE * 0.3:
            return ""
        
        if self.model is None:
            return "识别失败, 模型未加载"
        result = self.model.generate(
            input=audio_data,
            language="zh",
            use_itn=True,
        )
        
        if result and len(result) > 0:
            text = result[0].get("text", "").strip()
            return self._clean_text(text)
        return ""
    
    def check_keyword(self, text: str) -> bool:
        """检查文本中是否包含停止关键词"""
        text = text.lower().replace(" ", "").replace(",", "").replace("，", "")
        for keyword in STOP_KEYWORDS:
            if keyword in text:
                return True
        return False


class RecognitionWorker:
    """
    识别工作器 - 用 2s 叠加切片检测关键词
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
        self.full_transcript = ""  # 完整转录结果
    
    def start(self, recorder, timeout=MAX_RECORD_SECONDS, should_stop_fn=None):
        """开始识别工作循环"""
        if self.is_running:
            return
        
        self.is_running = True
        self.keyword_detected = False
        self.all_texts = []
        self.full_transcript = ""
        
        self.thread = threading.Thread(
            target=self._recognize_loop,
            args=(recorder, timeout, should_stop_fn)
        )
        self.thread.start()
    
    def _merge_texts(self, new_text: str) -> str:
        """合并新识别的文本到完整转录结果，去除重复部分"""
        if not self.full_transcript:
            return new_text
        
        # 策略1：如果新文本与完整转录结果相同，不添加
        if new_text == self.full_transcript:
            return self.full_transcript
        
        # 策略2：如果新文本是完整转录结果的子集，不添加
        if new_text in self.full_transcript:
            return self.full_transcript
        
        # 策略3：如果完整转录结果是新文本的子集，用新文本替换
        if self.full_transcript in new_text:
            return new_text
        
        # 策略4：检查是否有重叠部分
        max_overlap = min(len(self.full_transcript), len(new_text))
        overlap = 0
        
        for i in range(1, max_overlap + 1):
            if self.full_transcript[-i:] == new_text[:i]:
                overlap = i
        
        # 策略5：如果有重叠，合并文本
        if overlap > 0:
            merged = self.full_transcript + new_text[overlap:]
            return merged
        
        # 策略6：如果没有重叠，检查新文本是否包含关键词
        # 如果包含关键词，直接用新文本替换（假设是更完整的结果）
        if self.recognizer.check_keyword(new_text):
            return new_text
        
        # 策略7：默认情况：如果新文本比完整转录结果长，用新文本替换
        if len(new_text) > len(self.full_transcript):
            return new_text
        
        # 策略8：如果以上都不满足，保留完整转录结果
        return self.full_transcript
    
    def _recognize_loop(self, recorder, timeout, should_stop_fn):
        """识别循环"""
        start_time = time.time()
        last_recognize_time = 0
        last_text = ""  # 用于去重
        
        print("[识别] 开始监听...")
        
        while self.is_running and not self.keyword_detected:
            # 检查外部停止信号
            if should_stop_fn and should_stop_fn():
                print("[识别] 收到停止信号")
                break
            
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"[识别] 超时 ({timeout}秒)")
                break
            
            # 每 1 秒用 2s 切片检测
            if elapsed - last_recognize_time >= RECOGNIZE_INTERVAL:
                last_recognize_time = elapsed
                
                # 获取 2s 切片（叠加）
                audio_slice = recorder.get_slice_for_recognition()
                
                if len(audio_slice) >= AUDIO_SAMPLE_RATE * 0.5:
                    # 识别
                    text = self.recognizer.transcribe(audio_slice)
                    
                    if text and text != last_text:
                        last_text = text
                        print(f"[识别] {text}")
                        
                        # 合并到完整转录结果
                        self.full_transcript = self._merge_texts(text)
                        
                        # 检查关键词
                        if self.recognizer.check_keyword(text):
                            print(f"[识别] 检测到关键词！")
                            self.keyword_detected = True
                            
                            # 使用完整转录结果
                            self.all_texts = [self.full_transcript]
                            
                            if self.on_keyword:
                                self.on_keyword(text)
                            break
            
            time.sleep(0.05)
        
        # 如果没检测到关键词，用最后识别的内容
        if not self.keyword_detected and not self.all_texts:
            if self.full_transcript:
                self.all_texts = [self.full_transcript]
            elif last_text:
                self.all_texts = [last_text]
        
        self.is_running = False
        print("[识别] 循环结束")
    
    def stop(self):
        """停止识别"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def get_all_text(self) -> str:
        """获取所有识别到的文字"""
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
