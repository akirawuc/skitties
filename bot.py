import os
from dotenv import load_dotenv
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from fc import *
from summarize import *
from datetime import datetime, timedelta, date, timezone
import time

load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Constants for pagination steps
FIRST_PAGE = 0
ITEMS_PER_PAGE = 1
df = pd.DataFrame()

def get_pagination_keyboard(current_page):
    
    keyboard = []
    # Add a 'Previous' button if it's not the first page
    if current_page > FIRST_PAGE:
        keyboard.append(InlineKeyboardButton('Previous', callback_data=f'page_{current_page - 1}'))
    # Add a 'Next' button if there are more pages left
    if (current_page + 1) * ITEMS_PER_PAGE < 25:
        keyboard.append(InlineKeyboardButton('Next', callback_data=f'page_{current_page + 1}'))
    return keyboard

def render_cast(i, row, show_text=False):
    if show_text:
        result = row['text'] + "\n\n"
        return result
    last_date = time_passed(row['timestamp'], timezone_aware=True) if row['timestamp'] is not None else 'Unknown'
    handle = row['handle'] if row['handle'] is not None else ''
    display_name = row['display_name'] if row['display_name'] is not None else ''

    result = "<b>#" + str(i) + ". "+display_name + " - <i>@" + handle + "</i></b> \n"  
    result += str(row['likes']) + " 👍 - " + str(row['replies']) + " 💬 - " + str(row['shares']) + " 📣 \n" 
    result += "<i>" +last_date + "</i> \n\n" 

    result += f"👉 See <a href='{FARCASTER_CLIENT_URL_REDIRECT + handle}/0x{row['hash'][:9]}'>cast</a> or <a href='{FARCASTER_CLIENT_URL_REDIRECT + handle}'>profile</a> on Warpcast."

    return result

def render_message(df, page):
    
    for i, row in df.iloc[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE].iterrows():
        cast_as_message = render_cast(page+1, row)
        
        read = [
            InlineKeyboardButton("Read cast", callback_data=f"read_{page}"),
            InlineKeyboardButton("Similar casts", callback_data=f"similar_{row['hash']}")]
        if row['replies'] > 0:
            summarize = [InlineKeyboardButton("Summarize replies", callback_data=f"summarize_{row['hash']}")]
            reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), read, summarize])
        else:
            reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), read])
            # keyboard = [
            #     [
            #         InlineKeyboardButton("Like", callback_data=f"like_{row['hash']}}"),
            #         InlineKeyboardButton("Share", callback_data=f"share_{row['hash']}"),
            #         InlineKeyboardButton("Reply", callback_data=f"reply_{row['hash']}"),
            #     ],
            #     [
            #         InlineKeyboardButton("Read Post", callback_data=f"/post_{row['hash']}"),
            #         InlineKeyboardButton("Show Replies", callback_data=f"/replies_{row['hash']}")
            #     ],
            # ]

        return cast_as_message, reply_markup
  
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    message = " Welcome anon! Skitties are your little birds that live Farcaster. 🦜\n\n"
    message += "Constanttly, they fly up and down the blocks and around the hubs to bring you the latest news, conversations directly into your chatbox. \n\n"
    message += "Get started by typing /search 'keyword' to find your people, or /trending to see what's up."
    message += "Slitties also keep tab on who is /popular to keep you in the loop. \n\n"
    message += "Are you a Farcaster user already? Type /forme 'handle' to see your personalized feed. Or heck, ask Skitties to show you Vitalik's! (/forme vitalik.eth) \n\n"
    message += "And don't forget, Skitties have highly dense artificial neurons so they are well versed in human language... They can summarize the long conversations and can give you time back and less FOMO. \n\n"
    message += "And when you find something interesting, Skitties will get you more of it. Just type /similar 'post_link' or the similar button under a cast you like. \n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML')
    
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df
    page = FIRST_PAGE

    bot_message = f"Fetching search results... \n\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

    # GET SEARCH RESULTS
    user_query = ' '.join(context.args)
    sql_condition = translate_query_to_sql(user_query)
    
    df = get_latest_posts(sql_condition, 25, 1)

    if df.shape[0] != 0:
        cast_as_message, reply_markup = render_message(df, page)
        await update.message.reply_text(cast_as_message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        result = f"⚠️ No results found. \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df
    page = FIRST_PAGE

    bot_message = f"Fetching trending posts... \n\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

    # GET TRENDING POSTS
    item_ids_list = get_trending_posts(model_id = "farcaster-v2-trending-now-items-1day", 
                                        filter_values = {},
                                        items_per_page = 25
                                    )

    if len(item_ids_list) != 0:
        df = get_posts_from_item_ids(item_ids_list)
        df.sort_values(by="hash", key=lambda column: column.map(lambda e: item_ids_list.index(e)), inplace=True)
        
        cast_as_message, reply_markup = render_message(df, page)
        await update.message.reply_text(cast_as_message, parse_mode='HTML', reply_markup=reply_markup)

    else:
        result = f"⚠️ No results found. \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def forme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df
    page = FIRST_PAGE

    handle = context.args[0]
    id = get_user_id_from_handle(handle)

    if id:
        bot_message = f"Fetching personalized posts for {handle} (fid: {id}) ... \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

        # GET USER'S CASTS
        item_ids_list = get_for_you_posts(user_id = id, 
                                            model_id = "farcaster-v2-user-perosnalization-3exp-30days", 
                                            filter_values = {},
                                            items_per_page = 25)

        if len(item_ids_list) != 0:
            df = get_posts_from_item_ids(item_ids_list)

            result = f"{df.shape[0]} personalized casts for {handle}. \n\n"
            cast_as_message, reply_markup = render_message(df, page)
            await update.message.reply_text(cast_as_message, parse_mode='HTML', reply_markup=reply_markup)

        else:
            bot_message = f"⚠️ No results found. \n\n"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)
    else:
        bot_message = f"⚠️ Handle not found. \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

async def similar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df
    page = FIRST_PAGE

    post_link = context.args[0]
    # post_link = "https://warpcast.com/dwr.eth/0x7735946a4"

    # GET Similar castsS
    post_id = post_link.split("/")[-1]
    if len(post_id) == 11:
        item_df = get_item_id_from_post_id(post_id)  

        if item_df.shape[0] != 0:
            bot_message = f"Fetching simialr posts to {item_df['handle'].iat[0]}'s cast... \n\n"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

            item_ids_list = get_similar_posts(item_id=item_df['hash'].iat[0], model_id="farcaster-v2-similar-items", filter_values={}, items_per_page=25)

            if len(item_ids_list) != 0:
                df = get_posts_from_item_ids(item_ids_list)

                result = f"{df.shape[0]} Similar castss to {item_df['handle'].iat[0]}'s cast. \n\n"
                cast_as_message, reply_markup = render_message(df, page)
                await update.message.reply_text(cast_as_message, parse_mode='HTML', reply_markup=reply_markup)

            else:
                bot_message = f"⚠️ No results found. \n\n"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

        else:
            bot_message = f"Fetching personalized posts for {handle} (fid: {id}) ... \n\n"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

async def popular(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df
    page = FIRST_PAGE

    bot_message = f"Fetching popular posts... \n\n"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

    # GET POPULAR POSTS
    item_ids_list = get_popular_posts(model_id = "farcaster-v2-popular-items", 
                                        filter_values = {},
                                        # filter_values = {
                                        #     "item_type": ["post"],
                                        #     "start_date": "1598919338",
                                        #     "end_date": "1699524138"
                                        # }, 
                                        items_per_page = 25
                                    )

    if len(item_ids_list) != 0:
        df = get_posts_from_item_ids(item_ids_list)
        df.sort_values(by="hash", key=lambda column: column.map(lambda e: item_ids_list.index(e)), inplace=True)
        
        result = f"Latest {df.shape[0]} popular casts. \n\n"
        cast_as_message, reply_markup = render_message(df, page)
        await update.message.reply_text(cast_as_message, parse_mode='HTML', reply_markup=reply_markup)
        
    else:
        result = f"⚠️ No results found. \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    global df
    
    query = update.callback_query
    
    # await query.answer(text=f'{query.data}', show_alert=False)
    await query.answer()
    print(query.data)
    if query.data.split('_')[0] == 'page':
        page = int(query.data.split('_')[1])
    
        cast_as_message, reply_markup = render_message(df, page)
        await query.edit_message_text(text=cast_as_message, parse_mode='HTML', reply_markup=reply_markup)
    
    if query.data.split('_')[0] == 'summarize':
        hash = query.data.split('_')[1]
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Summarizing the top 50 replies...")
        summary = summarize_conversation(hash) #to be implemented....
        await context.bot.send_message(chat_id=update.effective_chat.id, parse_mode='HTML', text=summary)

    if query.data.split('_')[0] == 'read':
        page = int(query.data.split('_')[1])

        for i, row in df.iloc[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE].iterrows():
            cast_as_message = render_cast(page+1, row, show_text=True)
            unread = [
                InlineKeyboardButton("See engagement", callback_data=f"unread_{page}"),
                InlineKeyboardButton("Similar casts", callback_data=f"similar_{row['hash']}")
                ]
            if row['replies'] > 0:
                summarize = [InlineKeyboardButton("Summarize replies", callback_data=f"summarize_{row['hash']}")]
                reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), unread, summarize])
            else:
                reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), unread])
            await query.edit_message_text(text=cast_as_message, parse_mode='HTML', reply_markup=reply_markup)
    
    if query.data.split('_')[0] == 'unread':
        page = int(query.data.split('_')[1])

        for i, row in df.iloc[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE].iterrows():
            cast_as_message = render_cast(page+1, row)
            read = [
                InlineKeyboardButton("Read cast", callback_data=f"read_{page}"),
                InlineKeyboardButton("Similar casts", callback_data=f"similar_{row['hash']}")
            ]
            if row['replies'] > 0:
                summarize = [InlineKeyboardButton("Summarize replies", callback_data=f"summarize_{row['hash']}")]
                reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), read, summarize])
            else:
                reply_markup = InlineKeyboardMarkup([get_pagination_keyboard(page), read])
            await query.edit_message_text(text=cast_as_message, parse_mode='HTML', reply_markup=reply_markup)
        
    if query.data.split('_')[0] == 'similar':
        bot_message = f"/similar {query.data.split('_')[1]}"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

        page = FIRST_PAGE

        bot_message = f"Fetching simialr casts... \n\n"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)
        item_ids_list = get_similar_posts(item_id=query.data.split('_')[1], model_id="farcaster-v2-similar-items", filter_values={}, items_per_page=25)

        if len(item_ids_list) != 0:
            df = get_posts_from_item_ids(item_ids_list)

            cast_as_message, reply_markup = render_message(df, page)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=cast_as_message, parse_mode='HTML', reply_markup=reply_markup)

        else:
            bot_message = f"⚠️ No results found. \n\n"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_message)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

if __name__ == '__main__':
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    forme_handler = CommandHandler('forme', forme)
    application.add_handler(forme_handler)

    search_handler = CommandHandler('search', search)
    application.add_handler(search_handler)

    trending_handler = CommandHandler('trending', trending)
    application.add_handler(trending_handler)
    application.add_handler(CallbackQueryHandler(button))

    similar_handler = CommandHandler('similar', similar)
    application.add_handler(similar_handler)

    popular_handler = CommandHandler('popular', popular)
    application.add_handler(popular_handler)

    # Other handlers
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)
    
    application.run_polling()