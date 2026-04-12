from funasr import AutoModel
from recorder import AudioRecorder, merge, list_mics, print_mics
import re
from numpy import ndarray


class Recognizer:
    _model = AutoModel(
        model="iic/SenseVoiceSmall",
        device_type="cpu",
        use_itn=True,
        language="zh"
    )

    def __init__(self, device: int | None = None):
        self._recorder = AudioRecorder(device=device)

    def transcribe(self, audio: str | ndarray) -> str:
        """语音识别"""
        # 转换维度: (n, 1) -> (n,) 一维波形
        if isinstance(audio, ndarray) and audio.ndim > 1:
            audio = audio.squeeze()
        result = self._model.generate(audio) # 需要将[{'key': 'rand_key_2yW4Acq9GFz6Y', 'text': '<|ko|><|EMO_UNKNOWN|><|Speech|><|withitn|>这种.'}] 转化为['这种.']
        print(f"原始识别结果: {result}")
        text = re.sub(r'<\|[^|]+\|>', '', " ".join(item['text'] for item in result))
        return text.strip()

    def keep_transcribing(self, keyword: str = "完毕") -> str:
        """持续录音直到检测到关键词"""
        chunks: list = []
        for chunk in self._recorder.stream():
            chunks.append(chunk)
            if len(chunks) == 1:
                result = self.transcribe(chunk)
            else:
                result = self.transcribe(merge(chunks[-2:]))
            print(f"识别结果: {result}")
            if keyword in result:
                break
        return self.transcribe(merge(chunks)).replace(keyword, "")
