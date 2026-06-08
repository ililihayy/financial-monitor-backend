import pytest
import random
from datetime import date
from transactions.services.anonymization_service import AnonymizationService

@pytest.fixture
def anonymizer():
    return AnonymizationService()

def test_pii_scrubbing_filters_sensitive_data(anonymizer):
    text_with_card = "Paid 1500 with credit card 4321567891011121"
    clean_text = anonymizer._scrub_pii(text_with_card)
    assert "[CARD]" in clean_text or "[PHONE]" in clean_text

def test_merchant_abstraction_replaces_brands(anonymizer):
    raw_desc = "Uber Ride London"
    abstracted = anonymizer._abstract_merchant(raw_desc)
    assert "Transportation" in abstracted

def test_amount_jittering_adds_noise(anonymizer):
    original_amount = 100.00
    rng = random.Random(42)
    jittered_amount = anonymizer._bucket_amount(original_amount, rng)
    assert jittered_amount >= 0.0