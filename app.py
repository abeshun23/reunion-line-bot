import os
import json
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# 環境変数から設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
GAS_URL = os.environ.get('GAS_URL')
PASSPHRASE = "2026同窓会" # 合言葉

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)

def call_gas(action, sheet_name, row_data=None):
    payload = {"action": action, "sheetName": sheet_name, "row": row_data}
    res = requests.post(GAS_URL, data=json.dumps(payload))
    return res.json() if action == "read" else res.text

@app.route("/callback", methods=['POST'])
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
    user_id = event.source.user_id
    user_message = event.message.text

    # 1. 幹事からの返信中継
    if user_id == ADMIN_USER_ID:
        logs = call_gas("read", "対話ログ")
        target_user = next((log['ユーザーID'] for log in reversed(logs) if log['対応ステータス'] == '未対応'), None)
        if target_user:
            line_bot_api.push_message(target_user, TextSendMessage(text=f"【幹事回答】\n{user_message}"))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="回答を転送しました。"))
            # 本来はここで「対応済」にする処理を入れるがプロトタイプでは簡易化
        return

    # 2. 認証チェック
    users = call_gas("read", "ユーザー管理")
    if not any(u['ユーザーID'] == user_id for u in users):
        if user_message == PASSPHRASE:
            call_gas("append", "ユーザー管理", [user_id, "認証済み"])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="認証完了！質問をどうぞ。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="合言葉を入力してください。"))
        return

    # 3. AI回答
    faqs = call_gas("read", "FAQ")
    context = "同窓会事務局です。以下の情報で答えて。不明なら『幹事に確認します』と返して。\n" + \
              "\n".join([f"- {f['項目']}: {f['詳細内容']}" for f in faqs])
    
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(f"{context}\n質問: {user_message}")
    ai_reply = response.text

    if "幹事に確認します" in ai_reply:
        call_gas("append", "対話ログ", [user_id, "ユーザー", user_message, "未対応"])
        line_bot_api.push_message(ADMIN_USER_ID, TextSendMessage(text=f"【転送】{user_message}"))
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="幹事に確認中です。"))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)