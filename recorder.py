"""
recorder.py - 音频录制模块
提供两种录制模式：
1. 同步录制指定时长
2. 同步迭代器模式，持续产出 2 秒音频片段
"""

import numpy as np
import sounddevice as sd
import threading
import queue


# 录音参数
SAMPLE_RATE = 16000
CHUNK_DURATION = 2  # 秒
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)


def list_mics() -> list:
    """
    列出所有可用的麦克风设备

    Returns:
        list: 麦克风设备信息列表
    """
    devices = sd.query_devices()
    mics = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            mics.append({
                'index': i,
                'name': dev['name'],
                'channels': dev['max_input_channels'],
                'sample_rate': dev['default_samplerate']
            })
    return mics


def print_mics():
    """打印所有可用的麦克风"""
    mics = list_mics()
    print(f"可用麦克风数量: {len(mics)}")
    for mic in mics:
        print(f"  [{mic['index']}] {mic['name']} (通道数: {mic['channels']})")


class AudioRecorder:
    """音频录制器"""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = 1, device: int | None = None):
        """
        初始化录制器

        Args:
            sample_rate: 采样率，默认 16000
            channels: 声道数，默认 1（单声道）
            device: 麦克风设备索引，默认 None（使用系统默认设备）
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._stream = None
        self._audio_buffer = []
        self._is_recording = False

    def record(self, duration: float) -> np.ndarray:
        """
        录制指定时长的音频

        Args:
            duration: 录制时长（秒）

        Returns:
            numpy.ndarray: 录制的音频数据 (samples, channels)
        """
        print(f"开始录制 {duration} 秒...")
        audio_data = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device,
            dtype='float32'
        )
        sd.wait()  # 等待录制完成
        print("录制完成")
        return audio_data

    def record_to_file(self, duration: float, filename: str) -> None:
        """
        录制音频并保存到文件

        Args:
            duration: 录制时长（秒）
            filename: 输出文件路径
        """
        import wavio
        audio_data = self.record(duration)
        # 转为 int16 格式保存
        audio_int16 = (audio_data * 32767).astype(np.int16)
        wavio.write(filename, audio_int16, self.sample_rate)
        print(f"已保存到 {filename}")

    def stream(self):
        """
        同步迭代器，持续产出 2 秒音频片段
        
        用法:
            for chunk in recorder.stream():
                process(chunk)
                if done:
                    break

        Yields:
            np.ndarray: 2 秒的音频数据
        """
        audio_queue = queue.Queue()
        stop_event = threading.Event()
        buffer = []

        def callback(indata, frames, time, status):
            if status:
                print(f"Stream status: {status}")
            buffer.append(indata.copy())
            # 凑满 2 秒就放入队列
            total_samples = sum(len(chunk) for chunk in buffer)
            while total_samples >= CHUNK_SAMPLES:
                needed = CHUNK_SAMPLES
                chunk_data = []
                while needed > 0 and buffer:
                    available = len(buffer[0])
                    if available <= needed:
                        chunk_data.append(buffer.pop(0))
                        needed -= available
                    else:
                        chunk_data.append(buffer[0][:needed])
                        buffer[0] = buffer[0][needed:]
                        needed = 0
                        break
                if chunk_data:
                    audio_queue.put(np.concatenate(chunk_data))
                total_samples = sum(len(chunk) for chunk in buffer)

        def background_thread():
            import time
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                callback=callback,
                dtype='float32'
            )
            stream.start()
            try:
                while not stop_event.is_set():
                    time.sleep(0.1)
            finally:
                stream.stop()
                stream.close()

        buffer.clear()
        thread = threading.Thread(target=background_thread, daemon=True)
        thread.start()

        try:
            while True:
                # 阻塞等待下一个音频片段
                chunk = audio_queue.get()  # 会阻塞直到有数据
                yield chunk
        except GeneratorExit:
            pass
        finally:
            stop_event.set()
            thread.join(timeout=1)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._stream:
            self._stream.close()


def merge(*chunks_or_list) -> np.ndarray:
    """
    合并多个音频片段为一个完整音频

    Args:
        *chunks_or_list: 
            - 多个 np.ndarray: merge(chunk1, chunk2, ...)
            - 一个列表: merge([chunk1, chunk2, ...])

    Returns:
        np.ndarray: 合并后的音频数据
    """
    # 统一转为列表处理
    if len(chunks_or_list) == 1 and isinstance(chunks_or_list[0], (list, tuple)):
        chunks = chunks_or_list[0]
    else:
        chunks = chunks_or_list
    
    if not chunks:
        return np.array([])
    return np.concatenate(chunks)


def merge_to_file(chunks: list, filename: str, sample_rate: int = SAMPLE_RATE) -> None:
    """
    合并音频片段并保存到文件

    Args:
        chunks: 音频片段列表
        filename: 输出文件路径
        sample_rate: 采样率
    """
    import wavio
    audio = merge(*chunks)
    if len(audio) > 0:
        audio_int16 = (audio * 32767).astype(np.int16)
        wavio.write(filename, audio_int16, sample_rate)
        print(f"已保存到 {filename}")


def record_to_file(duration: float, filename: str, sample_rate: int = SAMPLE_RATE) -> None:
    """
    录制并保存到文件

    Args:
        duration: 录制时长（秒）
        filename: 输出文件路径
        sample_rate: 采样率
    """
    recorder = AudioRecorder(sample_rate=sample_rate)
    recorder.record_to_file(duration, filename)


# ============ 测试 ============

if __name__ == "__main__":
    # 列出所有麦克风
    print("=" * 50)
    print("可用麦克风")
    print("=" * 50)
    print_mics()

    # 使用默认设备录制
    print("\n" + "=" * 50)
    print("使用默认设备录制")
    print("=" * 50)
    recorder = AudioRecorder()
    recorder.record_to_file(3, "default.wav")

    # 使用指定设备录制（如果有多于一个麦克风）
    mics = list_mics()
    if len(mics) > 1:
        print("\n" + "=" * 50)
        print(f"使用麦克风 [{mics[0]['index']}]: {mics[0]['name']}")
        print("=" * 50)
        recorder = AudioRecorder(device=mics[0]['index'])
        recorder.record_to_file(3, "mic1.wav")
