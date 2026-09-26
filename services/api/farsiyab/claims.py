"""Business owners claiming their listing, without accounts.

1. The owner starts a claim and gets a short token.
2. They prove control of the business by putting the token on the business's own
   website (as found by our sources) or in its Telegram channel description, and ask
   us to check. With method "manual" an admin verifies by other means instead.
3. On success they receive an owner key, shown once; only its hash is stored. The
   key lets them correct the listing's details, mark it closed or hide it.

Corrections go live at once: the owner is the best source for their own address and
phone. The indexer never overwrites a field that already has a value, so they stay.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from farsiyab.adapters.telegram import PREVIEW
from farsiyab.config import get_settings
from farsiyab.links import website_link
from farsiyab.models import Business, BusinessLink, Claim

TOKEN_PREFIX = "farsiyab-"
OWNER_STATUSES = ("active", "closed", "hidden")


class ClaimError(Exception):
    """A claim cannot go ahead; the message says why (shown to the owner)."""


@dataclass
class Proof:
    method: str
    where: str | None  # the page the token must appear on


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_hex(6)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def proof_target(session: Session, business: Business, method: str) -> Proof:
    """Where the token has to be put for this method."""
    if method == "manual":
        return Proof(method, None)
    kind = "website" if method == "website" else "telegram"
    link = session.scalar(
        select(BusinessLink).where(BusinessLink.business_id == business.id,
                                   BusinessLink.kind == kind).order_by(BusinessLink.id)
    )
    if link is None:
        raise ClaimError(f"this business has no known {kind}")
    return Proof(method, link.url if kind == "website" else PREVIEW.format(name=link.value))


def start_claim(
    session: Session, business: Business, method: str, contact_email: str | None,
    note: str | None, client_hash: str | None,
) -> tuple[Claim, Proof]:
    proof = proof_target(session, business, method)
    claim = Claim(business_id=business.id, method=method, token=new_token(),
                  contact_email=contact_email, note=note, client_hash=client_hash)
    session.add(claim)
    session.flush()
    return claim, proof


def page_has_token(url: str, token: str, client: httpx.Client | None = None) -> bool:
    """Fetch the owner's page once, at their request, and look for the token."""
    client = client or httpx.Client(headers={"User-Agent": get_settings().user_agent},
                                    timeout=20, follow_redirects=True)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise ClaimError(f"could not open {url}: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise ClaimError(f"{url} answered HTTP {response.status_code}")
    return token in response.text


def grant(claim: Claim) -> str:
    """Mark the claim verified and return a fresh owner key (never stored in clear)."""
    key = secrets.token_urlsafe(24)
    claim.status = "verified"
    claim.owner_key_hash = hash_key(key)
    claim.verified_at = datetime.now(UTC)
    return key


def verify(session: Session, claim: Claim, client: httpx.Client | None = None) -> str:
    if claim.status != "pending":
        raise ClaimError(f"claim already {claim.status}")
    if claim.method == "manual":
        raise ClaimError("an admin verifies this claim")
    business = session.get(Business, claim.business_id)
    proof = proof_target(session, business, claim.method)
    if not page_has_token(proof.where, claim.token, client):
        raise ClaimError(f"the code {claim.token} was not found on {proof.where}")
    key = grant(claim)
    business.owner_verified_at = claim.verified_at
    return key


def owner_claim(session: Session, claim_id: uuid.UUID, key: str) -> Claim:
    claim = session.get(Claim, claim_id)
    if (claim is None or claim.status != "verified" or not claim.owner_key_hash
            or not secrets.compare_digest(claim.owner_key_hash, hash_key(key))):
        raise ClaimError("unknown claim or wrong key")
    return claim


def apply_owner_edit(session: Session, business: Business, changes: dict) -> None:
    """Owner corrections. Empty values are ignored: owners correct, they do not erase."""
    if changes.get("name_fa"):
        business.name_fa = changes["name_fa"].strip()
    if changes.get("name_latin"):
        business.name_latin = changes["name_latin"].strip()
    if changes.get("address"):
        business.address = changes["address"].strip()
    if changes.get("phone"):
        business.phone_e164 = changes["phone"].strip()
    if changes.get("website"):
        link = website_link(changes["website"])
        if link is None:
            raise ClaimError("not a website address")
        business.website = link.url
    if changes.get("status"):
        if changes["status"] not in OWNER_STATUSES:
            raise ClaimError("status must be active, closed or hidden")
        business.status = changes["status"]
    business.owner_verified_at = datetime.now(UTC)
