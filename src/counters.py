from typing import Dict, Any
from .crdt_base import CvRDT


class GrowOnlyCounter(CvRDT):
    """Grow-only Counter (State-based CvRDT).
    
    A counter that can only increase. Each replica maintains its own counter
    value, and the total value is the sum of all replica counters.
    
    Merge takes the maximum value for each replica.
    
    Example:
        >>> c1 = GrowOnlyCounter()
        >>> c2 = GrowOnlyCounter()
        >>> c1.increment('replica_1', 5)
        >>> c2.increment('replica_2', 3)
        >>> c1.merge(c2)
        >>> c1.value()
        8
    """

    def __init__(self) -> None:
        """Initialize a grow-only counter at 0.""" 
        self._counts: Dict[str, int] = {}

    def increment(self, replica_id: str, value: int = 1) -> None:
        """Increment the counter for a specific replica.
        
        Args:
            replica_id: The ID of the replica incrementing the counter
            value: The amount to increment by (default 1)
        """
        # += потому что инкремент — это накопление
        self._counts[replica_id] = self._counts.get(replica_id, 0) + value

    def value(self) -> int:
        """Get the current total value of the counter.
        
        Returns:
            The sum of all replica counters
        """
        return sum(self._counts.values())

    def merge(self, other: "GrowOnlyCounter") -> None:
        """Merge another grow-only counter into this one.
        
        For each replica, keep the maximum count value.
        """
        for replica_id, count in other._counts.items():
            current = self._counts.get(replica_id, 0)
            # max — потому что другая реплика может знать больше про свой счётчик
            self._counts[replica_id] = max(current, count)

    def __eq__(self, other: Any) -> bool:
        """Check if two grow-only counters have the same value."""
        if not isinstance(other, GrowOnlyCounter):
            return False
        return self._counts == other._counts

    def __repr__(self) -> str:
        """Return string representation of the counter."""
        return f"GrowOnlyCounter({self._counts})"


class PNCounter(CvRDT):
    """Positive-Negative Counter (State-based CvRDT).
    
    A counter that supports both increment and decrement operations.
    Uses two grow-only counters internally: one for increments (P) and
    one for decrements (N).
    
    The value is: value() = P.value() - N.value()
    
    Example:
        >>> c = PNCounter()
        >>> c.increment('replica_1', 5)
        >>> c.decrement('replica_1', 2)
        >>> c.value()
        3
    """

    def __init__(self) -> None:
        """Initialize a PN-counter at 0."""
        self._p = GrowOnlyCounter()  # инкременты
        self._n = GrowOnlyCounter()  # декременты (тоже растут, но вычитаются)

    def increment(self, replica_id: str, value: int = 1) -> None:
        """Increment the counter for a specific replica.
        
        Args:
            replica_id: The ID of the replica incrementing the counter
            value: The amount to increment by (default 1)
        """
        self._p.increment(replica_id, value)

    def decrement(self, replica_id: str, value: int = 1) -> None:
        """Decrement the counter for a specific replica.
        
        Args:
            replica_id: The ID of the replica decrementing the counter
            value: The amount to decrement by (default 1)
        """
        self._n.increment(replica_id, value)

    def value(self) -> int:
        """Get the current total value of the counter.
        
        Returns:
            The difference: (sum of increments) - (sum of decrements)
        """
        return self._p.value() - self._n.value()

    def merge(self, other: "PNCounter") -> None:
        """Merge another PN-counter into this one.
        
        Merges the positive and negative components separately.
        """
        self._p.merge(other._p)
        self._n.merge(other._n)

    def __eq__(self, other: Any) -> bool:
        """Check if two PN-counters have the same value."""
        if not isinstance(other, PNCounter):
            return False
        return self._p == other._p and self._n == other._n

    def __repr__(self) -> str:
        """Return string representation of the counter."""
        return f"PNCounter(P={self._p}, N={self._n})"