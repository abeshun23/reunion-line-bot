import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# 環境変数の読み込み
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GAS_URL = os.environ.get('GAS_URL')

# API初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Gemini初期化
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
        # GASにユーザーの登録状況を問い合わせ
        check_res = requests.post(GAS_URL, json={"userId": user_id, "action": "check"}).json()
        is_registered = check_res.get("registered", False)
        has_id_only = check_res.get("hasIdOnly", False)

        if is_registered:
            # 【登録済み】configシートの知識を使ってAIが回答
            settings_res = requests.post(GAS_URL, json={"action": "getSettings"}).json()
            knowledge_base = settings_res.get("info", "詳細は現在確認中です。")

            prompt = f"""
            あなたは山形東高校「1995天一同窓会」の幹事事務局です。
            以下の【公式情報】に基づき、丁寧な敬語（私、〜です、〜ですね）で回答してください。

            【公式情報】
            {knowledge_base}

            【回答ルール】
            1. 内容が「調整中」や「未定」の項目は、そのまま「調整中」と伝えつつ、備考があればその内容を添えて丁寧に説明してください。
            2. カテゴリ（1次会、2次会、共通など）を意識して、正確に情報を伝えてください。
            3. 同窓会に全く関係のない質問には「申し訳ございません。当事務局では同窓会に関するご案内のみ承っております。同窓会に関することは何でも聞いてくださいね！」と回答してください。

            ユーザーの質問: {user_message}
            """
            response = model.generate_content(prompt)
            reply_text = response.text
        
        elif user_message == "1995天一同窓会":
            # 【未登録：ステップ1】合言葉が一致
            requests.post(GAS_URL, json={"userId": user_id, "action": "register"})
            reply_text = "【パスワード認証成功】\nありがとうございます！本人確認のため、あなたの「お名前（フルネーム）」をこのチャットに送信してください。"
        
        elif has_id_only:
            # 【未登録：ステップ2】名前を送信してきた
            requests.post(GAS_URL, json={"userId": user_id, "realName": user_message, "action": "updateName"})
            reply_text = f"ありがとうございます！「{user_message}」さんで登録しました。同窓会について知りたいことはありますか？"
        
        else:
            # 【未登録：合言葉待ち】
            reply_text = "パスワードが間違っています。正しい合言葉を送信してください。"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "システムエラーが発生しました。しばらく経ってから再度お試しください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)