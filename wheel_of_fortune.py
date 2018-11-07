import json
import logging
import time, datetime

import database as db

import telegram
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler
)

from telegram.ext.dispatcher import run_async

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

with open('config.json', encoding='utf-8') as config_file:
    config = json.load(config_file)

TOKEN = config['TOKEN']
REQUEST_KWARGS = config['REQUEST_KWARGS']

updater = Updater(token=TOKEN, request_kwargs=REQUEST_KWARGS)

@run_async
def start(bot:telegram.Bot, update:telegram.Update, user_data):
    logging.info('Get the /start command')

    session = db.Session()

    chat_id = update.message.chat_id

    msg = 'You are in the queue. Searching are working for 60 sec.'
    bot.send_message(chat_id=chat_id, text=msg)

    player_query = session.query(db.Player).filter(db.Player.chat_id == chat_id)
    player = player_query.one_or_none()

    if player:
        player.player_search = True
    else:
        player = db.Player(chat_id=chat_id, player_search=True)
        session.add(player)
    
    session.commit()
    
    start = time.time()
    elapsed = 0
    while elapsed < 60:
        result = session.query(db.PlayerGameLink, db.Game, db.Question) \
                .filter(db.PlayerGameLink.player_id == chat_id) \
                .filter(db.Game.game_end == None).one_or_none()
        if result:
            player.player_search = False
            session.commit()
            game_looking, game, question = result

            user_data['game'] = game
            user_data['question'] = question
            user_data['players'] = [player_in_game.player_id for player_in_game in session.query(db.PlayerGameLink).filter(db.PlayerGameLink.game_id == game.game_id)]

            msg = 'Prepare! The Game is starting now!'
            bot.send_message(chat_id=chat_id, text=msg)
            msg = 'Question: ' + question.question + '\nWord: ' + '*' * len(question.answer)
            bot.send_message(chat_id=chat_id, text=msg)

            keyboard = [
                [InlineKeyboardButton(text='Word', callback_data='word')],
                [InlineKeyboardButton(text='Letter', callback_data='letter')]
            ]
            
            keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

            time_to_wait_answer = time.time()
            elapsed_to_wait_answer = 0
            while True:
                if elapsed_to_wait_answer > 900:
                    msg = "Another player doesn't answer to the bot for a long time. Game is over."
                    return
                if game.game_turn == chat_id:
                    bot.send_message(chat_id=chat_id, text='What would you like to say?', reply_markup=keyboard_markup)
                    return 'SECOND'
                else:
                    session.refresh(game)
                    time.sleep(5)
                elapsed_to_wait_answer = time.time() - time_to_wait_answer
        elapsed = time.time() - start
    else:
        msg = 'No one is searching a game at the moment. Try it later.'
        player.player_search = False
        session.commit()

    bot.send_message(chat_id=chat_id, text=msg)

@run_async
def retrieve_answer(bot:telegram.Bot, update:telegram.Update, user_data):
    logging.info('Retrieving the answer.')

    session = db.Session()

    chat_id = update.message.chat_id

    player_answer = update.message.text

    players = user_data['players']
    question_data = user_data['question']
    game_data = user_data['game']

    question_data, game_data, _ = session.query(db.Question, db.Game, db.PlayerGameLink).filter(db.PlayerGameLink.player_id == chat_id).filter(db.Game.game_end == None).one_or_none()

    session.refresh(question_data)
    session.refresh(game_data)

    answer = question_data.answer
    game_word = game_data.game_word

    bot.send_message(chat_id=chat_id, text=game_word)

    waiting = user_data['waiting']

    if waiting == 'letter':
        if len(player_answer) != 1:
            msg = 'Please send a one letter.'
        else:
            if player_answer in answer:
                msg = "You're right! This letter in the answer!"
                indexes = [index for index, letter in enumerate(answer) if player_answer == letter]
                game_word_list = list(game_word)
                for index in indexes:
                    game_word_list[index] = player_answer
                game_word = "".join(game_word_list)
                game_data.game_word = game_word
                session.commit()
            else:
                msg = "You're wrong! There is not this letter in the answer"
                next_player = game_data.game_turn_prev
                game_data.game_turn_prev = chat_id
                game_data.game_turn = next_player
                session.commit()
    else:
        if player_answer != answer:
            msg = "You're wrong! This isn't answer!"
            # next_player = [player for player in players if player != game_data.game_turn and player != game_data.game_turn_prev][0]
            next_player = game_data.game_turn_prev
            game_data.game_turn_prev = chat_id
            game_data.game_turn = next_player
            session.commit()
        else:
            msg = "You're the winner! Congratulation!"
            bot.send_message(chat_id=chat_id, text=msg)
            game_data.game_end = datetime.datetime.now()
            session.commit()
            return

    bot.send_message(chat_id=chat_id, text=msg)

    keyboard = [
        [InlineKeyboardButton(text='Word', callback_data='word')],
        [InlineKeyboardButton(text='Letter', callback_data='letter')]
    ]
    
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    time_to_wait_answer = time.time()
    elapsed_to_wait_answer = 0
    while True:
        if elapsed_to_wait_answer > 900:
            msg = "Another player doesn't answer to the bot for a long time. Game is over."
            return
        if game_data.game_turn == chat_id:
            bot.send_message(chat_id=chat_id, text='What would you like to say?', reply_markup=keyboard_markup)
            return 'SECOND'
        else:
            session.refresh(game_data)
            time.sleep(5)
        elapsed_to_wait_answer = time.time() - time_to_wait_answer

    bot.send_message(chat_id=chat_id, text='Choose', reply_markup=keyboard_markup)

    return 'SECOND'


def game(bot:telegram.Bot, update:telegram.Update, user_data):
    logging.info('Game.')

    query = update.callback_query
    chat_id = query.message.chat_id

    session = db.Session()

    question_data, game_data, _ = session.query(db.Question, db.Game, db.PlayerGameLink).filter(db.PlayerGameLink.player_id == chat_id).filter(db.Game.game_end == None).one_or_none()

    user_data['waiting'] = query.data

    msg = f'Current word: {game_data.game_word}\nSend a {query.data.lower()}.'

    bot.send_message(chat_id=chat_id, text=msg)

    return 'FIRST'

def status(bot:telegram.Bot, update:telegram.Update):
    logging.info('Print the count of active games')
    count = session.query(db.Game).filter(db.Game.game_end == None).count()
    msg = f'{count} games are active at the moment.'
    bot.send_message(chat_id=update.message.chat_id, text=msg)


dispatcher = updater.dispatcher

conversation = ConversationHandler(
    entry_points=[CommandHandler('start', start, pass_user_data=True)],
    states={
        'FIRST': [MessageHandler(Filters.text, retrieve_answer, pass_user_data=True)],
        'SECOND': [CallbackQueryHandler(game, pass_user_data=True)]
    },
    fallbacks=[CommandHandler('status', status)]
)

dispatcher.add_handler(conversation)
dispatcher.add_handler(CommandHandler('status', status))

updater.start_polling()
logging.info('Bot is started!')
updater.idle()