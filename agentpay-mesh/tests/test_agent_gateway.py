import pytest
from unittest.mock import MagicMock, patch
import json
import urllib.error

# Import targeted modules from our architecture
from config import MAX_ALLOWANCE_XRP
from agent.graph import risk_auditor_agent_node
from agent.tools import trigger_agent_delivery_webhook, generate_invoice


# ==============================================================================
# TEST CONFIG 1: RISK AUDITOR GUARDRAIL BOUNDARIES
# ==============================================================================
def test_risk_auditor_approves_under_limit():
    """Verifies that the risk auditor approves costs under the MAX_ALLOWANCE_XRP."""
    # Under limit: 15 XRP = 15,000,000 drops
    state = {"price_drops": 15_000_000}
    result = risk_auditor_agent_node(state)
    
    assert result["auditor_approved"] is True
    assert "rejection_reason" not in result

def test_risk_auditor_rejects_over_limit():
    """Verifies that the risk auditor catches and blocks costs over the limit."""
    # Over limit: 100 XRP = 100,000,000 drops (Max configured ceiling is 75.0)
    state = {"price_drops": 100_000_000}
    result = risk_auditor_agent_node(state)
    
    assert result["auditor_approved"] is False
    assert "Breached ceiling" in result["rejection_reason"]


# ==============================================================================
# TEST CONFIG 2: HMAC SIGNED WEBHOOK RETRY LOOPS (WITH BACKOFF)
# ==============================================================================
@patch("urllib.request.urlopen")
def test_webhook_success_on_first_attempt(mock_urlopen):
    """Verifies webhook marks success instantly when receiving an HTTP 200."""
    # Simulate a successful HTTP response object
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = trigger_agent_delivery_webhook(
        target_url="http://mockagent/webhook",
        invoice_id="INV-111",
        tx_hash="HASH123",
        product_id="PROD_001",
        max_retries=3,
        initial_delay=0.01  # Low timeout speed for testing
    )

    assert result["status"] == "success"
    assert result["attempts"] == 1
    assert result["http_code"] == 200
    assert mock_urlopen.call_count == 1


@patch("time.sleep", return_value=None)  # Patched to bypass wait times during testing
@patch("urllib.request.urlopen")
def test_webhook_exponential_backoff_retry_loop(mock_urlopen, mock_sleep):
    """Verifies the webhook safely retries on failure and follows backoff limits."""
    # Simulate an HTTP error exception for the first 2 attempts, then success on attempt 3
    mock_failed_response = urllib.error.URLError("Server Offline")
    mock_success_response = MagicMock()
    mock_success_response.__enter__.return_value.getcode.return_value = 200

    mock_urlopen.side_effect = [mock_failed_response, mock_failed_response, mock_success_response]

    result = trigger_agent_delivery_webhook(
        target_url="http://mockagent/webhook",
        invoice_id="INV-222",
        tx_hash="HASH456",
        product_id="PROD_002",
        max_retries=3,
        initial_delay=0.1
    )

    assert result["status"] == "success"
    assert result["attempts"] == 3
    assert mock_urlopen.call_count == 3
    # Check that the exponential delay doubled between retries (0.1s -> 0.2s)
    mock_sleep.assert_any_call(0.1)
    mock_sleep.assert_any_call(0.2)


@patch("time.sleep", return_value=None)
@patch("urllib.request.urlopen")
def test_webhook_fails_after_max_retries(mock_urlopen, mock_sleep):
    """Verifies that the gateway logs a failure if the target remains unreachable."""
    # Force connection drops across all attempts
    mock_urlopen.side_effect = urllib.error.URLError("Connection Timed Out")

    result = trigger_agent_delivery_webhook(
        target_url="http://mockagent/webhook",
        invoice_id="INV-333",
        tx_hash="HASH789",
        product_id="PROD_003",
        max_retries=3,
        initial_delay=0.1
    )

    assert result["status"] == "failed"
    assert result["attempts"] == 3
    assert "Max retry limit reached" in result["message"]
