import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# 環境変数の読み込み（Renderで設定したもの）
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
GAS_URL = os.environ['GAS_URL']

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

@app.route("/callback", method=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    
    # ユーザー名を取得（LINEの設定名）
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    # 【重要】合言葉の判定
    if user_message == "1995天一同窓会":
        # GAS（スプレッドシート）にデータを送信
        payload = {
            "name": display_name,
            "userId": user_id,
            "message": "参加登録希望"
        }
        try:
            response = requests.post(GAS_URL, json=payload)
            if response.status_code == 200:
                reply_text = f"【認証完了】\n{display_name}さん、本人確認がとれました！同窓会名簿に登録しました。当日お会いできるのを楽しみにしています！"
            else:
                reply_text = "すみません、登録システムが一時的に混み合っているようです。少し時間を置いて再度送ってください。"
        except Exception as e:
            reply_text = "接続エラーが発生しました。管理者にお問い合わせください。"
    
    else:
        # 合言葉以外はAI（Gemini）が自由に回答
        response = model.generate_content(f"あなたは同窓会の幹事です。親しみやすい口調で回答してください。質問：{user_message}")
        reply_text = response.text

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)