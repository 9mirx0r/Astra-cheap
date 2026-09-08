import json
import os
import random
from pathlib import Path

BASE = Path(r"c:\ANTIGRAVITY WORKS\astra-ultra\benchmarks\heavy_workloads")

# 1. Raft Consensus Fixture
raft_dir = BASE / "raft_consensus"
raft_dir.mkdir(parents=True, exist_ok=True)
raft_logs = raft_dir / "logs"
raft_logs.mkdir(parents=True, exist_ok=True)

print("Generating 35,000-line Raft concurrent cluster log...")
random.seed(42)
lines = []
lines.append("CLUSTER_INIT nodes=[node-1, node-2, node-3, node-4, node-5] term=1 election_timeout_ms=150")

# Generate 34,000 lines of interleaved heartbeat, election, and log replication traffic
for i in range(1, 34500):
    node = random.randint(1, 5)
    term = 1 + (i // 5000)
    if i % 15 == 0:
        lines.append(f"DEBUG node={node} term={term} RPC=RequestVote candidate=node-{node} last_log_index={i-1} last_log_term={term}")
    elif i % 25 == 0:
        lines.append(f"INFO  node={node} term={term} RPC=AppendEntries leader=node-1 prev_log_index={i-2} prev_log_term={term} entries_count=3")
    elif i % 50 == 0:
        lines.append(f"TRACE node={node} term={term} HEARTBEAT_ACK leader=node-1 commit_index={i-10}")
    else:
        lines.append(f"DEBUG node={node} term={term} STATE_TICK state=Follower clock_ms={1000 + i}")

# Inject the exact critical Byzantine Split-Brain failure at line 34501
lines.append("WARN  node-3 term=8 NETWORK_PARTITION isolated_nodes=[node-3, node-5]")
lines.append("WARN  node-3 term=9 ELECTION_TIMEOUT starting election candidate=node-3")
lines.append("ERROR node-3 term=9 RAFT_INVARIANT_VIOLATION: SplitBrainDetected! Candidate node-3 granted vote in Term 9 while leader node-1 already committed index 34210 in Term 8")
lines.append("CRITICAL node-3 term=9 STATE_MACHINE_CORRUPTION: MonotonicityFailure: uncommitted entry at index 34210 overwritten with conflicting payload without majority quorum")
error_line_index = len(lines)

# Remaining post-failure log lines
for i in range(1, 500):
    lines.append(f"FATAL node-3 term=9 ABORT_IMMINENT uncommitted_index=34210 payload_hash=0xDEADBEEF_{i}")
lines.append("CLUSTER_HALTED reason='Raft Election Safety Invariant Section 5.4.1 Broken'")

(raft_logs / "raft_cluster_trace.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Raft trace generated: {len(lines)} lines (critical error at line {error_line_index})")

# 2. MVCC Storage Engine Codebase Fixture
mvcc_dir = BASE / "mvcc_storage"
mvcc_dir.mkdir(parents=True, exist_ok=True)

tx_manager_code = '''"""Transaction Manager with ARIES WAL and 2PL."""
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
'''

mvcc_engine_code = '''"""Multi-Version Concurrency Control (MVCC) Storage Engine."""
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
'''

(mvcc_dir / "transaction_manager.py").write_text(tx_manager_code, encoding="utf-8")
(mvcc_dir / "mvcc_engine.py").write_text(mvcc_engine_code, encoding="utf-8")
print("MVCC Storage engine codebase generated.")

# 3. Benchmark manifest metadata
meta = {
    "suite_name": "Astra-Ultra Heavyweight Operations Benchmark Suite",
    "version": "1.0.0",
    "workloads": [
        {
            "id": "raft_split_brain_recovery",
            "name": "Distributed Raft Consensus Split-Brain & Invariant Violation",
            "category": "distributed_systems",
            "difficulty": "EXTREME",
            "fixture_path": "heavy_workloads/raft_consensus/logs/raft_cluster_trace.log",
            "total_log_lines": len(lines),
            "expected_error_line": error_line_index - 1,
            "target_model": "Luna-5.6 (High Effort) / o1 / o3-mini",
            "description": "Isolate the exact term, candidate ID, and log index where the Raft Election Safety Invariant broke in a 35,000-line concurrent trace without dumping the log into context."
        },
        {
            "id": "mvcc_aries_dirty_read",
            "name": "High-Concurrency MVCC Delta Chain & ARIES Rollback Race",
            "category": "storage_engines",
            "difficulty": "HARD",
            "codebase_path": "heavy_workloads/mvcc_storage/",
            "target_model": "Terra (Medium Effort) / Luna-5.6 / o1",
            "description": "Identify the missing version unlinking race condition in TransactionManager.abort causing dirty reads across concurrent checkpoints."
        }
    ]
}
(BASE / "benchmark_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"Benchmark manifest saved to {BASE / 'benchmark_manifest.json'}")
