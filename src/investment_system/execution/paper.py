from investment_system.execution.base import BaseExecutor, Fill, Order

class PaperExecutor(BaseExecutor):
    def execute(self, orders: list[Order]) -> list[Fill]:
        raise NotImplementedError("paper execution belongs to roadmap phase 8")
