"""The MVP's codes, still spoken by two old formats: the report's script and version 1 of the verification
baseline. The domain codes are translated to them only there; the mapping goes when the new interface replaces the
report (Phase 6) and the baseline moves to a new version.
"""

from .domain.codes import EvidenceStatus, MonthStatus, TransactionKind
from .domain.labels import EVIDENCE_STATUS, MONTH_STATUS

KIND = {
    TransactionKind.PURCHASE: "harcama",
    TransactionKind.REFUND: "iade",
    TransactionKind.INTEREST_FEE: "faiz_ucret",
    TransactionKind.P2P_TRANSFER: "kisiye_transfer",
    TransactionKind.LOAN_PRINCIPAL: "kredi_anapara",
    TransactionKind.CASH_ADVANCE: "nakit_avans",
    TransactionKind.INVESTMENT: "yatirim",
    TransactionKind.INCOME: "gelir",
    TransactionKind.CARD_PAYMENT_NO_STATEMENT: "ekstresiz_kart",
    TransactionKind.CARD_PAYMENT: "kart_odemesi",
    TransactionKind.OWN_TRANSFER: "transfer",
}
MONTH = {
    MonthStatus.CLOSED: "kapandi",
    MonthStatus.WAITING: "bekleniyor",
    MonthStatus.MISSING: "eksik",
    MonthStatus.CHECK: "kontrol",
    MonthStatus.RUNNING: "suruyor",
}
RECEIPT = {
    EvidenceStatus.PROVISIONAL: "gecici",
    EvidenceStatus.MATCHED: "eslesti",
    EvidenceStatus.UNMATCHED: "eslesmedi",
    EvidenceStatus.NO_STATEMENT: "ekstresiz",
}
# The Turkish labels by the old codes.
MONTH_LABEL = {old: MONTH_STATUS[code] for code, old in MONTH.items()}
RECEIPT_LABEL = {old: EVIDENCE_STATUS[code] for code, old in RECEIPT.items()}
