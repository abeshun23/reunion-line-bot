import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# RenderのEnvironmentタブで設定した名前と一字一句合わせる必要があります
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GAS_URL = os.environ.get('GAS_URL')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Geminiの設定（エラーになっても止まらないようにtryを入れています）
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Gemini Init Error: {e}")

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
        # 1. ユーザー名の取得
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name

        # 2. 合言葉の判定
        if user_message == "1995天一同窓会":
            payload = {
                "name": display_name,
                "userId": user_id,
                "message": "参加登録"
            }
            # スプレッドシートへ送信
            requests.post(GAS_URL, json=payload)
            reply_text = f"【認証完了】\n{display_name}さん、名簿に登録しました！当日を楽しみにしています。"
        
        else:
            # 3. AIに返信を考えてもらう
            try:
                response = model.generate_content(f"あなたは同窓会の幹事です。親しみやすく短めに回答して。質問：{user_message}")
                reply_text = response.text
            except Exception:
                reply_text = "（AIが少し休憩中です。登録したい場合は「1995天一同窓会」と送ってください！）"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "エラーが発生しました。合言葉が正しいか確認してください。"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    # Renderで起動するために必要な設定
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)