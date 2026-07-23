import telebot
import yt_dlp
import os
import requests

# আপনার বটের টোকেন এবং API লিংক
BOT_TOKEN = '8383008423:AAHF-K6u19fRvu-_bJuMDTMHyf8wPDeRJto'
API_URL = 'https://teraboxvid.vercel.app/api/video' 

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 স্বাগতম! TeraVid টেলিগ্রাম বটে আপনাকে স্বাগতম।\n\n"
        "🔗 আমাকে যেকোনো TeraBox লিংক দিন, আমি ডাইরেক্ট ভিডিওটি ডাউনলোড করে এখানে পাঠিয়ে দেব।"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: message.text.startswith('http'))
def handle_link(message):
    original_url = message.text
    status_msg = bot.reply_to(message, "🔍 TeraBox লিংক প্রসেস করা হচ্ছে...")

    try:
        # ১. TeraVid API থেকে ডাইরেক্ট লিংক বের করা
        response = requests.post(API_URL, json={'url': original_url})
        
        if response.status_code != 200:
            raise Exception("API সার্ভার থেকে রেসপন্স পাওয়া যাচ্ছে না।")
            
        data = response.json()
        
        if data.get('status') == 'success' and len(data.get('list', [])) > 0:
            video_info = data['list'][0]
            direct_stream_url = video_info.get('stream_url')
            video_title = video_info.get('name', f'video_{message.chat.id}')
            
            # ফাইলের নাম ঠিক করা (অপ্রয়োজনীয় ক্যারেক্টার বাদ দিয়ে)
            safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            file_name = f"{safe_title}.mp4"
            
            bot.edit_message_text(
                f"⬇️ ভিডিও পাওয়া গেছে! ডাউনলোড হচ্ছে...\n\n🎬 নাম: {video_title}", 
                chat_id=message.chat.id, 
                message_id=status_msg.message_id
            )
            
            # ২. ডাইরেক্ট লিংক থেকে yt-dlp দিয়ে ডাউনলোড
            ydl_opts = {
                'outtmpl': file_name,
                'format': 'best',
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([direct_stream_url])
                
            # ৩. টেলিগ্রামে আপলোড করা
            bot.edit_message_text(
                "⬆️ টেলিগ্রামে আপলোড করা হচ্ছে... একটু অপেক্ষা করুন।", 
                chat_id=message.chat.id, 
                message_id=status_msg.message_id
            )
            
            with open(file_name, 'rb') as video_file:
                bot.send_video(
                    message.chat.id, 
                    video_file, 
                    caption=f"✅ ডাউনলোড সম্পন্ন!\n📁 {video_title}\n\n🤖 Powered by TeraVid"
                )
                
            # ৪. কাজ শেষে লোকাল সার্ভার থেকে ফাইল ডিলিট করে স্টোরেজ ক্লিয়ার করা
            if os.path.exists(file_name):
                os.remove(file_name)
            bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            
        else:
            bot.edit_message_text(
                "❌ ভিডিও লিংকটি কাজ করছে না বা ফাইলটি ডিলিট হয়ে গেছে।", 
                chat_id=message.chat.id, 
                message_id=status_msg.message_id
            )

    except Exception as e:
        error_text = f"❌ এরর: ভিডিওটি প্রসেস করা সম্ভব হয়নি।\n{str(e)}"
        bot.edit_message_text(error_text, chat_id=message.chat.id, message_id=status_msg.message_id)
        
        # ফেইল হলে যেকোনো অসম্পূর্ণ .mp4 ফাইল ডিলিট করে সার্ভার ক্লিন রাখা
        for file in os.listdir():
            if file.endswith('.mp4'):
                os.remove(file)

print("✅ TeraVid Telegram Bot is running successfully...")
bot.infinity_polling()