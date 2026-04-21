"""
PII (Personally Identifiable Information) Detection Service.

Scans free-text fields for common PII patterns (credit card numbers,
SSN, IBAN, phone numbers, emails) and warns users before saving.
"""

import re
from typing import Dict, List


class PIIDetectionService:
    """
    Regex-based PII detector.

    Returns a list of PII type labels found in the input text.
    Designed to be called from serializer validators.
    """

    # Compiled patterns — order does not matter; all are checked.
    _PATTERNS: List[Dict] = [
        {
            'label': 'credit_card',
            'description': 'Credit/debit card number',
            'regex': re.compile(
                r'\b(?:\d[ -]*?){13,19}\b'
            ),
            # Extra Luhn check performed in code below
        },
        {
            'label': 'ssn',
            'description': 'US Social Security Number',
            'regex': re.compile(
                r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
            ),
        },
        {
            'label': 'iban',
            'description': 'International Bank Account Number',
            'regex': re.compile(
                r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b', re.IGNORECASE
            ),
        },
        {
            'label': 'phone',
            'description': 'Phone number',
            'regex': re.compile(
                r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{2,4}[-.\s]?\d{0,4}'
            ),
        },
        {
            'label': 'email',
            'description': 'Email address',
            'regex': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
        },
        {
            'label': 'passport',
            'description': 'Passport number pattern',
            'regex': re.compile(
                r'\b[A-Z]{1,2}\d{6,9}\b'
            ),
        },
    ]

    @classmethod
    def _luhn_check(cls, number_str: str) -> bool:
        """Validate a number string with the Luhn algorithm."""
        digits = [int(d) for d in number_str if d.isdigit()]
        if len(digits) < 13:
            return False
        checksum = 0
        reverse_digits = digits[::-1]
        for i, d in enumerate(reverse_digits):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        return checksum % 10 == 0

    @classmethod
    def scan(cls, text: str) -> List[Dict[str, str]]:
        """
        Scan *text* for PII patterns.

        Returns:
            List of dicts ``{"type": "<label>", "description": "..."}``
            for every PII category detected.  Empty list when clean.
        """
        if not text:
            return []

        findings: List[Dict[str, str]] = []
        seen_labels = set()

        for pattern in cls._PATTERNS:
            matches = pattern['regex'].findall(text)
            if not matches:
                continue

            label = pattern['label']

            # Credit-card: require Luhn-valid match to reduce false positives
            if label == 'credit_card':
                matches = [m for m in matches if cls._luhn_check(m)]
                if not matches:
                    continue

            # Phone: require at least 7 digits to avoid matching short numbers
            if label == 'phone':
                matches = [m for m in matches if sum(
                    c.isdigit() for c in m) >= 7]
                if not matches:
                    continue

            if label not in seen_labels:
                seen_labels.add(label)
                findings.append({
                    'type': label,
                    'description': pattern['description'],
                })

        return findings

    @classmethod
    def contains_pii(cls, text: str) -> bool:
        """Return True if *text* contains any detectable PII."""
        return len(cls.scan(text)) > 0
