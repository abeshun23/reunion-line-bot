import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GAS_URL = os.environ.get('GAS_URL')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
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
    
    try:
        # 1. GASに現在の登録状況を確認する
        check_payload = {"userId": user_id, "action": "check"}
        check_res = requests.post(GAS_URL, json=check_payload).json()
        is_registered = check_res.get("registered", False)

        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name

        # 判定ロジック
        if is_registered:
            # 【登録済みの方】AIが自由に答える
            response = model.generate_content(f"あなたは同窓会の幹事です。登録済みのメンバーに親しみやすく答えて。質問：{user_message}")
            reply_text = response.text
        
        elif user_message == "1995天一同窓会":
            # 【未登録の方】合言葉が正しければ登録
            reg_payload = {"name": display_name, "userId": user_id, "action": "register"}
            requests.post(GAS_URL, json=reg_payload)
            reply_text = f"【認証完了】\n{display_name}さん、名簿に登録しました！これで幹事AIと会話できるようになりました。"
        
        else:
            # 【未登録かつ合言葉も違う】拒否
            reply_text = "パスワードが間違っています。受信したメールに記載されたパスワードを確認してください。"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "システムエラーが発生しました。時間を置いて再度お試しください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)