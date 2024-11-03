import random
import logging
from telegram import Update, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler

# লগিং কনফিগারেশন
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# অ্যাডমিন আইডির তালিকা
ADMIN_IDS = [6061043680]

# ক্যাপচা প্রশ্নের ধরন
captcha_questions = [
    {"type": "text", "question": "৫ + ৩ কত?", "answer": "৮", "options": ["৬", "৭", "৮", "৯"]},
    {"type": "text", "question": "বাংলার রাজধানী কী?", "answer": "ঢাকা", "options": ["ঢাকা", "চট্টগ্রাম", "খুলনা", "রাজশাহী"]},
    {"type": "image", "question": "এই ছবিতে কোন প্রাণী আছে?", "answer": "বাঘ", "media": "media/im.jpg", "options": ["হাতি", "গরু", "বাঘ", "পান্ডা"]},
    {"type": "audio", "question": "এই অডিওতে কোন সুর শোনা যাচ্ছে?", "answer": "সুর ১", "media": "media/au.mp3", "options": ["সুর ১", "সুর ২", "সুর ৩", "সুর ৪"]}
]

# ক্যাপচা চেষ্টার পরিসংখ্যান
captcha_stats = {
    "total_attempts": 0,
    "successful_captchas": 0,
    "failed_captchas": 0
}

# নোটিফিকেশন চ্যানেল আইডি
NOTIFY_CHANNEL_ID = "@captchboss"  # চ্যানেল প্রাইভেট হলে সঠিক আইডি ব্যবহার করুন

# নতুন সদস্যদের স্বাগতম জানানো ও ক্যাপচা পাঠানো
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        question_data = random.choice(captcha_questions)
        captcha_stats["total_attempts"] += 1

        welcome_message = f"🥰 স্বাগতম  {member.first_name}!\nগ্রুপের নিয়ম মেনে চলুন এবং ক্যাপচা সমাধান করুন।"
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=member.id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        # ইনলাইন বোতাম অপশন সেটআপ
        keyboard = [
            [InlineKeyboardButton(option, callback_data=f"{member.id}:{option}") for option in question_data["options"]]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # প্রশ্নের ধরন অনুযায়ী মেসেজ পাঠানো
            if question_data["type"] == "image":
                with open(question_data["media"], 'rb') as photo:
                    sent_message = await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=f"{welcome_message}\n\nক্যাপচা প্রশ্ন: \n{question_data['question']}",
                        reply_markup=reply_markup
                    )
            elif question_data["type"] == "audio":
                with open(question_data["media"], 'rb') as audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio,
                        caption=f"{welcome_message}\n\nক্যাপচা প্রশ্ন: \n{question_data['question']}",
                        reply_markup=reply_markup
                    )
            else:
                sent_message = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"{welcome_message}\n\nক্যাপচা প্রশ্ন: \n{question_data['question']}",
                    reply_markup=reply_markup
                )

            # সঠিক উত্তর ও বার্তা আইডি সংরক্ষণ
            context.user_data[member.id] = {
                "correct_answer": question_data["answer"].lower(),
                "attempts": 0,
                "message_id": sent_message.message_id
            }

        except Exception as e:
            logger.error(f"বার্তা পাঠাতে ত্রুটি: {e}")

# ক্যাপচা উত্তর যাচাই
async def captcha_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id, answer = query.data.split(":")
    user_id = int(user_id)

    if query.from_user.id != user_id:
        await query.answer("এই ক্যাপচাটি আপনার জন্য নয়!❌", show_alert=True)
        return

    user_data = context.user_data.get(user_id, {})
    correct_answer = user_data.get("correct_answer", "").lower()
    attempts = user_data.get("attempts", 0)

    if answer.lower() == correct_answer:
        captcha_stats["successful_captchas"] += 1

        await context.bot.restrict_chat_member(
            chat_id=query.message.chat.id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=True)
        )

        await query.answer("ধন্যবাদ! আপনি সফলভাবে ক্যাপচা সমাধান করেছেন! ✅")

        # সফল সমাধানকারীর তথ্য চ্যানেলে পাঠানো
        username = query.from_user.username or "N/A"
        user_message = (
            f"*সফল ক্যাপচা সমাধানকারী:*\n\n"
            f"*ইউজারনেম:* @{username}\n"
            f"*চ্যাট আইডি:* `{query.message.chat.id}`\n"
            f"*ইউজার আইডি:* `{user_id}`"
        ).replace("_", "\\_").replace("*", "\\*")  # Escaping special characters

        try:
            await context.bot.send_message(
                chat_id=NOTIFY_CHANNEL_ID,
                text=user_message,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"চ্যানেলে বার্তা পাঠাতে ত্রুটি: {e}")

        # ক্যাপচা বার্তা মুছে ফেলা
        try:
            await context.bot.delete_message(chat_id=query.message.chat.id, message_id=user_data["message_id"])
        except Exception as e:
            logger.error(f"ক্যাপচা বার্তা মুছতে ত্রুটি: {e}")

        del context.user_data[user_id]
    else:
        attempts += 1
        user_data["attempts"] = attempts

        if attempts >= 5:
            captcha_stats["failed_captchas"] += 1
            await query.message.reply_text("আপনি বারবার ভুল উত্তর দিয়েছেন। দুঃখিত, আপনার প্রবেশাধিকার বন্ধ করা হয়েছে।")
            await context.bot.ban_chat_member(chat_id=query.message.chat.id, user_id=user_id)

            if "message_id" in user_data:
                try:
                    await context.bot.delete_message(chat_id=query.message.chat.id, message_id=user_data["message_id"])
                except Exception as e:
                    logger.error(f"বার্তা মুছতে ত্রুটি: {e}")

            del context.user_data[user_id]
        else:
            await query.answer("আপনার উত্তর সঠিক নয়, আবার চেষ্টা করুন!", show_alert=True)

# অ্যাডমিনদের জন্য ক্যাপচা পরিসংখ্যান দেখানো
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(
            f"**ক্যাপচা পরিসংখ্যান**:\n\n"
            f"*মোট চেষ্টা:* {captcha_stats['total_attempts']}\n"
            f"*সফল ক্যাপচা:* {captcha_stats['successful_captchas']}\n"
            f"*ব্যর্থ ক্যাপচা:* {captcha_stats['failed_captchas']}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"অ্যাডমিন {update.effective_user.id} ক্যাপচা পরিসংখ্যান দেখতে চেয়েছেন।")
    else:
        await update.message.reply_text("দুঃখিত, এই কমান্ডটি কেবল এডমিনদের জন্য।")

# নতুন ক্যাপচা প্রশ্ন যুক্ত করার অ্যাডমিন কমান্ড
async def add_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        if len(context.args) < 3:
            await update.message.reply_text("দয়া করে প্রশ্ন, সঠিক উত্তর এবং অপশনসমূহ দিয়ে ক্যাপচা যুক্ত করুন।")
            return

        new_question = " ".join(context.args[:-1])
        answer = context.args[-1]
        options = context.args[2:-1]

        captcha_questions.append({
            "type": "text",
            "question": new_question,
            "answer": answer,
            "options": options
        })

        await update.message.reply_text(f"নতুন ক্যাপচা প্রশ্ন যুক্ত হয়েছে: {new_question}")
        logger.info(f"নতুন ক্যাপচা প্রশ্ন যুক্ত করেছেন অ্যাডমিন {update.effective_user.id}: {new_question}")
    else:
        await update.message.reply_text("দুঃখিত, এই কমান্ডটি কেবল এডমিনদের জন্য।")


# কোনো সদস্য গ্রুপ ত্যাগ করলে নোটিফিকেশন পাঠানো
async def left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    left_member = update.message.left_chat_member
    if left_member:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{left_member.full_name} আবাল গ্রুপ থেকে চলে গেছে।"
        )
        logger.info(f"সদস্য চলে গেছে: {left_member.full_name}")

# মূল ফাংশন যা বট চালায়
def main():
    application = Application.builder().token("7827787271:AAGeLcQfjriN6W-BJrfNWfW-GbNYKvLGZdo").build()  # আপনার টোকেন এখানে বসান

    # হ্যান্ডলার যুক্ত করা
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    application.add_handler(CallbackQueryHandler(captcha_button))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("add_captcha", add_captcha))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, left_member))

    # বট চালানো
    application.run_polling()

if __name__ == '__main__':
    main()
