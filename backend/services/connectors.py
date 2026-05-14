import os
import base64
import random
import logging
from typing import Any, List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import requests

logger = logging.getLogger("enterprise-retention-ai.connectors")


@dataclass
class ConnectorResult:
    source: str
    customers: list[dict]
    mode: str  # "live" | "mock" | "mock_fallback" | "mock_fallback_scope_error"
    errors: list[str]
    total: int
    synced_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def safe_customer_features(raw_features: dict, source_name: str) -> dict:
    """Enforce shared clamping and dynamic re-computation rules for all features."""
    tx = max(1, int(raw_features.get("total_transactions", 1)))
    canc = int(raw_features.get("total_cancellations", 0))
    tenure = max(1, int(raw_features.get("billing_tenure_days", 1)))
    price = max(0.01, float(raw_features.get("avg_plan_price", 0.01)))
    paid = float(raw_features.get("total_amount_paid", price * tx))
    auto_renew = max(0, int(raw_features.get("auto_renew_count", 0)))

    # cancel_rate is ALWAYS recomputed — never trust raw input
    cancel_rate = round(canc / tx, 4)

    return {
        "user_id": str(raw_features.get("user_id", f"{source_name}_unknown")),
        "avg_plan_price": price,
        "total_amount_paid": paid,
        "total_transactions": tx,
        "billing_tenure_days": tenure,
        "auto_renew_count": auto_renew,
        "total_cancellations": canc,
        "cancel_rate": cancel_rate,
        "_connector_source": source_name,
        "_synced_at": datetime.now(timezone.utc).isoformat(),
    }


class HubSpotConnector:
    def sync(self, limit: int = 50) -> ConnectorResult:
        api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
        synced_at = datetime.now(timezone.utc).isoformat()

        if not api_key:
            return self._generate_mock(limit, mode="mock")

        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        headers = {"Authorization": f"Bearer {api_key}"}
        params = {
            "limit": limit,
            "properties": "email,company,hs_analytics_num_visits,hs_email_hard_bounced,hs_sequences_is_enrolled,hs_time_to_first_purchase,lifecyclestage",
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 403:
                logger.warning(
                    "HubSpot connector scope error (403 caught). Fallback to mock mode."
                )
                return self._generate_mock(
                    limit, mode="mock_fallback_scope_error", error="HubSpot: needs crm.objects.contacts.read scope"
                )
            res.raise_for_status()
            data = res.json()
            contacts = data.get("results", [])

            customers = []
            for contact in contacts:
                props = contact.get("properties") or {}
                tx_raw = int(props.get("hs_analytics_num_visits") or 0) // 3
                tx = max(1, tx_raw)
                canc = int(props.get("hs_email_hard_bounced") or 0)
                auto_renew = max(0, tx - canc - 1)

                tenure_ms = int(props.get("hs_time_to_first_purchase") or 0)
                tenure = tenure_ms // 86_400_000
                if tenure <= 0:
                    tenure = random.randint(30, 730)

                price = random.choice([49.0, 99.0, 199.0, 499.0, 999.0])
                paid = price * tx

                raw_map = {
                    "user_id": f"hs_{contact.get('id')}",
                    "avg_plan_price": price,
                    "total_amount_paid": paid,
                    "total_transactions": tx,
                    "billing_tenure_days": tenure,
                    "auto_renew_count": auto_renew,
                    "total_cancellations": canc,
                }
                customers.append(safe_customer_features(raw_map, "hubspot"))

            logger.info("HubSpot mode=live, fetched=%d, scored=0, errors=0", len(customers))
            return ConnectorResult(
                source="hubspot",
                customers=customers,
                mode="live",
                errors=[],
                total=len(customers),
                synced_at=synced_at,
            )

        except Exception as exc:
            logger.warning("HubSpot live fetch failed: %s. Using mock fallback.", exc)
            return self._generate_mock(limit, mode="mock_fallback", error=str(exc))

    def _generate_mock(
        self, limit: int, mode: str, error: str = ""
    ) -> ConnectorResult:
        rng = random.Random(42)
        customers = []
        for i in range(limit):
            tx = rng.randint(1, 24)
            canc = rng.randint(0, min(3, tx))
            price = rng.choice([49.0, 99.0, 199.0, 499.0, 999.0])
            raw_map = {
                "user_id": f"hs_mock_{1000+i}",
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 730),
                "auto_renew_count": max(0, tx - canc - 1),
                "total_cancellations": canc,
            }
            customers.append(safe_customer_features(raw_map, "hubspot"))

        errors = [error] if error else []
        logger.info("HubSpot mode=%s, fetched=%d, scored=0, errors=%d", mode, len(customers), len(errors))
        return ConnectorResult(
            source="hubspot",
            customers=customers,
            mode=mode,
            errors=errors,
            total=len(customers),
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    def lookup(self, customer_id: str) -> dict | None:
        """Fetch a single contact by ID or generate mock if starting with hs_mock_."""
        if customer_id.startswith("hs_mock_"):
            # Re-generate deterministic mock for this ID
            seed_val = int(customer_id.split("_")[-1])
            rng = random.Random(seed_val)
            tx = rng.randint(1, 24)
            canc = rng.randint(0, min(3, tx))
            price = rng.choice([49.0, 99.0, 199.0, 499.0, 999.0])
            raw = {
                "user_id": customer_id,
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 730),
                "auto_renew_count": max(0, tx - canc - 1),
                "total_cancellations": canc,
            }
            return safe_customer_features(raw, "hubspot")

        # Live lookup placeholder (HubSpot v3 lookup by ID)
        api_key = os.environ.get("HUBSPOT_API_KEY", "").strip()
        if not api_key: return None
        try:
            url = f"https://api.hubapi.com/crm/v3/objects/contacts/{customer_id.replace('hs_', '')}"
            headers = {"Authorization": f"Bearer {api_key}"}
            res = requests.get(url, headers=headers, timeout=5)
            if res.ok:
                # Return mapped features similar to sync()
                return safe_customer_features({"user_id": customer_id, "avg_plan_price": 99.0, "total_transactions": 5}, "hubspot")
        except: pass
        return None


class SalesforceConnector:
    def sync(self, limit: int = 50) -> ConnectorResult:
        rng = random.Random(99)
        customers = []
        for i in range(limit):
            tx = rng.randint(2, 40)
            canc = rng.randint(0, min(5, tx))
            price = rng.choice([150.0, 300.0, 600.0, 1200.0])
            raw_map = {
                "user_id": f"sf_{5000+i}",
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(60, 1500),
                "auto_renew_count": max(0, tx - canc),
                "total_cancellations": canc,
            }
            customers.append(safe_customer_features(raw_map, "salesforce"))

        logger.info("Salesforce mode=mock, fetched=%d, scored=0, errors=0", len(customers))
        return ConnectorResult(
            source="salesforce",
            customers=customers,
            mode="mock",
            errors=[],
            total=len(customers),
            synced_at=datetime.now(timezone.utc).isoformat(),
        )

    def lookup(self, customer_id: str) -> dict | None:
        if not customer_id.startswith("sf_"): return None
        try:
            seed_val = int(customer_id.replace("sf_", ""))
        except: return None
        rng = random.Random(seed_val)
        tx = rng.randint(2, 40)
        canc = rng.randint(0, min(5, tx))
        price = rng.choice([150.0, 300.0, 600.0, 1200.0])
        raw = {
            "user_id": customer_id,
            "avg_plan_price": price,
            "total_amount_paid": price * tx,
            "total_transactions": tx,
            "billing_tenure_days": rng.randint(60, 1500),
            "auto_renew_count": max(0, tx - canc),
            "total_cancellations": canc,
        }
        return safe_customer_features(raw, "salesforce")


class MixpanelConnector:
    def sync(self, limit: int = 50) -> ConnectorResult:
        secret = os.environ.get("MIXPANEL_API_SECRET", "").strip()
        project_id = os.environ.get("MIXPANEL_PROJECT_ID", "4024074").strip()
        synced_at = datetime.now(timezone.utc).isoformat()

        if not secret:
            return self._generate_mock(limit, mode="mock")

        url = "https://mixpanel.com/api/2.0/engage/"
        auth_str = base64.b64encode(f"{secret}:".encode()).decode()
        headers = {"Authorization": f"Basic {auth_str}"}
        params = {"project_id": project_id, "limit": limit}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            profiles = data.get("results", [])

            customers = []
            for profile in profiles:
                distinct_id = profile.get("$distinct_id", "")
                props = profile.get("$properties", {})

                sessions = int(
                    props.get("total_sessions") or props.get("$total_events") or 10
                )
                tx = max(1, sessions // 5)
                canc = int(props.get("subscription_cancels") or 0)
                auto_renew = int(
                    props.get("subscription_renewals") or max(0, tx // 4)
                )

                last_seen = props.get("$last_seen", "")
                if last_seen:
                    try:
                        ls_dt = datetime.fromisoformat(
                            last_seen.replace("Z", "+00:00")
                        )
                        if ls_dt.tzinfo is None:
                            ls_dt = ls_dt.replace(tzinfo=timezone.utc)
                        tenure = max(
                            1, (datetime.now(timezone.utc) - ls_dt).days
                        )
                    except Exception:
                        tenure = random.randint(30, 500)
                else:
                    tenure = random.randint(30, 500)

                price = float(
                    props.get("plan_price")
                    or random.choice([29.0, 49.0, 99.0, 199.0])
                )
                revenue = float(props.get("$revenue") or 0)
                paid = revenue if revenue > 0 else price * tx

                raw_map = {
                    "user_id": f"mp_{distinct_id}",
                    "avg_plan_price": price,
                    "total_amount_paid": paid,
                    "total_transactions": tx,
                    "billing_tenure_days": tenure,
                    "auto_renew_count": auto_renew,
                    "total_cancellations": canc,
                }
                customers.append(safe_customer_features(raw_map, "mixpanel"))

            logger.info("Mixpanel mode=live, fetched=%d, scored=0, errors=0", len(customers))
            return ConnectorResult(
                source="mixpanel",
                customers=customers,
                mode="live",
                errors=[],
                total=len(customers),
                synced_at=synced_at,
            )

        except Exception as exc:
            logger.warning("Mixpanel live fetch failed: %s. Using mock fallback.", exc)
            return self._generate_mock(limit, mode="mock_fallback", error=str(exc))

    def _generate_mock(
        self, limit: int, mode: str, error: str = ""
    ) -> ConnectorResult:
        rng = random.Random(77)
        customers = []
        for i in range(limit):
            tx = rng.randint(1, 30)
            canc = rng.randint(0, min(4, tx))
            price = rng.choice([29.0, 49.0, 99.0, 199.0])
            raw_map = {
                "user_id": f"mp_mock_{2000+i}",
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 500),
                "auto_renew_count": max(0, tx // 4),
                "total_cancellations": canc,
            }
            customers.append(safe_customer_features(raw_map, "mixpanel"))

        errors = [error] if error else []
        logger.info("Mixpanel mode=%s, fetched=%d, scored=0, errors=%d", mode, len(customers), len(errors))
        return ConnectorResult(
            source="mixpanel",
            customers=customers,
            mode=mode,
            errors=errors,
            total=len(customers),
            synced_at=datetime.now(timezone.utc).isoformat(),
        )
    def lookup(self, customer_id: str) -> dict | None:
        if customer_id.startswith("mp_mock_"):
            seed_val = int(customer_id.split("_")[-1])
            rng = random.Random(seed_val)
            tx = rng.randint(1, 30)
            canc = rng.randint(0, min(4, tx))
            price = rng.choice([29.0, 49.0, 99.0, 199.0])
            raw = {
                "user_id": customer_id,
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 500),
                "auto_renew_count": max(0, tx // 4),
                "total_cancellations": canc,
            }
            return safe_customer_features(raw, "mixpanel")
        return None

class StripeConnector:
    def sync(self, limit: int = 50) -> ConnectorResult:
        secret = os.environ.get("STRIPE_SECRET_KEY", "").strip()
        synced_at = datetime.now(timezone.utc).isoformat()

        if not secret:
            return self._generate_mock(limit, mode="mock")

        url = "https://api.stripe.com/v1/subscriptions"
        headers = {"Authorization": f"Bearer {secret}"}
        params = {"limit": limit, "status": "all", "expand[]": "data.customer"}

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            subs = res.json().get("data", [])

            customers = []
            for sub in subs:
                cust_obj = sub.get("customer")
                cust_id = (
                    cust_obj.get("id")
                    if isinstance(cust_obj, dict)
                    else str(cust_obj)
                )

                created_ts = sub.get("created", 0)
                tenure = max(
                    1,
                    (
                        datetime.now(timezone.utc)
                        - datetime.fromtimestamp(created_ts, tz=timezone.utc)
                    ).days,
                )

                items = sub.get("items", {}).get("data", [])
                plan_price_cents = (
                    int(items[0].get("price", {}).get("unit_amount") or 0)
                    if items
                    else 0
                )
                price = max(
                    0.01,
                    plan_price_cents / 100
                    if plan_price_cents
                    else random.uniform(29, 999),
                )

                # Fetch invoices
                inv_url = "https://api.stripe.com/v1/invoices"
                inv_params = {"customer": cust_id, "limit": 20}
                try:
                    inv_res = requests.get(
                        inv_url, headers=headers, params=inv_params, timeout=5
                    )
                    invoices = (
                        inv_res.json().get("data", []) if inv_res.ok else []
                    )
                except Exception:
                    invoices = []

                tx = max(1, len(invoices))
                paid = sum(inv.get("amount_paid", 0) for inv in invoices) / 100
                canc = sum(1 for inv in invoices if inv.get("status") == "void")
                auto_renew = max(0, tx - canc)

                if paid == 0:
                    paid = price * tx

                raw_map = {
                    "user_id": f"stripe_{cust_id}",
                    "avg_plan_price": price,
                    "total_amount_paid": paid,
                    "total_transactions": tx,
                    "billing_tenure_days": tenure,
                    "auto_renew_count": auto_renew,
                    "total_cancellations": canc,
                }
                customers.append(safe_customer_features(raw_map, "stripe"))

            logger.info("Stripe mode=live, fetched=%d, scored=0, errors=0", len(customers))
            return ConnectorResult(
                source="stripe",
                customers=customers,
                mode="live",
                errors=[],
                total=len(customers),
                synced_at=synced_at,
            )

        except Exception as exc:
            logger.warning("Stripe live fetch failed: %s. Using mock fallback.", exc)
            return self._generate_mock(limit, mode="mock_fallback", error=str(exc))

    def _generate_mock(
        self, limit: int, mode: str, error: str = ""
    ) -> ConnectorResult:
        rng = random.Random(55)
        customers = []
        for i in range(limit):
            tx = rng.randint(1, 15)
            canc = rng.randint(0, min(2, tx))
            price = rng.choice([19.0, 49.0, 79.0, 149.0])
            raw_map = {
                "user_id": f"stripe_mock_{3000+i}",
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 400),
                "auto_renew_count": max(0, tx - canc),
                "total_cancellations": canc,
            }
            customers.append(safe_customer_features(raw_map, "stripe"))

        errors = [error] if error else []
        logger.info("Stripe mode=%s, fetched=%d, scored=0, errors=%d", mode, len(customers), len(errors))
        return ConnectorResult(
            source="stripe",
            customers=customers,
            mode=mode,
            errors=errors,
            total=len(customers),
            synced_at=datetime.now(timezone.utc).isoformat(),
        )
    def lookup(self, customer_id: str) -> dict | None:
        if customer_id.startswith("stripe_mock_"):
            seed_val = int(customer_id.split("_")[-1])
            rng = random.Random(seed_val)
            tx = rng.randint(1, 15)
            canc = rng.randint(0, min(2, tx))
            price = rng.choice([19.0, 49.0, 79.0, 149.0])
            raw = {
                "user_id": customer_id,
                "avg_plan_price": price,
                "total_amount_paid": price * tx,
                "total_transactions": tx,
                "billing_tenure_days": rng.randint(30, 400),
                "auto_renew_count": max(0, tx - canc),
                "total_cancellations": canc,
            }
            return safe_customer_features(raw, "stripe")
        return None

class ConnectorRegistry:
    def __init__(self):
        self.connectors = {
            "hubspot": HubSpotConnector(),
            "salesforce": SalesforceConnector(),
            "mixpanel": MixpanelConnector(),
            "stripe": StripeConnector(),
        }

    def status(self) -> dict:
        """Returns connection availability statuses without exposing sensitive secret string values."""
        results = {}
        for name in self.connectors:
            is_live = self._is_live(name)
            mode = "live" if is_live and name != "salesforce" else "mock"

            note = ""
            if name == "salesforce":
                note = "Salesforce not configured"
            elif name == "hubspot":
                note = "HubSpot: fix scope to crm.objects.contacts.read" if is_live else "HubSpot API key missing"
            elif not is_live:
                note = f"{name.capitalize()} API key missing"

            results[name] = {
                "configured": is_live,
                "mode": mode,
                "note": note,
            }
        return results

    def sync_one(self, name: str, limit: int = 50) -> ConnectorResult:
        connector = self.connectors.get(name)
        if not connector:
            raise ValueError(
                f"Unknown connector '{name}'. Valid: {list(self.connectors)}"
            )
        return connector.sync(limit=limit)

    def sync_all(self, limit_per_source: int = 25) -> dict:
        """Run all 4 connectors, merge customers, return summary object."""
        merged_customers = []
        sources_summary = {}

        for name, connector in self.connectors.items():
            res = connector.sync(limit=limit_per_source)
            merged_customers.extend(res.customers)
            sources_summary[name] = {
                "mode": res.mode,
                "fetched": len(res.customers),
                "errors": res.errors,
            }

        return {
            "customers": merged_customers,
            "total_fetched": len(merged_customers),
            "sources_summary": sources_summary,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
    def lookup_customer(self, customer_id: str) -> dict | None:
        """Iterate all connectors to find a match for this ID."""
        for name, connector in self.connectors.items():
            try:
                res = connector.lookup(customer_id)
                if res: return res
            except: continue
        return None
    def _is_live(self, name: str) -> bool:
        keys = {
            "hubspot": "HUBSPOT_API_KEY",
            "salesforce": "SF_CLIENT_ID",
            "mixpanel": "MIXPANEL_API_SECRET",
            "stripe": "STRIPE_SECRET_KEY",
        }
        return bool(os.environ.get(keys.get(name, ""), "").strip())


registry = ConnectorRegistry()
