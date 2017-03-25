from django.apps import AppConfig

from wagtail_pgsearchbackend.utils import (
    BOOSTS_WEIGHTS, WEIGHTS_VALUES, determine_boosts_weights)


class PgSearchBackendConfig(AppConfig):
    name = 'wagtail_pgsearchbackend'

    def ready(self):
        BOOSTS_WEIGHTS.extend(determine_boosts_weights())
        sorted_boosts_weights = sorted(BOOSTS_WEIGHTS, key=lambda t: t[0])
        max_weight = sorted_boosts_weights[-1][0]
        WEIGHTS_VALUES.extend([v / max_weight
                               for v, w in sorted_boosts_weights])
