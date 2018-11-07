import datetime

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import select, func

_engine = create_engine("postgresql+psycopg2://root:root@localhost:5432/sqlalchemy")

Session = scoped_session(sessionmaker(bind=_engine))

_Base = declarative_base()

# def get_stars(context):
#     question_id = context.get_current_parameters()['question_id']
#     query = select([func.length(Question.answer)]).where(Question.question_id == question_id)
#     result = session.execute(query)
#     row = result.fetchone()
#     return '*' * row[0]

class Player(_Base):
    __tablename__ = 'player'

    chat_id = Column(Integer, primary_key=True)
    player_search = Column(Boolean, default=False)

class Question(_Base):
    __tablename__ = 'question'

    question_id = Column(Integer, primary_key=True)
    question = Column(String)
    answer = Column(String)

    games = relationship('Game', back_populates='questions')

class Game(_Base):
    __tablename__ = 'game'

    game_id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey(Question.question_id))
    game_word = Column(String)
    game_turn_prev = Column(Integer, ForeignKey(Player.chat_id))
    game_turn = Column(Integer, ForeignKey(Player.chat_id))
    winner_id = Column(Integer, ForeignKey(Player.chat_id), nullable=True)
    game_start = Column(DateTime, default=datetime.datetime.now)
    game_end = Column(DateTime, nullable=True)

    questions = relationship('Question', back_populates='games')
    winner = relationship('Player', foreign_keys=[winner_id])
    player_turn_prev = relationship('Player', foreign_keys=[game_turn_prev])
    player_turn = relationship('Player', foreign_keys=[game_turn])
    player_game = relationship('PlayerGameLink', back_populates='game')

class PlayerGameLink(_Base):
    __tablename__ = 'player_game'

    player_id = Column(Integer, ForeignKey('player.chat_id'), primary_key=True)
    game_id = Column(Integer, ForeignKey('game.game_id'), primary_key=True)
    player_score = Column(Integer, default=0)

    player = relationship('Player')
    game = relationship('Game', back_populates='player_game')

if __name__ == '__main__':
    _Base.metadata.create_all(bind=_engine)