"""
backend/solutions/tests/test_bunching.py

Unit tests for the seat-aware preflop card-bunching (dead-card) profile.
"""

from django.test import SimpleTestCase

from solutions.services.bunching import (
    RANKS,
    derive_bunching_weights,
    expected_folded_cards_by_rank,
    fallback_profile,
    rank_survival_weights,
)


class BunchingProfileTests(SimpleTestCase):
    def test_profile_has_13_normalized_weights(self):
        w = derive_bunching_weights(["UTG", "MP", "CO"])
        self.assertEqual(len(w), 13)
        self.assertAlmostEqual(sum(w) / 13.0, 1.0, places=9)

    def test_low_cards_are_more_likely_dead_than_aces(self):
        w = derive_bunching_weights(["UTG", "MP", "CO"])
        self.assertLess(w[RANKS.index("2")], w[RANKS.index("A")])
        self.assertLess(w[RANKS.index("7")], w[RANKS.index("K")])

    def test_no_folded_seats_is_uniform(self):
        w = derive_bunching_weights([])
        self.assertTrue(all(abs(x - 1.0) < 1e-12 for x in w))

    def test_more_folded_seats_remove_more_cards(self):
        one = expected_folded_cards_by_rank(
            [derive_range_stub()]
        )
        two = expected_folded_cards_by_rank(
            [derive_range_stub(), derive_range_stub()]
        )
        self.assertGreater(sum(two), sum(one))

    def test_rank_survival_weights_are_monotone_in_removal(self):
        # A range that plays only aces leaves low cards dead.
        ranges = [{"AA": 1.0, "AKs": 1.0, "AKo": 1.0}]
        w = rank_survival_weights(ranges)
        self.assertLess(w[0], w[12])

    def test_builtin_fallback_matches_engine_profile_shape(self):
        w = fallback_profile(4)
        self.assertAlmostEqual(sum(w) / 13.0, 1.0, places=9)
        self.assertGreater(w[RANKS.index("A")], w[RANKS.index("2")])
        self.assertTrue(all(abs(x - 1.0) < 1e-12 for x in fallback_profile(0)))


def derive_range_stub():
    """A small playing range used to make removal measurable."""
    return {"AA": 1.0, "KK": 1.0, "QQ": 1.0, "AKs": 1.0}
