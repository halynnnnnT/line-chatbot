from flask import Flask, request, jsonify
from datetime import datetime
import google.generativeai as genai
import sqlite3
import os
from dotenv import load_dotenv
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.exceptions import InvalidSignatureError
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# 新增 LINE 的 handler 設定
line_config = Configuration(access_token=os.getenv("YOUR_CHANNEL_ACCESS_TOKEN"))
line_handler = WebhookHandler(os.getenv("YOUR_CHANNEL_SECRET"))

# === Setup Gemini API ===
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

def generate_expense_json(user_input):
    prompt = f"""你是一個記帳助理，請從下列訊息中抽取出：品項、金額、分類，並自動填入今天的日期。
輸出 JSON 格式：{{"date": ..., "item": ..., "amount": ..., "category": ...}}
訊息：{user_input}
"""
    response = model.generate_content(prompt)
    return response.text

# === Setup SQLite ===
def init_db():
    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        item TEXT,
        amount INTEGER,
        category TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# === LINE 模擬入口（或作為 POST 接口） ===
@app.route("/record", methods=["POST"])
def record():
    user_input = request.json.get("message")

    result = generate_expense_json(user_input)
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return jsonify({"error": "Gemini API 無法正確解析輸出。", "raw": result}), 400

    if data.get("date") == "今天":
        data["date"] = datetime.today().strftime("%Y-%m-%d")

    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO expenses (date, item, amount, category) VALUES (?, ?, ?, ?)",
                  (data["date"], data["item"], data["amount"], data["category"]))
        conn.commit()
        status = "記錄成功"
    except Exception as e:
        conn.rollback()
        status = f"記錄失敗：{str(e)}"
        data = None
    finally:
        conn.close()

    return jsonify({"status": status, "data": data})

# === 查看資料用 ===
@app.route("/list", methods=["GET"])
def list_expenses():
    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute("SELECT * FROM expenses ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "date": r[1], "item": r[2], "amount": r[3], "category": r[4]} for r in rows])

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    return "OK", 200

@line_handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_input = event.message.text
    result = generate_expense_json(user_input)

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        reply_text = "抱歉，我無法理解這筆記帳訊息。"
    else:
        if data.get("date") == "今天":
            data["date"] = datetime.today().strftime("%Y-%m-%d")

        conn = sqlite3.connect("expenses.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO expenses (date, item, amount, category) VALUES (?, ?, ?, ?)",
                      (data["date"], data["item"], data["amount"], data["category"]))
            conn.commit()
            reply_text = f"已記錄：{data.get('item', '未知')} {data.get('amount', '未知')} 元（{data.get('category', '未知')}）"
        except Exception as e:
            conn.rollback()
            reply_text = f"記錄失敗，請稍後再試。錯誤訊息：{str(e)}"
        finally:
            conn.close()

    # 回覆 LINE 使用者
    with ApiClient(line_config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(debug=True)