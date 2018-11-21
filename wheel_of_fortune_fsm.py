

class State:
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name


SEARCH_GAME = State('Search a game')
CREATE_GAME = State('Create a game')
MAKE_TURN = State('Make a turn')
WAIT_TURN = State('Wait a turn')
CHOOSE_LETTER = State('Choose a letter')
CHOOSE_WORD = State('Choose a word')
SET_WINNER = State('Set a winner')
CHANGE_TURN = State('Change a turn')
CANCEL_GAME = State('Cancel a game')

FSM_MAP = (
    {
        'source': SEARCH_GAME,
        'next': CREATE_GAME,
        'chat_id': ,
        'condition': ,
        'transition': ,
    }
)


class StateMachine:
    def __init__(self, initial_state, transition_table):
        self.state = initial_state
        self.transition_table = transition_table

    # Conditions

    # Transitions
    def transition_create_game(self, state)
        self.state = state

    def run(self):
        for transition in self.transition_table:
            if not self.next_state(transition):

    def next_state(self, state):
        for map_item in FSM_MAP:
            if map_item['source'] == state:
                pass




