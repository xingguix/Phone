"""音频录制模块 - 兼容层，使用 sounddevice

本模块是 recorder.py 的兼容封装，提供与原 pyaudio 版本相同的接口。
"""

from recorder import AudioRecorder as _Recorder, merge, SAMPLE_RATE, CHUNK_SAMPLES
from config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, MIC_DEVICE_INDEX
import numpy as np
import threading
import queue
from collections import deque


class AudioRecorder:
    """
    音频录制器 - 兼容原 API
    
    提供与原 pyaudio 版本相同的方法：
    - start() / stop() - 控制录音
    - get_slice_for_recognition() - 获取最新切片
    - get_full_audio() - 获取全部音频
    """
    
    def __init__(self, device_index=None):
        self.device_index = device_index if device_index is not None else MIC_DEVICE_INDEX
        self._recorder = _Recorder(
            sample_rate=AUDIO_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            device=self.device_index
        )
        
        # 兼容属性
        self.audio = None  # 兼容原 API
        self.is_recording = False
        
        # 缓冲区（保存录音数据）
        self._buffer = deque()
        self._buffer_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # 流生成器
        self._stream_generator = None
        self._stream_thread = None
    
    def stream(self):
        """
        同步迭代器，持续产出 2 秒音频片段
        直接代理到用户的 _Recorder.stream()
        """
        return self._recorder.stream()
    
    def _stream_loop(self):
        """后台流循环"""
        for chunk in self._recorder.stream():
            if self._stop_event.is_set():
                break
            with self._buffer_lock:
                self._buffer.append(chunk)
                # 保持缓冲区不超过 35 秒
                max_samples = int(35 * AUDIO_SAMPLE_RATE)
                while sum(len(c) for c in self._buffer) > max_samples:
                    self._buffer.popleft()
    
    def start(self):
        """开始录音"""
        if self.is_recording:
            return
        
        # 清空缓冲区
        with self._buffer_lock:
            self._buffer.clear()
        
        self._stop_event.clear()
        self.is_recording = True
        
        # 启动后台流
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        
        print(f"[录音] 已开始，采样率 {AUDIO_SAMPLE_RATE}Hz")
    
    def stop(self):
        """停止录音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self._stop_event.set()
        
        if self._stream_thread:
            self._stream_thread.join(timeout=2)
            self._stream_thread = None
        
        print("[录音] 已停止")
    
    def _get_slice_audio(self, duration_seconds):
        """从缓冲区获取指定时长的音频（最新的）"""
        with self._buffer_lock:
            samples_needed = int(duration_seconds * AUDIO_SAMPLE_RATE)
            audio_data = []
            samples_collected = 0
            
            # 从后往前取
            for chunk in reversed(self._buffer):
                if samples_collected + len(chunk) <= samples_needed:
                    audio_data.insert(0, chunk)
                    samples_collected += len(chunk)
                else:
                    remaining = samples_needed - samples_collected
                    audio_data.insert(0, chunk[-remaining:])
                    samples_collected += remaining
                    break
            
            if audio_data:
                return np.concatenate(audio_data)
            return np.array([], dtype=np.float32)
    
    def get_slice_for_recognition(self):
        """获取用于识别的音频切片（最新的 2 秒）"""
        # 兼容原 API：返回 2 秒切片
        from config import SLICE_DURATION
        return self._get_slice_audio(SLICE_DURATION)
    
    def get_full_audio(self):
        """获取全部录制的音频"""
        with self._buffer_lock:
            if self._buffer:
                return np.concatenate(list(self._buffer))
            return np.array([], dtype=np.float32)
    
    def cleanup(self):
        """清理资源"""
        self.stop()


def test_recorder():
    """测试录音功能"""
    import time
    
    recorder = AudioRecorder()
    recorder.start()
    
    print("录音 5 秒...")
    time.sleep(5)
    
    audio = recorder.get_full_audio()
    print(f"录制了 {len(audio)/AUDIO_SAMPLE_RATE:.2f} 秒音频")
    
    # 测试切片
    slice_audio = recorder.get_slice_for_recognition()
    print(f"切片长度: {len(slice_audio)/AUDIO_SAMPLE_RATE:.2f} 秒")
    
    recorder.cleanup()


if __name__ == "__main__":
    test_recorder()
