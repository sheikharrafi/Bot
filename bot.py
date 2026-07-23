import os
import requests
import yt_dlp
import asyncio
import threading
from flask import Flask
from pyrogram import Client, filters

# --- Render-এর জন্য Dummy Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "TeraVid Bot is Alive and Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
# --------------------------------------

# আপনার টোকেন এবং API
BOT_TOKEN = '8383008423:AAHF-K6u19fRvu-_bJuMDTMHyf8wPDeRJto'
API_URL = 'https://teraboxvid.vercel.app/api/video'
API_ID = 21879840
API_HASH = "7f7e473950f5b9576c468d6f67347d77"

app = Client("teravid_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# বটের গ্লোবাল ভেরিয়েবল
target_channel = None
link_queue = []
is_processing = False

# সিরিয়াল অনুযায়ী কাজ করার ফাংশন
async def process_video_task(client):
    global is_processing
    if is_processing:
        return
    
    is_processing = True
    
    while len(link_queue) > 0:
        task = link_queue.pop(0)
        chat_id = task['chat_id']
        original_url = task['url']
        
        status_msg = await client.send_message(chat_id, "🔍 লিংক প্রসেস করা হচ্ছে...")
        
        try:
            response = await asyncio.to_thread(requests.post, API_URL, json={'url': original_url})
            if response.status_code != 200:
                raise Exception("API সার্ভার কাজ করছে না।")
                
            data = response.json()
            
            if data.get('status') == 'success' and len(data.get('list', [])) > 0:
                files = data['list']
                await status_msg.edit_text(f"📁 ফোল্ডারে {len(files)}টি ফাইল পাওয়া গেছে! ডাউনলোড শুরু হচ্ছে...")
                
                for index, video_info in enumerate(files):
                    direct_stream_url = video_info.get('stream_url')
                    video_title = video_info.get('name', f'video_{index}')
                    
                    safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                    file_name = f"{safe_title}.mp4"
                    thumb_name = f"{safe_title}.jpg"
                    
                    await status_msg.edit_text(f"⬇️ ডাউনলোড হচ্ছে ({index+1}/{len(files)}): \n🎬 {video_title}")
                    
                    ydl_opts = {
                        'outtmpl': file_name,
                        'format': 'best',
                        'writethumbnail': True,
                        'quiet': True,
                        'concurrent_fragment_downloads': 5
                    }
                    
                    def download_vid():
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([direct_stream_url])
                            
                    await asyncio.to_thread(download_vid)
                    
                    await status_msg.edit_text(f"⬆️ টেলিগ্রামে আপলোড হচ্ছে ({index+1}/{len(files)})...")
                    
                    thumb_path = thumb_name if os.path.exists(thumb_name) else None
                    
                    await client.send_video(
                        chat_id, 
                        video=file_name, 
                        thumb=thumb_path,
                        caption=f"✅ {video_title}\n\n🤖 Powered by TeraVid",
                        supports_streaming=True
                    )
                    
                    if os.path.exists(file_name): os.remove(file_name)
                    if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
                    
                await status_msg.delete()
                await client.send_message(chat_id, "✅ কাজ সফলভাবে শেষ হয়েছে!")
                
            else:
                await status_msg.edit_text("❌ ভিডিও লিংকটি কাজ করছে না।")

        except Exception as e:
            await status_msg.edit_text(f"❌ এরর: {str(e)}")
            for file in os.listdir():
                if file.endswith(('.mp4', '.jpg', '.webp')): os.remove(file)
                
    is_processing = False

# বটের ইনবক্সে কমান্ড দিয়ে চ্যানেল সেট করার নিয়ম
@app.on_message(filters.private & filters.command("setchannel"))
async def set_channel_cmd(client, message):
    global target_channel
    try:
        channel_username = message.text.split(" ")[1]
        target_channel = channel_username
        await message.reply(f"✅ চ্যানেল সেট করা হয়েছে: {target_channel}\n\n⚠️ মনে রাখবেন: আমাকে অবশ্যই এই চ্যানেলে **অ্যাডমিন (Admin)** বানাতে হবে, নাহলে আমি লিংকের মেসেজগুলো পড়তে পারব না।")
    except:
        await message.reply("⚠️ সঠিক নিয়ম: `/setchannel @আপনার_চ্যানেলের_ইউজারনেম`\n(যেমন: /setchannel @mychannel)")

# ইনবক্সে লিংক দিলে সিরিয়ালে যুক্ত করার নিয়ম (যদি আপনি ইনবক্সেও ব্যবহার করতে চান)
@app.on_message(filters.private & filters.text & filters.regex("http"))
async def private_link_handler(client, message):
    link_queue.append({'chat_id': message.chat.id, 'url': message.text})
    queue_position = len(link_queue)
    
    if queue_position > 1:
        await message.reply(f"⏳ লিংকটি সিরিয়ালে যুক্ত হয়েছে। আপনার আগে আরও {queue_position - 1} টি লিংক ডাউনলোডের কাজ চলছে।")
    
    asyncio.create_task(process_video_task(client))

# চ্যানেলে অটোমেটিক কাজ করার নিয়ম (অ্যাডমিন থাকলে)
@app.on_message(filters.channel & filters.text & filters.regex("http"))
async def channel_link_handler(client, message):
    global target_channel
    if target_channel:
        current_chat_username = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
        
        # যদি পোস্টটি সেট করা চ্যানেলেই হয়
        if target_channel == current_chat_username or target_channel == str(message.chat.id):
            link_queue.append({'chat_id': message.chat.id, 'url': message.text})
            asyncio.create_task(process_video_task(client))

print("✅ Pro TeraVid Bot is running with Auto-Detect, Admin Access & Web Server...")
app.run()
