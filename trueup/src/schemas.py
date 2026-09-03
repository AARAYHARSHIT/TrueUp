import enum
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date
from typing import Optional, Union


@dataclass
class GatewayTransaction:
    order_id: str
    amount: Decimal
    txn_date: date
    status: str
    gateway_fee: Decimal

    def __repr__(self) -> str:
        return (
            f"GatewayTransaction(order_id={self.order_id!r}, amount={self.amount}, "
            f"txn_date={self.txn_date}, status={self.status!r}, gateway_fee={self.gateway_fee})"
        )


@dataclass
class BankSettlement:
    utr: str
    settlement_amount: Decimal
    settlement_date: date
    order_id_ref: str

    def __repr__(self) -> str:
        return (
            f"BankSettlement(utr={self.utr!r}, settlement_amount={self.settlement_amount}, "
            f"settlement_date={self.settlement_date}, order_id_ref={self.order_id_ref!r})"
        )


@dataclass
class MerchantLedger:
    order_id: str
    expected_amount: Decimal
    entry_date: date
    notes: str

    def __repr__(self) -> str:
        return (
            f"MerchantLedger(order_id={self.order_id!r}, expected_amount={self.expected_amount}, "
            f"entry_date={self.entry_date}, notes={self.notes!r})"
        )


class MatchPass(enum.Enum):
    DETERMINISTIC = "deterministic"
    FUZZY = "fuzzy"
    LLM_RESOLVER = "llm_resolver"


class RecordSource(enum.Enum):
    GATEWAY = "gateway"
    BANK = "bank"
    LEDGER = "ledger"


SourceRecord = Union[GatewayTransaction, BankSettlement, MerchantLedger]


@dataclass
class MatchResult:
    gateway_txn: GatewayTransaction
    bank_settlement: Optional[BankSettlement]
    merchant_ledger: Optional[MerchantLedger]
    match_pass: MatchPass
    method: str
    confidence: float
    amount_agrees: bool
    date_lag_days: Optional[int]

    @property
    def order_id(self) -> str:
        return self.gateway_txn.order_id

    def is_full_triple(self) -> bool:
        return (
            self.bank_settlement is not None and self.merchant_ledger is not None
        )

    def __repr__(self) -> str:
        return (
            f"MatchResult(order_id={self.order_id!r}, pass={self.match_pass.value!r}, "
            f"method={self.method!r}, confidence={self.confidence}, "
            f"amount_agrees={self.amount_agrees}, date_lag_days={self.date_lag_days}, "
            f"utr={getattr(self.bank_settlement, 'utr', None)!r})"
        )


@dataclass
class UnmatchedRecord:
    source: RecordSource
    record: SourceRecord
    reason_hint: str
    candidates: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        if isinstance(self.record, BankSettlement):
            return self.record.utr
        return self.record.order_id

    def __repr__(self) -> str:
        return (
            f"UnmatchedRecord(source={self.source.value!r}, key={self.key!r}, "
            f"reason_hint={self.reason_hint!r}, candidates={self.candidates})"
        )
