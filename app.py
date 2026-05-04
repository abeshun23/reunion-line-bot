import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# 1. 環境変数の読み込み
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GAS_URL = os.environ.get('GAS_URL')

# 2. APIの初期化（ここで handler を定義！）
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 3. Geminiの設定
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        # ここで handler を使用します
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    
    try:
        # GASに状況確認（action: check）
        check_payload = {"userId": user_id, "action": "check"}
        check_res = requests.post(GAS_URL, json=check_payload).json()
        
        is_registered = check_res.get("registered", False) # 本名まで登録済みか
        has_id_only = check_res.get("hasIdOnly", False)   # IDだけ登録済みか

        if is_registered:
            # 【完全登録済み】AIが幹事として答える
            response = model.generate_content(f"あなたは同窓会の幹事です。登録済みのメンバーに親しみやすく答えて。質問：{user_message}")
            reply_text = response.text
        
        elif user_message == "1995天一同窓会":
            # 【ステップ1】合言葉が一致したらIDを仮登録
            reg_payload = {"name": "LINEユーザー", "userId": user_id, "action": "register"}
            requests.post(GAS_URL, json=reg_payload)
            reply_text = "【パスワード認証成功】\nありがとうございます！本人確認のため、あなたの「お名前（フルネーム）」をこのチャットに送信してください。"
        
        elif has_id_only:
            # 【ステップ2】IDはあるが名前がない状態でメッセージが来たら、それを本名として登録
            update_payload = {"userId": user_id, "realName": user_message, "action": "updateName"}
            requests.post(GAS_URL, json=update_payload)
            reply_text = f"ありがとうございます！「{user_message}」さんで登録しました。これで全ての機能が利用可能です。会場案内など、何でも聞いてくださいね！"
        
        else:
            # 【未認証】合言葉も名前登録もまだ
            reply_text = "パスワードが間違っています。受信したメールに記載されたパスワードを確認してください。"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "システムエラーが発生しました。時間を置いて再度お試しください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)