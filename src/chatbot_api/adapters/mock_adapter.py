from copy import deepcopy

from chatbot_api.adapters.base import Adapter


MOCK_USER_DATA = {
    "tnt_demo": {
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
