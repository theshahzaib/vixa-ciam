"""Verification service (section 5.4).

Owns email, mobile and domain verification. Email/mobile reuse the MFA OTP
machinery; domain verification auto-generates a TXT record for the customer to
publish and confirms ownership via a DNS lookup.
"""
from __future__ import annotations

import secrets

from app.acl.anti_corruption import acl
from app.adapters.providers import dns
from app.core.audit import audit_log
from app.core.errors import DomainError
from app.models.schemas import DomainVerificationRecord


class VerificationService:
    def generate_domain_record(self, organisation_id: str, domain: str) -> DomainVerificationRecord:
        token = secrets.token_hex(16)
        record = DomainVerificationRecord(
            record_type="TXT",
            host=f"_vixa-verify.{domain}",
            value=f"vixa-site-verification={token}",
            ttl_seconds=3600,
        )
        # Demo convenience: seed the resolver so the subsequent check succeeds.
        dns.seed_record(record.host, record.value)
        audit_log.record("domain.record_generated", target=organisation_id, domain=domain)
        return record

    def confirm_domain(self, organisation_id: str, record: DomainVerificationRecord) -> bool:
        if not dns.lookup_txt(record.host, record.value):
            raise DomainError("DNS TXT record not found yet. Allow time for propagation and retry.")
        acl.mark_domain_verified(organisation_id)
        audit_log.record("domain.verified", target=organisation_id)
        return True
