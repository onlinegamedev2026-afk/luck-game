const SUIT = { H: "♥", D: "♦", C: "♣", S: "♠" };
const RED = new Set(["H", "D"]);
const gameKey = document.querySelector(".game-shell").dataset.gameKey;
let cardsA = [];
let cardsB = [];

function el(id) { return document.getElementById(id); }
function setStatus(text) { el("conn-status").textContent = text; }

function makeCard(card, isWinning = false) {
  const rank = card.rank || card[0];
  const suit = card.suit || card[1];
  const node = document.createElement("div");
  node.className = `card ${RED.has(suit) ? "red" : "black"}${isWinning ? " winning-card" : ""}`;
  node.textContent = `${rank === "T" ? "10" : rank}${SUIT[suit]}`;
  return node;
}

function renderJoker(card) {
  const box = el("joker-card");
  box.innerHTML = "";
  box.appendChild(card ? makeCard(card) : Object.assign(document.createElement("div"), { className: "slot" }));
}

function renderRow(id, cards, winningCard = null) {
  const row = el(id);
  row.innerHTML = "";
  if (!cards.length) {
    row.appendChild(Object.assign(document.createElement("div"), { className: "slot" }));
    return;
  }
  for (const card of cards) {
    const isWin = winningCard && card.rank === winningCard.rank && card.suit === winningCard.suit;
    row.appendChild(makeCard(card, isWin));
  }
}

function renderCounts() {
  el("count-a").textContent = `${cardsA.length} cards`;
  el("count-b").textContent = `${cardsB.length} cards`;
}

function renderHistory(last10) {
  const track = el("history-track");
  track.innerHTML = "";
  for (let i = 0; i < 10; i += 1) {
    const badge = document.createElement("div");
    badge.className = "h-badge";
    badge.textContent = last10[i] || "-";
    track.appendChild(badge);
  }
}

function clearBoard() {
  cardsA = [];
  cardsB = [];
  el("panel-a").className = "group-panel";
  el("panel-b").className = "group-panel";
  el("result").textContent = "";
  renderJoker(null);
  renderRow("cards-a", []);
  renderRow("cards-b", []);
  renderCounts();
}

function replay(cards, joker, winningCard) {
  clearBoard();
  renderJoker(joker);
  for (const item of cards || []) {
    if (item.group === "A") cardsA.push(item);
    else cardsB.push(item);
  }
  renderRow("cards-a", cardsA, winningCard);
  renderRow("cards-b", cardsB, winningCard);
  renderCounts();
}

function handle(event, data) {
  if (data && data.game_key && data.game_key !== gameKey) return;
  if (event === "server_state") {
    replay(data.cards_dealt || [], data.joker || null, data.winning_card || null);
    renderHistory(data.last_10_winners || []);
    el("banner").textContent = data.in_progress ? "Round in progress" : "Open betting, place bets, then start the round";
  }
  if (event === "betting_opened") {
    clearBoard();
    el("banner").textContent = `Betting open for ${data.seconds} seconds`;
  }
  if (event === "game_started") {
    clearBoard();
    el("banner").textContent = "Round started. Opening joker.";
  }
  if (event === "joker_opened") {
    renderJoker(data.joker);
    el("banner").textContent = "Joker opened. Cards are being dealt.";
  }
  if (event === "card_dealt") {
    if (data.group === "A") cardsA.push(data);
    else cardsB.push(data);
    renderRow("cards-a", cardsA);
    renderRow("cards-b", cardsB);
    renderCounts();
    el("banner").textContent = `Draw ${data.draw_num} of ${data.total_draws}: ${data.group === "A" ? "Andar" : "Bahar"}`;
  }
  if (event === "game_result") {
    renderHistory(data.last_10_winners || []);
    renderRow("cards-a", cardsA, data.winning_card);
    renderRow("cards-b", cardsB, data.winning_card);
    const name = data.winner === "A" ? "A / Andar" : "B / Bahar";
    el("result").textContent = `${name} wins at ${data.time}`;
    el(`panel-${data.winner.toLowerCase()}`).classList.add("winner");
    el(`panel-${data.winner === "A" ? "b" : "a"}`).classList.add("loser");
    el("banner").textContent = "Round complete.";
    refreshPlayerAmount();
  }
  if (event === "game_error") {
    el("banner").textContent = `Game error: ${data.message || "unknown error"}`;
  }
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/games/${gameKey}`);
  socket.onopen = () => setStatus("Live");
  socket.onclose = () => {
    setStatus("Offline");
    setTimeout(connect, 1200);
  };
  socket.onmessage = (message) => {
    const payload = JSON.parse(message.data);
    handle(payload.event, payload.data);
  };
}

clearBoard();
renderHistory([]);
connect();
