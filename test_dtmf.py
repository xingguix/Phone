"""DTMF 按键检测测试脚本"""

import numpy as np
import pyaudio
from collections import deque

# DTMF 频率定义
DTMF_FREQS = {
    '1': (697, 1209), '2': (697, 1336), '3': (697, 1477),
    '4': (770, 1209), '5': (770, 1336), '6': (770, 1477),
    '7': (852, 1209), '8': (852, 1336), '9': (852, 1477),
    '*': (941, 1209), '0': (941, 1336), '#': (941, 1477),
}

# 频率容差
FREQ_TOLERANCE = 20  # Hz


def detect_dtmf(audio_data: np.ndarray, sample_rate: int = 16000) -> str:
    """
    从音频中检测 DTMF 按键
    
    Returns:
        检测到的按键（如 '1', '#', 等），未检测到返回空字符串
    """
    if len(audio_data) < sample_rate * 0.1:  # 至少 100ms
        return ""
    
    # FFT
    fft = np.fft.fft(audio_data)
    freqs = np.fft.fftfreq(len(audio_data), 1/sample_rate)
    magnitude = np.abs(fft)
    
    # 只关心 600-1600Hz 范围
    mask = (freqs >= 600) & (freqs <= 1600)
    freqs = freqs[mask]
    magnitude = magnitude[mask]
    
    # 找峰值
    peaks = []
    for i in range(1, len(magnitude)-1):
        if magnitude[i] > magnitude[i-1] and magnitude[i] > magnitude[i+1]:
            if magnitude[i] > np.max(magnitude) * 0.3:  # 阈值
                peaks.append(freqs[i])
    
    # 找两个最接近 DTMF 频率的峰值
    if len(peaks) < 2:
        return ""
    
    # 匹配 DTMF
    for key, (f1, f2) in DTMF_FREQS.items():
        match1 = any(abs(p - f1) < FREQ_TOLERANCE for p in peaks)
        match2 = any(abs(p - f2) < FREQ_TOLERANCE for p in peaks)
        if match1 and match2:
            return key
    
    return ""


def main():
    """主测试循环"""
    print("=" * 50)
    print("DTMF 按键检测测试")
    print("=" * 50)
    print("请打电话进来，然后按手机拨号盘的数字键")
    print("按 Ctrl+C 停止")
    print("=" * 50)
    
    # 初始化音频
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1600  # 100ms
    )
    
    # 用于去重
    last_key = ""
    last_key_time = 0
    
    try:
        while True:
            # 读取音频
            data = stream.read(1600, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # 检测 DTMF
            key = detect_dtmf(audio_data)
            
            # 去重（同一个按键持续 500ms 才算一次）
            if key and key != last_key:
                import time
                current_time = time.time()
                if current_time - last_key_time > 0.5:
                    print(f"[检测到按键] {key}")
                    last_key = key
                    last_key_time = current_time
            elif not key:
                last_key = ""
                
    except KeyboardInterrupt:
        print("\n测试结束")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
