"""音频录制模块 - 支持重叠切片"""

import pyaudio
import numpy as np
import threading
import queue
from collections import deque
from config import *


class AudioRecorder:
    """音频录制器，支持重叠切片"""
    
    def __init__(self, device_index=None):
        self.device_index = device_index if device_index is not None else MIC_DEVICE_INDEX
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        
        # 音频缓冲区（环形缓冲区，保存最近几秒音频）
        self.buffer = deque()
        self.buffer_lock = threading.Lock()
        
        # 识别队列
        self.recognize_queue = queue.Queue()
        
    def _get_buffer_duration(self):
        """获取缓冲区当前时长（秒）"""
        with self.buffer_lock:
            samples = sum(len(chunk) for chunk in self.buffer)
            return samples / AUDIO_SAMPLE_RATE
    
    def _get_slice_audio(self, duration_seconds):
        """从缓冲区获取指定时长的音频（最新的）"""
        with self.buffer_lock:
            samples_needed = int(duration_seconds * AUDIO_SAMPLE_RATE)
            audio_data = []
            samples_collected = 0
            
            # 从后往前取
            for chunk in reversed(self.buffer):
                if samples_collected + len(chunk) <= samples_needed:
                    audio_data.insert(0, chunk)
                    samples_collected += len(chunk)
                else:
                    # 只需要一部分
                    remaining = samples_needed - samples_collected
                    audio_data.insert(0, chunk[-remaining:])
                    samples_collected += remaining
                    break
            
            if audio_data:
                return np.concatenate(audio_data)
            return np.array([], dtype=np.float32)
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频采集回调"""
        # 转换为 float32 数组
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        with self.buffer_lock:
            self.buffer.append(audio_data)
            
            # 保持缓冲区不超过最大长度（MAX_RECORD_SECONDS + 一些余量）
            max_samples = int((MAX_RECORD_SECONDS + 5) * AUDIO_SAMPLE_RATE)
            while sum(len(chunk) for chunk in self.buffer) > max_samples:
                self.buffer.popleft()
        
        return (in_data, pyaudio.paContinue)
    
    def start(self):
        """开始录音"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.buffer.clear()
        
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=AUDIO_CHANNELS,
            rate=AUDIO_SAMPLE_RATE,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=AUDIO_CHUNK_SIZE,
            stream_callback=self._audio_callback
        )
        
        self.stream.start_stream()
        print(f"[录音] 已开始，采样率 {AUDIO_SAMPLE_RATE}Hz")
    
    def stop(self):
        """停止录音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        print("[录音] 已停止")
    
    def get_slice_for_recognition(self):
        """获取用于识别的音频切片（最新的 SLICE_DURATION 秒）"""
        return self._get_slice_audio(SLICE_DURATION)
    
    def get_full_audio(self):
        """获取全部录制的音频"""
        with self.buffer_lock:
            if self.buffer:
                return np.concatenate(list(self.buffer))
            return np.array([], dtype=np.float32)
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        self.audio.terminate()


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
