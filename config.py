"""语音识别配置"""

# Whisper 模型配置
WHISPER_MODEL = "medium"        # 模型大小: tiny, base, small, medium, large
WHISPER_DEVICE = "cpu"          # cuda 或 cpu
WHISPER_LANGUAGE = "zh"         # 中文

# 音频录制配置
AUDIO_SAMPLE_RATE = 16000       # Whisper 要求 16kHz
AUDIO_CHANNELS = 1              # 单声道
AUDIO_CHUNK_SIZE = 1024         # 每次读取的采样数

# 重叠切片配置
SLICE_DURATION = 2.0            # 切片长度（秒）
RECOGNIZE_INTERVAL = 1.0        # 识别间隔（秒），重叠 50%
MAX_RECORD_SECONDS = 30         # 最大录音时长（超时强制停止）

# 关键词配置
STOP_KEYWORDS = ["完毕"]        # 触发停止的关键词

# 麦克风设备索引（None 使用默认设备）
# 如果默认不对，可以改成上面检测到的索引，比如 1 或 46
MIC_DEVICE_INDEX = None
