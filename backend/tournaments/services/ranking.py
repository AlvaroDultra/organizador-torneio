from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
from statistics import mean

from django.db.models import Q

from tournaments.models import Tournament, Match, Team
from tournaments.modalities import get_ruleset, validate_report


@dataclass
class TeamAgg:
    team: Team
    points: int = 0
    wins: int = 0
    losses: int = 0
    wo_count: int = 0

    # índices por modalidade (usados em desempates)
    round_diff: int = 0           # Valorant
    map_diff: int = 0             # Valorant (em MD3)
    avg_win_times: List[float] = field(default_factory=list)  # Valorant/LoL
    round_wins: int = 0           # Free Fire (total de rounds vencidos)
    win_times_sum: float = 0.0    # para calcular média rápido
    win_times_n: int = 0

    # head-to-head cache (pontos contra cada equipe)
    h2h_points: Dict[int, int] = field(default_factory=dict)  # key = team_id adversário


def _apply_valorant(agg_home: TeamAgg, agg_away: TeamAgg, indices: Dict[str, Any], ruleset: Dict[str, Any], winner: str, is_wo: bool):
    # Pontuação
    if winner == "home":
        agg_home.points += ruleset["scoring"]["win"]
        agg_home.wins += 1
        agg_away.points += ruleset["scoring"]["loss"]
        agg_away.losses += 1
    elif winner == "away":
        agg_away.points += ruleset["scoring"]["win"]
        agg_away.wins += 1
        agg_home.points += ruleset["scoring"]["loss"]
        agg_home.losses += 1

    if is_wo:
        if winner == "home":
            agg_away.wo_count += 1
        else:
            agg_home.wo_count += 1

    # Índices de rounds/mapas
    rounds = indices.get("rounds", [])
    mode = indices.get("mode", "MD1")
    home_rounds_total = sum(r.get("home", 0) for r in rounds)
    away_rounds_total = sum(r.get("away", 0) for r in rounds)
    agg_home.round_diff += home_rounds_total - away_rounds_total
    agg_away.round_diff += away_rounds_total - home_rounds_total

    if mode == "MD3":
        # saldo de mapas baseado no placar por mapa
        home_maps = sum(1 for r in rounds if r.get("home", 0) > r.get("away", 0))
        away_maps = sum(1 for r in rounds if r.get("away", 0) > r.get("home", 0))
        agg_home.map_diff += home_maps - away_maps
        agg_away.map_diff += away_maps - home_maps

    # tempos médios de vitória (opcional no regulamento/preset)
    avg_win_time = indices.get("avgWinTimeSec")
    if isinstance(avg_win_time, (int, float)) and avg_win_time > 0:
        if winner == "home":
            agg_home.win_times_sum += avg_win_time
            agg_home.win_times_n += 1
        elif winner == "away":
            agg_away.win_times_sum += avg_win_time
            agg_away.win_times_n += 1


def _apply_free_fire(agg_home: TeamAgg, agg_away: TeamAgg, indices: Dict[str, Any], ruleset: Dict[str, Any], winner: str, is_wo: bool):
    # Pontuação (1 por vitória de partida)
    if winner == "home":
        agg_home.points += ruleset["scoring"]["win"]
        agg_home.wins += 1
        agg_away.points += ruleset["scoring"]["loss"]
        agg_away.losses += 1
    elif winner == "away":
        agg_away.points += ruleset["scoring"]["win"]
        agg_away.wins += 1
        agg_home.points += ruleset["scoring"]["loss"]
        agg_home.losses += 1

    if is_wo:
        if winner == "home":
            agg_away.wo_count += 1
        else:
            agg_home.wo_count += 1

    # vitórias de round contam para desempate
    rw = indices.get("roundWins", {})
    home_rw = int(rw.get("home", 0))
    away_rw = int(rw.get("away", 0))
    agg_home.round_wins += home_rw
    agg_away.round_wins += away_rw


def _apply_lol(agg_home: TeamAgg, agg_away: TeamAgg, indices: Dict[str, Any], ruleset: Dict[str, Any], winner: str, is_wo: bool):
    # Pontuação: vitória 1, derrota 0; WO derrota pode ser -1 (preset)
    if winner == "home":
        agg_home.points += ruleset["scoring"]["win"]
        agg_home.wins += 1
        # derrota "normal"
        agg_away.points += ruleset["scoring"]["loss"]
        agg_away.losses += 1
        # tempo de vitória
        dur = indices.get("gameDurationSec")
        if isinstance(dur, (int, float)) and dur > 0:
            agg_home.win_times_sum += dur
            agg_home.win_times_n += 1
    elif winner == "away":
        agg_away.points += ruleset["scoring"]["win"]
        agg_away.wins += 1
        agg_home.points += ruleset["scoring"]["loss"]
        agg_home.losses += 1
        dur = indices.get("gameDurationSec")
        if isinstance(dur, (int, float)) and dur > 0:
            agg_away.win_times_sum += dur
            agg_away.win_times_n += 1

    if is_wo:
        # quem perdeu por WO recebe penalidade se houver
        wo_loss_pen = ruleset["scoring"].get("wo_loss")
        if wo_loss_pen is not None:
            if winner == "home":
                agg_away.points += wo_loss_pen
            else:
                agg_home.points += wo_loss_pen
        # conta WO sofrido
        if winner == "home":
            agg_away.wo_count += 1
        else:
            agg_home.wo_count += 1


def _winner_from_indices(modality: str, indices: Dict[str, Any]) -> str:
    m = modality.upper()
    if m == "FREE_FIRE":
        return indices.get("winner")
    if m == "LOL":
        return indices.get("winner")
    if m == "VALORANT":
        # por simplicidade: exigimos que o report informe winner explícito (home|away)
        # (poderíamos inferir pelos rounds, mas manteremos direto para o MVP)
        return indices.get("winner")
    return None


def _apply_match_to_aggs(modality: str, ruleset: Dict[str, Any], match: Match, aggs: Dict[int, TeamAgg]):
    # valida indices (levanta ValueError se inválido)
    validate_report(modality, match.indices or {})

    home = aggs[match.home_team_id]
    away = aggs[match.away_team_id]

    winner = _winner_from_indices(modality, match.indices or {})
    is_wo = bool(match.is_wo)

    # pontuação head-to-head (p/ critério H2H)
    if winner == "home":
        home.h2h_points[match.away_team_id] = home.h2h_points.get(match.away_team_id, 0) + ruleset["scoring"]["win"]
        away.h2h_points[match.home_team_id] = away.h2h_points.get(match.home_team_id, 0) + ruleset["scoring"]["loss"]
    elif winner == "away":
        away.h2h_points[match.home_team_id] = away.h2h_points.get(match.home_team_id, 0) + ruleset["scoring"]["win"]
        home.h2h_points[match.away_team_id] = home.h2h_points.get(match.away_team_id, 0) + ruleset["scoring"]["loss"]

    if modality == "VALORANT":
        _apply_valorant(home, away, match.indices or {}, ruleset, winner, is_wo)
    elif modality == "FREE_FIRE":
        _apply_free_fire(home, away, match.indices or {}, ruleset, winner, is_wo)
    elif modality == "LOL":
        _apply_lol(home, away, match.indices or {}, ruleset, winner, is_wo)
    else:
        raise ValueError(f"Modality not supported: {modality}")


def _avg_win_time(agg: TeamAgg) -> float:
    if agg.win_times_n > 0:
        return agg.win_times_sum / agg.win_times_n
    return float("inf")  # se não venceu nenhuma, pior média possível para ranking por menor tempo


def _cmp_pair(a: TeamAgg, b: TeamAgg, tiebreakers: List[str]) -> int:
    # Retorna -1 se a < b, 0 se igual, +1 se a > b (para ordenar)
    # Primeira ordenação SEMPRE por pontos desc (quanto mais pontos, melhor)
    if a.points != b.points:
        return -1 if a.points > b.points else 1

    for tb in tiebreakers:
        if tb == "WO_FEWEST":
            if a.wo_count != b.wo_count:
                return -1 if a.wo_count < b.wo_count else 1
        elif tb == "WINS":
            if a.wins != b.wins:
                return -1 if a.wins > b.wins else 1
        elif tb == "H2H":
            # mais pontos contra o adversário
            ap = a.h2h_points.get(b.team.id, 0)
            bp = b.h2h_points.get(a.team.id, 0)
            if ap != bp:
                return -1 if ap > bp else 1
        elif tb == "ROUND_DIFF":
            if a.round_diff != b.round_diff:
                return -1 if a.round_diff > b.round_diff else 1
        elif tb == "MAP_DIFF":
            if a.map_diff != b.map_diff:
                return -1 if a.map_diff > b.map_diff else 1
        elif tb == "ROUND_WINS":
            if a.round_wins != b.round_wins:
                return -1 if a.round_wins > b.round_wins else 1
        elif tb == "AVG_WIN_TIME":
            aavg = _avg_win_time(a)
            bavg = _avg_win_time(b)
            if aavg != bavg:
                return -1 if aavg < bavg else 1
        elif tb in ("EXTRA_MATCH", "EXTRA_MATCH_OR_DRAW"):
            # o app marca pendência para jogo de desempate/sorteio; aqui consideramos empate
            return 0
        else:
            # tiebreaker desconhecido -> ignora
            continue

    return 0


def _sort_with_tiebreakers(aggs: List[TeamAgg], tiebreakers: List[str]) -> List[TeamAgg]:
    # Ordena com aplicação de critérios em cascata, incluindo H2H para pares;
    # para empates com 3+ times, aplicamos "mini-liga": recalcula H2H e reaplica critérios.
    # 1) Ordena por pontos desc como base
    aggs.sort(key=lambda x: x.points, reverse=True)

    i = 0
    while i < len(aggs):
        # encontra bloco de empatados em pontos
        j = i + 1
        while j < len(aggs) and aggs[j].points == aggs[i].points:
            j += 1

        block = aggs[i:j]
        if len(block) >= 2:
            # Para bloco de empatados, ordena aplicando os tiebreakers
            # 1º tentativa: comparação par-a-par
            block_sorted = sorted(block, key=lambda x: (
                -x.points,  # já iguais, mas mantemos
                x.wo_count,
                -x.wins,
                -x.h2h_points.get(x.team.id, 0),  # placeholder para estabilidade
            ))

            # Reordena de fato usando a função de comparação
            # Python não tem cmp nativo no sorted; então fazemos um bubble/merge simples:
            changed = True
            while changed:
                changed = False
                for k in range(len(block_sorted) - 1):
                    a, b = block_sorted[k], block_sorted[k + 1]
                    cmp = _cmp_pair(a, b, tiebreakers)
                    if cmp > 0:  # a "menor" que b → troca
                        block_sorted[k], block_sorted[k + 1] = b, a
                        changed = True

            aggs[i:j] = block_sorted

        i = j

    return aggs


def compute_group_table(tournament: Tournament, group_id: int) -> List[TeamAgg]:
    """Calcula as agregações e devolve a lista ordenada (sem persistir)."""
    ruleset = tournament.ruleset or get_ruleset(tournament.modality)
    tiebreakers: List[str] = ruleset.get("tiebreakers", [])
    modality = tournament.modality

    # Times do grupo
    team_ids = list(
        tournament.enrollments.filter(group_id=group_id).values_list("team_id", flat=True)
    )
    teams = {t.id: t for t in Team.objects.filter(id__in=team_ids)}
    aggs: Dict[int, TeamAgg] = {tid: TeamAgg(team=teams[tid]) for tid in team_ids}

    # Partidas reportadas do grupo
    matches = Match.objects.filter(
        tournament=tournament,
        group_id=group_id,
        status="REPORTED",
    )

    for m in matches:
        _apply_match_to_aggs(modality, ruleset, m, aggs)

    # finalizar médias
    for agg in aggs.values():
        if agg.win_times_n > 0:
            agg.avg_win_times = [_avg_win_time(agg)]

    # ordenar com desempates
    ordered = _sort_with_tiebreakers(list(aggs.values()), tiebreakers)
    return ordered
