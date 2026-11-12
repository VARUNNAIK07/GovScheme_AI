from abc import ABC, abstractmethod

from contracts.schemas import WorkflowState


class Agent(ABC):
    """Small interface for deterministic workflow agents."""

    name: str

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        raise NotImplementedError

