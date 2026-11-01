"""The TEB Bonus card as its statements and payment receipts name it."""

from ...domain.codes import AccountType
from ...domain.models import Account


def card_account(last4: str) -> Account:
    return Account(
        id=f"teb-{last4}", label=f"TEB Bonus •{last4}", bank="TEB", type=AccountType.CREDIT_CARD, number=last4
    )
