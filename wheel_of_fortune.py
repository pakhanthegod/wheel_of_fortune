import json
import logging
import time
import datetime

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
REQUEST_KWARGS = config['REQUEST_KWARGS_NONFREE']

updater = Updater(token=TOKEN, request_kwargs=REQUEST_KWARGS)


def check_game_status(bot, chat_id, game_data, question_data, session, keyboard_markup):
    """
        Checks the game status by update 'database.Game' object:
        1. If other player doesn't do anything for 900 secs the game will over.
        2. If 'database.Game.game_turn' equal to user's chat_id it will be user's turn.
        3. If 'database.Game.winner_id' is Null the game will continue
    """
    import database as db
    time_to_wait_answer = time.time()
    elapsed_to_wait_answer = 0
    while True:
        if elapsed_to_wait_answer > 900:
            msg = "Other player doesn't answer to the bot for a long time. Game is over."
            db.Session.remove()
            return -1
        if game_data.game_turn == chat_id:
            current_game_word = game_data.game_word
            msg = f"Current game word: {current_game_word}\nWhat would you like to say?"
            try:
                bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard_markup)
            except telegram.error.Unauthorized:
                logging.info('Get telegram.error.Unathorized')
                game_data.game_cancelled = True
                session.commit()
                db.Session.remove()
                return -1
            db.Session.remove()
            return 'SECOND'
        if game_data.winner_id is not None:
            msg = f"The game is over! Other player has won! Answer was \"{question_data.answer}\""
            try:
                bot.send_message(chat_id=chat_id, text=msg)
            except telegram.error.Unauthorized:
                logging.info('Get telegram.error.Unathorized')
                game_data.game_cancelled = True
                session.commit()
            db.Session.remove()
            return -1
        if game_data.game_cancelled == True:
            msg = f"The game has been canceled by other player."
            try:
                bot.send_message(chat_id=chat_id, text=msg)
            except telegram.error.Unauthorized:
                logging.info('Get telegram.error.Unathorized')
                game_data.game_cancelled = True
                session.commit()
            db.Session.remove()
            return -1
        else:
            session.refresh(game_data)
            time.sleep(4)
        elapsed_to_wait_answer = time.time() - time_to_wait_answer


def change_player_turn(chat_id, game_data, session):
    # TODO: realize the function for 3 players, it's for 2 players right now
    next_player = game_data.game_turn_prev
    game_data.game_turn_prev = chat_id
    game_data.game_turn = next_player
    session.commit()


def set_winner(chat_id, game_data, session):
    game_data.winner_id = chat_id
    game_data.game_end = datetime.datetime.now()
    session.commit()


@run_async
def start(bot: telegram.Bot, update: telegram.Update, user_data):
    logging.info('Get the /start command')

    chat_id = update.message.chat_id

    session = db.Session()
    player = (
        session.query(db.Player)
        .filter(db.Player.chat_id == chat_id)
        .one_or_none()
    )

    msg = 'You are in the queue. Searching are working for 60 sec.'
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')
        return -1

    if player:
        player.player_search = True
        session.commit()
    else:
        player = db.Player(chat_id=chat_id, player_search=True)
        session.add(player)
        session.commit()

    start = time.time()
    elapsed = 0
    while elapsed < 60:
        result = (
            session.query(db.PlayerGameLink, db.Game, db.Question)
            .join(db.Game)
            .join(db.Question)
            .filter(db.PlayerGameLink.player_id == chat_id)
            .filter(db.Game.game_end == None).one_or_none()
        )
        if result:
            player.player_search = False
            session.commit()

            _, game_data, question_data = result

            msg = 'Question: ' + question_data.question + '\nWord: ' + '*' * len(question_data.answer)
            try:
                bot.send_message(chat_id=chat_id, text=msg)
            except telegram.error.Unauthorized:
                logging.info('Get telegram.error.Unathorized')
                game_data.game_cancelled = True
                session.commit()
                db.Session.remove()
                return -1

            keyboard = [
                [InlineKeyboardButton(text='Word', callback_data='word')],
                [InlineKeyboardButton(text='Letter', callback_data='letter')]
            ]
            keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

            players = [player.player_id for player in session.query(db.PlayerGameLink).join(db.Game).filter(db.Game.game_id == game_data.game_id)]
            user_data['players'] = players

            if game_data.game_turn == chat_id:
                msg = "What would you like to say?"
                try:
                    bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard_markup)
                except telegram.error.Unauthorized:
                    logging.info('Get telegram.error.Unathorized')
                    game_data.game_cancelled = True
                    session.commit()
                    db.Session.remove()
                    return -1
                db.Session.remove()
                return 'SECOND'

            return check_game_status(bot, chat_id, game_data, question_data, session, keyboard_markup)
        elapsed = time.time() - start
    else:
        msg = 'No one is searching a game at the moment. Try it later.'
        player.player_search = False
        session.commit()

    db.Session.remove()
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')
        game_data.game_cancelled = True
        session.commit()
        db.Session.remove()
        return -1


@run_async
def retrieve_answer(bot: telegram.Bot, update: telegram.Update, user_data):
    logging.info('Retrieve the answer.')

    chat_id = update.message.chat_id
    player_answer = update.message.text.lower()

    session = db.Session()

    # players = user_data['players']

    _, game_data, question_data = (
        session.query(db.PlayerGameLink, db.Game, db.Question)
        .join(db.Game)
        .join(db.Question)
        .filter(db.PlayerGameLink.player_id == chat_id)
        .filter(db.Game.game_end == None)
        .one_or_none()
    )

    answer = question_data.answer.lower()

    waiting = user_data['waiting']

    keyboard = [
        [InlineKeyboardButton(text='Word', callback_data='word')],
        [InlineKeyboardButton(text='Letter', callback_data='letter')]
    ]
    keyboard_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if waiting == 'letter':
        if len(player_answer) != 1:
            msg = 'Please send a one letter.'
        else:
            game_word = game_data.game_word
            if player_answer in answer and player_answer not in game_word:
                indexes = [index for index, letter in enumerate(answer) if player_answer == letter]
                game_word_list = list(game_word)
                for index in indexes:
                    game_word_list[index] = player_answer
                game_word = "".join(game_word_list)
                game_data.game_word = game_word
                session.commit()

                if '*' not in game_word:
                    msg = "You're the winner! Congratulation!"
                    try:
                        bot.send_message(chat_id=chat_id, text=msg)
                    except telegram.error.Unauthorized:
                        logging.info('Get telegram.error.Unathorized')
                        game_data.game_cancelled = True
                        session.commit()
                        db.Session.remove()
                        return -1
                    set_winner(chat_id, game_data, session)
                    return -1
                
                msg = f"You're right! This letter in the answer!\nCurrent game word: {game_word}"
                try:
                    bot.send_message(chat_id=chat_id, text=msg)
                    bot.send_message(chat_id=chat_id, text='What would you like to say?', reply_markup=keyboard_markup)
                except telegram.error.Unauthorized:
                    logging.info('Get telegram.error.Unathorized')
                    game_data.game_cancelled = True
                    session.commit()
                    db.Session.remove()
                    return -1

                db.Session.remove()

                return 'SECOND'
            else:
                msg = "You're wrong! There is not this letter in the answer"
                change_player_turn(chat_id, game_data, session)
    else:
        if player_answer != answer:
            msg = "You're wrong! This isn't answer!"
            change_player_turn(chat_id, game_data, session)
        else:
            msg = "You're the winner! Congratulation!"
            try:
                bot.send_message(chat_id=chat_id, text=msg)
            except telegram.error.Unauthorized:
                logging.info('Get telegram.error.Unathorized')
                game_data.game_cancelled = True
                session.commit()
                db.Session.remove()
                return -1
            set_winner(chat_id, game_data, session)
            return -1

    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')
        game_data.game_cancelled = True
        session.commit()
        db.Session.remove()
        return -1

    return check_game_status(bot, chat_id, game_data, question_data, session, keyboard_markup)


@run_async
def game(bot: telegram.Bot, update: telegram.Update, user_data):
    logging.info('Get the callback from the keyboard.')

    query = update.callback_query
    chat_id = query.message.chat_id

    user_data['waiting'] = query.data

    msg = f'Send a {query.data.lower()}.'
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')

        session = db.Session()

        _, game_data = (
            session.query(db.PlayerGameLink, db.Game)
            .join(db.Game)
            .filter(db.PlayerGameLink.player_id == chat_id)
            .filter(db.Game.game_end == None)
            .one_or_none()
        )

        game_data.game_cancelled = True

        session.commit()
        db.Session.remove()

        return -1

    return 'FIRST'


@run_async
def stop(bot: telegram.Bot, update: telegram.Update):
    logging.info('Get stop command.')

    chat_id = update.message.chat_id

    session = db.Session()
    _, game_data = (
        session.query(db.PlayerGameLink, db.Game)
        .join(db.Game)
        .filter(db.PlayerGameLink.player_id == chat_id)
        .filter(db.Game.game_end == None)
        .one_or_none()
    )
    game_data.game_end = datetime.datetime.now()
    game_data.game_canceled = True

    msg = 'You have stopped the game.'
    try:
        bot.send_message(chat_id=chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')

    session.commit()
    db.Session.remove()

    return -1


@run_async
def status(bot: telegram.Bot, update: telegram.Update):
    logging.info('Print the count of active games')

    session = db.Session()
    count = session.query(db.Game).filter(db.Game.game_end == None).count()

    msg = f'{count} games are active at the moment.'
    try:
        bot.send_message(chat_id=update.message.chat_id, text=msg)
    except telegram.error.Unauthorized:
        logging.info('Get telegram.error.Unathorized')
        return


dispatcher = updater.dispatcher

conversation = ConversationHandler(
    entry_points=[CommandHandler('start', start, pass_user_data=True)],
    states={
        'FIRST': [MessageHandler(Filters.text, retrieve_answer, pass_user_data=True)],
        'SECOND': [CallbackQueryHandler(game, pass_user_data=True)]
    },
    fallbacks=[CommandHandler('stop', stop)]
)

dispatcher.add_handler(conversation)
dispatcher.add_handler(CommandHandler('status', status))

updater.start_polling()
logging.info('Bot is started!')
updater.idle()
