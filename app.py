@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    
    try:
        # GASに状況確認
        check_payload = {"userId": user_id, "action": "check"}
        check_res = requests.post(GAS_URL, json=check_payload).json()
        
        is_registered = check_res.get("registered", False) # 本名まで登録済みか
        has_id_only = check_res.get("hasIdOnly", False)   # IDだけ登録済みか

        if is_registered:
            # 【完全登録済み】AIチャット
            response = model.generate_content(f"あなたは同窓会の幹事です。質問：{user_message}")
            reply_text = response.text
        
        elif user_message == "1995天一同窓会":
            # 【ステップ1】合言葉でIDを登録
            reg_payload = {"name": event.source.user_id, "userId": user_id, "action": "register"}
            requests.post(GAS_URL, json=reg_payload)
            reply_text = "【パスワード認証成功】\nありがとうございます！本人確認のため、あなたの「お名前（フルネーム）」をこのチャットに送信してください。"
        
        elif has_id_only:
            # 【ステップ2】名前が送られてきたら本名を登録
            update_payload = {"userId": user_id, "realName": user_message, "action": "updateName"}
            requests.post(GAS_URL, json=update_payload)
            reply_text = f"ありがとうございます！「{user_message}」さんで登録しました。これで全ての機能が利用可能です。会場案内など、何でも聞いてくださいね！"
        
        else:
            # 【未認証】
            reply_text = "パスワードが間違っています。受信したメールに記載されたパスワードを確認してください。"

    except Exception as e:
        print(f"Error: {e}")
        reply_text = "システムエラーが発生しました。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))