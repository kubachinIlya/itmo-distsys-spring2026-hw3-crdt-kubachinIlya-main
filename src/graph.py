"""CRDT Implementations - Graph module.

Graph is implemented as a State-based CvRDT.
"""

from typing import Any, Tuple, Set
from .crdt_base import CvRDT


class AddOnlyDAG(CvRDT):
    """Add-only Monotonic Directed Acyclic Graph (DAG, State-based CvRDT).
    
    A graph where nodes and edges can only be added, never removed.
    The graph must remain acyclic (no cycles allowed).
    
    When attempting to add an edge that would create a cycle, the operation
    is rejected (returns False).
    
    Merge operation combines all nodes and edges from both graphs,
    checking acyclicity.
    
    Example:
        >>> g1 = AddOnlyDAG()
        >>> g2 = AddOnlyDAG()
        >>> g1.add_node('A')
        >>> g1.add_node('B')
        >>> g1.add_edge('A', 'B')  # True, no cycle
        True
        >>> g1.add_edge('B', 'A')  # False, would create cycle
        False
        >>> g2.add_node('C')
        >>> g2.add_edge('B', 'C')
        >>> g1.merge(g2)
        >>> g1.nodes()
        {'A', 'B', 'C'}
        >>> g1.edges()
        {('A', 'B'), ('B', 'C')}
    """

    def __init__(self) -> None:
        """Initialize an empty DAG."""
        self._nodes: Set[Any] = set()
        self._edges: Set[Tuple[Any, Any]] = set()

    def add_node(self, node: Any) -> None:
        """Add a node to the graph.
        
        Args:
            node: The node to add (can be any hashable type)
        """
        self._nodes.add(node)

    def _has_path(self, start: Any, target: Any) -> bool:
        visited = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            for (f, t) in self._edges:
                if f == node:
                    stack.append(t)
        return False
    
    def add_edge(self, from_node: Any, to_node: Any) -> bool:
        """Add a directed edge from from_node to to_node.
        
        Args:
            from_node: The source node
            to_node: The destination node
        
        Returns:
            True if edge was added successfully
            False if adding the edge would create a cycle
        
        Note:
            If nodes don't exist, they are added automatically.
        """
        # Автоматически добавляем узлы
        self._nodes.add(from_node)
        self._nodes.add(to_node)

        if from_node == to_node:
            return False
        if (from_node, to_node) in self._edges:
            return True  # уже есть, не цикл, идемпотентно
        if self._has_path(to_node, from_node):
            return False  # создаст цикл
        self._edges.add((from_node, to_node))
        return True

    def has_edge(self, from_node: Any, to_node: Any) -> bool:
        """Check if a directed edge exists.
        
        Args:
            from_node: The source node
            to_node: The destination node
        
        Returns:
            True if edge from_node -> to_node exists
        """
        # TODO: Implement
        return (from_node, to_node) in self._edges

    def nodes(self) -> Set[Any]:
        """Return all nodes in the graph."""
        return set(self._nodes)


    def edges(self) -> Set[Tuple[Any, Any]]:
        """Return all edges in the graph.
        
        Returns:
            A set of tuples (from_node, to_node)
        """
        return set(self._edges)

    def _has_cycle(self) -> bool:
        # Стандартный DFS-детектор циклов
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self._nodes}

        def dfs(node):
            color[node] = GRAY
            for (f, t) in self._edges:
                if f != node:
                    continue
                if color[t] == GRAY:
                    return True
                if color[t] == WHITE and dfs(t):
                    return True
            color[node] = BLACK
            return False

        for n in self._nodes:
            if color[n] == WHITE:
                if dfs(n):
                    return True
        return False
    
    def merge(self, other: "AddOnlyDAG") -> None:
        """Merge another DAG into this one.
        
        Combines all nodes and edges. If the merge would create a cycle,
        raises an exception (as both DAGs should be acyclic already,
        this indicates a logical error).
        
        Args:
            other: Another DAG to merge
        
        Raises:
            ValueError: If merging would create a cycle (shouldn't happen
                       if both DAGs are valid)
        """
        merged_nodes = self._nodes | other._nodes
        merged_edges = self._edges | other._edges

        # Проверяем цикл во временной копии
        old_nodes, old_edges = self._nodes, self._edges
        self._nodes, self._edges = merged_nodes, merged_edges
        if self._has_cycle():
            self._nodes, self._edges = old_nodes, old_edges
            raise ValueError("Merge would create a cycle")
        # иначе self уже обновлён

    def __eq__(self, other: Any) -> bool:
        """Check if two DAGs have the same nodes and edges."""
        if not isinstance(other, AddOnlyDAG):
            return False
        return self._nodes == other._nodes and self._edges == other._edges

    def __repr__(self) -> str:
        """Return string representation of the DAG."""
        return f"AddOnlyDAG(nodes={self._nodes}, edges={self._edges})"