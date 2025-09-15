from django.contrib import admin
from .models import Tournament, Group, Team, Enrollment, Match, Standing

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "modality", "groups_count", "teams_per_group", "advance_per_group", "status")
    list_filter = ("modality", "status")
    search_fields = ("name",)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "tournament", "code")
    list_filter = ("tournament",)
    search_fields = ("code",)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "tournament", "team", "group")
    list_filter = ("tournament", "group")
    search_fields = ("team__name",)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "tournament", "group", "home_team", "away_team", "status", "is_wo")
    list_filter = ("tournament", "group", "status", "is_wo")
    search_fields = ("home_team__name", "away_team__name")

@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ("id", "tournament", "group", "team", "order_rank")
    list_filter = ("tournament", "group")
    search_fields = ("team__name",)
