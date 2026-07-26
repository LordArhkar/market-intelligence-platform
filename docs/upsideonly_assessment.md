# UpsideOnly Integration Assessment

**Date:** 2026-07-26  
**Assessment Status:** COMPLETE  
**Platform:** UpsideOnly (upsideonly.com)  
**Powered by:** Perpetuals

---

## Executive Summary

**Automated UpsideOnly Integration: NOT AUTHORIZED**

After thorough review of UpsideOnly's Terms of Service, Privacy Policy, platform architecture, and technical implementation, **no official trading API exists** and **programmatic/automated trading is explicitly discouraged** through deposit-based anti-bot measures.

---

## Assessment Findings

### 1. Official API Availability

| Finding | Status | Evidence |
|---------|--------|----------|
| Public API Documentation | NOT FOUND | No `/api` endpoint with documented endpoints |
| Developer Portal | NOT FOUND | No developer.upsideonly.com or similar |
| Trading API | NOT FOUND | No endpoints for order entry, positions, or account access |
| Auth0 Configuration | DETECTED | Platform uses Auth0 for authentication (inferred from HTML) |
| Rate Limits | NOT APPLICABLE | No API = no rate limits to document |

### 2. Terms of Service Analysis

**Evidence from UpsideOnly Terms of Service (https://upsideonly.com/terms):**

#### Bot/AI Agent Policy (Direct Quote)

> "in order to reduce the presence of bots or AI agents, users that put down a refundable deposit of US$1 or more will be eligible to receive higher payouts from the Platform. The rationale behind the Deposit is that users that make even small deposits are less likely to be part of a bot-based attack and more likely to make well-considered and reliable predictions."

**Interpretation:** The platform explicitly acknowledges concern about bots/AI agents and has implemented financial barriers (deposit requirement) as an anti-bot measure.

#### Prohibited Conduct

The Terms explicitly prohibit:
- Interfering with Platform operation
- Disseminating viruses, malware, or malicious code
- Collecting personal information without consent
- Interfering with network, equipment, or servers

#### License Restrictions

> "Subject to your complete and ongoing compliance with these Terms, the Company grants you, solely for your personal, non-commercial use, a limited, non-exclusive, non-transferable, non-sublicensable, revocable license to access and use the Platform."

### 3. Technical Architecture Observations

| Component | Finding | Implication |
|-----------|---------|-------------|
| Platform Type | React SPA | No server-rendered API for scraping |
| Authentication | Auth0 | OAuth-based, not designed for programmatic access |
| Security | Cloudflare + Turnstile | Bot protection actively blocks automation |
| TradingView Charts | Embedded | Data visualization only, not trading API |
| Account Type | Email-only signup | Designed for manual human use |

### 4. Platform Intent Analysis

UpsideOnly's business model is based on:
1. **Paper Trading** - Users submit trading predictions manually
2. **AI Evaluation** - Their proprietary AI evaluates prediction quality
3. **Capital Allocation** - If predictions are valuable, they trade with their capital
4. **Royalty Payments** - Users receive payments based on prediction contribution

**Key Insight:** The platform **wants human judgment**, not algorithmic trading. Their AI evaluates the *quality* of predictions to determine if they should trade with real capital.

---

## Conclusion

### Automated Trading: NOT AUTHORIZED

**Reasons:**
1. No official API exists or is documented
2. Terms explicitly mention anti-bot measures
3. Platform uses Cloudflare protection against automation
4. License is for "personal, non-commercial use"
5. Account access requires Auth0 authentication (human-oriented)

### Manual Execution: REQUIRED

**Required Approach:**
1. Build internal paper-trading simulator
2. Generate signals internally
3. Provide CSV export for manual UpsideOnly entry
4. Track performance independently
5. Document all decisions

### Execution Adapter: AVAILABLE BUT DISABLED

An execution adapter module will be created and maintained in disabled state until:
1. UpsideOnly releases an official API
2. Written authorization for programmatic trading is obtained
3. Terms of Service are updated to explicitly permit bots

---

## Compliance Actions Taken

1. No automated login attempted to UpsideOnly
2. No credential embedding in code or configuration
3. No web scraping of UpsideOnly pages
4. No reverse engineering of Auth0 authentication flows
5. Manual execution interface designed and built
6. CSV import/export for human-mediated trades
7. Execution adapter created in disabled state

---

## Evidence References

| Source | URL | Key Evidence |
|--------|-----|--------------|
| Homepage | https://upsideonly.com | Platform description, paper trading model |
| Terms of Service | https://upsideonly.com/terms | Bot policy, license restrictions, prohibited conduct |
| Privacy Policy | https://upsideonly.com/privacy | Data handling, Auth0 reference |
| Platform Source | HTML/JavaScript | Auth0, Cloudflare, React SPA architecture |

---

## Future Actions

| Action | Trigger | Status |
|--------|---------|--------|
| Re-assess API availability | UpsideOnly announces API | Awaiting |
| Request API access | Direct contact with UpsideOnly | Optional |
| Enable execution adapter | Written authorization obtained | BLOCKED |

---

*Assessment prepared by OpenHands AI Agent*  
*Document ID: UPSIDEONLY-ASSESSMENT-001*  
*Version: 1.0*
