"""Durable per-run/per-invocation reservations before each billable attempt."""
from decimal import Decimal
from pathlib import Path
import sqlite3
from uuid import uuid4


class BudgetExceeded(ValueError):
    pass


class RunBudget:
    """SQLite transactions preserve pending reservations through crash/restart."""
    def __init__(self,path: Path,run_limit: float,request_limit: float):
        self.path=path
        path.parent.mkdir(parents=True,exist_ok=True)
        self.run_limit,self.request_limit=Decimal(str(run_limit)),Decimal(str(request_limit))
        if not self.run_limit.is_finite() or not self.request_limit.is_finite() or not 0 < self.request_limit <= self.run_limit:
            raise ValueError("finite positive explicit budgets are required")
        with sqlite3.connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS policy (run_limit TEXT, request_limit TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS reservations (attempt_id TEXT PRIMARY KEY, cache_key TEXT, reserved TEXT, settled TEXT)")
            rows=db.execute("SELECT run_limit,request_limit FROM policy").fetchall()
            expected=(str(self.run_limit),str(self.request_limit))
            if rows and (len(rows)!=1 or tuple(Decimal(v) for v in rows[0]) != (self.run_limit,self.request_limit)):
                raise ValueError("cannot change the budget of an existing run")
            if not rows:
                db.execute("INSERT INTO policy VALUES (?,?)",expected)

    def reserve(self,cache_key: str,maximum: float) -> str:
        limit=Decimal(str(maximum))
        if not limit.is_finite() or limit < 0:
            raise ValueError("invalid reservation")
        with sqlite3.connect(self.path,timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            rows=db.execute("SELECT cache_key,reserved,settled FROM reservations").fetchall()
            total=sum((Decimal(settled if settled is not None else reserved) for _,reserved,settled in rows),Decimal(0))
            request=sum((Decimal(settled if settled is not None else reserved) for key,reserved,settled in rows if key==cache_key),Decimal(0))
            if total+limit > self.run_limit or request+limit > self.request_limit:
                raise BudgetExceeded("request_or_run_budget_insufficient")
            attempt=uuid4().hex
            db.execute("INSERT INTO reservations VALUES (?,?,?,NULL)",(attempt,cache_key,str(limit)))
            return attempt

    def settle(self,attempt_id: str,observed: float | None) -> float:
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT reserved,settled FROM reservations WHERE attempt_id=?",(attempt_id,)).fetchone()
            if row is None:
                raise ValueError("unknown budget reservation")
            amount=Decimal(row[0]) if observed is None else Decimal(str(observed))
            if not amount.is_finite() or amount < 0:
                raise ValueError("invalid settled amount")
            if row[1] is not None and Decimal(row[1]) != amount:
                raise ValueError("cannot rewrite an accounted attempt")
            # Keep NULL for unknown: durable conservative hold, not invented cost.
            if observed is not None:
                db.execute("UPDATE reservations SET settled=? WHERE attempt_id=?",(str(amount),attempt_id))
            return float(amount)

    def accounted(self) -> float:
        with sqlite3.connect(self.path) as db:
            return float(sum((Decimal(b if b is not None else a) for a,b in db.execute("SELECT reserved,settled FROM reservations")),Decimal(0)))
