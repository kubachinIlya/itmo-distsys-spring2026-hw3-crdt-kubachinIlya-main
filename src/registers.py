"""CRDT Implementations - Registers module.

Registers are implemented as Operation-based CRDTs (CmRDT).
Each write operation is tracked and replicated across all replicas.
"""

from typing import Any, Optional, List, Tuple, Dict
from .crdt_base import CmRDT


class LWWRegister(CmRDT):
    """Last-Writer-Wins Register (Operation-based CmRDT).
    
    An operation-based register that stores the last written value, resolved by timestamp.
    When multiple writes occur, the one with the highest timestamp wins.
    
    If timestamps are equal, a tiebreaker (replica_id) is used.
    
    How it works (Operation-based):
    - Each write(value, timestamp, replica_id) is an operation
    - Operations are replicated to all replicas
    - Each replica applies all operations and keeps only the one with highest timestamp
    - Commutativity: operations can be applied in any order, result is the same
    
    Example:
        >>> r = LWWRegister()
        >>> r.write(value=42, timestamp=1.0, replica_id='A')
        >>> r.read()
        42
        >>> r.write(value=99, timestamp=2.0, replica_id='B')
        >>> r.read()
        99
    """

    def __init__(self) -> None:
        """Initialize an empty LWW register."""
        self._value: Optional[Any] = None
        self._timestamp: float = float("-inf")
        self._replica_id: str = ""
        self._has_value: bool = False

    def read(self) -> Optional[Any]:
        """Read the current value from the register.
        
        Returns:
            The current value or None if register is empty
        """
        return self._value if self._has_value else None

    def write(self, value: Any, timestamp: float, replica_id: str) -> None:
        """Execute a write operation.
        
        Args:
            value: The value to write
            timestamp: The timestamp of this write
            replica_id: The ID of the replica performing the write
        """
        self.apply_operation(value, {"timestamp": timestamp, "replica_id": replica_id})

    def apply_operation(self, operation: Any, metadata: Any = None) -> None:
        """Apply a write operation from another replica.
        
        Args:
            operation: The value that was written
            metadata: Dict with 'timestamp' and 'replica_id'
        """
        if metadata is None:
            return
        ts = metadata["timestamp"]
        rid = metadata["replica_id"]
        if not self._has_value or (ts, rid) > (self._timestamp, self._replica_id):
            self._value = operation
            self._timestamp = ts
            self._replica_id = rid
            self._has_value = True

    def get_operations(self) -> List[tuple]:
        """Get all unsync'd operations.
        
        Returns:
            List of (value, metadata) tuples where metadata has 'timestamp' and 'replica_id'
        """
        if not self._has_value:
            return []
        return [(self._value, {"timestamp": self._timestamp, "replica_id": self._replica_id})]

    def __eq__(self, other: Any) -> bool:
        """Check if two LWW registers have the same state."""
        if not isinstance(other, LWWRegister):
            return False
        return (
            self._has_value == other._has_value
            and self._value == other._value
            and self._timestamp == other._timestamp
            and self._replica_id == other._replica_id
        )

    def __repr__(self) -> str:
        """Return string representation of the register state."""
        if not self._has_value:
            return "LWWRegister(empty)"
        return f"LWWRegister({self._value!r}, ts={self._timestamp}, rid={self._replica_id!r})"


class MVRegister(CmRDT):
    """Multi-Value Register (Operation-based CmRDT).
    
    An operation-based register that can hold multiple values in case of concurrent writes.
    Uses version vectors to track causal history.
    
    When writes are causally related (one happens-after another), only the newer value is kept.
    When writes are concurrent (incomparable in the causal order), both values are stored.
    
    How it works (Operation-based):
    - Each write(value) is an operation
    - Each operation has metadata: (replica_id, version_vector)
    - Operations are replicated to all replicas
    - Each replica applies operations atomically
    - Version vectors determine causal relationships
    
    Example:
        >>> r1 = MVRegister('replica_1')
        >>> r2 = MVRegister('replica_2')
        >>> r1.write(10)
        >>> r2.write(20)
        >>> # Sync: r1 and r2 exchange operations
        >>> r1.get_operations()  # r1 sends its write(10) to r2
        >>> r2.apply_operation(10, metadata={'replica_id': 'replica_1', 'vv': {...}})
        >>> r1.apply_operation(20, metadata={'replica_id': 'replica_2', 'vv': {...}})
        >>> r1.read()
        {10, 20}  # Both values since they were concurrent
    """

    def __init__(self, replica_id: str = "A") -> None:
        """Initialize an empty MV register.
        
        Args:
            replica_id: The ID of this replica
        """
        self._replica_id = replica_id
        self._vv: Dict[str, int] = {}
        # Список (value, vv, replica_id) — replica_id исходного writer-а
        self._values: List[Tuple[Any, Dict[str, int], str]] = []

    def write(self, value: Any) -> None:
        """Execute a write operation from this replica.
        
        This increments the version vector for this replica and records the write operation.
        
        Args:
            value: The value to write
        """
        self._vv[self._replica_id] = self._vv.get(self._replica_id, 0) + 1
        vv_copy = dict(self._vv)
        self._apply(value, vv_copy, self._replica_id)

    def _compare_vv(self, a, b):
        """-1 если a < b, 0 если a == b, 1 если a > b, None если несравнимы."""
        keys = set(a) | set(b)
        a_le_b = all(a.get(k, 0) <= b.get(k, 0) for k in keys)
        b_le_a = all(b.get(k, 0) <= a.get(k, 0) for k in keys)
        if a_le_b and b_le_a:
            return 0
        if a_le_b:
            return -1
        if b_le_a:
            return 1
        return None  # concurrent
    
    def _apply(self, value: Any, vv: Dict[str, int], replica_id: str) -> None:
        # Если новая операция устарела или совпадает — игнорируем
        for _, existing_vv, _ in self._values:
            cmp = self._compare_vv(vv, existing_vv)
            if cmp in (-1, 0):
                return
        # Удаляем все dominated-значения
        self._values = [
            (v, vv2, rid) for v, vv2, rid in self._values
            if self._compare_vv(vv2, vv) != -1
        ]
        self._values.append((value, dict(vv), replica_id))
    
    def read(self) -> set:
        """Read all current values.
        
        Returns:
            A set of all causally incomparable values
        """
        return {v for v, _, _ in self._values}

    def apply_operation(self, operation: Any, metadata: Any = None) -> None:
        """Apply a write operation to this replica.
        
        Args:
            operation: The value that was written
            metadata: Dict with 'replica_id' and 'vv' (version vector)
        """
        if metadata is None:
            return
        vv = metadata["vv"]
        rid = metadata.get("replica_id", "")
        # Обновляем свой vv (покомпонентный max)
        for k, val in vv.items():
            self._vv[k] = max(self._vv.get(k, 0), val)
        self._apply(operation, vv, rid)

    def get_operations(self) -> List[tuple]:
        """Get all unsync'd operations.
        
        Returns:
            List of (operation, metadata) tuples
        """
        return [
            (v, {"replica_id": rid, "vv": dict(vv)})
            for v, vv, rid in self._values
        ]

    def __eq__(self, other: Any) -> bool:
        """Check if two MV registers have the same values."""
        if not isinstance(other, MVRegister):
            return False
        s1 = {(v, tuple(sorted(vv.items()))) for v, vv, _ in self._values}
        s2 = {(v, tuple(sorted(vv.items()))) for v, vv, _ in other._values}
        return s1 == s2

    def __repr__(self) -> str:
        """Return string representation of the register state."""
        return f"MVRegister(values={self._values})"
