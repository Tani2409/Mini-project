import json
import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)


def _database_url():
    url = os.getenv("DATABASE_URL") or os.getenv("POKER_DATABASE_URL")
    if not url:
        return "sqlite:///poker_history.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_database_url(), future=True)
metadata = MetaData()

hand_results = Table(
    "hand_results",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("room_code", String(16), nullable=False, index=True),
    Column("hand_number", Integer, nullable=False),
    Column("board", JSON, nullable=False),
    Column("pot_delta", Integer, nullable=False),
    Column("finished_by", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

hand_player_results = Table(
    "hand_player_results",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("hand_result_id", ForeignKey("hand_results.id"), nullable=False),
    Column("player_id", String(80), nullable=False),
    Column("player_name", String(40), nullable=False),
    Column("seat", Integer, nullable=False),
    Column("hole_cards", JSON, nullable=False),
    Column("folded", Boolean, nullable=False),
    Column("winner", Boolean, nullable=False),
    Column("payoff", Integer, nullable=False),
    Column("chips_after", Integer, nullable=False),
)


def init_db():
    metadata.create_all(engine)


def record_hand_result(room):
    state = room.state
    if state is None:
        return

    payoffs = [int(value) for value in state.payoffs]
    winners = {seat for seat, payoff in enumerate(payoffs) if payoff > 0}
    board = cards_to_json(card for board_cards in state.board_cards for card in board_cards)
    finished_by = str((room.last_event or {}).get("kind") or "showdown")
    pot_delta = sum(payoff for payoff in payoffs if payoff > 0)
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        result = connection.execute(
            hand_results.insert().values(
                room_code=room.code,
                hand_number=room.hand_number,
                board=board,
                pot_delta=pot_delta,
                finished_by=finished_by,
                created_at=now,
            )
        )
        hand_result_id = result.inserted_primary_key[0]
        rows = []
        for seat, player in enumerate(room.players):
            rows.append({
                "hand_result_id": hand_result_id,
                "player_id": player.player_id,
                "player_name": player.name,
                "seat": seat,
                "hole_cards": room.dealt_hole_cards[seat] if seat < len(room.dealt_hole_cards) else [],
                "folded": seat in room.folded_seats,
                "winner": seat in winners,
                "payoff": payoffs[seat] if seat < len(payoffs) else 0,
                "chips_after": int(state.stacks[seat]) if seat < len(state.stacks) else 0,
            })
        if rows:
            connection.execute(hand_player_results.insert(), rows)


def room_history(room_code, limit=20):
    limit = max(1, min(int(limit), 50))
    query = (
        select(hand_results)
        .where(hand_results.c.room_code == room_code.upper())
        .order_by(hand_results.c.id.desc())
        .limit(limit)
    )
    with engine.begin() as connection:
        hands = [dict(row._mapping) for row in connection.execute(query)]
        if not hands:
            return []
        hand_ids = [hand["id"] for hand in hands]
        player_query = (
            select(hand_player_results)
            .where(hand_player_results.c.hand_result_id.in_(hand_ids))
            .order_by(hand_player_results.c.seat.asc())
        )
        players_by_hand = {hand_id: [] for hand_id in hand_ids}
        for row in connection.execute(player_query):
            data = dict(row._mapping)
            players_by_hand[data["hand_result_id"]].append(data)

    for hand in hands:
        hand["players"] = players_by_hand[hand["id"]]
        hand["created_at"] = hand["created_at"].isoformat()
    return hands


def cards_to_json(cards):
    return [repr(card) for card in cards]
