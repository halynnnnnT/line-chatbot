from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import os

app = Flask(__name__)

channel_access_token = os.getenv('YOUR_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('YOUR_CHANNEL_SECRET')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.warning("Invalid signature.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    app.logger.info("Received message: " + event.message.text)

    # 使用 v3 API 回覆訊息
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"你說的是：「{event.message.text}」")]
            )
        )


if __name__ == "__main__":
    app.run()