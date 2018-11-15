import time
import random

import database as db

session = db.Session()

def get_random_question():
    questions = session.query(db.Question).all()
    random_question = random.choice(questions)
    return random_question, '*' * len(random_question.answer)


def create_game():
    while True:
        players_in_search = (
            session.query(db.Player)
            .filter(db.Player.player_search == True)
            .all()
        )
        
        print(players_in_search)

        if len(players_in_search) > 1:
            searched_players = [players_in_search.pop(0) for _ in range(len(players_in_search))]
            question, game_word = get_random_question()

            game = db.Game(question_id=question.question_id, game_turn=searched_players[0].chat_id, game_turn_prev=searched_players[1].chat_id, game_word=game_word)
            session.add(game)
            session.commit()
            session.refresh(game)

            for player in searched_players:
                player_to_game = db.PlayerGameLink(player_id=player.chat_id, game_id=game.game_id)
                session.add(player_to_game)
                player.player_search = False

            session.commit()
        else:
            time.sleep(3)
            
if __name__ == '__main__':
    create_game()