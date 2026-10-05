"""Independent, deterministic planning tools. No bank or bureau integration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import APIRouter

router = APIRouter(prefix="/api/tools", tags=["Credit planning"])


class ToolInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


class LoanPlan(ToolInput):
    principal: float = Field(gt=0, le=100_000_000)
    annual_rate: float = Field(ge=0, le=60)
    months: int = Field(ge=1, le=600)
    monthly_extra: float = Field(default=0, ge=0, le=100_000_000)
    fee: float = Field(default=0, ge=0, le=100_000_000)


def payment(principal, annual_rate, months):
    rate = annual_rate / 1200
    return principal / months if rate == 0 else principal * rate / (1 - (1 + rate) ** -months)


def amortize(plan: LoanPlan):
    emi = payment(plan.principal, plan.annual_rate, plan.months)
    balance, interest_total, rows = plan.principal, 0.0, []
    for month in range(1, plan.months + 1):
        interest = balance * plan.annual_rate / 1200
        paid = min(balance + interest, emi + plan.monthly_extra)
        principal_paid = paid - interest
        balance = max(0, balance - principal_paid)
        interest_total += interest
        rows.append(dict(month=month, payment=round(paid, 2), principal=round(principal_paid, 2),
                         interest=round(interest, 2), balance=round(balance, 2)))
        if balance < 0.000001:
            break
    baseline_interest = emi * plan.months - plan.principal
    return dict(emi=round(emi, 2), interest=round(interest_total, 2),
                total=round(plan.principal + interest_total + plan.fee, 2),
                fee=plan.fee, payoff_months=len(rows), months_saved=plan.months - len(rows),
                interest_saved=round(max(0, baseline_interest - interest_total), 2), schedule=rows)


@router.post("/loan")
def loan_tool(plan: LoanPlan):
    return amortize(plan)


class Comparison(ToolInput):
    offers: list[LoanPlan] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def same_principal(self):
        if len({p.principal for p in self.offers}) != 1:
            raise ValueError("Compare offers for the same loan amount")
        return self


@router.post("/compare")
def compare_tool(data: Comparison):
    results = [amortize(p) for p in data.offers]
    return {"offers": results, "lowest_cost_index": min(range(len(results)), key=lambda i: results[i]["total"])}


class Affordability(ToolInput):
    income: float = Field(gt=0, le=100_000_000)
    expenses: float = Field(ge=0, le=100_000_000)
    existing_emis: float = Field(ge=0, le=100_000_000)
    reserve: float = Field(ge=0, le=100_000_000)
    target_dti: float = Field(default=35, gt=0, le=100)
    annual_rate: float = Field(ge=0, le=60)
    months: int = Field(ge=1, le=600)


@router.post("/affordability")
def affordability_tool(data: Affordability):
    cash = data.income - data.expenses - data.existing_emis - data.reserve
    capacity = max(0, min(cash, data.income * data.target_dti / 100 - data.existing_emis))
    return dict(monthly_capacity=round(capacity, 2),
                principal_capacity=round(capacity / payment(1, data.annual_rate, data.months), 2),
                current_dti=round(data.existing_emis / data.income * 100, 2),
                remaining_cash=round(cash, 2))


class Card(ToolInput):
    name: str = Field(min_length=1, max_length=60)
    limit: float = Field(gt=0, le=100_000_000)
    balance: float = Field(ge=0, le=100_000_000)


class Utilization(ToolInput):
    cards: list[Card] = Field(min_length=1, max_length=20)
    target: float = Field(default=30, ge=0, le=100)


@router.post("/utilization")
def utilization_tool(data: Utilization):
    total_limit = sum(c.limit for c in data.cards)
    total_balance = sum(c.balance for c in data.cards)
    return dict(utilization=round(total_balance / total_limit * 100, 2),
                total_limit=total_limit, total_balance=total_balance,
                available=round(max(0, total_limit - total_balance), 2),
                paydown=round(max(0, total_balance - total_limit * data.target / 100), 2),
                cards=[dict(name=c.name, utilization=round(c.balance / c.limit * 100, 2),
                            paydown=round(max(0, c.balance - c.limit * data.target / 100), 2)) for c in data.cards])


class Debt(ToolInput):
    name: str = Field(min_length=1, max_length=60)
    balance: float = Field(gt=0, le=100_000_000)
    annual_rate: float = Field(ge=0, le=60)
    minimum: float = Field(gt=0, le=100_000_000)


class Payoff(ToolInput):
    debts: list[Debt] = Field(min_length=1, max_length=20)
    extra: float = Field(default=0, ge=0, le=100_000_000)


def payoff(data: Payoff, strategy: Literal["avalanche", "snowball"]):
    balances = [d.balance for d in data.debts]
    budget = sum(d.minimum for d in data.debts) + data.extra
    interest_total, schedule, order = 0.0, [], []
    for month in range(1, 601):
        active = [i for i, b in enumerate(balances) if b > 0.000001]
        if not active:
            break
        priority = sorted(active, key=lambda i: (-data.debts[i].annual_rate, i) if strategy == "avalanche" else (balances[i], i))
        remaining = budget
        for i in active:
            interest = balances[i] * data.debts[i].annual_rate / 1200
            interest_total += interest
            balances[i] += interest
            paid = min(balances[i], data.debts[i].minimum)
            balances[i] -= paid
            remaining -= paid
        for i in priority:
            paid = min(balances[i], max(0, remaining))
            balances[i] -= paid
            remaining -= paid
        for i in active:
            if balances[i] < 0.000001:
                balances[i] = 0
                order.append(dict(name=data.debts[i].name, month=month))
        schedule.append(dict(month=month, payment=round(budget - remaining, 2), balance=round(sum(balances), 2)))
    completed = sum(balances) < 0.000001
    return dict(strategy=strategy, completed=completed, months=len(schedule) if completed else None,
                interest=round(interest_total, 2), remaining=round(sum(balances), 2),
                monthly_budget=round(budget, 2), order=order, schedule=schedule)


@router.post("/payoff")
def payoff_tool(data: Payoff):
    return {strategy: payoff(data, strategy) for strategy in ("avalanche", "snowball")}
