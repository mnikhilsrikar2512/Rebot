import re

from chatbot_api.config import settings


class LocalModelRuntime:
    def generate_account_response(
        self,
        normalized_query: str,
        user_context: dict,
        insights: dict,
        verbose: bool = False,
        runtime_settings: dict | None = None,
    ) -> tuple[str, float, list[str]]:
        missing_fields: list[str] = []
        if not user_context:
            missing_fields.extend(["user_context", "overview", "improvements"]) 
            return (
                "I can help with your account, but I need your latest account data first. "
                "Please sync your account or ask your app admin to enable context access.",
                0.35,
                missing_fields,
            )

        name = user_context.get("name", "there")
        overview = user_context.get("overview")
        strengths = user_context.get("strengths", [])
        improvements = user_context.get("improvements", [])
        score = user_context.get("score")

        if overview is None:
            missing_fields.append("overview")
        if not improvements:
            missing_fields.append("improvements")

        style = str((runtime_settings or {}).get("response_style") or "concise").lower()
        show_verdict = bool((runtime_settings or {}).get("show_verdict", True))
        max_recommendations = int((runtime_settings or {}).get("max_recommendations", 3) or 3)

        recommendations = list(insights.get("insight_candidates", improvements))
        top_n = max(1, min(5, max_recommendations))
        top_match = re.search(r"\btop\s+(\d+)\b", normalized_query)
        if top_match:
            try:
                top_n = max(1, min(5, int(top_match.group(1))))
            except ValueError:
                top_n = 3
        recommendations = recommendations[:top_n]
        asks_explanation = any(term in normalized_query for term in ["explain", "why", "details", "detailed", "breakdown"])
        is_admin = bool(user_context.get("is_admin"))
        platform_summary = user_context.get("platform_summary") or {}
        asks_platform = any(k in normalized_query for k in ["all users", "platform", "team", "overall users"])
        asks_overspending = any(k in normalized_query for k in ["overspending", "overspend", "spending too much"])
        budget_utilization = user_context.get("budget_utilization")
        balance = user_context.get("balance")

        lines: list[str] = []

        greeting = f"Hi {name}. "

        if asks_overspending and show_verdict:
            if is_admin and platform_summary:
                lines.append(
                    greeting + "Verdict: Platform spend is currently controlled, with a healthy net this month."
                )
            elif balance is not None:
                if balance < 0:
                    lines.append(greeting + "Verdict: Yes, you are overspending this month (net is negative).")
                elif isinstance(budget_utilization, (int, float)) and budget_utilization >= 90:
                    lines.append(
                        greeting + f"Verdict: High overspending risk ({budget_utilization:.1f}% budget used)."
                    )
                elif isinstance(budget_utilization, (int, float)) and budget_utilization >= 75:
                    lines.append(
                        greeting + f"Verdict: Moderate overspending risk ({budget_utilization:.1f}% budget used)."
                    )
                else:
                    lines.append(greeting + "Verdict: No major overspending signal right now.")
        elif show_verdict:
            if balance is not None and isinstance(balance, (int, float)):
                if balance >= 0:
                    lines.append(greeting + f"Verdict: You are net positive this month (INR {balance:,.0f}).")
                else:
                    lines.append(greeting + f"Verdict: You are net negative this month (INR {balance:,.0f}).")
            else:
                lines.append(greeting + f"Verdict: {overview or 'Account summary is available.'}")

        if recommendations:
            lines.append("Actions:")
            for item in recommendations:
                lines.append(f"- {item}")

        if style == "detailed":
            lines.append(f"Overview: {overview or 'Data not available yet.'}")
            lines.append(f"Current score: {score if score is not None else 'N/A'}")
            if strengths:
                lines.append(f"What is going well: {', '.join(strengths)}")

        if is_admin and asks_platform and platform_summary:
            lines.append("Platform snapshot:")
            lines.append(
                "- Active users: "
                f"{platform_summary.get('active_users', 0)}"
            )
            lines.append(
                "- Platform net: INR "
                f"{platform_summary.get('platform_balance', 0):,.0f}"
            )
            lines.append(
                "- Total platform transactions: "
                f"{platform_summary.get('platform_txns', 0)}"
            )

        if "how" in normalized_query or "better" in normalized_query:
            lines.append("Next step: Do the first action for 7 days, then review progress.")

        if verbose or asks_explanation:
            lines.append(
                "Explanation: Recommendations are prioritized using your current net position, budget usage, "
                "and top spend categories from your account data."
            )

        confidence = 0.9 if not missing_fields else 0.65
        return ("\n".join(lines), confidence, missing_fields)

    @property
    def model_name(self) -> str:
        return settings.default_model


runtime = LocalModelRuntime()
