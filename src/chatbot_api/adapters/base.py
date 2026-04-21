from typing import Protocol


class Adapter(Protocol):
    def get_user_context(self, user_id: str, tenant_id: str) -> dict:
        ...

    def get_domain_entities(self, query: str, user_id: str, tenant_id: str) -> dict:
        ...

    def run_action(self, action_name: str, params: dict, user_id: str, tenant_id: str) -> dict:
        ...

    def policy_checks(self, input_text: str, candidate_output: str, tenant_id: str) -> dict:
        ...
