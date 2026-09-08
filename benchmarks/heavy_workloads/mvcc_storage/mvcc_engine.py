"""Multi-Version Concurrency Control (MVCC) Storage Engine."""
from dataclasses import dataclass
from typing import Dict, List, Optional
import threading

@dataclass
class TupleVersion:
    tx_id: int
    data: dict
    prev_version: Optional['TupleVersion'] = None
    deleted: bool = False

class MVCCEngine:
    def __init__(self):
        self.table: Dict[str, TupleVersion] = {}
        self.lock = threading.RLock()

    def write(self, key: str, data: dict, tx_id: int) -> None:
        with self.lock:
            curr = self.table.get(key)
            new_ver = TupleVersion(tx_id=tx_id, data=data, prev_version=curr)
            self.table[key] = new_ver

    def read(self, key: str, active_tx_ids: set) -> Optional[dict]:
        with self.lock:
            ver = self.table.get(key)
            while ver:
                if ver.tx_id not in active_tx_ids and not ver.deleted:
                    return ver.data
                ver = ver.prev_version
            return None

    def rollback_versions(self, tx_id: int) -> int:
        """Unlinks uncommitted tuple versions created by tx_id."""
        with self.lock:
            reverted = 0
            for k, head in list(self.table.items()):
                if head and head.tx_id == tx_id:
                    self.table[k] = head.prev_version
                    reverted += 1
            return reverted
