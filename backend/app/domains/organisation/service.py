"""Organisation & site service (section 5.4).

Validates and assembles organisation and site profiles, then persists them in
Ost Infinity through the anti-corruption layer. The service is the logic; Ost
Infinity is the record (section 7). All writes carry an idempotency key so a
retried saga step cannot create duplicates.
"""
from __future__ import annotations

from app.acl.anti_corruption import acl
from app.core.audit import audit_log
from app.core.errors import DomainError
from app.models.schemas import OrganisationCreate, SiteCreate


class OrganisationService:
    def create_organisation(self, *, idem_key: str, customer_id: str,
                            org: OrganisationCreate) -> str:
        if not org.name.strip():
            raise DomainError("Organisation name is required.")
        organisation_id = acl.create_organisation(idem_key=idem_key, customer_id=customer_id, org=org)
        audit_log.record("organisation.created", target=organisation_id, customer=customer_id)
        return organisation_id

    def add_sites(self, *, idem_key: str, organisation_id: str, sites: list[SiteCreate]) -> list[str]:
        if not sites:
            return []
        site_ids = acl.add_sites(idem_key=idem_key, organisation_id=organisation_id, sites=sites)
        audit_log.record("sites.created", target=organisation_id, count=len(site_ids))
        return site_ids
