#!/usr/bin/env python3
"""Generate a test JWT signed with HS256 using a shared secret.

Usage:
  python3 scripts/generate_test_jwt.py --secret <secret> --tenant_id <tenant> --user_id <user> --role <role> [--exp_seconds <seconds>]

If --secret is not provided, the script will read the environment variable SECRET.
"""
import argparse
import base64
import json
import hmac
import hashlib
import time
from typing import Dict


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def sign_jwt(header_b64: str, payload_b64: str, secret: str) -> str:
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return b64url_encode(signature)


def build_jwt(secret: str, tenant_id: str, user_id: str, role: str, exp_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    iat = int(time.time())
    payload: Dict[str, object] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "iat": iat,
        "exp": iat + exp_seconds,
    }

    header_json = json.dumps(header, separators=(",", ":"))
    payload_json = json.dumps(payload, separators=(",", ":"))
    header_b64 = b64url_encode(header_json.encode("utf-8"))
    payload_b64 = b64url_encode(payload_json.encode("utf-8"))

    signature = sign_jwt(header_b64, payload_b64, secret)
    return f"{header_b64}.{payload_b64}.{signature}"


def main():
    parser = argparse.ArgumentParser(description="Generate test JWT (HS256) for chatbot auth")
    parser.add_argument("--secret", help="Shared JWT secret; if omitted, reads SECRET env var")
    parser.add_argument("--tenant_id", required=True)
    parser.add_argument("--user_id", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--exp_seconds", type=int, default=3600, help="Token expiry in seconds (default 3600)")
    args = parser.parse_args()

    secret = args.secret or __import__('os').environ.get('SECRET')
    if not secret:
        print("ERROR: secret not provided and SECRET env var not set.")
        exit(2)

    jwt = build_jwt(secret, args.tenant_id, args.user_id, args.role, args.exp_seconds)
    print(jwt)


if __name__ == "__main__":
    main()
