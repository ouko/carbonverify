# Secrets Rotation Guide

CarbonVerify uses several cryptographic secrets that must be rotated periodically. This guide documents each secret, its rotation procedure, and rollback strategy.

---

## Secret Inventory

| Secret | Purpose | Rotation Frequency | Downtime Required |
|--------|---------|-------------------|-------------------|
| `SECRET_KEY` | JWT signing (access + refresh tokens) | Every 90 days | No (graceful) |
| `ENCRYPTION_KEY_HEX` | Field-level PII encryption (Fernet) | Every 180 days | Yes (data migration) |
| `IOT_WEBHOOK_API_KEY` | IoT device authentication | Every 90 days | No |
| `DATABASE_URL` (password) | PostgreSQL connection | Every 90 days | No (connection pool) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 file storage | Per AWS IAM policy | No |

---

## JWT Secret Key (`SECRET_KEY`)

### Rotation Procedure (Zero-Downtime)

1. **Generate new secret**:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Deploy with dual-secret support**:
   - Set `SECRET_KEY` to the **new** value
   - Set `SECRET_KEY_PREVIOUS` to the **old** value
   - Deploy the application

3. **Verify**:
   - New logins issue tokens signed with the new key
   - Existing refresh tokens (signed with old key) still validate via `SECRET_KEY_PREVIOUS`

4. **Wait for token TTL**:
   - Wait 7 days (refresh token max age) or force logout all users

5. **Remove old secret**:
   - Unset `SECRET_KEY_PREVIOUS`
   - Deploy again

### Implementation

Dual-secret JWT validation is already implemented in `backend/app/auth/security.py` (`decode_token`). It tries `SECRET_KEY`, then `SECRET_KEY_PREVIOUS` if set.

---

## PII Encryption Key (`ENCRYPTION_KEY_HEX`)

### ⚠️ Not Yet Implemented

Field-level encryption uses Fernet. Rotating the key requires re-encrypting all encrypted columns. Dual-key (`ENCRYPTION_KEY_HEX_PREVIOUS`) support and an automated rotation script are **not yet implemented**.

### Planned Rotation Procedure

1. **Schedule maintenance window** (expect 5–30 minutes depending on data volume)

2. **Generate new key**:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().hex())"
   ```

3. Add `ENCRYPTION_KEY_HEX_PREVIOUS` support to `backend/app/config.py` and the encryption helpers.

4. **Run rotation migration** against all encrypted columns.

5. **Verify** decryption, then remove the previous key.

> Track this as a pre-production task if encrypted PII columns contain live data.

---

## IoT Webhook API Key (`IOT_WEBHOOK_API_KEY`)

### ⚠️ Not Yet Implemented

Dual-key (`IOT_WEBHOOK_KEY_PREVIOUS`) validation for IoT webhooks is **not yet implemented**. Rotation requires updating all devices and replacing the single key in the backend, causing a brief outage until every device is updated.

### Planned Rotation Procedure

1. **Generate new key**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Update devices** with the new key.

3. **Update backend** `IOT_WEBHOOK_API_KEY` to the new value and deploy.

4. **Monitor** for rejected requests from devices still using the old key.

> Implement `IOT_WEBHOOK_KEY_PREVIOUS` dual-key validation before scaling the IoT fleet.

---

## Database Password

### Rotation Procedure (Minimal Downtime)

1. **Create new DB user** (PostgreSQL):
   ```sql
   CREATE USER carbonverify_new WITH PASSWORD 'new-strong-password';
   GRANT ALL PRIVILEGES ON DATABASE carbonverify TO carbonverify_new;
   -- Run migration to grant table permissions
   ```

2. **Update connection string**:
   - `DATABASE_URL` = `postgresql+asyncpg://carbonverify_new:new-password@host:5432/carbonverify`

3. **Rolling restart**:
   - Restart app pods one by one (K8s rolling update)
   - Connection pool will drain old connections naturally

4. **Drop old user** (after 24 hours):
   ```sql
   DROP USER carbonverify_old;
   ```

---

## AWS IAM Keys

Follow AWS best practices:
1. Create new IAM user / role
2. Update application with new credentials
3. Monitor CloudTrail for usage of old keys
4. Deactivate old keys
5. Delete old keys after 7 days

---

## Automation

### Recommended: Rotate JWT and IoT keys via CI/CD

Add a GitHub Actions workflow that:
1. Runs monthly
2. Generates new secrets
3. Updates AWS Secrets Manager / Vault
4. Triggers a rolling deployment

### Alerting

Set Prometheus alerts for:
- `secret_age_days > 85` (warn 5 days before JWT rotation due)
- `secret_age_days > 175` (warn 5 days before encryption key rotation due)
