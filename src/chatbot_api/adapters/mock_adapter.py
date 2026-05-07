from copy import deepcopy

from chatbot_api.adapters.base import Adapter


MOCK_USER_DATA = {
    "tnt_demo": {
        "1": {
            "name": "System Admin",
            "overview": "Admin view: tenant spend is elevated in discretionary categories this month.",
            "strengths": ["Platform visibility", "Cross-user trend access"],
            "improvements": [
                "Review top-spend users weekly",
                "Set alerts for discretionary expense spikes",
                "Publish a budget adherence dashboard",
            ],
            "score": 92,
        },
        "2": {
            "name": "John Doe",
            "overview": "Income remains stable; expenses are trending up in dining and entertainment.",
            "strengths": ["Positive monthly balance", "Consistent budgeting habit"],
            "improvements": [
                "Cap dining spend for the next two weeks",
                "Shift one discretionary purchase to next month",
                "Track utility bills against a fixed threshold",
            ],
            "score": 82,
        },
        "3": {
            "name": "Jane Smith",
            "overview": "Strong net income with healthy side-income support.",
            "strengths": ["Diversified income", "Low transport spend"],
            "improvements": [
                "Automate monthly investment transfer",
                "Set a soft limit for shopping",
            ],
            "score": 87,
        },
        "4": {
            "name": "Priya Kapoor",
            "overview": "Budget utilization is high due to recurring and discretionary expenses.",
            "strengths": ["Reliable salary inflow", "Expense logging consistency"],
            "improvements": [
                "Pause nonessential subscriptions this month",
                "Reduce weekend discretionary spend by 15%",
                "Create category-level sub-budgets",
            ],
            "score": 71,
        },
        "5": {
            "name": "Arjun Mehta",
            "overview": "Current month is net negative and requires immediate spending controls.",
            "strengths": ["Regular transaction tracking"],
            "improvements": [
                "Cut low-priority purchases immediately",
                "Delay large discretionary orders",
                "Set a daily spend cap for the remainder of the month",
            ],
            "score": 62,
        },
        "usr_alex": {
            "name": "Alex",
            "overview": "Steady progress this month.",
            "strengths": ["Consistency", "Task completion"],
            "improvements": ["Prioritize top 3 tasks", "Reduce context switching"],
            "score": 78,
        },
        "usr_riya": {
            "name": "Riya",
            "overview": "Excellent output but with high workload stress.",
            "strengths": ["Execution speed", "Ownership"],
            "improvements": ["Delegate repetitive work", "Add buffer time to planning"],
            "score": 84,
        },
    }
}


class MockAdapter(Adapter):
    def get_user_context(self, user_id: str, tenant_id: str) -> dict:
        tenant_data = MOCK_USER_DATA.get(tenant_id, {})
        return deepcopy(tenant_data.get(user_id, {}))

    def get_domain_entities(self, query: str, user_id: str, tenant_id: str) -> dict:
        user_data = self.get_user_context(user_id=user_id, tenant_id=tenant_id)
        return {
            "query": query,
            "insight_candidates": user_data.get("improvements", []),
            "score": user_data.get("score"),
        }

    def run_action(self, action_name: str, params: dict, user_id: str, tenant_id: str) -> dict:
        return {
            "action_name": action_name,
            "status": "accepted",
            "params": params,
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

    def policy_checks(self, input_text: str, candidate_output: str, tenant_id: str) -> dict:
        banned = ["all users", "all accounts", "show everyone"]
        blocked = any(phrase in input_text.lower() for phrase in banned)
        return {"allowed": not blocked, "reason": "blocked_scope_request" if blocked else "ok"}
