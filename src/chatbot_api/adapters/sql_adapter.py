from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text

from chatbot_api.adapters.base import Adapter
from chatbot_api.config import settings


class SQLServerAdapter(Adapter):
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self._users_has_tenant_id = self._has_column("users", "tenant_id")
        self._has_tenant_user_map = self._has_table("chatbot_tenant_users")

    def _has_table(self, table_name: str) -> bool:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS total
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = :table_name
                    """
                ),
                {"table_name": table_name},
            ).scalar_one()
        return bool(value)

    def _has_column(self, table_name: str, column_name: str) -> bool:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS total
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
                    """
                ),
                {"table_name": table_name, "column_name": column_name},
            ).scalar_one()
        return bool(value)

    def _assert_tenant_access(self, tenant_id: str, db_user_id: int) -> None:
        if self._users_has_tenant_id:
            with self.engine.connect() as conn:
                exists = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS total
                        FROM users
                        WHERE id = :user_id
                          AND CAST(tenant_id AS NVARCHAR(100)) = :tenant_id
                        """
                    ),
                    {"user_id": db_user_id, "tenant_id": tenant_id},
                ).scalar_one()
            if not exists:
                raise PermissionError("User does not belong to tenant")
            return

        if self._has_tenant_user_map:
            with self.engine.connect() as conn:
                exists = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS total
                        FROM chatbot_tenant_users
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        """
                    ),
                    {"tenant_id": tenant_id, "user_id": db_user_id},
                ).scalar_one()
            if not exists:
                raise PermissionError("User does not belong to tenant")
            return

        if settings.tenant_isolation_enforced:
            raise RuntimeError("Tenant isolation metadata missing (users.tenant_id or chatbot_tenant_users)")

    def _tenant_filter_clause(self, alias: str = "t") -> str:
        if self._users_has_tenant_id:
            return (
                f"EXISTS (SELECT 1 FROM users tu "
                f"WHERE tu.id = {alias}.user_id AND CAST(tu.tenant_id AS NVARCHAR(100)) = :tenant_id)"
            )
        if self._has_tenant_user_map:
            return (
                f"EXISTS (SELECT 1 FROM chatbot_tenant_users tm "
                f"WHERE tm.user_id = {alias}.user_id AND tm.tenant_id = :tenant_id)"
            )
        return "1=1"

    def _resolve_user(self, user_id: str, tenant_id: str) -> dict | None:
        normalized = str(user_id).strip().lower()
        if not normalized.isdigit():
            return None
        db_user_id = int(normalized)
        self._assert_tenant_access(tenant_id, db_user_id)
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT TOP 1 id, name, email, role, status
                    FROM users
                    WHERE id = :id
                    """
                ),
                {"id": db_user_id},
            ).mappings().first()
            return dict(row) if row else None

    def _build_user_context(self, db_user_id: int) -> dict:
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)

        with self.engine.connect() as conn:
            summary_row = conn.execute(
                text(
                    """
                    SELECT
                        SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS total_income,
                        SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) AS total_expense,
                        COUNT(*) AS total_txns
                    FROM transactions
                    WHERE user_id = :user_id
                      AND date >= :month_start
                      AND (is_deleted = 0 OR is_deleted IS NULL)
                    """
                ),
                {"user_id": db_user_id, "month_start": month_start},
            ).mappings().first()

            top_category_row = conn.execute(
                text(
                    """
                    SELECT TOP 1 c.name AS category_name, SUM(ABS(t.amount)) AS spend
                    FROM transactions t
                    JOIN categories c ON c.id = t.category_id
                    WHERE t.user_id = :user_id
                      AND t.amount < 0
                      AND (t.is_deleted = 0 OR t.is_deleted IS NULL)
                    GROUP BY c.name
                    ORDER BY spend DESC
                    """
                ),
                {"user_id": db_user_id},
            ).mappings().first()

            budget_row = conn.execute(
                text(
                    """
                    SELECT SUM(amount) AS active_budget
                    FROM budgets
                    WHERE user_id = :user_id
                      AND start_date <= CAST(GETDATE() AS DATE)
                      AND end_date >= CAST(GETDATE() AS DATE)
                    """
                ),
                {"user_id": db_user_id},
            ).mappings().first()

        total_income = float(summary_row["total_income"] or 0)
        total_expense = float(summary_row["total_expense"] or 0)
        total_txns = int(summary_row["total_txns"] or 0)
        balance = total_income - total_expense

        top_category_name = top_category_row["category_name"] if top_category_row else None
        top_category_spend = float(top_category_row["spend"] or 0) if top_category_row else 0.0
        active_budget = float(budget_row["active_budget"] or 0) if budget_row else 0.0

        budget_utilization = None
        if active_budget > 0:
            budget_utilization = round((total_expense / active_budget) * 100, 1)

        strengths: list[str] = []
        improvements: list[str] = []

        if balance >= 0:
            strengths.append("You are net positive this month")
        if total_txns >= 10:
            strengths.append("You are consistently logging transactions")

        if budget_utilization is None:
            improvements.append("Create an active budget to get tighter spend guidance")
        elif budget_utilization > 90:
            improvements.append("You are near budget limit; reduce discretionary spending this week")
        elif budget_utilization > 75:
            improvements.append("Budget use is high; prioritize essentials for the rest of this period")

        if balance < 0:
            improvements.append("Your net balance is negative; cut low-priority expenses by 10-15%")

        if top_category_name:
            improvements.append(
                f"Top spend category is {top_category_name}; set a cap to reduce overspend quickly"
            )

        if not improvements:
            improvements.append("Maintain current habits and review spend categories weekly")

        score = 65
        if balance >= 0:
            score += 15
        if budget_utilization is not None and budget_utilization < 75:
            score += 10
        if total_txns >= 10:
            score += 5
        score = max(1, min(99, score))

        overview = (
            f"Income INR {total_income:,.0f}, expense INR {total_expense:,.0f}, "
            f"net INR {balance:,.0f} this month."
        )

        return {
            "overview": overview,
            "strengths": strengths,
            "improvements": improvements,
            "score": score,
            "balance": balance,
            "budget_utilization": budget_utilization,
            "top_category_name": top_category_name,
            "top_category_spend": top_category_spend,
            "tx_count": total_txns,
        }

    def _build_admin_context(self, db_user_id: int, tenant_id: str) -> dict:
        base = self._build_user_context(db_user_id)
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)

        tenant_filter = self._tenant_filter_clause("t")
        with self.engine.connect() as conn:
            platform_row = conn.execute(
                text(
                    f"""
                    SELECT
                        COUNT(DISTINCT t.user_id) AS active_users,
                        SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) AS platform_income,
                        SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) AS platform_expense,
                        COUNT(*) AS platform_txns
                    FROM transactions t
                    WHERE t.date >= :month_start
                      AND (t.is_deleted = 0 OR t.is_deleted IS NULL)
                      AND {tenant_filter}
                    """
                ),
                {"month_start": month_start, "tenant_id": tenant_id},
            ).mappings().first()

        active_users = int(platform_row["active_users"] or 0)
        platform_income = float(platform_row["platform_income"] or 0)
        platform_expense = float(platform_row["platform_expense"] or 0)
        platform_balance = platform_income - platform_expense
        platform_txns = int(platform_row["platform_txns"] or 0)

        base["overview"] = (
            f"Admin view: platform income INR {platform_income:,.0f}, "
            f"expense INR {platform_expense:,.0f}, net INR {platform_balance:,.0f} this month."
        )
        base["strengths"] = [
            "You have platform-level visibility",
            f"Active users this month: {active_users}",
        ]
        base["improvements"] = [
            "Review top-spend users and categories weekly",
            "Set alert thresholds for unusual expense spikes",
            "Track budget adherence across all users",
        ]
        base["score"] = 93
        base["platform_summary"] = {
            "active_users": active_users,
            "platform_income": round(platform_income, 2),
            "platform_expense": round(platform_expense, 2),
            "platform_balance": round(platform_balance, 2),
            "platform_txns": platform_txns,
        }
        base["is_admin"] = True
        return base

    def get_user_context(self, user_id: str, tenant_id: str) -> dict:
        user = self._resolve_user(user_id, tenant_id)
        if not user:
            return {}
        role = str(user.get("role") or "user").lower()
        context = (
            self._build_admin_context(int(user["id"]), tenant_id)
            if role == "admin"
            else self._build_user_context(int(user["id"]))
        )
        context["name"] = user.get("name") or user.get("email") or user_id
        context["user_key"] = user_id
        context["tenant_id"] = tenant_id
        context["role"] = role
        return context

    def get_domain_entities(self, query: str, user_id: str, tenant_id: str) -> dict:
        user_context = self.get_user_context(user_id=user_id, tenant_id=tenant_id)
        return {
            "query": query,
            "insight_candidates": user_context.get("improvements", []),
            "score": user_context.get("score"),
            "source": "sqlserver",
        }

    def run_action(self, action_name: str, params: dict, user_id: str, tenant_id: str) -> dict:
        return {
            "action_name": action_name,
            "status": "not_implemented",
            "params": params,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

    def policy_checks(self, input_text: str, candidate_output: str, tenant_id: str) -> dict:
        return {"allowed": True, "reason": "ok"}


def build_sql_adapter() -> SQLServerAdapter | None:
    if not settings.database_url:
        return None
    return SQLServerAdapter(settings.database_url)
