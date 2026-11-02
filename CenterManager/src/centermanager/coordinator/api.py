"""Opt-in HTTP adapter for the E1C coordinator.

This API cannot start without an injected trusted authentication verifier.
No Windows EXE code imports/starts it, and no Git credentials are accepted.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .authority import Coordinator, CoordinatorError
from .storage import LocalCandidateStore
from .verification import CandidateVerifier


@dataclass(frozen=True)
class Principal:
    identity: str
    repositories: frozenset[str]
    permissions: frozenset[str]


def build_app(coordinator: Coordinator, store: LocalCandidateStore,
              verify_token: Callable[[str], Principal],
              candidate_verifier: CandidateVerifier | None = None):
    """Build a staging API with pluggable authenticated identity.

    verify_token MUST cryptographically validate credentials and their audience
    in deployment. No trusting request-supplied usernames or boolean admin flags.
    """
    from fastapi import FastAPI, Header, HTTPException, Depends
    from pydantic import BaseModel

    class Command(BaseModel):
        request_id: str
        action: str
        params: dict = {}

    class CandidateUpload(BaseModel):
        candidate_id: str
        ciphertext_hex: str
        sha256: str
        generation: int
        identity: str

    app = FastAPI(title="AnTechKids E1C Coordinator — staging", version="0.1.0")

    def identity(authorization: str = Header(default="")) -> Principal:
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "AUTHENTICATION_REQUIRED")
        try:
            result = verify_token(authorization[7:])
            if not isinstance(result, Principal) or not result.identity:
                raise ValueError("Invalid identity")
            return result
        except Exception:
            raise HTTPException(401, "AUTHENTICATION_FAILED")

    def require(principal: Principal, repository: str, permission: str):
        if repository not in principal.repositories or permission not in principal.permissions:
            raise HTTPException(403, "FORBIDDEN")

    @app.get("/v1/repositories/{repository}/state")
    def state(repository: str, principal: Principal = Depends(identity)):
        require(principal, repository, "read")
        try:
            return coordinator.state(repository)
        except CoordinatorError as exc:
            raise HTTPException(404, exc.code)

    @app.post("/v1/repositories/{repository}/commands")
    def command(repository: str, body: Command, principal: Principal = Depends(identity)):
        permission = "admin" if body.action == "revoke" else "write"
        require(principal, repository, permission)
        params = dict(body.params)
        params.pop("admin_authorized", None)
        if body.action == "revoke":
            params["admin_authorized"] = True
        try:
            return coordinator.command(repository, principal.identity,
                                       body.request_id, body.action, **params)
        except CoordinatorError as exc:
            raise HTTPException(409, exc.code)

    @app.get("/v1/repositories/{repository}/requests/{request_id}")
    def receipt(repository: str, request_id: str, principal: Principal = Depends(identity)):
        require(principal, repository, "read")
        result = coordinator.get_receipt(repository, principal.identity, request_id)
        if result is None:
            raise HTTPException(404, "NOT_FOUND")
        return result

    @app.post("/v1/repositories/{repository}/candidates")
    def candidate(repository: str, body: CandidateUpload, principal: Principal = Depends(identity)):
        require(principal, repository, "write")
        try:
            payload = bytes.fromhex(body.ciphertext_hex)
            store.put(repository, payload, body.sha256)
            # Hash verification alone is NOT SQLCipher integrity or signed identity validation.
            return {"status": "UPLOADED_UNVERIFIED", "candidate_id": body.candidate_id}
        except (CoordinatorError, ValueError) as exc:
            raise HTTPException(422, str(exc))


    class CandidateVerification(BaseModel):
        candidate_id: str
        manifest: dict
        signature: str

    @app.post("/v1/repositories/{repository}/candidates/verify")
    def verify_candidate(repository: str, body: CandidateVerification,
                         principal: Principal = Depends(identity)):
        require(principal, repository, "write")
        if candidate_verifier is None:
            raise HTTPException(503, "TRUSTED_VERIFIER_NOT_CONFIGURED")
        try:
            return candidate_verifier.verify_and_register(
                repository, principal.identity, body.candidate_id,
                body.manifest, body.signature
            )
        except CoordinatorError as exc:
            raise HTTPException(422, exc.code)

    return app
