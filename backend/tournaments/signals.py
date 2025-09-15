from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Tournament
from .modalities import get_ruleset

@receiver(pre_save, sender=Tournament)
def fill_ruleset(sender, instance: Tournament, **kwargs):
    # se não houver ruleset ou estiver vazio, popular a partir da modalidade
    if not instance.ruleset:
        instance.ruleset = get_ruleset(instance.modality)
