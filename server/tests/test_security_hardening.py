"""Server hardening after the security review of 2026-11-10: fail-closed
JWT secret and DEV_AUTH off by default, proxy-aware client address (rate
limiter + registration velocity), SSRF guard on the AI proxy, Secure refresh
cookie, session revocation on credential change, constant-work login, size
limits on free text, fail-closed email defaults, and scripts without
laptop-specific defaults."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from starlette.requests import Request

from app import deps, ratelimit
from app import email as email_service
from app.models import User
from app.routers import ai as ai_module
from app.routers import auth as auth_module
from tests.conftest import register_payload
from tests.test_night3 import (
    PASSWORD,
    REFRESH_COOKIE,
    _bearer,
    _cookie_refresh,
    _create_concept,
    _login,
    _register,
)

SERVER_DIR = Path(__file__).resolve().parent.parent
PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700::6810:84e5"


def _request(headers: dict[str, str] | None = None, client=("10.0.0.7", 4242)) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": raw, "client": client}
    )


# --------------------------------------------------------------------------
# 3.1 — DEV_AUTH off by default, JWT_SECRET fail-closed, decode never 500s
# --------------------------------------------------------------------------


def test_dev_auth_is_off_unless_explicitly_on(monkeypatch):
    monkeypatch.delenv("DEV_AUTH", raising=False)
    assert deps.dev_auth_enabled() is False
    monkeypatch.setenv("DEV_AUTH", "0")
    assert deps.dev_auth_enabled() is False
    monkeypatch.setenv("DEV_AUTH", "1")
    assert deps.dev_auth_enabled() is True


@pytest.mark.parametrize(
    "secret",
    [deps.DEV_JWT_SECRET, "", "kort-hemlighet", "x" * (deps.MIN_JWT_SECRET_LENGTH - 1)],
)
def test_startup_refuses_weak_jwt_secret_when_dev_auth_is_off(monkeypatch, secret):
    monkeypatch.setenv("DEV_AUTH", "0")
    monkeypatch.setattr(deps, "JWT_SECRET", secret)
    with pytest.raises(SystemExit, match="JWT_SECRET must be set to a strong value"):
        deps.require_strong_jwt_secret()


def test_startup_accepts_strong_secret_and_tolerates_dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_AUTH", "0")
    monkeypatch.setattr(deps, "JWT_SECRET", "a" * deps.MIN_JWT_SECRET_LENGTH)
    deps.require_strong_jwt_secret()  # no raise
    # Local development: the dev secret is fine while the X-User fallback is on.
    monkeypatch.setenv("DEV_AUTH", "1")
    monkeypatch.setattr(deps, "JWT_SECRET", deps.DEV_JWT_SECRET)
    deps.require_strong_jwt_secret()


def test_entrypoint_script_applies_the_same_check():
    """The shell gate in docker-entrypoint.sh mirrors require_strong_jwt_secret
    so a misconfigured container dies before migrations run."""
    script = SERVER_DIR / "scripts" / "docker-entrypoint.sh"
    # Lift the gate out of the script: everything before `cd /app`.
    gate = script.read_text().split("cd /app", 1)[0]
    base_env = {k: v for k, v in os.environ.items() if k not in ("DEV_AUTH", "JWT_SECRET")}

    def run(**env):
        return subprocess.run(
            ["sh", "-c", gate + "\necho passed"],
            env={**base_env, **env},
            capture_output=True,
            text=True,
        )

    assert run().returncode == 1  # DEV_AUTH unset → off → secret required
    assert run(DEV_AUTH="0", JWT_SECRET=deps.DEV_JWT_SECRET).returncode == 1
    assert run(DEV_AUTH="0", JWT_SECRET="kort").returncode == 1
    assert "JWT_SECRET must be set" in run(DEV_AUTH="0", JWT_SECRET="kort").stderr
    assert run(DEV_AUTH="0", JWT_SECRET="b" * 40).stdout.strip() == "passed"
    assert run(DEV_AUTH="1").stdout.strip() == "passed"


def test_decode_token_degrades_every_failure_to_anonymous(client, monkeypatch):
    assert deps.decode_token("inte.en.token") is None
    assert deps.decode_token("!!!.@@@.###") is None
    assert deps.decode_token("") is None
    # A library raising something other than PyJWTError (PYSEC-2026-4142 on
    # older PyJWT) is swallowed too — never a 500 for a Bearer header.
    monkeypatch.setattr(deps.jwt, "decode", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError()))
    assert deps.decode_token("x.y.z") is None
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer x.y.z"}).status_code == 401
    )


# --------------------------------------------------------------------------
# 3.2 — client address behind the proxy chain
# --------------------------------------------------------------------------


def test_client_ip_uses_last_forwarded_hop_then_socket_peer():
    assert ratelimit.client_ip(_request()) == "10.0.0.7"
    assert ratelimit.client_ip(_request(client=None)) == "unknown"
    assert ratelimit.client_ip(_request({"X-Forwarded-For": "203.0.113.5"})) == "203.0.113.5"
    # The first value is whatever the client typed; the last is the proxy's.
    forged = _request({"X-Forwarded-For": "1.1.1.1, 203.0.113.5 , 198.51.100.9"})
    assert ratelimit.client_ip(forged) == "198.51.100.9"
    assert ratelimit.client_ip(_request({"X-Forwarded-For": " , "})) == "10.0.0.7"


def test_rate_limit_buckets_are_separate_per_forwarded_ip(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_AUTH", "2")
    ratelimit.reset()
    first = {"X-Forwarded-For": "198.51.100.1"}
    second = {"X-Forwarded-For": "198.51.100.2"}
    assert client.get("/api/v1/auth/challenge", headers=first).status_code == 200
    assert client.get("/api/v1/auth/challenge", headers=first).status_code == 200
    blocked = client.get("/api/v1/auth/challenge", headers=first)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # Another client behind the same proxy is unaffected …
    assert client.get("/api/v1/auth/challenge", headers=second).status_code == 200
    # … and a client prepending its own value cannot escape its bucket: the
    # proxy-appended LAST value is what counts.
    spoofed = {"X-Forwarded-For": "9.9.9.9, 198.51.100.1"}
    assert client.get("/api/v1/auth/challenge", headers=spoofed).status_code == 429
    ratelimit.reset()


def test_registration_velocity_keys_on_last_forwarded_ip(client, monkeypatch):
    monkeypatch.setenv("REG_VELOCITY_LIMIT", "2")

    def register(handle, forwarded):
        body = register_payload(
            client, email=f"{handle}@example.org", display_name=handle.title(), password=PASSWORD
        )
        resp = client.post(
            "/api/v1/auth/register", json=body, headers={"X-Forwarded-For": forwarded}
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["user"]["review_status"]

    assert register("root", "198.51.100.1") == "approved"  # bootstrap account
    assert register("anna", "198.51.100.2") == "approved"  # first from this source
    # Second from the same proxy-reported source → flagged, even though the
    # registrant prepended a fresh-looking address.
    assert register("bertil", "7.7.7.7, 198.51.100.2") == "pending"
    # A genuinely new source (last hop) is fine.
    assert register("cesar", "198.51.100.2, 198.51.100.3") == "approved"


# --------------------------------------------------------------------------
# 3.7 — SSRF guard on X-LLM-Base-URL; 3.5 — writable account required
# --------------------------------------------------------------------------


def _fake_resolver(table: dict[str, list[str]]):
    calls: list[str] = []

    def getaddrinfo(host, port, *args, **kwargs):
        calls.append(host)
        if host not in table:
            raise socket.gaierror(-2, "Name or service not known")
        return [(2, 1, 6, "", (address, port)) for address in table[host]]

    return getaddrinfo, calls


def test_base_url_accepts_public_https_host(monkeypatch):
    fake, calls = _fake_resolver({"api.openai.example": [PUBLIC_V4, PUBLIC_V6]})
    monkeypatch.setattr(ai_module.socket, "getaddrinfo", fake)
    assert (
        ai_module.validate_base_url(" https://api.openai.example/v1/ ")
        == "https://api.openai.example/v1/"
    )
    assert calls == ["api.openai.example"]


@pytest.mark.parametrize(
    "url",
    [
        "http://api.openai.example/v1",  # plain http
        "https://10.0.0.1/v1",  # IP literal
        "https://[::1]/v1",  # IPv6 literal
        "https://localhost/v1",
        "https://llm.localhost/v1",
        "https://server:8088/api/v1",  # container name → private address
        "https://traefik.internal/api",
        "https://printer.local/",
        "https://user:pw@api.openai.example/v1",  # credentials in the URL
        "https://cdn.mixed.example/v1",  # one private address among public ones
        "https://finns-inte.example/v1",  # does not resolve
        "https://api.openai.example:port/v1",  # malformed port
        "ftp://api.openai.example/v1",
        "not a url",
        "",
    ],
)
def test_base_url_rejects_internal_and_non_https_targets(monkeypatch, url):
    fake, _calls = _fake_resolver(
        {
            "api.openai.example": [PUBLIC_V4],
            "server": ["172.18.0.5"],
            "traefik.internal": [PUBLIC_V4],
            "printer.local": [PUBLIC_V4],
            "llm.localhost": [PUBLIC_V4],
            "cdn.mixed.example": [PUBLIC_V4, "192.168.1.20"],
        }
    )
    monkeypatch.setattr(ai_module.socket, "getaddrinfo", fake)
    with pytest.raises(Exception) as excinfo:
        ai_module.validate_base_url(url)
    detail = excinfo.value.detail
    assert excinfo.value.status_code == 400
    assert detail["code"] == "ai_base_url_rejected"
    assert "http_status" not in detail.get("params", {})


def test_ai_proxy_rejects_internal_base_url_before_any_request(client, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("the provider must not be contacted for a rejected base URL")

    monkeypatch.setattr(ai_module.httpx, "post", never)
    fake, _ = _fake_resolver({"server": ["172.18.0.5"]})
    monkeypatch.setattr(ai_module.socket, "getaddrinfo", fake)
    resp = client.post(
        "/api/v1/ai/extract",
        json={"text": "zon: ett område."},
        headers={
            "X-LLM-Key": "sk-test",
            "X-LLM-Provider": "openai",
            "X-LLM-Base-URL": "https://server:8088/api/v1",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "ai_base_url_rejected"
    # Anthropic ignores the header entirely — no resolution, no rejection.
    monkeypatch.setattr(ai_module.httpx, "post", lambda *a, **kw: _anthropic_rows())
    ok = client.post(
        "/api/v1/ai/extract",
        json={"text": "zon: ett område."},
        headers={"X-LLM-Key": "sk-test", "X-LLM-Base-URL": "http://server:8088"},
    )
    assert ok.status_code == 200


def _anthropic_rows():
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {"type": "text", "text": '[{"canonical_form": "zon", "definition": "d"}]'}
                ]
            }

    return FakeResponse()


def test_ai_endpoints_require_a_writable_account(client, db, collection, monkeypatch):
    db.add(User(handle="vantande", display_name="Väntande", review_status="pending"))
    db.commit()
    monkeypatch.setattr(ai_module.httpx, "post", lambda *a, **kw: _anthropic_rows())
    headers = {"X-User": "vantande", "X-LLM-Key": "sk-test"}
    denied = client.post("/api/v1/ai/extract", json={"text": "zon: ett område."}, headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "account_pending_review"
    concept = _create_concept(client, collection.id).json()
    denied = client.post(
        "/api/v1/ai/draft",
        json={"intent": "synthesize", "version_ids": [concept["head"]["id"]]},
        headers=headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "account_pending_review"
    # An approved account still gets through to the (mocked) provider.
    ok = client.post(
        "/api/v1/ai/extract", json={"text": "zon: ett område."}, headers={"X-LLM-Key": "sk-test"}
    )
    assert ok.status_code == 200


# --------------------------------------------------------------------------
# 3.1 — cookie, sessions, constant-work login
# --------------------------------------------------------------------------


def test_refresh_cookie_is_secure_outside_dev_mode(client, monkeypatch):
    monkeypatch.setenv("DEV_AUTH", "0")
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client, email="anna@example.org", display_name="Anna", password=PASSWORD
        ),
    )
    assert resp.status_code == 201
    assert "secure" in resp.headers.get("set-cookie", "").lower()
    monkeypatch.setenv("DEV_AUTH", "1")
    login = _login(client, "anna")
    assert login.status_code == 200
    assert "secure" not in login.headers.get("set-cookie", "").lower()


def _two_sessions(client):
    """Register (session A) and log in again (session B, the browser doing
    the change). Returns (auth of B, raw_a, raw_b)."""
    _register(client, "anna")
    raw_a = client.cookies.get(REFRESH_COOKIE)
    login = _login(client, "anna")
    assert login.status_code == 200
    raw_b = client.cookies.get(REFRESH_COOKIE)
    assert raw_a and raw_b and raw_a != raw_b
    return login.json(), raw_a, raw_b


def test_password_change_revokes_other_sessions_but_keeps_the_current(client):
    auth, raw_a, raw_b = _two_sessions(client)
    ok = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "nytt-losenord-12"},
        headers=_bearer(auth),
    )
    assert ok.status_code == 204
    assert _cookie_refresh(client, raw_a).status_code == 401  # the other device
    assert _cookie_refresh(client, raw_b).status_code == 200  # the browser that changed it


def test_email_change_revokes_other_sessions_only_when_the_address_changes(client):
    auth, raw_a, raw_b = _two_sessions(client)
    # Same address (re-send verification): nothing is revoked.
    same = client.post(
        "/api/v1/auth/email", json={"email": "anna@example.org"}, headers=_bearer(auth)
    )
    assert same.status_code == 204
    assert _cookie_refresh(client, raw_a).status_code == 200
    # That refresh rotated A and put the new value in the jar: the browser
    # that performs the next change is now session A'.
    raw_a = client.cookies.get(REFRESH_COOKIE)
    assert raw_a != raw_b
    # A new address: the other session (B) is out, the acting one (A') stays.
    changed = client.post(
        "/api/v1/auth/email", json={"email": "anna.ny@example.org"}, headers=_bearer(auth)
    )
    assert changed.status_code == 204
    assert _cookie_refresh(client, raw_b).status_code == 401
    assert _cookie_refresh(client, raw_a).status_code == 200


def test_login_verifies_a_hash_for_unknown_and_passwordless_accounts(client, db, monkeypatch):
    """No early 401: every attempt pays one argon2 verification, so timing
    does not reveal whether an identifier exists or is an unclaimed import."""

    class CountingHasher:
        def __init__(self, inner):
            self.inner, self.calls = inner, 0

        def verify(self, hash_, password):
            self.calls += 1
            return self.inner.verify(hash_, password)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    counting = CountingHasher(auth_module._hasher)
    monkeypatch.setattr(auth_module, "_hasher", counting)
    db.add(User(handle="oansprakad", display_name="Oanspråkad"))  # imported, no password
    db.commit()

    assert _login(client, "finns-inte", "vad-som-helst").status_code == 401
    assert counting.calls == 1
    assert _login(client, "oansprakad", "vad-som-helst").status_code == 401
    assert counting.calls == 2
    # The dummy hash can never be a way in.
    assert _login(client, "oansprakad", auth_module._DUMMY_HASH).status_code == 401


# --------------------------------------------------------------------------
# 3.4 — max lengths on free text
# --------------------------------------------------------------------------


def test_free_text_limits_on_concept_and_version_writes(client, collection):
    from app import schemas

    def create(**fields):
        return _create_concept(client, collection.id, **fields)

    assert create(form="x" * schemas.CANONICAL_FORM_MAX).status_code == 201
    assert create(form="x" * (schemas.CANONICAL_FORM_MAX + 1)).status_code == 422
    assert create(form="def-ok", definition_md="d" * schemas.DEFINITION_MAX).status_code == 201
    assert (
        create(form="def-lång", definition_md="d" * (schemas.DEFINITION_MAX + 1)).status_code
        == 422
    )
    assert create(form="note-lång", note="n" * (schemas.NOTE_MAX + 1)).status_code == 422
    assert (
        create(form="tags-ok", tags=[f"t{i}" for i in range(schemas.TAGS_MAX)]).status_code == 201
    )
    assert create(form="tags-många", tags=["t"] * (schemas.TAGS_MAX + 1)).status_code == 422
    assert create(form="tag-lång", tags=["t" * (schemas.TAG_MAX + 1)]).status_code == 422

    concept = create(form="gren").json()
    version = {
        "mode": "branch",
        "base_version_id": concept["head"]["id"],
        "canonical_form": "gren",
        "definition_md": "Ny text.",
    }
    url = f"/api/v1/concepts/{concept['id']}/versions"
    too_long = client.post(
        url, json={**version, "branch_name": "b" * (schemas.BRANCH_NAME_MAX + 1)}
    )
    assert too_long.status_code == 422
    assert (
        client.post(
            url, json={**version, "branch_name": "b" * schemas.BRANCH_NAME_MAX}
        ).status_code
        == 201
    )


def test_description_and_resolution_limits(client):
    from app import schemas

    root = _register(client, "root")
    too_long = client.post(
        "/api/v1/collections",
        json={"slug": "lang", "name": "Lång", "description": "d" * (schemas.DESCRIPTION_MAX + 1)},
        headers=_bearer(root),
    )
    assert too_long.status_code == 422
    ok = client.post(
        "/api/v1/collections",
        json={"slug": "lagom", "name": "Lagom", "description": "d" * schemas.DESCRIPTION_MAX},
        headers=_bearer(root),
    )
    assert ok.status_code == 201


# --------------------------------------------------------------------------
# 3.8 — email defaults fail closed
# --------------------------------------------------------------------------


def test_email_without_smtp_is_outbox_regardless_of_allowlist(db, monkeypatch):
    monkeypatch.delenv("SMTP_URL", raising=False)
    monkeypatch.delenv("EMAIL_ALLOWLIST", raising=False)
    stored = email_service.send(
        db, to_addr="x@example.org", subject="s", body_text="b", template="t"
    )
    assert stored.status == "outbox"
    assert email_service.allowlist() == set()  # no built-in address anywhere
    assert email_service.recipient_allowed("x@example.org") is False


def test_email_without_sender_stays_queued_and_never_sends(db, monkeypatch, caplog):
    calls: list[dict] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda **kw: calls.append(kw))
    monkeypatch.setenv("SMTP_URL", "smtp://mail.example.org:587")  # no user name
    monkeypatch.setenv("EMAIL_ALLOWLIST", "*")
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    with caplog.at_level("WARNING", logger="kollepedia.email"):
        queued = email_service.send(
            db, to_addr="x@example.org", subject="s", body_text="b", template="t"
        )
    assert queued.status == "queued"
    assert calls == []
    assert "No sender address" in caplog.text
    # EMAIL_FROM wins over the SMTP user name; the user name is the fallback.
    monkeypatch.setenv("EMAIL_FROM", "noreply@example.org")
    sent = email_service.send(
        db, to_addr="x@example.org", subject="s", body_text="b", template="t"
    )
    assert sent.status == "sent"
    assert calls[-1]["from_addr"] == "noreply@example.org"
    assert (
        email_service.sender_address("smtp://relay%40example.org:pw@h:587")
        == "noreply@example.org"
    )
    monkeypatch.delenv("EMAIL_FROM")
    assert (
        email_service.sender_address("smtp://relay%40example.org:pw@h:587") == "relay@example.org"
    )
    assert email_service.sender_address("smtp://h:587") is None


# --------------------------------------------------------------------------
# 2.2 — scripts carry no laptop-specific defaults
# --------------------------------------------------------------------------


def _run_script(name: str, *args: str, tmp_path: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "PROTOTYPE_DB"}
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'tom.db'}"
    return subprocess.run(
        [sys.executable, str(SERVER_DIR / "scripts" / name), *args],
        cwd=SERVER_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_prototype_scripts_refuse_to_guess_the_source_database(tmp_path):
    legacy = _run_script("migrate_006_legacy_ids.py", tmp_path=tmp_path)
    assert legacy.returncode == 1 and "PROTOTYPE_DB" in legacy.stderr
    proto = _run_script("migrate_from_prototype.py", tmp_path=tmp_path)
    assert proto.returncode == 1 and "PROTOTYPE_DB" in proto.stderr
    incremental = _run_script("import_v1_collections_incremental.py", tmp_path=tmp_path)
    assert incremental.returncode == 2 and "--old-db" in incremental.stderr


def test_migration_007_requires_an_explicit_old_database(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_007", SERVER_DIR / "scripts" / "migrate_007_collection_details.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not hasattr(module, "DEFAULT_OLD_DB")
    with pytest.raises(SystemExit, match="Old database path required"):
        module.migrate(tmp_path / "ng.db", None)


def test_seed_script_uses_reserved_addresses_and_a_clearly_local_password():
    text = (SERVER_DIR / "scripts" / "seed_local_orgs.py").read_text()
    assert "linderagroup.com" not in text and "lindera.se" not in text
    assert "@example.org" in text
    assert "kollepedia-dev" not in text
    assert "lokal-utveckling-byt-mig" in text
