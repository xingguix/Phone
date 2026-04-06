"""DTMF 按键检测模块"""

import numpy as np
from typing import Optional

# DTMF 频率定义
DTMF_FREQS = {
    '1': (697, 1209), '2': (697, 1336), '3': (697, 1477),
    '4': (770, 1209), '5': (770, 1336), '6': (770, 1477),
    '7': (852, 1209), '8': (852, 1336), '9': (852, 1477),
    '*': (941, 1209), '0': (941, 1336), '#': (941, 1477),
}

# 频率容差
FREQ_TOLERANCE = 25  # Hz，稍微放宽一点


class DTMFDetector:
    """DTMF 按键检测器"""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.last_key = ""
        self.last_key_count = 0  # 连续检测计数
        self.confirm_threshold = 3  # 连续3次确认才输出
    
    def detect(self, audio_data: np.ndarray) -> str:
        """
        从音频中检测 DTMF 按键（带防抖）
        
        Returns:
            检测到的按键，未检测到返回空字符串
        """
        if len(audio_data) < self.sample_rate * 0.05:  # 至少 50ms
            return ""
        
        # FFT
        fft = np.fft.fft(audio_data)
        freqs = np.fft.fftfreq(len(audio_data), 1/self.sample_rate)
        magnitude = np.abs(fft)
        
        # 只关心 600-1600Hz 范围
        mask = (freqs >= 600) & (freqs <= 1600)
        freqs = freqs[mask]
        magnitude = magnitude[mask]
        
        # 找峰值
        peaks = []
        for i in range(1, len(magnitude)-1):
            if magnitude[i] > magnitude[i-1] and magnitude[i] > magnitude[i+1]:
                if magnitude[i] > np.max(magnitude) * 0.25:  # 阈值
                    peaks.append(freqs[i])
        
        # 找两个最接近 DTMF 频率的峰值
        if len(peaks) < 2:
            self._reset()
            return ""
        
        # 匹配 DTMF
        detected_key = ""
        for key, (f1, f2) in DTMF_FREQS.items():
            match1 = any(abs(p - f1) < FREQ_TOLERANCE for p in peaks)
            match2 = any(abs(p - f2) < FREQ_TOLERANCE for p in peaks)
            if match1 and match2:
                detected_key = key
                break
        
        # 防抖处理：连续确认才输出
        if detected_key == self.last_key and detected_key:
            self.last_key_count += 1
            if self.last_key_count == self.confirm_threshold:
                return detected_key  # 确认输出
        else:
            self.last_key = detected_key
            self.last_key_count = 1 if detected_key else 0
        
        return ""
    
    def _reset(self):
        """重置状态"""
        self.last_key = ""
        self.last_key_count = 0


def test_dtmf():
    """测试 DTMF 检测"""
    import pyaudio
    
    print("DTMF 测试 - 按 Ctrl+C 停止")
    
    detector = DTMFDetector()
    
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=800  # 50ms
    )
    
    try:
        while True:
            data = stream.read(800, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            key = detector.detect(audio_data)
            if key:
                print(f"[DTMF] 检测到按键: {key}")
                
    except KeyboardInterrupt:
        print("\n测试结束")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    test_dtmf()
