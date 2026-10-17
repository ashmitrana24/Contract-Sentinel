"""Comprehensive unit tests for PII redaction and restoration rules."""

from __future__ import annotations

from clauseguard.ask.privacy import (
    is_luhn_valid,
    is_verhoeff_valid,
    redact_sensitive_pii,
    restore_sensitive_pii,
)


def test_verhoeff_checksum_algorithm():
    """Verify that is_verhoeff_valid correctly differentiates valid from invalid Aadhaar numbers."""
    # Valid Verhoeff Aadhaar test numbers
    assert is_verhoeff_valid("999999990019") is True
    assert is_verhoeff_valid("234567890124") is True
    assert is_verhoeff_valid("123456789012") is False  # Invalid checksum
    assert is_verhoeff_valid("111111111111") is False  # Invalid checksum


def test_luhn_checksum_algorithm():
    """Verify that is_luhn_valid correctly validates credit card numbers."""
    assert is_luhn_valid("1234567812345670") is True
    assert is_luhn_valid("1234567812345671") is False


def test_aadhaar_redaction_and_restoration():
    """Verify Aadhaar numbers (with and without spaces or hyphens) are masked and restored."""
    valid_aadhaar_spaced = "9999 9999 0019"
    valid_aadhaar_dashed = "2345-6789-0124"
    invalid_aadhaar = "1234 5678 9012"

    sample_text = (
        f"Borrower's Aadhaar is {valid_aadhaar_spaced} and co-borrower is {valid_aadhaar_dashed}. "
        f"Invalid test ID is {invalid_aadhaar}."
    )

    redacted, mapping = redact_sensitive_pii(sample_text)

    # Valid Aadhaar must be masked
    assert valid_aadhaar_spaced not in redacted
    assert valid_aadhaar_dashed not in redacted
    assert "[AADHAAR_REDACTED_" in redacted

    # Invalid checksum must NOT be masked as Aadhaar
    assert invalid_aadhaar in redacted

    # Restoration must restore exact original text
    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample_text


def test_pan_redaction_and_restoration():
    """Verify Indian PAN cards (AAAAA9999A) are redacted and restored."""
    pan1 = "ABCDE1234F"
    pan2 = "ZXCVB9876Q"
    sample = f"Taxpayer PAN is {pan1} and corporate PAN is {pan2}."

    redacted, mapping = redact_sensitive_pii(sample)
    assert pan1 not in redacted
    assert pan2 not in redacted
    assert "[PAN_REDACTED_" in redacted

    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample


def test_ifsc_redaction_and_restoration():
    """Verify Indian IFSC codes (AAAA0XXXXXX) are redacted and restored."""
    ifsc = "HDFC0001234"
    sample = f"Remit funds to bank using IFSC code {ifsc} immediately."

    redacted, mapping = redact_sensitive_pii(sample)
    assert ifsc not in redacted
    assert "[IFSC_REDACTED_" in redacted

    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample


def test_card_number_redaction():
    """Verify Luhn-valid payment cards are masked."""
    card = "1234-5678-1234-5670"  # Luhn valid 16 digits
    sample = f"Charge payment to card {card}."

    redacted, mapping = redact_sensitive_pii(sample)
    assert card not in redacted
    assert "[CARD_REDACTED_" in redacted

    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample


def test_bank_account_redaction():
    """Verify bank account numbers (9-18 digits near account/banking keywords) are masked."""
    sample = "Please transfer payment to Account No. 987654321098 at State Bank."

    redacted, mapping = redact_sensitive_pii(sample)
    assert "987654321098" not in redacted
    assert "[BANK_ACCOUNT_REDACTED_" in redacted

    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample


def test_negative_guardrails_must_not_be_masked():
    """Verify that contracts, invoices, amounts in lakh/crore, dates, clauses, and PIN codes are preserved."""
    negatives_text = (
        "Agreement Ref: AGR-2024-001 under Invoice INV-987654. "
        "The total compensation is Rs. 50,00,000 (Fifty Lakh) or 5 crore under Clause 12.3 and Section 4.1.2. "
        "Executed on 2024-10-15 with PIN code 110001. "
        "Tracking item order 9876543210."
    )

    redacted, mapping = redact_sensitive_pii(negatives_text)

    # None of these legal/contractual terms must be masked
    assert "AGR-2024-001" in redacted
    assert "INV-987654" in redacted
    assert "Rs. 50,00,000" in redacted
    assert "Fifty Lakh" in redacted
    assert "5 crore" in redacted
    assert "Clause 12.3" in redacted
    assert "Section 4.1.2" in redacted
    assert "2024-10-15" in redacted
    assert "110001" in redacted
    assert "9876543210" in redacted  # Standalone 10-digit number without phone context
