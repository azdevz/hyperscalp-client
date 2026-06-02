"""
hl_bot/ota_tuner.py — OTA strategy parameters synchronization client.
Polls central app.hyperscalp.com secure API every 30 minutes to dynamically update settings.
"""

import logging
import urllib.request
import json
import ssl

import config
import db

logger = logging.getLogger(__name__)

CENTRAL_URL = "https://app.hyperscalp.com/api/v1/strategy/config"

def run_ota_sync() -> None:
    """Fetch strategy params from central SaaS and update local config variables in RAM."""
    license_key = db.get_bot_state("license_key") or ""
    if not license_key:
        logger.warning("OTA Tuner: No license_key found in database. Skipping sync.")
        return

    req_url = f"{CENTRAL_URL}?license_key={license_key}"
    logger.info(f"OTA Tuner: Fetching remote strategy config...")

    try:
        # Create unverified context if needed, but standard SSL is safer
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # For dev/testing flexibility

        req = urllib.request.Request(
            req_url,
            headers={
                "User-Agent": "HyperScalp-Bot-Worker/1.0",
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode())
                
                # Payload keys to process and apply
                params = payload.get("parameters", {})
                updated_keys = []
                for k, v in params.items():
                    if hasattr(config, k):
                        # Safely convert type based on current config type
                        current_type = type(getattr(config, k))
                        try:
                            # Apply correct casting
                            if current_type is int:
                                cast_val = int(v)
                            elif current_type is float:
                                cast_val = float(v)
                            elif current_type is bool:
                                cast_val = str(v).lower() in ("true", "1")
                            else:
                                cast_val = v
                            
                            setattr(config, k, cast_val)
                            updated_keys.append(f"{k}={cast_val}")
                        except Exception as e:
                            logger.error(f"OTA Tuner: Failed casting {k} value {v}: {e}")
                
                if updated_keys:
                    msg = f"OTA Tuner: Strategy synchronized. Updated {len(updated_keys)} keys: " + ", ".join(updated_keys)
                    logger.info(msg)
                    db.log_error("ota_tuner", msg)
                else:
                    logger.debug("OTA Tuner: Strategy synchronized. No config modifications needed.")
            else:
                logger.error(f"OTA Tuner: Central API returned status code {response.status}.")
    except Exception as exc:
        logger.error(f"OTA Tuner: Failed syncing strategy parameters: {exc}")
