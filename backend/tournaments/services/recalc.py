from __future__ import annotations
from typing import List

from django.db import transaction

from tournaments.models import Tournament, Standing, Group
from .ranking import compute_group_table


@transaction.atomic
def recalc_group_standings(tournament: Tournament, group: Group) -> List[Standing]:
    """Recalcula e persiste a tabela (Standings) do grupo informado."""
    table = compute_group_table(tournament, group.id)

    # apaga standings antigos do grupo
    Standing.objects.filter(tournament=tournament, group=group).delete()

    new_rows: List[Standing] = []
    for pos, agg in enumerate(table, start=1):
        stats = {
            "points": agg.points,
            "wins": agg.wins,
            "losses": agg.losses,
            "wo_count": agg.wo_count,
            "round_diff": agg.round_diff,
            "map_diff": agg.map_diff,
            "round_wins": agg.round_wins,
            "avg_win_time": agg.avg_win_times[0] if agg.avg_win_times else None,
        }
        row = Standing.objects.create(
            tournament=tournament,
            group=group,
            team=agg.team,
            stats=stats,
            order_rank=pos,
        )
        new_rows.append(row)

    return new_rows
