import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# --- 環境変数の読み込み ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GAS_URL = os.environ.get('GAS_URL')

# --- API初期化 ---
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # 安定版の名称に変更

# --- 1. ヘルスチェック用ルート (これがないとNot Foundになります) ---
@app.route("/", methods=['GET'])
def index():
    return "AI Bot is running", 200

# --- 2. LINE Webhook受信用ルート ---
@app.route("/webhook", methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        abort(400)
        
    events = data.get('events', [])
    knowledge_base = data.get('knowledgeBase', "詳細は調整中です。")

    for event in events:
        if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
            handle_message_logic(event, knowledge_base)
            
    return 'OK'

# --- 3. メインロジック ---
def handle_message_logic(event, knowledge_base):
    user_message = event['message']['text']
    user_id = event['source']['userId']
    reply_token = event['replyToken']
    
    try:
        # GASへ状況確認
        check_res = requests.post(GAS_URL, json={"userId": user_id, "action": "check"}).json()
        is_registered = check_res.get("registered", False)
        has_id_only = check_res.get("hasIdOnly", False)
        user_name = check_res.get("userName", "同級生")

        if is_registered:
           
            prompt = f"""
            あなたは「天一（てんいち）同窓会」の専用AIボットです。
            30歳の節目に集まる大切な友人たちを、明るく、親切にサポートしてください。

            【あなたの役割】
            ・挨拶は「こんにちは！天一同窓会の専用AIボットです。同窓会について決まっていることを案内するね！」と、爽やかに名乗ってください。
            ・ユーザーが登録済み（今回のユーザー：{user_name}さん）なら、「{user_name}さん、お久しぶりです！何か手伝えることはある？」と、名前を呼んで親しみやすく接してください。

            【回答のルール】
            ・以下の「確定事項」に基づいて、正確な情報を伝えてください。
            ・情報は分かりやすく、最後に「楽しみだね！」といったポジティブな一言を添えて回答してください。
            ・まだ決まっていないことは「今、幹事メンバーが一生懸命調整中だから、決まるまでもう少し待っててね！」と伝えてください。
            ・「*」や「**」などのマークダウン記号は、LINEで見づらくなるため一切使用しないでください。
            ・箇条書きをする場合は「・」や「1.」などを使ってください。  
            
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
            requests.post(GAS_URL, json={"userId": user_id, "action": "register"})
            reply_text = "パスワードを認証しました！本人確認のため、フルネームを送信してください。"
        
        elif has_id_only:
            requests.post(GAS_URL, json={"userId": user_id, "realName": user_message, "action": "updateName"})
            reply_text = f"ありがとうございます！{user_message}さんとして登録しました。同窓会について何でも聞いてくださいね！"
        
        else:
            reply_text = "同窓会ボットです！利用するには正しい合言葉を送信してください。"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "少し疲れちゃったみたい。時間を置いてまた話しかけてね！"

    line_bot_api.reply_message(reply_token, TextSendMessage(text=reply_text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)