class PNSet(CvRDT):
    def __init__(self) -> None:
        self._adds: Set[tuple] = set()
        self._removes: Set[tuple] = set()

    def add(self, element: Any, uid: str) -> None:
        self._adds.add((element, uid))

    def remove(self, element: Any, uid: str) -> None:
        self._removes.add((element, uid))

    def contains(self, element: Any) -> bool:
        for (el, uid) in self._adds:
            if el == element and (el, uid) not in self._removes:
                return True
        return False

    def elements(self) -> Set[Any]:
        result = set()
        for (el, uid) in self._adds:
            if (el, uid) not in self._removes:
                result.add(el)
        return result

    def merge(self, other: "PNSet") -> None:
        self._adds |= other._adds
        self._removes |= other._removes

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PNSet):
            return False
        return self._adds == other._adds and self._removes == other._removes

    def __repr__(self) -> str:
        return f"PNSet(adds={self._adds}, removes={self._removes})"