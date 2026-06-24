from typing import TypedDict, Optional, Dict, Any

class AgentCommerceState(TypedDict):
    target_product_id: str
    inventory_metadata: Dict[str, Any]
    invoice_id: Optional[str]
    price_drops: Optional[int]
    procurement_decision: Optional[str]
    auditor_approved: Optional[bool]
    rejection_reason: Optional[str]
    xrpl_tx_hash: Optional[str]
