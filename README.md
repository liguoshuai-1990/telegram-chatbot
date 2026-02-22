# Telegram Gemini Chatbot

🤖 基于 Telegram Bot API + Google Gemini 的 AI 对话机器人

## 功能特性

- 💬 文本对话（支持 Gemini 系列模型）
- 🖼️ 图片分析（发送图片自动识别）
- 🔄 模型切换（多个 Gemini 模型可选）
- 👥 多用户独立会话
- ⌨️ 菜单按钮 + 命令支持
- 📝 Markdown 格式支持

## 支持的命令

| 命令 | 说明 |
|------|------|
| `/start` | 启动机器人 |
| `/help` | 显示帮助 |
| `/models` | 查看可用模型 |
| `/model <name>` | 切换模型 |
| `/new` | 清除会话历史 |

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:liguoshuai-1990/telegram-chatbot.git
cd telegram-chatbot
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
export TELEGRAM_TOKEN="your-telegram-bot-token"
export GEMINI_API_KEY="your-gemini-api-key"
```

### 5. 运行

```bash
python main.py
```

或使用 systemd 服务（Linux）:

```bash
sudo cp telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot.service
sudo systemctl start telegram-bot.service
```

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `TELEGRAM_TOKEN` | Telegram Bot Token | ✅ |
| `GEMINI_API_KEY` | Google Gemini API Key | ✅ |
| `DEFAULT_MODEL` | 默认模型（可选，默认 `gemini-2.0-flash`） | ❌ |

## 项目结构

```
telegram-chatbot/
├── main.py          # 主程序
├── .venv/环境
├── bot           # 虚拟.log          # 运行日志
└── README.md        # 本文件
```

## 依赖

- python-telegram-bot>=20.0
- google-generativeai
- httpx

## License

MIT
