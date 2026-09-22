#!/usr/bin/env bash
# Template: exchange a ZITADEL service-account key for an access token (private key JWT).
#
# This is a TEMPLATE, not a finished script: it must be adapted to your machine.
# Marked spots (# ADAPT) differ per environment — see the notes at the bottom.
#
# What it does: builds a signed JWT assertion and POSTs it to the token endpoint
# of your ZITADEL instance, then prints the access token.
#
# Required environment variables:
#   ZITADEL_DOMAIN         the instance domain that is the OIDC issuer, e.g. id.example.com (no scheme)
#   ZITADEL_USER_ID        user id of the service account (the JWT "iss" and "sub")
#   ZITADEL_KEY_ID         key id of the registered public key (the JWT "kid")
#   ZITADEL_KEY_FILE       path to the private key file (PEM, as downloaded when the key was created)
# Optional:
#   SCOPE                  defaults to "openid urn:zitadel:iam:org:project:id:zitadel:aud"
#   TTL                    assertion lifetime in seconds, defaults to 300
#   DRY_RUN=1              print the assertion instead of calling the token endpoint
#
# Dependencies: openssl (signing), base64/date (coreutils), curl.

set -euo pipefail

: "${ZITADEL_DOMAIN:?set ZITADEL_DOMAIN (issuer host, no scheme)}"
: "${ZITADEL_USER_ID:?set ZITADEL_USER_ID (service account user id)}"
: "${ZITADEL_KEY_ID:?set ZITADEL_KEY_ID (key id of the registered public key)}"
: "${ZITADEL_KEY_FILE:?set ZITADEL_KEY_FILE (path to the PEM private key)}"
SCOPE="${SCOPE:-openid urn:zitadel:iam:org:project:id:zitadel:aud}"
TTL="${TTL:-300}"

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

iat=$(date +%s)
exp=$((iat + TTL))

header=$(printf '{"alg":"RS256","kid":"%s"}' "$ZITADEL_KEY_ID" | b64url)
payload=$(printf '{"iss":"%s","sub":"%s","aud":"https://%s","iat":%d,"exp":%d}' \
  "$ZITADEL_USER_ID" "$ZITADEL_USER_ID" "$ZITADEL_DOMAIN" "$iat" "$exp" | b64url)
signing_input="$header.$payload"

# ADAPT: some openssl builds need -sha256 with `dgst`; older ones accept only sha256.
signature=$(printf '%s' "$signing_input" | openssl dgst -sha256 -sign "$ZITADEL_KEY_FILE" | b64url)
assertion="$signing_input.$signature"

if [ "${DRY_RUN:-0}" = "1" ]; then
  printf '%s\n' "$assertion"
  exit 0
fi

# ADAPT: add -k only if the instance uses a certificate your machine does not trust.
curl -sS -X POST "https://$ZITADEL_DOMAIN/oauth/v2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer" \
  --data-urlencode "assertion=$assertion" \
  --data-urlencode "scope=$SCOPE"
# The response is JSON: {"access_token":"...","token_type":"Bearer","expires_in":...,"scope":"..."}
# Print it raw so the caller can pipe it into a JSON parser instead of guessing at the shape.

# --- Environment notes (why the marked spots exist) -------------------------
# * openssl: the signing step requires the openssl CLI. If your machine has no
#   openssl, sign with the language SDK instead (Go/Node/Python crypto libs) —
#   the assertion layout above is what has to be produced, not the command.
# * Key file format: ZITADEL gives an application/service-account key either as a
#   JSON document ({"keyId":..., "key":..., "userId":...}) or as the PEM inside it.
#   Extract the PEM yourself and pass its path; do not paste the key into a repo.
# * Time: iat/exp are Unix seconds. A skewed clock produces a rejected assertion
#   ("Errors.Token.Invalid"), which looks like a bad key but is not.
# * The audience (aud) is the issuer URL, i.e. https://<domain>. It must match the
#   issuer in the instance's discovery document, otherwise the assertion is refused.
