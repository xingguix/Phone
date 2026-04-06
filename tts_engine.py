"""TTS 引擎 - 使用 Edge TTS"""

import asyncio
import os
import tempfile
import pygame
from typing import Optional

# 尝试导入 Edge TTS
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


# 确保 pygame mixer 已初始化
if not pygame.mixer.get_init():
    pygame.mixer.init()


class TTSEngine:
    """TTS 引擎"""
    
    # 可用的声音（中文）
    VOICES = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",      # 晓晓，女声，温柔
        "xiaoyi": "zh-CN-XiaoyiNeural",          # 小艺，女声，活泼
        "yunjian": "zh-CN-YunjianNeural",        # 云健，男声，新闻
        "yunxi": "zh-CN-YunxiNeural",            # 云希，男声，年轻
        "xiaochen": "zh-CN-XiaochenNeural",      # 晓晨，女声，成熟
    }
    
    def __init__(self, voice: str = "xiaoxiao"):
        if not EDGE_TTS_AVAILABLE:
            raise ImportError("edge-tts 未安装，运行: pip install edge-tts")
        
        self.voice = self.VOICES.get(voice, self.VOICES["xiaoxiao"])
        self.temp_dir = tempfile.mkdtemp()
        print(f"[TTS] 使用声音: {self.voice}")
    
    async def _generate_speech(self, text: str, output_file: str):
        """异步生成语音"""
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_file)
    
    def speak(self, text: str, block: bool = True) -> Optional[str]:
        """
        播放文字（TTS）
        
        Args:
            text: 要播放的文字
            block: 是否阻塞等待播放完成
        
        Returns:
            生成的音频文件路径，失败返回 None
        """
        if not text or not text.strip():
            return None
        
        # 生成临时文件
        temp_file = os.path.join(self.temp_dir, f"tts_{hash(text)}.mp3")
        
        try:
            # 异步生成语音
            asyncio.run(self._generate_speech(text, temp_file))
            
            # 播放
            if block:
                # 阻塞播放
                sound = pygame.mixer.Sound(temp_file)
                sound.play()
                while pygame.mixer.get_busy():
                    import time
                    time.sleep(0.1)
            else:
                # 非阻塞播放
                sound = pygame.mixer.Sound(temp_file)
                sound.play()
            
            return temp_file
            
        except Exception as e:
            print(f"[TTS] 播放失败: {e}")
            return None
    
    def cleanup(self):
        """清理临时文件"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


# 全局 TTS 实例
tts_engine: Optional[TTSEngine] = None


def init_tts(voice: str = "xiaoxiao") -> TTSEngine:
    """初始化 TTS 引擎"""
    global tts_engine
    if tts_engine is None:
        print("[初始化] TTS 引擎...")
        tts_engine = TTSEngine(voice)
        print("[初始化] TTS 引擎完成！")
    return tts_engine


def speak(text: str, block: bool = True) -> bool:
    """
    播放文字（便捷函数）
    
    Returns:
        是否成功
    """
    global tts_engine
    if tts_engine is None:
        tts_engine = init_tts()
    
    result = tts_engine.speak(text, block)
    return result is not None


def test_tts():
    """测试 TTS"""
    print("TTS 测试")
    print("-" * 50)
    
    engine = init_tts("xiaoxiao")
    
    test_texts = [
        "你好，我是你的 AI 助手。",
        "正在为您播放音乐。",
        "好的，音乐已停止。",
    ]
    
    for text in test_texts:
        print(f"播放: {text}")
        engine.speak(text, block=True)
        print()
    
    print("测试完成！")


if __name__ == "__main__":
    test_tts()
