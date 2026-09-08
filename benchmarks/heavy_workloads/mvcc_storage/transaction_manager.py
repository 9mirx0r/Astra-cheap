"""Transaction Manager with ARIES WAL and 2PL."""
from dataclasses import dataclass
from typing import Dict, Optional
import threading

@dataclass
class Transaction:
    tx_id: int
    status: str  # ACTIVE, COMMITTED, ABORTED
    prev_lsn: int

class TransactionManager:
    def __init__(self, wal_logger):
        self.wal_logger = wal_logger
        self.transactions: Dict[int, Transaction] = {}
        self.lock = threading.Lock()

    def begin(self, tx_id: int) -> Transaction:
        with self.lock:
            tx = Transaction(tx_id=tx_id, status="ACTIVE", prev_lsn=0)
            self.transactions[tx_id] = tx
            lsn = self.wal_logger.log_begin(tx_id)
            tx.prev_lsn = lsn
            return tx

    def commit(self, tx_id: int) -> int:
        with self.lock:
            tx = self.transactions.get(tx_id)
            if not tx or tx.status != "ACTIVE":
                raise ValueError("Invalid transaction state")
            tx.status = "COMMITTED"
            return self.wal_logger.log_commit(tx_id, tx.prev_lsn)

    def abort(self, tx_id: int, mvcc_engine) -> int:
        with self.lock:
            tx = self.transactions.get(tx_id)
            if not tx:
                raise ValueError("Transaction not found")
            tx.status = "ABORTED"
            # BUG: Missing unlinking of tuple version pointer during abort under fuzzy checkpointing!
            # mvcc_engine.rollback_versions(tx_id) is NOT called here, leaving dirty tuple pointers.
            return self.wal_logger.log_abort(tx_id, tx.prev_lsn)
