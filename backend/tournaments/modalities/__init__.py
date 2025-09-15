from __future__ import annotations
from typing import Dict, Any

# --------- PRESETS ----------
# NOTA: Estes presets foram derivados do regulamento que você forneceu (JUD 2K25).
# Ajustaremos a ordem/itens se houver erratas ou anexos técnicos novos.

VALORANT_RULESET: Dict[str, Any] = {
    "name": "VALORANT",
    "scoring": {"win": 1, "loss": 0},  # fase de grupos
    "indices_schema": {
        "mode": {"enum": ["MD1", "MD3"], "required": True},
        "maps": {"type": "list", "min": 1, "max": 3, "required": True},     # nomes dos mapas na ordem jogada
        "rounds": {"type": "list", "min": 1, "max": 3, "required": True},    # [{"home":13,"away":x}, ...]
        "avgWinTimeSec": {"type": "number", "required": False},              # opcional
        "wo": {"type": "bool", "required": False}
    },
    "tiebreakers": [
        "WO_FEWEST", "WINS", "H2H", "ROUND_DIFF", "MAP_DIFF", "AVG_WIN_TIME", "EXTRA_MATCH"
    ],
}

FREE_FIRE_RULESET: Dict[str, Any] = {
    "name": "FREE_FIRE",
    "scoring": {"win": 1, "loss": 0},  # 1 ponto por vitória da partida (duelo)
    "indices_schema": {
        "roundWins": {"type": "object", "required": True},  # {"home": 4, "away": 2}
        "winner": {"type": "str", "required": True},        # "home" ou "away"
        "wo": {"type": "bool", "required": False}
    },
    "tiebreakers": [
        "ROUND_WINS", "EXTRA_MATCH"
    ],
    "wo_penalty_points": -20  # aplicar ao quadro geral quando WO configurado
}

LOL_RULESET: Dict[str, Any] = {
    "name": "LOL",
    "scoring": {"win": 1, "loss": 0, "wo_loss": -1},  # provisório; ajustável pelo anexo técnico
    "indices_schema": {
        "winner": {"type": "str", "required": True},        # "home" ou "away"
        "gameDurationSec": {"type": "number", "required": True},
        "kills": {"type": "object", "required": False},
        "turrets": {"type": "object", "required": False},
        "dragons": {"type": "object", "required": False},
        "barons": {"type": "object", "required": False},
        "wo": {"type": "bool", "required": False}
    },
    "tiebreakers": [
        "WO_FEWEST", "WINS", "H2H", "AVG_WIN_TIME", "EXTRA_MATCH_OR_DRAW"
    ],
}

def get_ruleset(modality: str) -> Dict[str, Any]:
    m = modality.upper()
    if m == "VALORANT": return VALORANT_RULESET
    if m == "FREE_FIRE": return FREE_FIRE_RULESET
    if m == "LOL": return LOL_RULESET
    raise ValueError(f"Modality not supported: {modality}")

# --------- VALIDADORES BÁSICOS (para o report) ----------
def _ensure(cond: bool, msg: str):
    if not cond:
        raise ValueError(msg)

def validate_report_valorant(indices: Dict[str, Any]) -> None:
    mode = indices.get("mode")
    maps = indices.get("maps", [])
    rounds = indices.get("rounds", [])
    _ensure(mode in ("MD1", "MD3"), "mode deve ser MD1 ou MD3")
    max_maps = 1 if mode == "MD1" else 3
    _ensure(1 <= len(maps) <= max_maps, f"quantidade de mapas inválida para {mode}")
    _ensure(len(rounds) == len(maps), "rounds deve ter o mesmo tamanho de maps")
    for r in rounds:
        _ensure(isinstance(r, dict) and "home" in r and "away" in r, "rounds precisa de objetos {home, away}")
        _ensure(0 <= r["home"] <= 16 and 0 <= r["away"] <= 16, "rounds plausíveis (0-16)")
    # não decide vencedor aqui — o serviço de ranking usará a soma dos rounds e o resultado informado

def validate_report_free_fire(indices: Dict[str, Any]) -> None:
    rw = indices.get("roundWins") or {}
    winner = indices.get("winner")
    _ensure(isinstance(rw, dict) and "home" in rw and "away" in rw, "roundWins precisa de {home, away}")
    _ensure(isinstance(rw["home"], int) and isinstance(rw["away"], int), "roundWins devem ser inteiros")
    _ensure(winner in ("home", "away"), "winner deve ser 'home' ou 'away'")
    _ensure((rw["home"] != rw["away"]) or indices.get("wo") is True, "não pode empate sem WO no Free Fire")

def validate_report_lol(indices: Dict[str, Any]) -> None:
    _ensure(indices.get("winner") in ("home", "away"), "winner deve ser 'home' ou 'away'")
    dur = indices.get("gameDurationSec")
    _ensure(isinstance(dur, (int, float)) and dur > 0, "gameDurationSec deve ser > 0")
    # Em LoL não há empates; se 'wo' True, vencedor precisa estar coerente no serviço

def validate_report(modality: str, indices: Dict[str, Any]) -> None:
    m = modality.upper()
    if m == "VALORANT": return validate_report_valorant(indices)
    if m == "FREE_FIRE": return validate_report_free_fire(indices)
    if m == "LOL": return validate_report_lol(indices)
    raise ValueError(f"Modality not supported: {modality}")
