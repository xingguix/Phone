"""AI 主管模块 - 理解用户意图并输出固定格式"""

import json
import re
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# 读取 API key（不 print，不暴露）
with open("key.txt", "r", encoding="utf-8") as f:
    _API_KEY = f.read().strip()


def get_music_list() -> List[str]:
    """获取 music 文件夹中的音乐列表"""
    music_dir = "music"
    if not os.path.exists(music_dir):
        return []
    
    # 支持的音频格式
    extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
    
    files = []
    for f in os.listdir(music_dir):
        if f.lower().endswith(extensions):
            # 去掉扩展名作为歌曲名
            name = os.path.splitext(f)[0]
            files.append(name)
    
    return sorted(files)


@dataclass
class Intent:
    """意图定义"""
    name: str           # 意图标识名
    description: str    # 意图描述
    params: Optional[Dict[str, str]] = None  # 参数说明 {参数名: 参数描述}
    
    def __post_init__(self):
        if self.params is None:
            object.__setattr__(self, 'params', {})


class AISupervisor:
    """AI 主管 - 分析用户意图"""
    
    # 支持的意图列表
    INTENTS = {
        "play_music": Intent(
            name="play_music",
            description="播放音乐",
            params={"song_name": "歌曲名"}
        ),
        "stop_music": Intent(
            name="stop_music",
            description="停止音乐",
            params={}
        ),
        "chat": Intent(
            name="chat",
            description="闲聊/其他",
            params={}
        ),
    }
    
    def __init__(self):
        self.api_key = _API_KEY
        # 延迟导入，避免未安装时报错
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"  # 或其他API地址
            )
            self.available = True
        except ImportError:
            self.available = False
            raise ImportError("openai 未安装，运行: pip install openai")
    
    def _build_intent_list(self) -> str:
        """根据 INTENTS 自动生成意图列表说明"""
        lines = []
        for key, intent in self.INTENTS.items():
            lines.append(f"- {intent.name}: {intent.description}")
        return "\n".join(lines)
    
    def _build_params_doc(self) -> str:
        """根据 INTENTS 自动生成参数说明"""
        lines = []
        for key, intent in self.INTENTS.items():
            if intent.params:
                params_str = ", ".join([f"{k} ({v})" for k, v in intent.params.items()])
                lines.append(f"- {intent.name}: params 包含 {params_str}")
            else:
                lines.append(f"- {intent.name}: 无 params")
        return "\n".join(lines)
    
    def _build_music_doc(self) -> str:
        """构建音乐列表说明"""
        music_list = get_music_list()
        if not music_list:
            return "- 当前没有可用的音乐"
        
        lines = [f"- {name}" for name in music_list]
        return "\n".join(lines)
    
    def _build_prompt(self, user_input: str) -> str:
        """构建提示词（自动根据 INTENTS 生成）"""
        intent_list = self._build_intent_list()
        params_doc = self._build_params_doc()
        music_doc = self._build_music_doc()
        
        return f"""你是一个AI电话助手，负责理解用户的语音指令并输出固定格式的意图。

## 支持的意图类型
{intent_list}

## 可用的音乐列表（play_music 的 song_name 必须从以下选择）
{music_doc}

## 输出格式（必须严格遵循）
你必须且只能输出以下JSON格式，不要有任何其他内容：

{{
    "intent": "意图类型",
    "params": {{
        // 根据意图类型的参数
    }},
    "response": "给用户的友好回复（用于语音播放）"
}}

## 参数说明
{params_doc}

## 用户输入
"{user_input}"

## 请输出JSON格式的意图识别结果："""
    
    def understand(self, user_input: str) -> Dict[str, Any]:
        """
        理解用户意图
        
        Args:
            user_input: 用户的语音输入
        
        Returns:
            解析后的意图字典
        """
        if not self.available:
            return {"intent": "chat", "params": {}, "response": "抱歉，AI服务暂时不可用"}
        
        if not user_input or not user_input.strip():
            return {"intent": "chat", "params": {}, "response": "请问有什么可以帮您的？"}
        
        try:
            # 调用 AI
            response = self.client.chat.completions.create(
                model="deepseek-chat",  # 或其他模型
                messages=[
                    {"role": "system", "content": "你是一个AI电话助手，只输出JSON格式的意图识别结果。"},
                    {"role": "user", "content": self._build_prompt(user_input)}
                ],
                temperature=0.3,  # 低温度，更确定性的输出
                max_tokens=500,
            )
            
            # 获取 AI 回复
            if not response.choices or not response.choices[0].message.content:
                return {"intent": "chat", "params": {}, "response": "抱歉，AI服务暂时不可用"}
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON（可能被 ```json 包裹）
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                content = json_match.group(0)
            
            # 解析 JSON
            result = json.loads(content)
            
            # 验证必要字段
            if "intent" not in result:
                result["intent"] = "chat"
            if "params" not in result:
                result["params"] = {}
            if "response" not in result:
                result["response"] = "好的"
            
            return result
            
        except Exception as e:
            # 出错时返回默认意图
            return {
                "intent": "chat",
                "params": {},
                "response": f"抱歉，我没听清楚，您能再说一遍吗？"
            }


class IntentExecutor:
    """意图执行器 - 根据AI识别的意图执行操作"""
    
    def __init__(self):
        self.handlers = {
            "play_music": self._handle_play_music,
            "stop_music": self._handle_stop_music,
            "query_weather": self._handle_query_weather,
            "tell_joke": self._handle_tell_joke,
            "chat": self._handle_chat,
        }
        self.current_music = None  # 当前播放的音乐路径
        self.music_list = get_music_list()  # 缓存音乐列表
    
    def execute(self, intent_data: Dict[str, Any]) -> tuple:
        """
        执行意图
        
        Args:
            intent_data: AI识别的意图数据
        
        Returns:
            (回复文字, 音乐路径或None)
        """
        intent = intent_data.get("intent", "chat")
        params = intent_data.get("params", {})
        response = intent_data.get("response", "")
        
        handler = self.handlers.get(intent, self._handle_chat)
        return handler(params, response)
    
    def _find_music_file(self, song_name: str) -> Optional[str]:
        """根据歌曲名找到对应的文件"""
        music_dir = "music"
        extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a')
        
        # 精确匹配
        for ext in extensions:
            path = os.path.join(music_dir, f"{song_name}{ext}")
            if os.path.exists(path):
                return path
        
        # 模糊匹配（包含关系）
        for f in os.listdir(music_dir):
            name = os.path.splitext(f)[0]
            if song_name.lower() in name.lower() or name.lower() in song_name.lower():
                return os.path.join(music_dir, f)
        
        return None
    
    def _handle_play_music(self, params: Dict, default_response: str) -> tuple:
        """处理播放音乐"""
        song_name = params.get("song_name", "")
        
        if song_name:
            # 查找音乐文件
            music_path = self._find_music_file(song_name)
            if music_path:
                self.current_music = music_path
                response = default_response or f"好的，为您播放《{song_name}》"
                return response, music_path
            else:
                # 找不到，播放默认音乐
                default_path = self._get_default_music()
                self.current_music = default_path
                return f"抱歉，没有找到《{song_name}》，为您播放默认音乐", default_path
        else:
            # 没有指定歌曲，播放默认
            default_path = self._get_default_music()
            self.current_music = default_path
            return default_response or "好的，为您播放音乐", default_path
    
    def _get_default_music(self) -> Optional[str]:
        """获取默认音乐"""
        music_dir = "music"
        if not os.path.exists(music_dir):
            return None
        
        for f in os.listdir(music_dir):
            if f.lower().endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
                return os.path.join(music_dir, f)
        return None
    
    def _handle_stop_music(self, params: Dict, default_response: str) -> tuple:
        """处理停止音乐"""
        self.current_music = None
        return default_response or "音乐已停止", None
    
    def _handle_query_weather(self, params: Dict, default_response: str) -> tuple:
        """处理查询天气"""
        city = params.get("city", "本地")
        # TODO: 实际查询天气API
        return default_response or f"{city}今天天气晴朗，温度25度", None
    
    def _handle_tell_joke(self, params: Dict, default_response: str) -> tuple:
        """处理讲笑话"""
        jokes = [
            "为什么程序员总是分不清圣诞节和万圣节？因为 31 OCT = 25 DEC",
            "一个程序员走进酒吧，举起双手说：我要一杯啤酒。酒保问：一杯还是两杯？程序员说：一杯。然后举起两根手指。",
        ]
        import random
        return random.choice(jokes), None
    
    def _handle_chat(self, params: Dict, default_response: str) -> tuple:
        """处理闲聊"""
        return default_response or "我在听，请继续说", None


def test_ai_supervisor():
    """测试 AI 主管"""
    supervisor = AISupervisor()
    executor = IntentExecutor()
    
    test_inputs = [
        "帮我放首歌",
        "今天天气怎么样",
        "讲个笑话",
        "我待会要开会，提醒我",
        "你好啊",
    ]
    
    for user_input in test_inputs:
        print(f"\n用户: {user_input}")
        intent_data = supervisor.understand(user_input)
        print(f"意图: {intent_data}")
        response = executor.execute(intent_data)
        print(f"回复: {response}")


if __name__ == "__main__":
    test_ai_supervisor()
