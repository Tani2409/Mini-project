const $ = (selector) => document.querySelector(selector);

let ws;
let state;
let previousState;
let pendingAction = false;
let lastEventKey = "";

const playerId = localStorage.pokerPlayerId || (localStorage.pokerPlayerId = crypto.randomUUID());
const suits = { s: "♠", h: "♥", d: "♦", c: "♣" };
const chipColors = [
  ["black", 100],
  ["blue", 25],
  ["red", 10],
  ["gold", 5],
  ["white", 1],
];

function esc(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[char]));
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

function newBoardCard(code, index) {
  if (!previousState || previousState.hand !== state.hand) {
    return "dealt";
  }
  return previousState.board[index] !== code ? "dealt" : "";
}

function playerCardsHtml(player) {
  if (player.cards.length) {
    return player.cards.map((card, index) => {
      const oldPlayer = previousState?.players?.find((p) => p.seat === player.seat);
      const isNew = !oldPlayer || oldPlayer.cards[index] !== card || previousState.hand !== state.hand;
      return cardHtml(card, false, isNew ? "dealt" : "");
    }).join("");
  }
  if (!state.started) {
    return "";
  }
  const oldPlayer = previousState?.players?.find((p) => p.seat === player.seat);
  const hiddenIsNew = !oldPlayer || !previousState.started || previousState.hand !== state.hand;
  return cardHtml("", true, hiddenIsNew ? "dealt" : "") + cardHtml("", true, hiddenIsNew ? "dealt delay" : "");
}

async function enter(create) {
  const name = $("#name").value.trim();
  if (!name) {
    return fail("Hãy nhập tên của bạn");
  }

  let code = $("#room-code").value.trim().toUpperCase();
  try {
    if (create) {
      const response = await fetch("/api/rooms", { method: "POST" });
      code = (await response.json()).code;
    }
    if (code.length !== 5) {
      return fail("Mã phòng gồm 5 ký tự");
    }
    localStorage.pokerName = name;
    connect(code, name);
  } catch {
    fail("Không tạo được phòng. Hãy đợi server Render thức dậy rồi thử lại.");
  }
}

function fail(message) {
  $("#lobby-error").textContent = message;
}

function connect(code, name) {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocol}://${location.host}/ws/${code}/${playerId}?name=${encodeURIComponent(name)}`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "error") {
      pendingAction = false;
      setActionDisabled(false);
      return fail(data.message);
    }
    previousState = state;
    state = data;
    pendingAction = false;
    render();
  };
  ws.onopen = () => {
    $("#lobby").classList.add("hidden");
    $("#game").classList.remove("hidden");
  };
  ws.onclose = () => {
    $("#message").textContent = "Mất kết nối - hãy tải lại trang";
  };
}

function render() {
  if (!state) {
    return;
  }

  $("#room-label").textContent = state.room;
  $("#pot").innerHTML = `POT • ${state.pot}${chipStack(state.pot)}`;
  $("#message").textContent = state.message;
  $("#board").innerHTML = state.board.map((card, index) => cardHtml(card, false, newBoardCard(card, index))).join("");

  $("#seats").innerHTML = state.players.map((player) => {
    const name = esc(player.name);
    const isViewer = player.seat === state.viewerSeat;
    const isTurn = state.actor === player.seat;
    const reveal = state.finished && player.cards.length;
    const cards = playerCardsHtml(player);
    return `
      <div class="seat seat-${player.seat} ${isTurn ? "turn" : ""} ${player.connected ? "" : "offline"} ${reveal ? "showdown" : ""}">
        <div class="avatar">${name[0].toUpperCase()}</div>
        <div class="seat-name">${name}${isViewer ? " (Bạn)" : ""}</div>
        <div class="seat-chips">${chipStack(player.chips, player.chips)}</div>
        <div class="seat-bet">${player.bet ? `Cược ${player.bet}${chipStack(player.bet)}` : ""}</div>
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
    ? (state.finished ? "Chờ chủ phòng chia ván mới..." : "Đang chờ người chơi khác...")
    : "Chờ chủ phòng bắt đầu...";

  if (myTurn) {
    const slider = $("#raise");
    slider.min = state.minRaise;
    slider.max = state.maxRaise;
    slider.value = Math.max(state.minRaise, Math.min(Number(slider.value), state.maxRaise));
    $("#raise-value").textContent = slider.value;
  }

  animateLastEvent();
}

function animateLastEvent() {
  const event = state.lastEvent || {};
  const key = `${state.hand}:${event.kind}:${event.seat}:${event.amount}:${event.finished ? "done" : ""}`;
  if (!event.kind || key === lastEventKey || event.kind === "deal") {
    lastEventKey = key;
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

$("#create").onclick = () => enter(true);
$("#join").onclick = () => enter(false);
$("#name").value = localStorage.pokerName || "";
$("#room-code").oninput = (event) => {
  event.target.value = event.target.value.toUpperCase();
};
$("#start").onclick = () => ws.send(JSON.stringify({ type: "start" }));
$("#copy").onclick = async () => {
  await navigator.clipboard.writeText(state.room);
  $("#copy").textContent = "ĐÃ SAO CHÉP";
  setTimeout(() => {
    $("#copy").textContent = "SAO CHÉP MÃ MỜI";
  }, 1300);
};
$("#raise").oninput = (event) => {
  $("#raise-value").textContent = event.target.value;
};
document.querySelectorAll("[data-action]").forEach((button) => {
  button.onclick = () => sendAction(button.dataset.action);
});
