"""
Smart Home Appliance Scheduler
================================
DSA-driven IoT device scheduler using:
  - Min-Heap (Priority Queue) for urgency-based task execution
  - Dijkstra's Algorithm for power-cost path optimization
  - BFS/DFS for device dependency resolution
  - Greedy Interval Scheduling for peak-load reduction

Author: Rohit Yadav (github.com/rohit-yadav-ece)
"""

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set
import math


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(order=True)
class Task:
    """Represents a scheduled appliance task. Ordered by priority score."""
    priority_score: float
    task_id: str = field(compare=False)
    device: str = field(compare=False)
    power_watts: float = field(compare=False)
    duration_min: int = field(compare=False)
    urgency: int = field(compare=False)          # 1 (low) - 10 (critical)
    earliest_start: int = field(compare=False)   # minute of day [0, 1440)
    deadline: int = field(compare=False)         # minute of day [0, 1440)
    dependencies: List[str] = field(default_factory=list, compare=False)

    def __repr__(self):
        return f"Task({self.task_id}, {self.device}, {self.power_watts}W, urgency={self.urgency})"


# ============================================================
# 1. MIN-HEAP PRIORITY SCHEDULER  —  O(log n) per insertion
# ============================================================

class PriorityScheduler:
    """
    Min-Heap based priority scheduler.
    Priority score = -(urgency * 10) + (deadline_slack / 60)
    Lower score = higher priority.
    """

    def __init__(self):
        self.heap: List[Task] = []
        self.completed: List[str] = []

    @staticmethod
    def compute_priority(task: Task, current_time: int) -> float:
        slack = max(task.deadline - current_time - task.duration_min, 0)
        return -(task.urgency * 10) + (slack / 60)

    def add_task(self, task: Task, current_time: int = 0):
        task.priority_score = self.compute_priority(task, current_time)
        heapq.heappush(self.heap, task)

    def pop_next(self) -> Task:
        if not self.heap:
            return None
        return heapq.heappop(self.heap)

    def peek(self) -> Task:
        return self.heap[0] if self.heap else None

    def __len__(self):
        return len(self.heap)


# ============================================================
# 2. DEPENDENCY GRAPH  —  BFS / DFS / Topological Sort
# ============================================================

class DependencyGraph:
    """
    Models device dependencies (e.g., WaterPump must run before Dishwasher).
    Uses adjacency list + BFS for level ordering + DFS for cycle detection.
    """

    def __init__(self):
        self.graph: Dict[str, List[str]] = defaultdict(list)
        self.nodes: Set[str] = set()

    def add_dependency(self, prerequisite: str, dependent: str):
        """prerequisite -> dependent (prerequisite must run first)."""
        self.graph[prerequisite].append(dependent)
        self.nodes.add(prerequisite)
        self.nodes.add(dependent)

    def bfs_levels(self, start: str) -> Dict[str, int]:
        """BFS — Returns level (distance) of each reachable node from start."""
        levels = {start: 0}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in self.graph[node]:
                if neighbor not in levels:
                    levels[neighbor] = levels[node] + 1
                    queue.append(neighbor)
        return levels

    def dfs_has_cycle(self) -> bool:
        """DFS — Detects cycles (a cycle = scheduling conflict / impossible)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.nodes}

        def visit(u):
            color[u] = GRAY
            for v in self.graph[u]:
                if color[v] == GRAY:
                    return True
                if color[v] == WHITE and visit(v):
                    return True
            color[u] = BLACK
            return False

        for node in self.nodes:
            if color[node] == WHITE:
                if visit(node):
                    return True
        return False

    def topological_order(self) -> List[str]:
        """Returns valid execution order respecting dependencies (Kahn's algorithm)."""
        in_degree = {node: 0 for node in self.nodes}
        for u in self.graph:
            for v in self.graph[u]:
                in_degree[v] += 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in self.graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected — schedule infeasible!")
        return order


# ============================================================
# 3. DIJKSTRA'S ALGORITHM  —  Power-cost optimal path
# ============================================================

class PowerPathOptimizer:
    """
    Uses Dijkstra's algorithm to find minimum-power-cost path between device states.
    Useful when: appliance has multiple operating modes with different power costs.
    """

    def __init__(self):
        self.graph: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def add_edge(self, from_state: str, to_state: str, power_cost: float):
        self.graph[from_state].append((to_state, power_cost))

    def shortest_power_path(self, start: str, end: str) -> Tuple[float, List[str]]:
        """Dijkstra — Returns (min_total_power, path)."""
        distances = {start: 0}
        previous = {start: None}
        pq = [(0, start)]
        visited = set()

        while pq:
            current_dist, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)

            if current == end:
                break

            for neighbor, weight in self.graph[current]:
                if neighbor in visited:
                    continue
                new_dist = current_dist + weight
                if new_dist < distances.get(neighbor, math.inf):
                    distances[neighbor] = new_dist
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        if end not in distances:
            return math.inf, []

        # Reconstruct path
        path = []
        node = end
        while node is not None:
            path.append(node)
            node = previous[node]
        return distances[end], path[::-1]


# ============================================================
# 4. GREEDY INTERVAL SCHEDULER  —  Peak-power reduction
# ============================================================

class GreedyIntervalScheduler:
    """
    Greedy algorithm to schedule tasks within a peak-power budget.
    Sorts tasks by deadline (Earliest Deadline First / EDF) and schedules
    them in non-overlapping time slots while respecting power budget.
    """

    def __init__(self, peak_power_budget: float):
        self.peak_power_budget = peak_power_budget
        self.schedule: List[Tuple[int, int, Task]] = []  # (start, end, task)
        self.power_usage: Dict[int, float] = defaultdict(float)  # minute -> watts

    def can_fit(self, task: Task, start_time: int) -> bool:
        """Check if task fits within power budget across all its minutes."""
        for t in range(start_time, start_time + task.duration_min):
            if self.power_usage[t] + task.power_watts > self.peak_power_budget:
                return False
        return True

    def schedule_tasks(self, tasks: List[Task]) -> Dict:
        """Schedule tasks greedily by Earliest Deadline First (EDF)."""
        # Sort by deadline (EDF heuristic)
        sorted_tasks = sorted(tasks, key=lambda t: (t.deadline, -t.urgency))

        scheduled = []
        rejected = []
        peak_before = sum(t.power_watts for t in tasks)
        peak_after = 0

        for task in sorted_tasks:
            scheduled_flag = False
            # Try every minute from earliest_start to (deadline - duration)
            for start in range(task.earliest_start,
                               max(task.earliest_start + 1, task.deadline - task.duration_min + 1)):
                if self.can_fit(task, start):
                    end = start + task.duration_min
                    self.schedule.append((start, end, task))
                    for t in range(start, end):
                        self.power_usage[t] += task.power_watts
                    scheduled.append(task)
                    scheduled_flag = True
                    break
            if not scheduled_flag:
                rejected.append(task)

        peak_after = max(self.power_usage.values()) if self.power_usage else 0
        reduction_pct = ((peak_before - peak_after) / peak_before * 100) if peak_before else 0

        return {
            "scheduled": scheduled,
            "rejected": rejected,
            "peak_power_before_W": round(peak_before, 2),
            "peak_power_after_W": round(peak_after, 2),
            "peak_reduction_pct": round(reduction_pct, 2),
            "total_scheduled": len(scheduled),
            "total_rejected": len(rejected),
        }


# ============================================================
# 5. MAIN ORCHESTRATOR
# ============================================================

class SmartHomeScheduler:
    """High-level orchestrator combining all 4 DSA techniques."""

    def __init__(self, peak_power_budget: float = 3000.0):
        self.priority_q = PriorityScheduler()
        self.dependencies = DependencyGraph()
        self.power_optimizer = PowerPathOptimizer()
        self.interval_scheduler = GreedyIntervalScheduler(peak_power_budget)
        self.tasks: List[Task] = []

    def add_task(self, task: Task):
        self.tasks.append(task)
        self.priority_q.add_task(task)
        for dep in task.dependencies:
            self.dependencies.add_dependency(dep, task.task_id)

    def run(self) -> Dict:
        # Validate no cyclic dependencies
        if self.dependencies.nodes and self.dependencies.dfs_has_cycle():
            return {"error": "Cyclic dependency detected — schedule infeasible."}

        # Run greedy interval scheduling
        result = self.interval_scheduler.schedule_tasks(self.tasks)
        return result


# ============================================================
# QUICK DEMO (run `python scheduler.py`)
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Smart Home Appliance Scheduler — Demo")
    print("=" * 60)

    scheduler = SmartHomeScheduler(peak_power_budget=3500.0)

    sample_tasks = [
        Task(0, "T1", "WashingMachine", 2000, 60, 7, 600, 900),
        Task(0, "T2", "Dishwasher",     1500, 90, 5, 660, 1080, dependencies=["T1"]),
        Task(0, "T3", "WaterHeater",    2500, 30, 9, 360, 480),
        Task(0, "T4", "AirConditioner", 1800, 120, 6, 720, 1200),
        Task(0, "T5", "OvenMicrowave",  1200, 20, 8, 1080, 1140),
        Task(0, "T6", "EV_Charger",     3000, 240, 4, 0, 360),
        Task(0, "T7", "PoolPump",        800, 180, 3, 480, 1200),
        Task(0, "T8", "Iron",            900, 15, 7, 540, 600),
    ]

    for t in sample_tasks:
        scheduler.add_task(t)

    result = scheduler.run()

    print(f"\nTotal tasks submitted   : {len(sample_tasks)}")
    print(f"Tasks scheduled         : {result['total_scheduled']}")
    print(f"Tasks rejected          : {result['total_rejected']}")
    print(f"Peak power BEFORE       : {result['peak_power_before_W']} W")
    print(f"Peak power AFTER        : {result['peak_power_after_W']} W")
    print(f"Peak-power reduction    : {result['peak_reduction_pct']}%")
    print("=" * 60)
