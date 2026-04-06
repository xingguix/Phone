"""测试语音识别修复效果"""

from speech_recognition import SpeechRecognizer, RecognitionWorker
from audio_recorder import AudioRecorder
import time
import numpy as np

# 模拟音频数据生成函数
def generate_test_audio(text):
    """生成模拟音频数据（实际应用中不需要）"""
    # 这里只是为了测试，实际上我们会使用真实的录音
    pass

def test_keyword_detection():
    """测试关键词检测和修复效果"""
    print("=== 测试关键词检测和修复效果 ===")
    
    # 初始化组件
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    worker = RecognitionWorker(recognizer)
    
    def on_keyword(text):
        print(f"  → 🎉 关键词触发！识别结果: {text}")
    
    worker.on_keyword = on_keyword
    
    # 开始录音
    recorder.start()
    print("开始录音，说'你好，咱们能聊会天吗？完毕'...")
    print("（等待 10 秒后自动停止）")
    
    # 开始识别
    worker.start(recorder, timeout=10)
    
    # 等待识别完成
    while worker.is_running:
        time.sleep(0.1)
    
    # 停止录音
    recorder.stop()
    
    # 输出结果
    final_result = worker.get_all_text()
    print(f"\n最终识别结果: {final_result}")
    print(f"识别结果长度: {len(final_result)}")
    print("\n=== 测试完成 ===")
    
    # 检查结果是否有重复
    if final_result.count("你好") > 2:
        print("检测到重复识别！")
        return False
    else:
        print("没有检测到重复识别，修复成功！")
        return True

if __name__ == "__main__":
    test_keyword_detection()
