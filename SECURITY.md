# Security Policy

This public repository contains public and synthetic demonstration data only. Never commit real VIN, supplier, employee, warranty or production records, `.env`, passwords, HMAC keys, session databases or runtime logs.

Implemented PoC controls include PBKDF2-SHA256 salted password hashing, role-based server authorization, CSRF tokens, 8-hour sessions, account lockout, HMAC pseudonymization and 90-day audit cleanup.

This is not a production security certification. Enterprise deployment still requires HTTPS, SSO/MFA, managed secrets/KMS, database and backup encryption, network controls, monitoring, vulnerability testing and organizational privacy/legal review.
