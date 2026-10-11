import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading
import time
import json
import os
import re
import imaplib

# ================= CONFIGURATION =================
BOT_TOKEN = "8937677864:AAHy-2OCC12N1yxhPf8gXIbhcIIoBJ0XgsM"
ADMIN_ID = 8984439807
DATA_FILE = "bot_data.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ================= DATABASE =================
default_data = {
    "users": {},
    "channels": [], 
    "refer_target": 5,
    "payment": {"email": "", "password": "", "upi": "", "price": "150"},
    "welcome_text": "<b>Welcome to our Bot! Enjoy your stay.</b>",
    "normal_videos": [], 
    "premium_videos": [],
    "auto_post_channel_id": None
}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            db = json.load(f)
        except:
            db = default_data.copy()
else:
    db = default_data.copy()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=4)

deletion_queue = []
user_states = {}

# ================= FLASK SERVER =================
@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= BACKGROUND WORKER =================
def background_worker():
    last_post_time = time.time()
    while True:
        current_time = time.time()
        
        # Auto Delete Messages (30 mins = 1800 sec)
        to_remove = []
        for item in deletion_queue:
            if current_time - item['time'] >= 1800:
                try:
                    bot.delete_message(item['chat_id'], item['msg_id'])
                except:
                    pass
                to_remove.append(item)
        for item in to_remove:
            deletion_queue.remove(item)
            
        # Auto Post to Channel (Every 1 hour = 3600 sec)
        if current_time - last_post_time >= 3600:
            if db.get("auto_post_channel_id") and len(db["normal_videos"]) >= 3:
                import random
                post_vids = random.sample(db["normal_videos"], min(3, len(db["normal_videos"])))
                for vid in post_vids:
                    try:
                        if vid['type'] == 'photo':
                            bot.send_photo(db["auto_post_channel_id"], vid['file_id'], caption=vid['caption'], parse_mode="HTML")
                        else:
                            bot.send_video(db["auto_post_channel_id"], vid['file_id'], caption=vid['caption'], parse_mode="HTML")
                    except:
                        pass
            last_post_time = current_time
            
        time.sleep(10)

threading.Thread(target=background_worker, daemon=True).start()

# ================= EMAIL UTR VERIFICATION =================
def check_utr_in_mail(utr):
    try:
        email_user = db["payment"]["email"]
        email_pass = db["payment"]["password"]
        if not email_user or not email_pass:
            return False
            
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_user, email_pass)
        mail.select("inbox")
        
        status, messages = mail.search(None, f'TEXT "{utr}"')
        if status == "OK" and messages[0]:
            return True
        return False
    except:
        return False

# ================= KEYBOARDS =================
def user_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("GET VIDEO 🤤🫦"),
        KeyboardButton("GET PREMIUM 👑"),
        KeyboardButton("Refer and get premium 🎁")
    )
    return markup

def admin_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Manage Channel 📢", callback_data="admin_channel"),
        InlineKeyboardButton("Refer Manage 🎁", callback_data="admin_refer"),
        InlineKeyboardButton("Manage Payment 💳", callback_data="admin_payment"),
        InlineKeyboardButton("Stats 📊", callback_data="admin_stats"),
        InlineKeyboardButton("Backup 📁", callback_data="admin_backup"),
        InlineKeyboardButton("Restore 🔄", callback_data="admin_restore"),
        InlineKeyboardButton("Broadcast 📢", callback_data="admin_broadcast"),
        InlineKeyboardButton("Add Normal Video 🎬", callback_data="admin_add_normal"),
        InlineKeyboardButton("Add Premium Video 💎", callback_data="admin_add_premium"),
        InlineKeyboardButton("Set Welcome Text 📝", callback_data="admin_set_welcome"),
        InlineKeyboardButton("Set Auto-Post Channel ⚙️", callback_data="admin_set_channel_id")
    )
    return markup

# ================= AUTO APPROVE JOIN REQUESTS =================
@bot.chat_join_request_handler()
def handle_join_request(request):
    try:
        user_id = str(request.from_user.id)
        bot.approve_chat_join_request(request.chat.id, request.from_user.id)
        
        if user_id not in db["users"]:
            db["users"][user_id] = {"premium": False, "refers": 0, "normal_index": 0, "premium_index": 0, "verified": True}
        else:
            db["users"][user_id]["verified"] = True
        save_data()
        
        bot.send_message(request.from_user.id, "✅ <b>Your join request was approved!</b>", parse_mode="HTML")
        bot.send_message(request.from_user.id, db["welcome_text"], reply_markup=user_main_keyboard(), parse_mode="HTML")
    except:
        pass

# ================= /START & FORCE JOIN =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    
    # Referral handling
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
        if ref_id != user_id and user_id not in db["users"]:
            if ref_id in db["users"]:
                db["users"][ref_id]["refers"] += 1
                save_data()
                try:
                    bot.send_message(ref_id, f"🎉 <b>New user joined using your link!</b>\nTotal Refers: {db['users'][ref_id]['refers']}/{db['refer_target']}", parse_mode="HTML")
                    if db["users"][ref_id]["refers"] >= db["refer_target"] and not db["users"][ref_id]["premium"]:
                        db["users"][ref_id]["premium"] = True
                        save_data()
                        bot.send_message(ref_id, "🥳 <b>Congratulations! You unlocked PREMIUM!</b>", parse_mode="HTML")
                except:
                    pass
    
    if user_id not in db["users"]:
        db["users"][user_id] = {"premium": False, "refers": 0, "normal_index": 0, "premium_index": 0, "verified": False}
        save_data()

    # Admin Bypass
    if user_id == str(ADMIN_ID):
        db["users"][user_id]["verified"] = True
        save_data()
        bot.send_message(message.chat.id, db["welcome_text"], reply_markup=user_main_keyboard(), parse_mode="HTML")
        return

    check_channels_and_proceed(message.chat.id)

def check_channels_and_proceed(chat_id):
    not_joined = []
    for ch in db["channels"]:
        try:
            status = bot.get_chat_member(int(ch['id']), chat_id).status
            if status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch['link'])
        except:
            not_joined.append(ch['link'])
            
    if not_joined:
        markup = InlineKeyboardMarkup()
        for i, link in enumerate(not_joined):
            markup.add(InlineKeyboardButton(f"Join Channel {i+1}", url=link))
        markup.add(InlineKeyboardButton("✅ Verify", callback_data="verify_join"))
        bot.send_message(chat_id, "⚠️ <b>Please join our channels to use this bot!</b>\n<i>Send join request and click Verify.</i>", reply_markup=markup, parse_mode="HTML")
    else:
        db["users"][str(chat_id)]["verified"] = True
        save_data()
        bot.send_message(chat_id, db["welcome_text"], reply_markup=user_main_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    chat_id = call.message.chat.id
    
    not_joined = []
    for ch in db["channels"]:
        try:
            status = bot.get_chat_member(int(ch['id']), chat_id).status
            if status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch['link'])
        except:
            not_joined.append(ch['link'])
            
    if not_joined:
        bot.answer_callback_query(call.id, "❌ Not joined yet! Please join the channels and try again.", show_alert=True)
    else:
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        db["users"][str(chat_id)]["verified"] = True
        save_data()
        bot.answer_callback_query(call.id, "✅ Verified successfully!")
        bot.send_message(chat_id, db["welcome_text"], reply_markup=user_main_keyboard(), parse_mode="HTML")

# ================= USER BUTTON HANDLERS =================
@bot.message_handler(func=lambda msg: msg.text and "GET VIDEO" in msg.text.upper())
def send_normal_video(message):
    user_id = str(message.chat.id)
    if not db["users"].get(user_id, {}).get("verified"):
        return check_channels_and_proceed(message.chat.id)
        
    videos = db["normal_videos"]
    if not videos:
        bot.send_message(message.chat.id, "No normal videos available right now!")
        return
        
    idx = db["users"][user_id]["normal_index"]
    if idx >= len(videos):
        idx = 0 
        
    to_send = videos[idx:idx+3]
    db["users"][user_id]["normal_index"] = idx + len(to_send)
    save_data()
    
    for vid in to_send:
        try:
            if vid['type'] == 'photo':
                msg = bot.send_photo(message.chat.id, vid['file_id'], caption=vid['caption'] + "\n\n<i>⏳ Auto delete in 30 mins</i>", parse_mode="HTML")
            else:
                msg = bot.send_video(message.chat.id, vid['file_id'], caption=vid['caption'] + "\n\n<i>⏳ Auto delete in 30 mins</i>", parse_mode="HTML")
            deletion_queue.append({'chat_id': message.chat.id, 'msg_id': msg.message_id, 'time': time.time()})
        except:
            pass

@bot.message_handler(func=lambda msg: msg.text and "GET PREMIUM" in msg.text.upper())
def get_premium(message):
    user_id = str(message.chat.id)
    if not db["users"].get(user_id, {}).get("verified"):
        return check_channels_and_proceed(message.chat.id)

    if db["users"].get(user_id, {}).get("premium"):
        videos = db["premium_videos"]
        if not videos:
            bot.send_message(message.chat.id, "No premium videos available!")
            return
        idx = db["users"][user_id]["premium_index"]
        if idx >= len(videos):
            idx = 0
        vid = videos[idx]
        db["users"][user_id]["premium_index"] = idx + 1
        save_data()
        
        try:
            if vid['type'] == 'photo':
                msg = bot.send_photo(message.chat.id, vid['file_id'], caption=vid['caption'] + "\n\n<i>⏳ Auto delete in 30 mins</i>", parse_mode="HTML")
            else:
                msg = bot.send_video(message.chat.id, vid['file_id'], caption=vid['caption'] + "\n\n<i>⏳ Auto delete in 30 mins</i>", parse_mode="HTML")
            deletion_queue.append({'chat_id': message.chat.id, 'msg_id': msg.message_id, 'time': time.time()})
        except:
            pass
    else:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Buy Premium", callback_data="buy_premium"))
        price = db["payment"]["price"]
        bot.send_message(message.chat.id, f"💎 <b>PREMIUM MEMBERSHIP</b>\n\nGet Ads-free unlimited exclusive videos!\n<b>Price:</b> ₹{price}\n\nClick below to buy!", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "buy_premium")
def buy_premium_callback(call):
    upi = db["payment"]["upi"]
    if not upi:
        bot.answer_callback_query(call.id, "Payment not configured by admin.", show_alert=True)
        return
        
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={upi}%26pn=Admin"
    bot.send_photo(call.message.chat.id, qr_url, caption=f"Scan this QR or Pay to: `{upi}`\n\n<b>After payment, send your 12-digit UTR/Ref No below.</b>", parse_mode="HTML")
    user_states[call.message.chat.id] = "WAITING_FOR_UTR"

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "WAITING_FOR_UTR")
def process_utr(message):
    utr = message.text.strip()
    chat_id = message.chat.id
    msg_load = bot.send_message(chat_id, "🔄 <i>Verifying your payment... please wait 3 seconds.</i>", parse_mode="HTML")
    time.sleep(3) 
    
    if check_utr_in_mail(utr):
        db["users"][str(chat_id)]["premium"] = True
        save_data()
        bot.edit_message_text("✅ <b>Payment Approved! PREMIUM UNLOCKED!</b> 🥳", chat_id, msg_load.message_id, parse_mode="HTML")
        user_states.pop(chat_id, None)
    else:
        bot.edit_message_text("❌ <b>Payment not found or UTR invalid!</b> Please check and try again.", chat_id, msg_load.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text and "REFER" in msg.text.upper())
def refer_system(message):
    user_id = str(message.chat.id)
    if not db["users"].get(user_id, {}).get("verified"):
        return check_channels_and_proceed(message.chat.id)

    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    refers = db["users"].get(user_id, {}).get("refers", 0)
    target = db["refer_target"]
    
    msg = f"🎁 <b>Refer & Earn Premium!</b>\n\nInvite friends and get premium for FREE!\n\n<b>Your Points:</b> {refers}/{target}\n<b>Your Link:</b> <code>{ref_link}</code>\n\n<i>Share this link with your friends. Once they verify, you get 1 point!</i>"
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

# ================= ADMIN PANEL =================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "🛠 <b>Admin Control Panel</b>", reply_markup=admin_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    chat_id = call.message.chat.id
    if chat_id != ADMIN_ID:
        return
        
    action = call.data
    if action == "admin_stats":
        tot_users = len(db["users"])
        prem_users = sum(1 for u in db["users"].values() if u["premium"])
        bot.send_message(chat_id, f"📊 <b>Bot Stats</b>\n👥 Total Users: {tot_users}\n💎 Premium Users: {prem_users}\n🎬 Normal Videos: {len(db['normal_videos'])}\n👑 Premium Videos: {len(db['premium_videos'])}", parse_mode="HTML")
    elif action == "admin_backup":
        try: bot.send_document(chat_id, open(DATA_FILE, "rb"))
        except: bot.send_message(chat_id, "Backup file not found.")
    elif action == "admin_restore":
        bot.send_message(chat_id, "Send me the backup `bot_data.json` file.", parse_mode="Markdown")
        user_states[chat_id] = "WAITING_RESTORE"
    elif action == "admin_set_welcome":
        bot.send_message(chat_id, "Send the new welcome text (HTML format supported).")
        user_states[chat_id] = "WAITING_WELCOME"
    elif action == "admin_broadcast":
        bot.send_message(chat_id, "Send the message you want to broadcast.")
        user_states[chat_id] = "WAITING_BROADCAST"
    elif action == "admin_add_normal":
        bot.send_message(chat_id, "Forward normal photos/videos here. Type /stop when done.")
        user_states[chat_id] = "WAITING_NORMAL_VIDEOS"
    elif action == "admin_add_premium":
        bot.send_message(chat_id, "Forward premium photos/videos here. Type /stop when done.")
        user_states[chat_id] = "WAITING_PREMIUM_VIDEOS"
    elif action == "admin_payment":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Set Email & Pass", callback_data="set_pay_email"), InlineKeyboardButton("Set UPI", callback_data="set_pay_upi"))
        markup.add(InlineKeyboardButton("Set Price", callback_data="set_pay_price"))
        bot.send_message(chat_id, "Manage Payment System:", reply_markup=markup)
    elif action == "admin_refer":
        bot.send_message(chat_id, "Send the number of refers needed for Premium:")
        user_states[chat_id] = "WAITING_REFER_TARGET"
    elif action == "admin_channel":
        bot.send_message(chat_id, "Send Channel ID and Invite Link separated by space.\nExample: `-1001234567 https://t.me/joinchat/...`\nType /clear to remove all.")
        user_states[chat_id] = "WAITING_CHANNEL"
    elif action == "admin_set_channel_id":
        bot.send_message(chat_id, "Forward a message from your target Auto-Post channel.")
        user_states[chat_id] = "WAITING_AUTOPOST_CHANNEL"

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_pay_"))
def payment_callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "set_pay_email":
        bot.send_message(chat_id, "Send Email and App Password separated by space.")
        user_states[chat_id] = "WAITING_PAY_EMAIL"
    elif call.data == "set_pay_upi":
        bot.send_message(chat_id, "Send your UPI ID")
        user_states[chat_id] = "WAITING_PAY_UPI"
    elif call.data == "set_pay_price":
        bot.send_message(chat_id, "Send Premium Price amount")
        user_states[chat_id] = "WAITING_PAY_PRICE"

@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and user_states.get(msg.chat.id) in ["WAITING_RESTORE", "WAITING_WELCOME", "WAITING_BROADCAST", "WAITING_PAY_EMAIL", "WAITING_PAY_UPI", "WAITING_PAY_PRICE", "WAITING_REFER_TARGET", "WAITING_CHANNEL", "WAITING_AUTOPOST_CHANNEL"])
def admin_text_inputs(message):
    chat_id = message.chat.id
    state = user_states[chat_id]
    
    if state == "WAITING_WELCOME":
        db["welcome_text"] = message.text
        save_data()
        bot.send_message(chat_id, "✅ Welcome text updated!")
    elif state == "WAITING_REFER_TARGET":
        try:
            db["refer_target"] = int(message.text)
            save_data()
            bot.send_message(chat_id, "✅ Refer target updated!")
        except: bot.send_message(chat_id, "❌ Valid number required.")
    elif state == "WAITING_PAY_EMAIL":
        parts = message.text.split(maxsplit=1)
        if len(parts) == 2:
            db["payment"]["email"] = parts[0]
            db["payment"]["password"] = parts[1].replace(" ", "")
            save_data()
            bot.send_message(chat_id, "✅ Email & Password saved!")
    elif state == "WAITING_PAY_UPI":
        db["payment"]["upi"] = message.text
        save_data()
        bot.send_message(chat_id, "✅ UPI ID saved!")
    elif state == "WAITING_PAY_PRICE":
        db["payment"]["price"] = message.text
        save_data()
        bot.send_message(chat_id, "✅ Price saved!")
    elif state == "WAITING_CHANNEL":
        if message.text == "/clear":
            db["channels"] = []
            save_data()
            bot.send_message(chat_id, "✅ Channels cleared!")
        else:
            parts = message.text.split()
            if len(parts) >= 2:
                db["channels"].append({"id": parts[0], "link": parts[1]})
                save_data()
                bot.send_message(chat_id, "✅ Channel Added!")
    elif state == "WAITING_BROADCAST":
        sent = 0
        bot.send_message(chat_id, "⏳ Broadcasting...")
        for u in list(db["users"].keys()):
            try:
                bot.copy_message(u, chat_id, message.message_id)
                sent += 1
            except: pass
        bot.send_message(chat_id, f"✅ Broadcast sent to {sent} users.")
    elif state == "WAITING_AUTOPOST_CHANNEL":
        if message.forward_from_chat:
            db["auto_post_channel_id"] = message.forward_from_chat.id
            save_data()
            bot.send_message(chat_id, f"✅ Auto-post channel ID saved.")
    user_states.pop(chat_id, None)

@bot.message_handler(content_types=['document'], func=lambda msg: msg.chat.id == ADMIN_ID and user_states.get(msg.chat.id) == "WAITING_RESTORE")
def restore_backup(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(DATA_FILE, 'wb') as new_file: new_file.write(downloaded_file)
        global db
        with open(DATA_FILE, "r") as f: db = json.load(f)
        bot.send_message(ADMIN_ID, "✅ Backup restored!")
    except: bot.send_message(ADMIN_ID, "❌ Restore failed!")
    user_states.pop(ADMIN_ID, None)

@bot.message_handler(content_types=['photo', 'video', 'text'], func=lambda msg: msg.chat.id == ADMIN_ID and user_states.get(msg.chat.id) in ["WAITING_NORMAL_VIDEOS", "WAITING_PREMIUM_VIDEOS"])
def add_videos(message):
    chat_id = message.chat.id
    state = user_states[chat_id]
    
    if message.text == "/stop":
        user_states.pop(chat_id, None)
        bot.send_message(chat_id, "✅ Stopped adding videos.")
        return
    if message.content_type not in ['photo', 'video']: return

    file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.video.file_id
    caption = message.caption or ""

    if state == "WAITING_NORMAL_VIDEOS":
        links = re.findall(r'(https?://[^\s]+)', caption)
        link = links[0] if links else "LINK_NOT_FOUND"
        new_caption = f"<b>FULL VIDEO LINK 👇🤤🫦</b>\n\n🔗 {link}\n\n👑 <i>Buy Premium for ADS FREE unlimited videos!</i>"
        db["normal_videos"].append({'type': message.content_type, 'file_id': file_id, 'caption': new_caption})
        save_data()
        bot.send_message(chat_id, "✅ Normal Post Added!")
    elif state == "WAITING_PREMIUM_VIDEOS":
        db["premium_videos"].append({'type': message.content_type, 'file_id': file_id, 'caption': caption})
        save_data()
        bot.send_message(chat_id, "✅ Premium Post Added!")

# Fallback catch-all for verified users
@bot.message_handler(func=lambda msg: True)
def fallback_handler(message):
    user_id = str(message.chat.id)
    if db["users"].get(user_id, {}).get("verified"):
        bot.send_message(message.chat.id, "Please use the menu below 👇", reply_markup=user_main_keyboard())
    else:
        check_channels_and_proceed(message.chat.id)

# ================= START BOT =================
if __name__ == "__main__":
    print("Bot is running...")
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
