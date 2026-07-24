import asyncio
# 🚨 ইভেন্ট লুপ ফিক্স 
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import os
import re
import requests
import yt_dlp
import threading
from flask import Flask
from pyrogram import Client, filters

# --- Render-এর জন্য Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "TeraVid Bot is Alive and Running perfectly!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
# ----------------------------------

BOT_TOKEN = '8383008423:AAHF-K6u19fRvu-_bJuMDTMHyf8wPDeRJto'
API_URL = 'https://teraboxvid.vercel.app/api/video'
API_ID = 21879840
API_HASH = "7f7e473950f5b9576c468d6f67347d77"

app = Client("teravid_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

target_channel = None
link_queue = []
is_processing = False

# --- সিরিয়াল অনুযায়ী কাজ করার ফাংশন ---
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
            response = await asyncio.to_thread(requests.post, API_URL, json={'url': original_url}, timeout=30)
            if response.status_code != 200:
                raise Exception("API সার্ভার এই মুহূর্তে কাজ করছে না।")
                
            data = response.json()
            
            if data.get('status') == 'success' and len(data.get('list', [])) > 0:
                files = data['list']
                await status_msg.edit_text(f"📁 ফোল্ডারে {len(files)}টি ফাইল পাওয়া গেছে! ডাউনলোড শুরু হচ্ছে...")
                
                for index, video_info in enumerate(files):
                    # 🚨 প্রতিবার ভিডিও ডাউনলোডের আগে API থেকে ফ্রেশ লিংক আনা হচ্ছে যেন লিংক এক্সপায়ার না হয়
                    try:
                        fresh_response = await asyncio.to_thread(requests.post, API_URL, json={'url': original_url}, timeout=30)
                        fresh_data = fresh_response.json()
                        fresh_stream_url = fresh_data['list'][index].get('stream_url')
                    except:
                        fresh_stream_url = video_info.get('stream_url')

                    video_title = video_info.get('name', f'video_{index}')
                    
                    safe_title = "".join([c for c in video_title if c.isalnum() or c==' ']).strip()
                    if not safe_title:
                        safe_title = f"video_{index}"
                        
                    file_name = f"{safe_title}.mp4"
                    
                    await status_msg.edit_text(f"⬇️ ডাউনলোড হচ্ছে ({index+1}/{len(files)}): \n🎬 {video_title}")
                    
                    # 🚨 ০.০০ মিনিটের সমস্যা ঠিক করার জন্য নতুন এবং শক্তিশালী yt-dlp সেটিংস
                    ydl_opts = {
                        'outtmpl': file_name,
                        'format': 'best',
                        'writethumbnail': True,
                        'quiet': True,
                        'retries': 15,                  # কানেকশন কাটলে ১৫ বার চেষ্টা করবে
                        'fragment_retries': 15,         # ফাইলের কোনো অংশ মিসিং হলে আবার চেষ্টা করবে
                        'nocheckcertificate': True,     # SSL এরর ইগনোর করবে
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                            'Accept': '*/*'
                        }
                    }
                    
                    def download_vid():
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([fresh_stream_url])
                        except Exception as e:
                            print(f"Download Error for {file_name}: {e}")
                            
                    await asyncio.to_thread(download_vid)
                    
                    # ফাইল সাইজ অন্তত ৫০০ কেবি হতে হবে, নাহলে সেটা করাপ্ট (০.০০ মিনিট)
                    if os.path.exists(file_name) and os.path.getsize(file_name) > 500 * 1024:  
                        await status_msg.edit_text(f"⬆️ টেলিগ্রামে আপলোড হচ্ছে ({index+1}/{len(files)})...")
                        
                        thumb_path = None
                        for ext in ['.jpg', '.jpeg', '.webp', '.png']:
                            potential_thumb = f"{safe_title}{ext}"
                            if os.path.exists(potential_thumb):
                                thumb_path = potential_thumb
                                break
                        
                        await client.send_video(
                            chat_id, 
                            video=file_name, 
                            thumb=thumb_path,
                            caption=f"✅ {video_title}\n\n🤖 Powered by TeraVid",
                            supports_streaming=True
                        )
                    else:
                        await client.send_message(chat_id, f"⚠️ '{video_title}' ভিডিওটি TeraBox সার্ভার ব্লক করার কারণে ডাউনলোড হয়নি। এটি স্কিপ করা হলো।")
                    
                    if os.path.exists(file_name): os.remove(file_name)
                    if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
                    
                await status_msg.delete()
                await client.send_message(chat_id, "✅ কাজ সফলভাবে শেষ হয়েছে!")
                
            else:
                await status_msg.edit_text("❌ ভিডিও লিংকটি কাজ করছে না বা ফাইল পাওয়া যায়নি।")

        except Exception as e:
            await status_msg.edit_text(f"❌ এরর: {str(e)}")
            for file in os.listdir():
                if file.endswith(('.mp4', '.jpg', '.webp', '.png', '.jpeg')): 
                    try: os.remove(file)
                    except: pass
                
    is_processing = False

# --- Start Command ---
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    await message.reply("হ্যালো! 🤖 আমি TeraVid প্রো বট।\n\nআমাকে যেকোনো TeraBox লিংক (বা ফরোয়ার্ড করা পোস্ট) দিলে আমি ভিডিও ডাউনলোড করে দেব।\n\nচ্যানেল অটো-ডিটেক্ট চালু করতে লিখুন: `/setchannel @আপনার_চ্যানেলের_ইউজারনেম`")

# --- Set Channel Command ---
@app.on_message(filters.private & filters.command("setchannel"))
async def set_channel_cmd(client, message):
    global target_channel
    try:
        parts = message.text.split(" ")
        if len(parts) > 1:
            channel = parts[1].strip()
            if not channel.startswith("@"): channel = "@" + channel
            target_channel = channel
            await message.reply(f"✅ চ্যানেল সেট করা হয়েছে: {target_channel}\n\n⚠️ মনে রাখবেন: আমাকে অবশ্যই এই চ্যানেলে **অ্যাডমিন (Admin)** বানাতে হবে।")
        else:
            raise Exception()
    except:
        await message.reply("⚠️ সঠিক নিয়ম: `/setchannel @আপনার_চ্যানেলের_ইউজারনেম`")

# --- ইনবক্সে লিংক বা ফরোয়ার্ড করা পোস্ট আসলে (টেক্সট এবং ক্যাপশন সাপোর্ট) ---
@app.on_message(filters.private & (filters.text | filters.caption) & filters.regex(r"https?://"))
async def private_link_handler(client, message):
    text = message.text or message.caption
    
    urls = re.findall(r'(https?://[^\s]+)', text)
    if not urls:
        return
        
    for url in urls:
        link_queue.append({'chat_id': message.chat.id, 'url': url})
        
    queue_position = len(link_queue)
    if queue_position > len(urls):
        await message.reply(f"⏳ লিংকগুলো সিরিয়ালে যুক্ত হয়েছে। আগে আরও {queue_position - len(urls)} টি লিংক ডাউনলোডের কাজ চলছে।")
    
    asyncio.create_task(process_video_task(client))

# --- চ্যানেলে লিংক বা ফরোয়ার্ড করা পোস্ট আসলে ---
@app.on_message(filters.channel & (filters.text | filters.caption) & filters.regex(r"https?://"))
async def channel_link_handler(client, message):
    global target_channel
    if target_channel:
        chat_username = f"@{message.chat.username}" if message.chat.username else ""
        chat_id_str = str(message.chat.id)
        
        if target_channel.lower() == chat_username.lower() or target_channel == chat_id_str:
            text = message.text or message.caption
            urls = re.findall(r'(https?://[^\s]+)', text)
            
            for url in urls:
                link_queue.append({'chat_id': message.chat.id, 'url': url})
            
            asyncio.create_task(process_video_task(client))

print("✅ Pro TeraVid Bot is running smoothly with 0.00 min Fix...")
app.run()
