class MVRegister(CmRDT):
    def __init__(self, replica_id: str = "A") -> None:
        self._replica_id = replica_id
        self._vv: Dict[str, int] = {}
        # Список (value, vv, replica_id) — replica_id исходного writer-а
        self._values: List[Tuple[Any, Dict[str, int], str]] = []

    def write(self, value: Any) -> None:
        self._vv[self._replica_id] = self._vv.get(self._replica_id, 0) + 1
        vv_copy = dict(self._vv)
        self._apply(value, vv_copy, self._replica_id)

    def _apply(self, value: Any, vv: Dict[str, int], replica_id: str) -> None:
        # Если новая операция устарела или совпадает — игнорируем
        for _, existing_vv, _ in self._values:
            cmp = _compare_vv(vv, existing_vv)
            if cmp in (-1, 0):
                return
        # Удаляем все dominated-значения
        self._values = [
            (v, vv2, rid) for v, vv2, rid in self._values
            if _compare_vv(vv2, vv) != -1
        ]
        self._values.append((value, dict(vv), replica_id))

    def read(self) -> set:
        return {v for v, _, _ in self._values}

    def apply_operation(self, operation: Any, metadata: Any = None) -> None:
        if metadata is None:
            return
        vv = metadata["vv"]
        rid = metadata.get("replica_id", "")
        # Обновляем свой vv (покомпонентный max)
        for k, val in vv.items():
            self._vv[k] = max(self._vv.get(k, 0), val)
        self._apply(operation, vv, rid)

    def get_operations(self) -> List[tuple]:
        return [
            (v, {"replica_id": rid, "vv": dict(vv)})
            for v, vv, rid in self._values
        ]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, MVRegister):
            return False
        s1 = {(v, tuple(sorted(vv.items()))) for v, vv, _ in self._values}
        s2 = {(v, tuple(sorted(vv.items()))) for v, vv, _ in other._values}
        return s1 == s2

    def __repr__(self) -> str:
        return f"MVRegister(values={self._values})"