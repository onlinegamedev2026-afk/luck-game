from gevent import monkey
monkey.patch_all()

from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO, emit
# from tin_patti import initiate_game
from tin_patti_modified import initiate_game
import random
import gevent

app = Flask(__name__)
app.config['SECRET_KEY'] = 'eae18a0c95f2c96111805ff293b001a62e6e0618a7780f52cab582e2e20210a9'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

UNIVERSAL_CARD_DRAWING_DELAY = 5

LAST_10_WINNERS = []
game_in_progress = False

# Tracks every card already dealt so late joiners can catch up instantly
game_state = {
    'in_progress': False,
    'cards_dealt': [],   # list of { group, rank, suit, draw_num } in order
    'winner': None,
    'time': None,
    'delay': 3,
    'total_draws': 6,
    'last_10_winners': [],
}


def add_winner(winner):
    global LAST_10_WINNERS
    LAST_10_WINNERS.append(winner)
    if len(LAST_10_WINNERS) > 10:
        LAST_10_WINNERS.pop(0)


def reset_game_state():
    game_state['in_progress'] = False
    game_state['cards_dealt'] = []
    game_state['winner'] = None
    game_state['time'] = None


@app.route("/tinpatti/last/ten/winners")
def get_last_ten_winners():
    return jsonify({'last_10_winners': LAST_10_WINNERS})


@socketio.on('connect')
def on_connect():
    """
    New / refreshed device connects.
    Send them everything that has already happened so they catch up instantly.
    """
    emit('server_state', {
        'in_progress':    game_state['in_progress'],
        'cards_dealt':    game_state['cards_dealt'],   # all cards dealt so far
        'winner':         game_state['winner'],        # None if still playing
        'time':           game_state['time'],
        'delay':          game_state['delay'],
        'total_draws':    game_state['total_draws'],
        'last_10_winners': LAST_10_WINNERS,
    })


@socketio.on('request_play')
def on_request_play(data):
    global game_in_progress

    if game_in_progress:
        emit('play_rejected', {'reason': 'A game is already in progress.'})
        return

    game_in_progress = True
    reset_game_state()
    game_state['in_progress'] = True

    # a_bid = int(data.get('group_a_bid', 50))
    # b_bid = int(data.get('group_b_bid', 50))
    ### TODO it must be from server side bidding data not from client side.
    a_bid = random.randint(10, 290)
    b_bid = random.randint(10, 290)
    delay = UNIVERSAL_CARD_DRAWING_DELAY  # seconds between cards

    try:
        record = initiate_game(a_bid, b_bid, delay)
    except Exception as e:
        print("ERROR:", e)
        socketio.emit('game_error', {'message': str(e)})
        game_in_progress = False
        reset_game_state()
        return

    hand_a = record['A']   # list of (rank, suit)
    hand_b = record['B']
    winner = record['WINNER']
    time   = record['TIME']

    game_state['delay']       = delay
    game_state['total_draws'] = 6
    game_state['winner']      = winner   # stored but not sent until reveal
    game_state['time']        = time

    # Tell everyone a game just started
    socketio.emit('game_started', {'delay': delay})

    # Deal cards one at a time with delay, broadcasting each card live
    for i in range(3):
        # Group A card
        gevent.sleep(delay)
        card_event = {
            'group':    'A',
            'rank':     hand_a[i][0],
            'suit':     hand_a[i][1],
            'draw_num': i * 2 + 1,   # 1, 3, 5
        }
        game_state['cards_dealt'].append(card_event)
        socketio.emit('card_dealt', card_event)

        # Group B card
        gevent.sleep(delay)
        card_event = {
            'group':    'B',
            'rank':     hand_b[i][0],
            'suit':     hand_b[i][1],
            'draw_num': i * 2 + 2,   # 2, 4, 6
        }
        game_state['cards_dealt'].append(card_event)
        socketio.emit('card_dealt', card_event)

    # Final reveal
    gevent.sleep(delay)
    add_winner(winner)
    game_state['last_10_winners'] = LAST_10_WINNERS

    socketio.emit('game_result', {
        'winner':          winner,
        'time':            time,
        'last_10_winners': LAST_10_WINNERS,
    })

    game_in_progress = False
    game_state['in_progress'] = False


@socketio.on('disconnect')
def on_disconnect():
    pass


@app.route("/tinpatti")
def home():
    # Build the server URL from the incoming request so any device on the
    # network gets the correct IP automatically — no manual config needed.
    server_url = request.host_url.rstrip('/')
    return render_template_string(
        open("templates/teen_patti_group_battle_synced.html", encoding="utf-8").read(),
        server_url=server_url
    )


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)