const SUIT = { H: "♥", D: "♦", C: "♣", S: "♠" };
const RED = new Set(["H", "D"]);
const gameKey = document.querySelector(".game-shell").dataset.gameKey;
let cardsA = [];
let cardsB = [];
let countdownTimer = null;
let bettingOpen = false;

function el(id) { return document.getElementById(id); }
function setStatus(text) { el("conn-status").textContent = text; }

function setBettingOpen(open, message) {
  bettingOpen = open;
  const form = el("bet-form");
  if (!form) return;
  const controls = form.querySelectorAll("select, input, button");
  controls.forEach((control) => {
    control.disabled = !open;
  });
  const status = el("bet-status");
  if (status) {
    status.textContent = message || (open ? "Betting open" : "Betting closed");
    status.classList.toggle("ok", open);
    status.classList.toggle("error", false);
  }
}

function setBetStatus(message, ok = false) {
  const status = el("bet-status");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("ok", ok);
  status.classList.toggle("error", !ok);
}

function startCountdown(prefix, data, maxSeconds) {
  if (countdownTimer) clearInterval(countdownTimer);
  const initial = Math.min(
    maxSeconds,
    Math.max(0, Math.ceil(Number(data.remaining_seconds ?? data.seconds ?? maxSeconds)))
  );
  const startedAt = performance.now();
  const render = () => {
    const elapsed = Math.floor((performance.now() - startedAt) / 1000);
    const remaining = Math.max(0, initial - elapsed);
    const separator = prefix.includes("pending") ? ": " : " ";
    el("banner").textContent = `${prefix}${separator}${remaining} seconds`;
    if (remaining <= 0 && countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  };
  render();
  countdownTimer = setInterval(render, 250);
}

function stopCountdown() {
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = null;
}

function updateTotals(data) {
  const totalBox = el("betting-totals");
  const totalA = el("total-a");
  const totalB = el("total-b");
  if (!totalA || !totalB) return;
  totalA.textContent = data.group_a_total || "0.000";
  totalB.textContent = data.group_b_total || "0.000";
  if (totalBox) totalBox.hidden = data.hide || !("group_a_total" in data && "group_b_total" in data);
}

function renderMyBets(bets) {
  const list = el("my-bets-list");
  if (!list) return;
  list.innerHTML = "";
  if (!bets || !bets.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No bets placed in this cycle.";
    list.appendChild(empty);
    return;
  }
  bets.forEach((bet) => {
    const row = document.createElement("div");
    row.className = "my-bet-row";
    const side = document.createElement("strong");
    side.textContent = bet.side === "A" ? "A / Andar" : "B / Bahar";
    const amount = document.createElement("span");
    amount.textContent = `${bet.amount} units`;
    const status = document.createElement("span");
    status.textContent = bet.status;
    row.append(side, amount, status);
    list.appendChild(row);
  });
}

async function loadMyBets() {
  const list = el("my-bets-list");
  if (!list) return;
  const response = await fetch(`/api/games/${gameKey}/my-bets`, { headers: { Accept: "application/json" } });
  if (!response.ok) return;
  const data = await response.json();
  renderMyBets(data.bets || []);
}

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
  el("result").className = "result";
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
    updateTotals(data);
    if (data.phase === "BETTING" && data.phase_ends_at) {
      setBettingOpen(true, "Betting open");
      loadMyBets();
      startCountdown("Betting will be over within", data, 40);
    } else if (data.phase === "INITIATING" && data.phase_ends_at) {
      setBettingOpen(false, "Betting closed");
      loadMyBets();
      startCountdown("Game will be initiated within", data, 20);
    } else if (data.phase === "SETTLING" && data.phase_ends_at) {
      setBettingOpen(false, "Betting closed");
      loadMyBets();
      startCountdown("Betting for next game will start within", data, 20);
    } else {
      setBettingOpen(false, "Waiting for betting time");
      el("banner").textContent = data.in_progress ? "Round in progress" : "Waiting for the next betting window";
    }
  }
  if (event === "betting_opened") {
    clearBoard();
    const totalBox = el("betting-totals");
    if (totalBox) {
      totalBox.hidden = true;
      updateTotals({ group_a_total: "0.000", group_b_total: "0.000", hide: true });
    }
    setBettingOpen(true, "Betting open");
    renderMyBets([]);
    startCountdown("Betting will be over within", data, 40);
  }
  if (event === "game_initiating") {
    setBettingOpen(false, "Betting closed");
    loadMyBets();
    startCountdown("Game will be initiated within", data, 20);
  }
  if (event === "betting_totals") {
    updateTotals(data);
  }
  if (event === "game_started") {
    setBettingOpen(false, "Betting closed");
    stopCountdown();
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
    el("result").className = "result winner-result";
    el("result").textContent = `${name} wins at ${data.time}`;
    el(`panel-${data.winner.toLowerCase()}`).classList.add("winner");
    el(`panel-${data.winner === "A" ? "b" : "a"}`).classList.add("loser");
    el("banner").textContent = "Round complete.";
    refreshPlayerAmount();
  }
  if (event === "settlement_cooldown") {
    setBettingOpen(false, "Betting closed");
    loadMyBets();
    startCountdown("Betting for next game will start within", data, 20);
    refreshPlayerAmount();
  }
  if (event === "cycle_complete") {
    const totalBox = el("betting-totals");
    if (totalBox) totalBox.hidden = true;
    setBettingOpen(false, "Waiting for betting time");
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
setBettingOpen(false, "Waiting for betting time");
const betForm = el("bet-form");
if (betForm) {
  betForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!bettingOpen) {
      setBetStatus("Betting is not open right now.");
      return;
    }
    const amount = el("bet-amount").value.trim();
    if (Number(amount) < 10) {
      setBetStatus("Minimum bet is 10.000.");
      return;
    }
    setBetStatus("Placing bet...", true);
    const body = new URLSearchParams(new FormData(betForm));
    const response = await fetch(betForm.action, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      setBetStatus(data.error || "Bet could not be placed.");
      return;
    }
    setBetStatus(data.message || "Bet placed successfully.", true);
    renderMyBets(data.bets || []);
    refreshPlayerAmount();
  });
}
loadMyBets();
connect();
