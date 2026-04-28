from gevent import monkey
monkey.patch_all()

from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO, emit
from andar_bahar_modified import initiate_game
import random
import gevent

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-this-secret-key-for-production'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='gevent')

UNIVERSAL_CARD_DRAWING_DELAY = 5
LAST_10_WINNERS = []
game_in_progress = False

game_state = {
    'in_progress': False,
    'joker': None,
    'cards_dealt': [],
    'winner': None,
    'winning_card': None,
    'time': None,
    'delay': 3,
    'total_draws': 0,
    'last_10_winners': [],
}


def add_winner(winner):
    LAST_10_WINNERS.append(winner)
    if len(LAST_10_WINNERS) > 10:
        LAST_10_WINNERS.pop(0)


def reset_game_state():
    game_state.update({
        'in_progress': False,
        'joker': None,
        'cards_dealt': [],
        'winner': None,
        'winning_card': None,
        'time': None,
        'total_draws': 0,
    })


def card_dict(card_tuple):
    return {'rank': card_tuple[0], 'suit': card_tuple[1]}


@app.route('/andarbahar/last/ten/winners')
def get_last_ten_winners():
    return jsonify({'last_10_winners': LAST_10_WINNERS})


@socketio.on('connect')
def on_connect():
    emit('server_state', {
        'in_progress': game_state['in_progress'],
        'joker': game_state['joker'],
        'cards_dealt': game_state['cards_dealt'],
        'winner': game_state['winner'],
        'winning_card': game_state['winning_card'],
        'time': game_state['time'],
        'delay': game_state['delay'],
        'total_draws': game_state['total_draws'],
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

    # TODO: Replace random bids with real server-side bidding data.
    a_bid = random.randint(10, 290)
    b_bid = random.randint(10, 290)
    delay = UNIVERSAL_CARD_DRAWING_DELAY

    try:
        record = initiate_game(a_bid, b_bid, delay)
    except Exception as e:
        print('ERROR:', e)
        socketio.emit('game_error', {'message': str(e)})
        game_in_progress = False
        reset_game_state()
        return

    joker = record['JOKER']
    hand_a = record['A'] or []
    hand_b = record['B'] or []
    winner = record['WINNER']
    winning_card = record['WINNING_CARD']
    time = record['TIME']
    total_draws = int(record['TOTAL_DRAWS'] or 0)
    deal_order = list(record.get('DEAL_ORDER') or [])

    game_state['delay'] = delay
    game_state['total_draws'] = total_draws
    game_state['winner'] = winner
    game_state['winning_card'] = card_dict(winning_card) if winning_card else None
    game_state['time'] = time
    game_state['joker'] = card_dict(joker)

    socketio.emit('game_started', {'delay': delay})

    gevent.sleep(delay)
    socketio.emit('joker_opened', game_state['joker'])

    a_index = 0
    b_index = 0
    for draw_num in range(1, total_draws + 1):
        gevent.sleep(delay)
        group = deal_order[draw_num - 1] if draw_num - 1 < len(deal_order) else ('A' if draw_num % 2 == 1 else 'B')
        if group == 'A':
            card = hand_a[a_index]
            a_index += 1
        else:
            card = hand_b[b_index]
            b_index += 1

        card_event = {
            'group': group,
            'rank': card[0],
            'suit': card[1],
            'draw_num': draw_num,
            'total_draws': total_draws,
        }
        game_state['cards_dealt'].append(card_event)
        socketio.emit('card_dealt', card_event)

    gevent.sleep(delay)
    add_winner(winner)
    game_state['last_10_winners'] = LAST_10_WINNERS

    socketio.emit('game_result', {
        'winner': winner,
        'winning_card': game_state['winning_card'],
        'time': time,
        'last_10_winners': LAST_10_WINNERS,
    })

    game_in_progress = False
    game_state['in_progress'] = False


@socketio.on('disconnect')
def on_disconnect():
    pass


@app.route('/andarbahar')
def home():
    server_url = request.host_url.rstrip('/')
    return render_template_string(
        open('templates/andar_bahar_synced.html', encoding='utf-8').read(),
        server_url=server_url,
    )


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
