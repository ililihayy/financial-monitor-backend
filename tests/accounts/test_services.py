import pytest
from accounts.services import AuditService, PIIDetectionService

def test_tamper_evident_logging_integrity():
    log_entry = AuditService.log(action='password_change', user='user@finsecure.net', ip='192.168.1.1')
    assert AuditService.verify_entry(log_entry.copy()) is True
    
    tampered_entry = log_entry.copy()
    tampered_entry['ip'] = '10.0.0.5' 
    assert AuditService.verify_entry(tampered_entry) is False

def test_dlp_pii_detection_luhn_algorithm():
    valid_card = "4321 5678 9101 1121"
    fake_string = "Just normal transactional text without data"
    
    assert PIIDetectionService.contains_pii(valid_card) is True
    assert PIIDetectionService.contains_pii(fake_string) is False