import os
import requests
import time
from flask import Flask, request, jsonify
import google.generativeai as genai
import yt_dlp

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route("/", methods=["GET"])
def home():
    return "Reel Catcher Bot is live with Google Docs & Sheets integration!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data and "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]
        
        if "instagram.com" in text:
            send_message(chat_id, "Caught the Reel! Analyzing with Gemini, generating Google Doc & updating Sheet...")
            process_reel(chat_id, text)
        else:
            send_message(chat_id, "Please send me a valid Instagram Reel link!")
            
    return jsonify({"status": "ok"}), 200

def process_reel(chat_id, url):
    try:
        # 1. Download the Reel audio
        ydl_opts = {
            'outtmpl': '/tmp/reel_%(id)s.%(ext)s',
            'format': 'bestaudio/best', 
            'quiet': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        # 2. Upload file to Google Gemini
        media_file = genai.upload_file(path=filename)
        
        # 3. Generate structured summary with Gemini
        model = genai.GenerativeModel(model_name="gemini-3.6-flash")
        prompt = "Listen to this audio from an Instagram Reel. Write a highly detailed, engaging explanation of what this content is about. Extract all key insights and format it clearly."
        
        response = model.generate_content([prompt, media_file])
        summary = response.text
        
        # Clean up audio files
        os.remove(filename)
        media_file.delete()
        
        # 4. Trigger Google Apps Script to build Doc & log in Sheet
        doc_url = None
        if APPS_SCRIPT_URL:
            payload = {
                "title": f"Reel Summary - {info.get('title', 'Instagram Reel')[:30]}",
                "content": summary,
                "reel_url": url
            }
            res = requests.post(APPS_SCRIPT_URL, json=payload, allow_redirects=True)
            if res.status_code == 200:
                res_data = res.json()
                if res_data.get("status") == "success":
                    doc_url = res_data.get("doc_url")

        # 5. Send message and Google Doc link to Telegram
        msg = f"📝 **Reel Summary:**\n\n{summary}\n\n---"
        if doc_url:
            msg += f"\n\n📄 **Google Doc Created:**\n{doc_url}\n\n📊 *Saved to your Google Sheet tracker!*"
        
        send_message(chat_id, msg)
        
    except Exception as e:
        send_message(chat_id, f"Oops, something went wrong processing that Reel: {str(e)}")

def send_message(chat_id, text):
    if not TELEGRAM_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
