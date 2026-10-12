import pytest

from pcb_copilot.review.design_rules_native import val_to_farads


@pytest.mark.parametrize(('value', 'farads'), [
    ('100n', 100e-9),
    ('100 nF', 100e-9),
    ('100n / 50V', 100e-9),
    ('100 nF / 50 V / X7R', 100e-9),
    ('22u / 25V', 22e-6),
    ('220 uF / 50 V / 20%', 220e-6),
    ('0.1 uF', 100e-9),
    ('.1 uF', 100e-9),
    ('1 \u00b5F / 16 V', 1e-6),
    ('1 \u03bcF / 16 V', 1e-6),
    ('2u2 / 16V', 2.2e-6),
    ('4n7F', 4.7e-9),
    ('33p / 50V', 33e-12),
    ('1 mF', 1e-3),
    ('0.000001 F', 1e-6),
])
def test_capacitance_with_units_and_ratings(value, farads):
    assert val_to_farads(value) == pytest.approx(farads, rel=1e-12, abs=0)


@pytest.mark.parametrize('value', [
    '', '50 V', '100k / 1%', '100n note', '100nFgarbage',
    '1.2.3u', '1.2u3', '-100n', 'NaN', 'inf', 'uF', '/ 50V',
])
def test_unrecognized_or_malformed_values_do_not_count_as_capacitors(value):
    assert val_to_farads(value) == 0


def test_rated_bypass_is_recognized_without_misclassifying_bulk_capacitance():
    values = ['100n / 50V', '1 uF / 25 V', '22u / 25V', '220u / 50V']
    eligible = [value for value in values if 0 < val_to_farads(value) <= 1e-6]
    assert eligible == ['100n / 50V', '1 uF / 25 V']
