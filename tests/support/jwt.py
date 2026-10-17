"""测试用的本地签发：生成 RSA 密钥、JWKS，并签发令牌。"""

import json
import time
import uuid
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://sso.test/realms/digital-workforce"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"


class LocalIssuer:
    def __init__(self, kid: str = "k1") -> None:
        self.kid = kid
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwks_requests = 0

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == JWKS_URL
            self.jwks_requests += 1
            return httpx.Response(200, json=self.jwks())

        return httpx.MockTransport(handler)

    def token(self, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "sub": "user-1-id",
            "azp": "contexture-bff",
            "aud": ["contexture-bff", "contexture-ai-gateway"],
            "exp": now + 300,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "preferred_username": "user1",
            "name": "User One",
            "realm_access": {"roles": ["business-user", "offline_access"]},
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": self.kid})
