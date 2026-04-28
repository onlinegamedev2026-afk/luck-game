const SUIT = { H: "♥", D: "♦", C: "♣", S: "♠" };
const RED = new Set(["H", "D"]);
const gameKey = document.querySelector(".game-shell").dataset.gameKey;
let cardsA = [];
let cardsB = [];

function el(id) { return document.getElementById(id); }
function setStatus(text) { el("conn-status").textContent = text; }

function makeCard(card) {
  const node = document.createElement("div");
  node.className = `card ${RED.has(card[1]) ? "red" : "black"}`;
  node.textContent = `${card[0] === "T" ? "10" : card[0]}${SUIT[card[1]]}`;
  return node;
}

function renderRow(id, cards) {
  const row = el(id);
  row.innerHTML = "";
  for (let i = 0; i < 3; i += 1) {
    row.appendChild(cards[i] ? makeCard(cards[i]) : Object.assign(document.createElement("div"), { className: "slot" }));
  }
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
  renderRow("cards-a", []);
  renderRow("cards-b", []);
}

function replay(cards) {
  clearBoard();
  for (const item of cards || []) {
    const card = [item.rank, item.suit];
    if (item.group === "A") cardsA.push(card);
    else cardsB.push(card);
  }
  renderRow("cards-a", cardsA);
  renderRow("cards-b", cardsB);
}

function handle(event, data) {
  if (data && data.game_key && data.game_key !== gameKey) return;
  if (event === "server_state") {
    replay(data.cards_dealt || []);
    renderHistory(data.last_10_winners || []);
    el("banner").textContent = data.in_progress ? "Round in progress" : "Open betting, place bets, then start the round";
  }
  if (event === "betting_opened") {
    clearBoard();
    el("banner").textContent = `Betting open for ${data.seconds} seconds`;
  }
  if (event === "game_started") {
    clearBoard();
    el("banner").textContent = "Round started. Cards are being dealt.";
  }
  if (event === "card_dealt") {
    const card = [data.rank, data.suit];
    if (data.group === "A") cardsA.push(card);
    else cardsB.push(card);
    renderRow("cards-a", cardsA);
    renderRow("cards-b", cardsB);
    el("banner").textContent = `Draw ${data.draw_num} of 6: Group ${data.group}`;
  }
  if (event === "game_result") {
    renderHistory(data.last_10_winners || []);
    el("result").textContent = `Group ${data.winner} wins at ${data.time}`;
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

renderRow("cards-a", []);
renderRow("cards-b", []);
renderHistory([]);
connect();
