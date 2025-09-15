from __future__ import annotations
from django.db import models
from django.core.validators import MinValueValidator

# -----------------------------
# Choices e constantes
# -----------------------------
class Modality(models.TextChoices):
    FREE_FIRE = "FREE_FIRE", "Free Fire"
    VALORANT = "VALORANT", "Valorant"
    LOL = "LOL", "League of Legends"

class TournamentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Rascunho"
    ACTIVE = "ACTIVE", "Ativo"
    FINISHED = "FINISHED", "Encerrado"

class MatchStatus(models.TextChoices):
    PENDING = "PENDING", "Pendente"
    REPORTED = "REPORTED", "Reportada"

# -----------------------------
# Núcleo
# -----------------------------
class Tournament(models.Model):
    name = models.CharField(max_length=120)
    modality = models.CharField(max_length=20, choices=Modality.choices)
    groups_count = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    teams_per_group = models.PositiveIntegerField(validators=[MinValueValidator(2)], default=4)
    advance_per_group = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=2)
    ruleset = models.JSONField(default=dict)  # presets de pontuação, tiebreakers, índices
    status = models.CharField(max_length=20, choices=TournamentStatus.choices, default=TournamentStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["modality", "status"])]
        ordering = ["-id"]

    def __str__(self):
        return f"{self.name} [{self.modality}]"


class Group(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="groups")
    code = models.CharField(max_length=4)  # A, B, C...

    class Meta:
        unique_together = [("tournament", "code")]
        ordering = ["code"]

    def __str__(self):
        return f"{self.tournament.name} - Grupo {self.code}"


class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    meta = models.JSONField(default=dict, blank=True)  # opcional: contatos, tags etc.

    def __str__(self):
        return self.name


class Enrollment(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="enrollments")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="enrollments")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="enrollments")

    class Meta:
        unique_together = [("tournament", "team")]
        indexes = [models.Index(fields=["tournament", "group"])]

    def __str__(self):
        return f"{self.team} @ {self.tournament} ({self.group.code})"


class Match(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="matches")
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_matches")
    scheduled_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.PENDING)
    is_wo = models.BooleanField(default=False)

    # resultado mínimo + índices específicos por modalidade
    result = models.JSONField(default=dict, blank=True)
    indices = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tournament", "group"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(home_team=models.F("away_team")),
                name="match_home_neq_away",
                violation_error_message="Times da mesma partida devem ser diferentes.",
            ),
        ]
        # evita duplicar confrontos iguais dentro do torneio+grupo
        unique_together = [("tournament", "group", "home_team", "away_team")]

    def __str__(self):
        return f"{self.group.code}: {self.home_team} x {self.away_team}"


class Standing(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="standings")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="standings")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="standings")

    # snapshot agregada (pontos, vitórias, saldos, tempos…)
    stats = models.JSONField(default=dict)
    order_rank = models.PositiveIntegerField(default=0)  # posição final no grupo

    class Meta:
        unique_together = [("group", "team")]
        indexes = [models.Index(fields=["group", "order_rank"])]

    def __str__(self):
        return f"{self.group.code} #{self.order_rank} - {self.team}"
