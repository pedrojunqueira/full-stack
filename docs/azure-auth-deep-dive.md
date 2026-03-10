# Azure Authentication Deep Dive

A conceptual guide to understanding how OAuth2 Authorization Code Flow with PKCE works,
how Swagger UI and FastAPI integrate with Azure AD, and how the authentication code is
structured inside the application.

---

## Part 1: Authorization Code Flow with PKCE

### The Problem

A browser-based app (SPA, Swagger UI) needs to call a protected API on behalf of a user.
It needs an `access_token` to do this — but it cannot safely store a `client_secret`
because anything in the browser is visible to anyone with DevTools.

PKCE (Proof Key for Code Exchange) solves this. It allows a public client (no secret)
to prove it is the same entity that initiated the login, using a one-time cryptographic
commitment instead of a stored secret.

---

### Step-by-Step: What Actually Happens

#### Phase 1 — The PKCE Setup (before any network call)

The browser app generates two values locally, in memory, before doing anything:

```
code_verifier  = random high-entropy string (e.g. 64 random bytes, base64url-encoded)
code_challenge = BASE64URL( SHA256( code_verifier ) )
```

The `code_verifier` is kept secret in memory.
The `code_challenge` is a one-way hash — safe to send over the network.

---

#### Phase 2 — Authorization Request

The app redirects the user to Azure's login page, including the challenge:

```
GET https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize
  ?client_id=<swagger-app-id>
  &response_type=code
  &redirect_uri=http://localhost:8004/oauth2-redirect
  &scope=api://<api-app-id>/user_impersonation
  &code_challenge=<hashed value>
  &code_challenge_method=S256
```

Azure stores `code_challenge` and shows the login page.

---

#### Phase 3 — User Authenticates

The user enters their credentials. Azure validates them, then redirects back to the app:

```
http://localhost:8004/oauth2-redirect?code=<short-lived-auth-code>
```

The `auth_code` is short-lived (usually 10 minutes) and single-use.
It is useless on its own — it can only be exchanged by someone who has the `code_verifier`.

---

#### Phase 4 — Token Exchange

The app sends both the `auth_code` and the original `code_verifier` to Azure's token endpoint:

```
POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
  Content-Type: application/x-www-form-urlencoded

  grant_type=authorization_code
  &client_id=<swagger-app-id>
  &code=<auth-code>
  &redirect_uri=http://localhost:8004/oauth2-redirect
  &code_verifier=<original-secret>
```

Azure hashes `code_verifier` and checks:

```
SHA256(code_verifier) == stored code_challenge  ?
```

If yes — issues the `access_token` (JWT). If no — rejects the request.

The key insight: an attacker who intercepted the `auth_code` in Phase 3 cannot exchange
it because they never saw `code_verifier`. It was generated locally and only sent in
this final step.

---

#### Phase 5 — API Calls with Bearer Token

Every subsequent API call includes the token in the HTTP header:

```
GET /summaries/
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

The backend validates this token on every request.

---

#### The Full Flow as a Diagram

```
Browser App (Swagger UI)           Azure AD                  FastAPI Backend
        |                             |                              |
        | 1. generate                 |                              |
        |    code_verifier            |                              |
        |    code_challenge           |                              |
        |                             |                              |
        | 2. GET /authorize           |                              |
        |    ?code_challenge=...      |                              |
        | --------------------------> |                              |
        |                             |                              |
        |        3. user logs in      |                              |
        | <-------------------------- |                              |
        |    redirect with auth_code  |                              |
        |                             |                              |
        | 4. POST /token              |                              |
        |    { code, code_verifier }  |                              |
        | --------------------------> |                              |
        | <-------------------------- |                              |
        |    access_token (JWT)       |                              |
        |                             |                              |
        | 5. GET /summaries/          |                              |
        |    Authorization: Bearer .. | --------------------------> |
        |                             |                              |
        |                             |    6. validate JWT sig       |
        |                             |    against Azure JWKS keys   |
        |                             | <--------------------------- |
        |                             | --------------------------> |
        |                             |        valid  ✅            |
        | <------------------------------------------------------- 200 OK
```

---

### JWT Token Anatomy

The `access_token` is a JWT — three base64url-encoded sections separated by dots:

```
header.payload.signature
```

Your backend cares most about the payload claims:

```json
{
  "aud": "api://3ea0e8f4-...",          // who this token is for (must match your API)
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",  // who issued it
  "exp": 1772973948,                    // expiry (unix timestamp)
  "oid": "823961bd-...",               // user's unique object ID in Azure AD
  "preferred_username": "user@company.onmicrosoft.com",
  "name": "API Manager",
  "scp": "user_impersonation",          // granted scope
  "tid": "078c6c18-...",               // tenant ID
  "ver": "2.0"                          // token version (must be 2.0)
}
```

The signature is verified using Azure's public keys (JWKS endpoint). The backend
fetches these keys once at startup and caches them. No call to Azure is made per request.

---

## Part 2: Swagger UI + FastAPI — The Full Picture

### What Swagger UI Is Doing

Swagger UI is a Single-Page Application (SPA) — a public client. It uses the browser's
JavaScript engine to:

1. Run the PKCE setup (generate `code_verifier` and `code_challenge`)
2. Redirect to Azure's login page
3. Catch the redirect back with the `auth_code`
4. Exchange the code for a token
5. Store the token in memory (browser tab only — gone on refresh)
6. Attach the token as a `Bearer` header on every "Try it out" request

All of this behaviour is built into Swagger UI — you configure it, not implement it.

---

### What FastAPI Configures for Swagger

In `main.py`, two things tell Swagger UI how to behave:

```python
application = FastAPI(
    # tells Swagger where Azure will redirect after login
    swagger_ui_oauth2_redirect_url="/oauth2-redirect",

    # tells Swagger which OAuth2 flow to use and which client/scopes to request
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.openapi_client_id,        # the Swagger app registration
        "scopes": f"api://{settings.app_client_id}/user_impersonation",
    },
)
```

And the `azure_scheme` object (from `fastapi-azure-auth`) tells FastAPI's OpenAPI
generator to include the OAuth2 Authorization Code flow definition in the schema,
which is what causes the **Authorize** button to appear in Swagger UI.

---

### What FastAPI Does on Every Request

When a request arrives with a `Bearer` token:

1. The `azure_scheme` dependency intercepts it
2. Fetches Azure's public signing keys (cached from startup)
3. Verifies the JWT signature cryptographically
4. Checks claims: `aud` matches your API, `iss` matches your tenant, `exp` not expired
5. Returns the decoded token as a Python object
6. Your route handler receives a typed `CurrentUserSchema` with `email`, `name`, `oid`

If any step fails — wrong audience, expired token, bad signature — FastAPI returns
a `401` before your route code ever runs.

---

## Part 3: Why Two App Registrations?

### The Separation of Concerns

The two registrations represent fundamentally different actors in OAuth2:

| Registration | Role | OAuth2 term |
|---|---|---|
| `fastapi-tdd-api` | Defines what resources exist and who can access them | **Resource Server** |
| `fastapi-tdd-swagger` | An app that wants to access those resources | **Client** |

This is not an Azure-specific concept — it is core OAuth2 design.

---

### The API Registration — "The Resource"

The API registration does not represent any running application. It is a declaration:

- "These scopes exist: `user_impersonation`"
- "Tokens for this resource must have `aud: api://<my-id>`"
- "My token version is 2.0" (set via manifest `accessTokenAcceptedVersion: 2`)

The backend validates that incoming tokens were issued **for this specific resource**.
The `aud` claim in the JWT must match this registration's ID. A token issued for
Microsoft Graph or for a different API will be rejected even if it is cryptographically valid.

---

### The Swagger Registration — "A Client"

The Swagger registration represents Swagger UI as a client application:

- Has redirect URIs (where Azure sends users back after login)
- Is a public client — no secret, uses PKCE
- Has been granted permission to request the API's scopes
- Is identified by `clientId` in the token exchange (`azp` claim in the JWT)

---

### Why Not Combine Them?

You could technically use one registration for both. But separating them gives you
a critical architectural benefit: **multiple clients, one API**.

```
                        ┌─────────────────────────┐
                        │   fastapi-tdd-api        │
                        │   (API Registration)     │
                        │                          │
                        │   Scopes:                │
                        │   - user_impersonation   │
                        └────────────┬────────────┘
                                     │  aud claim must match
                    ┌────────────────┼────────────────┐
                    │                │                 │
          ┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
          │ fastapi-tdd-   │ │ react-spa    │ │ mobile-app   │
          │ swagger        │ │ (future)     │ │ (future)     │
          │ (Client)       │ │ (Client)     │ │ (Client)     │
          └────────────────┘ └──────────────┘ └──────────────┘
```

Each client:
- Has its own registration with its own redirect URIs
- Can be revoked independently (if the Swagger client is compromised, revoke it — the
  React app keeps working)
- Can be granted different scopes (mobile app might only get read access)
- Can be tracked independently in Azure AD sign-in logs

The backend (API registration) never changes. Clients come and go.

---

### What the JWT Tells You

The token carries both identities:

```json
{
  "aud": "api://3ea0e8f4-...",       ← API registration (who the token is FOR)
  "azp": "125d3bbe-...",             ← Client registration (who REQUESTED it)
  "scp": "user_impersonation",       ← scope granted by the API registration
  "oid": "823961bd-...",             ← the user who authenticated
  "tid": "078c6c18-..."              ← the tenant
}
```

Your backend checks `aud`. It doesn't need to know which client was used — that is
Azure's concern. You just know the token was legitimately issued for your API.

---

## Part 4: FastAPI Code Structure Deep Dive

### The Three Files and Their Roles

```
app/
├── azure.py     ← configures the security scheme (one object, two jobs)
├── auth.py      ← dependency chain that turns a raw token into a user object
└── api/
    └── summaries.py  ← routes that declare what they need via Depends/Security
```

---

### azure.py — The Security Scheme Object

```python
azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=settings.app_client_id,
    tenant_id=settings.tenant_id,
    scopes={
        f"api://{settings.app_client_id}/user_impersonation": "user_impersonation",
    },
    allow_guest_users=True,
)
```

This single object has **two completely separate jobs**:

**Job 1 — Swagger UI configuration**

When passed to `FastAPI(swagger_ui_init_oauth=...)`, it instructs Swagger UI which
OAuth2 flow to offer, which scopes to request, and where to redirect. This is a
front-end concern — it configures the browser.

**Job 2 — JWT validation on every request**

When used as `Security(azure_scheme)` in a dependency, it intercepts incoming requests,
extracts the `Bearer` token, validates the JWT cryptographically, and returns the
decoded payload. This is a back-end concern — it protects routes.

Same object. Two jobs. Neither knows about the other.

---

### auth.py — The Dependency Chain

The three functions in `auth.py` form a pipeline that transforms a raw HTTP request
into a clean Python object your routes can use:

```
HTTP Request (Bearer token)
        │
        ▼
┌───────────────────────┐
│   get_azure_user()    │  ← calls Security(azure_scheme)
│                       │    validates JWT, returns raw token object
│   scope="function"    │    with a .claims dict
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│  parse_azure_claims() │  ← extracts email, oid, name, roles
│                       │    from the raw .claims dict
│  AzureUserClaims      │    handles Azure's inconsistent claim names
└──────────┬────────────┘
           │
           ▼
┌───────────────────────┐
│  get_current_user()   │  ← validates claims are present
│                       │    returns clean CurrentUserSchema
│  CurrentUserSchema    │    (email, azure_oid, name)
└──────────┬────────────┘
           │
           ▼
   Your route handler
   receives typed user object
```

Each function has one job. The chain is composable — you can stop at any level.
A route that only needs the raw token can depend on `get_azure_user`. A route that
needs the full user profile depends on `get_current_user`.

---

### Why `get_azure_user` Exists as a Wrapper

```python
async def get_azure_user(
    azure_user: Annotated[object, Security(azure_scheme)],
) -> object:
    return azure_user
```

This looks like it does nothing — and at runtime, it almost does. Its purpose is
**testability**.

In tests, you override this single function to bypass all of Azure:

```python
app.dependency_overrides[get_azure_user] = lambda: get_mock_azure_user()
```

This one line makes every protected route work in tests without a real Azure tenant,
real credentials, or network calls. If `Security(azure_scheme)` were declared inline
in every route, you would have nothing to override — you would need to mock Azure's
entire JWKS infrastructure.

---

### `Depends` vs `Security` — Why Both Exist

Both resolve dependencies the same way at runtime. The difference is metadata:

```python
# Security — marks this as an auth requirement in the OpenAPI schema
azure_user: Annotated[object, Security(azure_scheme)]

# Depends — just a regular dependency, no OpenAPI significance
azure_user: Annotated[object, Depends(get_azure_user)]
```

When FastAPI builds the OpenAPI schema, it walks the **entire dependency tree** of
every route and looks for `Security()` calls. When it finds one, it marks that route
as requiring authentication — which is what causes the lock icon to appear in Swagger UI
and the route to be listed under the security requirement in the OpenAPI spec.

`Security` is used exactly once — at the point where the raw security scheme is
invoked. Everything else in the chain uses `Depends`.

---

### How `Annotated` Ties It Together

```python
current_user: Annotated[CurrentUserSchema, Depends(get_current_user)]
```

This is standard Python typing (`typing.Annotated`) with three parts:

| Part | Meaning |
|---|---|
| `current_user` | variable name in your function |
| `CurrentUserSchema` | the type you will receive |
| `Depends(get_current_user)` | how FastAPI should produce that value |

FastAPI reads the `Depends(...)` metadata and resolves the full chain before calling
your function. You declare what you need; FastAPI figures out how to get it.

---

### The Full Dependency Resolution on a Request

Take a protected route:

```python
@router.get("/summaries/")
async def read_all_summaries(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    return {"user": current_user.email}
```

When `GET /summaries/` is called, FastAPI resolves this tree before your function runs:

```
Depends(get_current_user)
  └── Depends(get_azure_user)
        └── Security(azure_scheme)
              └── HTTP request: extract "Authorization: Bearer <token>"
                    └── validate JWT signature against Azure JWKS
                    └── check aud, iss, exp claims
                    └── return raw token object
              ← raw token object
        ← raw token object (get_azure_user just passes it through)
  └── parse_azure_claims(raw token)
        └── extract email, oid, name, roles from .claims dict
  └── validate claims present, raise 401 if missing
  ← CurrentUserSchema(email=..., oid=..., name=...)
← your route receives current_user
```

If anything fails at any level — invalid token, missing claims, expired JWT — FastAPI
short-circuits and returns the appropriate HTTP error. Your route code never runs.

---

### The Lock Icon — How it Propagates

The Swagger UI lock icon appears on a route because FastAPI found `Security(azure_scheme)`
**anywhere** in that route's dependency tree — not just at the top level.

```
summaries router
    └── Depends(get_current_user)         ← no Security here
          └── Depends(get_azure_user)     ← no Security here either
                └── Security(azure_scheme)  ← FastAPI finds this
                                             → marks the route as protected
                                             → lock icon appears
```

This means you declare `Security` once, deep in a shared dependency, and every route
that uses `get_current_user` (or any function in the chain) automatically gets the
lock icon and OpenAPI security annotation. No repetition needed.

---

### Summary

```
Azure AD                  FastAPI App                      Developer Experience
─────────────────────     ────────────────────────────     ────────────────────
API Registration      →   azure_scheme validates tokens    One object, two jobs
  defines scopes          azure_scheme configures Swagger

Swagger Registration  →   swagger_ui_init_oauth config     Authorize button
  public client (PKCE)    swagger_ui_oauth2_redirect_url   in Swagger UI

JWT access_token      →   Security(azure_scheme)           Automatic on every
  signed by Azure         verifies signature + claims      request, no boilerplate

Decoded claims        →   get_azure_user()                 Single override point
  oid, email, name        get_current_user()               for testing
                          CurrentUserSchema

Protected routes      →   Depends(get_current_user)        Lock icon in Swagger
                          Security deep in the tree        401 on invalid token
```
