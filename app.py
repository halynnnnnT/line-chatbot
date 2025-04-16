from flask import Flask, request, jsonify
from datetime import datetime
# from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# === Setup OpenAI ===
llm = ChatOpenAI(temperature=0.2, model="gpt-3.5-turbo", openai_api_key=os.getenv("OPENAI_API_KEY"))

prompt = PromptTemplate(
    input_variables=["input"],
    template="""
你是一個記帳助理，請從下列訊息中抽取出：品項、金額、分類，並自動填入今天日期。
輸出 JSON 格式：{{"date": ..., "item": ..., "amount": ..., "category": ...}}
訊息：{input}
"""
)

chain = LLMChain(llm=llm, prompt=prompt)

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

    result = chain.run(user_input)
    try:
        data = eval(result)  # ⚠️ 建議改為 json.loads 如用 format 推理方式
    except:
        return jsonify({"error": "LLM 無法正確解析輸出。", "raw": result}), 400

    if data["date"] == "今天":
        data["date"] = datetime.today().strftime("%Y-%m-%d")

    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute("INSERT INTO expenses (date, item, amount, category) VALUES (?, ?, ?, ?)",
              (data["date"], data["item"], data["amount"], data["category"]))
    conn.commit()
    conn.close()

    return jsonify({"status": "記錄成功", "data": data})

# === 查看資料用 ===
@app.route("/list", methods=["GET"])
def list_expenses():
    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute("SELECT * FROM expenses ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "date": r[1], "item": r[2], "amount": r[3], "category": r[4]} for r in rows])

if __name__ == "__main__":
    app.run(debug=True)
