# API Conventions

All endpoints under `/api/v1` follow the conventions documented below.

---

## 1. Authentication Header Format

The API uses stateless JWT Bearer authentication (`HS256`):

```http
Authorization: Bearer <access_token>
```

- **Access tokens**: short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, default `15` minutes), contain `sub` (user ID), `role`, `type: "access"`, `jti`, `iat`, `exp`.
- **Refresh tokens**: longer-lived (`REFRESH_TOKEN_EXPIRE_DAYS`, default `7` days), contain `type: "refresh"`, accepted exclusively by `POST /api/v1/auth/refresh`.
- Public registration (`POST /api/v1/auth/register`) **always** assigns `role = "student"` server-side.

---

## 2. Standard Error Envelope

Every error response (`400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`) uses one consistent JSON shape and never leaks stack traces:

```json
{
  "error": {
    "code": "COURSE_NOT_FOUND",
    "message": "Course not found",
    "details": {}
  }
}
```

For `422` validation errors, `details.fields` lists each invalid field:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "fields": [
        {
          "field": "body.password",
          "message": "Value error, Password must include at least one uppercase letter",
          "type": "value_error"
        }
      ]
    }
  }
}
```

---

## 3. HTTP Status Codes

| Status | Meaning |
|---|---|
| `200 OK` | Successful read, update, login, refresh, publish/unpublish/archive, reorder |
| `201 Created` | Resource created (register, course, module, lesson, enrollment, lesson completion) |
| `204 No Content` | Successful deletion or unenrollment / unmark completion |
| `400 Bad Request` | Invalid state transition or business rule violation (e.g. enroll in draft course, invalid reorder IDs, admin self-deactivation) |
| `401 Unauthorized` | Missing, malformed, wrong-type, or expired JWT, or invalid login credentials |
| `403 Forbidden` | Authenticated user lacks required role, ownership, enrollment, or account is deactivated |
| `404 Not Found` | Resource does not exist (or draft course hidden from non-owners) |
| `409 Conflict` | Uniqueness conflict (duplicate email, duplicate slug, already enrolled, already completed) |
| `422 Unprocessable Content` | Schema or query parameter validation failure |
| `429 Too Many Requests` | Rate limit exceeded on auth endpoints (includes `Retry-After` header) |

---

## 4. Pagination Format

Every list endpoint accepts:

- `page` (integer, `>= 1`, default `1`)
- `per_page` (integer, `1..100`, default `20`)

Responses follow:

```json
{
  "items": [],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## 5. Roles & Permission Matrix

| Capability | Public | Student | Instructor (Owner) | Instructor (Other) | Admin |
|---|---|---|---|---|---|
| Browse published courses | Yes | Yes | Yes | Yes | Yes |
| View draft/archived course | No | No | Yes | No | Yes |
| Create course | No | No | Yes | Yes | Yes |
| Edit/publish/delete course, modules, lessons | No | No | Yes | No | Yes |
| View course roster | No | No | Yes | No | Yes |
| Enroll / unenroll in published course | No | Yes | Yes | Yes | Yes |
| View full lesson content (`GET /lessons/{id}`) | No | Enrolled only | Yes | Enrolled only | Yes |
| Mark lesson complete / view own progress | No | Enrolled only | Enrolled only | Enrolled only | Enrolled only |
| View another student's progress | No | No | Yes | No | Yes |
| Manage / deactivate / delete users | No | No | No | No | Yes |

---

## 6. Request Tracing & Security Headers

- Send an optional `X-Request-ID` header; the API echoes it back (or generates a UUIDv4) and correlates all structured JSON logs for that request.
- Responses include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `X-XSS-Protection: 0`.
