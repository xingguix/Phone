"""测试完整转录效果"""

from speech_recognition import SpeechRecognizer, RecognitionWorker
from audio_recorder import AudioRecorder
import time

# 测试函数
def test_complete_transcript():
    """测试完整转录功能"""
    print("=== 测试完整转录功能 ===")
    
    # 初始化组件
    recognizer = SpeechRecognizer()
    recorder = AudioRecorder()
    worker = RecognitionWorker(recognizer)
    
    def on_keyword(text):
        print(f"  → 关键词触发！识别结果: {text}")
    
    worker.on_keyword = on_keyword
    
    # 开始录音
    recorder.start()
    print("开始录音，说'你好，我想知道你可以做什么？完毕'...")
    print("（等待 15 秒后自动停止）")
    
    # 开始识别
    worker.start(recorder, timeout=15)
    
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
    
    # 检查结果是否包含完整内容
    expected_phrases = ["你好", "我想知道", "可以做什么", "完毕"]
    missing_phrases = []
    
    for phrase in expected_phrases:
        if phrase not in final_result:
            missing_phrases.append(phrase)
    
    if missing_phrases:
        print(f"缺少以下短语: {missing_phrases}")
        return False
    else:
        print("成功捕获完整对话内容！")
        # 检查是否有重复
        if final_result.count("你好") > 1:
            print("检测到重复内容！")
            return False
        else:
            print("没有检测到重复内容，修复成功！")
            return True

if __name__ == "__main__":
    test_complete_transcript()
