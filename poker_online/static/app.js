const $ = (selector) => document.querySelector(selector);

const DEFAULT_ROOM = "POKER";
const playerId = localStorage.pokerPlayerId || (localStorage.pokerPlayerId = crypto.randomUUID());
const fallbackName = `Player ${playerId.slice(-4).toUpperCase()}`;
const suits = { s: "♠", h: "♥", d: "♦", c: "♣" };
const chipColors = [
  ["black", 100],
  ["blue", 25],
  ["red", 10],
  ["gold", 5],
  ["white", 1],
];

let ws;
let state;
let previousState;
let pendingAction = false;
let lastAnimatedHand = 0;
let lastAnimatedBoardCount = 0;
let lastEventKey = "";

function esc(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[char]));
}

function currentName() {
  return ($("#name").value.trim() || localStorage.pokerName || fallbackName).slice(0, 18);
}

function setStatus(message) {
  $("#message").textContent = message;
  $("#turn-note").textContent = message;
}

function cardHtml(code, hidden = false, extraClass = "") {
  if (hidden) {
    return `<div class="playing-card back ${extraClass}">♠</div>`;
  }
  const rank = code[0] === "T" ? "10" : code[0];
  const suit = suits[code[1]] || "";
  const red = "hd".includes(code[1]) ? " red" : "";
  return `<div class="playing-card${red} ${extraClass}"><b>${rank}</b><span>${suit}</span></div>`;
}

function chipStack(amount, label = "") {
  let remaining = Math.max(0, Number(amount) || 0);
  const chips = [];
  for (const [color, value] of chipColors) {
    const count = Math.min(4, Math.floor(remaining / value));
    remaining %= value;
    for (let i = 0; i < count; i += 1) {
      chips.push(`<i class="chip ${color}" style="--i:${chips.length}"></i>`);
    }
  }
  if (!chips.length && amount > 0) {
    chips.push('<i class="chip white" style="--i:0"></i>');
  }
  return `<div class="chip-stack">${chips.join("")}${label ? `<span>${label}</span>` : ""}</div>`;
}

function boardCardHtml(code, index) {
  const isNew = previousState && previousState.hand === state.hand && previousState.board[index] !== code;
  return cardHtml(code, false, isNew ? "board-card landing" : "board-card");
}

function playerCardsHtml(player) {
  if (player.cards.length) {
    return player.cards.map((card, index) => {
      const oldPlayer = previousState?.players?.find((p) => p.seat === player.seat);
      const isReveal = state.finished && oldPlayer && oldPlayer.cards.length === 0;
      return cardHtml(card, false, isReveal ? "flipped" : "");
    }).join("");
  }
  if (!state.started) {
    return "";
  }
  return cardHtml("", true) + cardHtml("", true);
}

function connect() {
  const name = currentName();
  localStorage.pokerName = name;
  $("#name").value = name;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${location.host}/ws/${DEFAULT_ROOM}/${playerId}?name=${encodeURIComponent(name)}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "error") {
      pendingAction = false;
      setActionDisabled(false);
      setStatus(data.message);
      return;
    }
    previousState = state;
    state = data;
    pendingAction = false;
    render();
  };
  ws.onopen = () => setStatus("Đã vào bàn POKER");
  ws.onclose = () => setStatus("Mất kết nối - hãy tải lại trang");
}

function render() {
  if (!state) {
    return;
  }

  $("#room-label").textContent = state.room;
  $("#pot").innerHTML = `POT • ${state.pot}${chipStack(state.pot)}`;
  $("#message").textContent = state.message;
  $("#board").innerHTML = state.board.map((card, index) => boardCardHtml(card, index)).join("");

  $("#seats").innerHTML = state.players.map((player) => {
    const name = esc(player.name);
    const isViewer = player.seat === state.viewerSeat;
    const isTurn = state.actor === player.seat;
    const reveal = state.finished && player.cards.length;
    const cards = playerCardsHtml(player);
    const resultText = state.finished
      ? (player.winner ? `Thắng +${player.payoff}` : (player.folded ? "Fold" : `${player.payoff}`))
      : (player.bet ? `Cược ${player.bet}${chipStack(player.bet)}` : "");
    return `
      <div class="seat seat-${player.seat} ${isTurn ? "turn" : ""} ${player.connected ? "" : "offline"} ${reveal ? "showdown" : ""} ${player.winner ? "winner" : ""} ${player.folded ? "folded" : ""}">
        <div class="avatar">${name[0].toUpperCase()}</div>
        <div class="seat-name">${name}${isViewer ? " (Bạn)" : ""}</div>
        <div class="seat-chips">${chipStack(player.chips, player.chips)}</div>
        <div class="seat-bet">${resultText}</div>
        <div class="cards">${cards}</div>
      </div>`;
  }).join("");

  const start = state.host && (!state.started || state.finished);
  $("#start").classList.toggle("hidden", !start);
  $("#start").textContent = state.finished ? "VÁN MỚI" : "CHIA BÀI";

  const myTurn = state.actor === state.viewerSeat && !pendingAction;
  $("#actions").classList.toggle("hidden", !myTurn);
  $("#turn-note").classList.toggle("hidden", myTurn);
  $("#turn-note").textContent = state.started
    ? (state.finished ? "Chờ chủ bàn chia ván mới..." : "Đang chờ người chơi khác...")
    : "Chờ chủ bàn bắt đầu...";

  if (myTurn) {
    const slider = $("#raise");
    slider.min = state.minRaise;
    slider.max = state.maxRaise;
    slider.value = Math.max(state.minRaise, Math.min(Number(slider.value), state.maxRaise));
    $("#raise-value").textContent = slider.value;
  }

  animateTableEvents();
}

function animateTableEvents() {
  if (!state.started) {
    return;
  }
  if (state.hand !== lastAnimatedHand) {
    lastAnimatedHand = state.hand;
    lastAnimatedBoardCount = 0;
    animateHoleDeal();
  }
  if (state.board.length > lastAnimatedBoardCount) {
    const start = lastAnimatedBoardCount;
    const cards = state.board.slice(start);
    lastAnimatedBoardCount = state.board.length;
    animateBoardDeal(start, cards);
  }
  animateChipEvent();
}

function animateHoleDeal() {
  state.players.forEach((player, seatOrder) => {
    for (let cardIndex = 0; cardIndex < 2; cardIndex += 1) {
      const target = document.querySelector(`.seat-${player.seat} .cards .playing-card:nth-child(${cardIndex + 1})`);
      if (target) {
        flyCardTo(target, cardHtml("", true), seatOrder * 120 + cardIndex * 70);
      }
    }
  });
}

function animateBoardDeal(startIndex, cards) {
  cards.forEach((card, offset) => {
    const target = document.querySelector(`#board .playing-card:nth-child(${startIndex + offset + 1})`);
    if (target) {
      flyCardTo(target, cardHtml(card), offset * 180);
    }
  });
}

function flyCardTo(target, html, delay = 0) {
  const table = $(".table");
  const dealer = $(".dealer-zone");
  if (!table || !dealer || !target) {
    return;
  }

  const tableRect = table.getBoundingClientRect();
  const dealerRect = dealer.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const startX = dealerRect.left + dealerRect.width / 2 - tableRect.left;
  const startY = dealerRect.top + dealerRect.height / 2 - tableRect.top;
  const endX = targetRect.left + targetRect.width / 2 - tableRect.left;
  const endY = targetRect.top + targetRect.height / 2 - tableRect.top;

  const layer = document.createElement("div");
  layer.className = "flying-card";
  layer.innerHTML = html;
  layer.style.left = `${startX}px`;
  layer.style.top = `${startY}px`;
  layer.style.setProperty("--end-left", `${endX}px`);
  layer.style.setProperty("--end-top", `${endY}px`);
  layer.style.animationDelay = `${delay}ms`;
  table.appendChild(layer);
  setTimeout(() => layer.remove(), delay + 900);
}

function animateChipEvent() {
  const event = state.lastEvent || {};
  const key = `${state.hand}:${event.kind}:${event.seat}:${event.amount}:${event.finished ? "done" : ""}`;
  if (!event.kind || key === lastEventKey) {
    return;
  }
  lastEventKey = key;
  if (!event.amount || !["call", "raise"].includes(event.kind)) {
    return;
  }

  const table = $(".table");
  const layer = document.createElement("div");
  layer.className = `chip-flight from-${event.seat}`;
  layer.innerHTML = chipStack(event.amount);
  table.appendChild(layer);
  setTimeout(() => layer.remove(), 900);
}

function setActionDisabled(disabled) {
  document.querySelectorAll("#actions button, #raise").forEach((control) => {
    control.disabled = disabled;
  });
}

function sendAction(action) {
  if (!ws || ws.readyState !== WebSocket.OPEN || pendingAction) {
    return;
  }
  pendingAction = true;
  setActionDisabled(true);
  $("#actions").classList.add("hidden");
  $("#turn-note").classList.remove("hidden");
  $("#turn-note").textContent = "Đã gửi hành động, chờ bàn cập nhật...";
  ws.send(JSON.stringify({
    type: "action",
    action,
    amount: action === "raise" ? Number($("#raise").value) : null,
  }));
}

$("#start").onclick = () => ws?.send(JSON.stringify({ type: "start" }));
$("#copy").onclick = async () => {
  await navigator.clipboard.writeText(location.href);
  $("#copy").textContent = "ĐÃ SAO CHÉP";
  setTimeout(() => {
    $("#copy").textContent = "SAO CHÉP LINK";
  }, 1300);
};
$("#rename").onclick = () => {
  const name = currentName();
  localStorage.pokerName = name;
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "rename", name }));
  }
};
$("#raise").oninput = (event) => {
  $("#raise-value").textContent = event.target.value;
};
document.querySelectorAll("[data-action]").forEach((button) => {
  button.onclick = () => sendAction(button.dataset.action);
});

$("#name").value = localStorage.pokerName || fallbackName;
connect();
