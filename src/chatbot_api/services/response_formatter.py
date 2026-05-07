from __future__ import annotations

from chatbot_api.schemas import ImprovementSuggestion


OUT_OF_SCOPE_MESSAGE = (
    "This question is outside the scope of this website. "
    "I can help only with topics related to this website and its domain."
)


def _context_line(domain: str | None = None) -> str:
    if domain:
        return f"Here are some suggestions based on your request ({domain})."
    return "Here are some suggestions based on your request:"


def format_informational(summary: str, support: str | None = None, domain: str | None = None) -> str:
    lines = [
        _context_line(domain),
        "",
        "Overview:",
        f"- {summary.strip()}",
        "",
            "Key Points:",
    ]
    if support:
        lines.append(f"- Supporting website context: {support.strip()}")
    lines.extend(
        [
            "- Information is grounded in available website context.",
            "- If context is limited, confidence is reduced.",
            "",
            "Suggested Next Step:",
            "- You can use this as a starting point and confirm details on the referenced section.",
        ]
    )
    return "\n".join(lines)


def format_recommendation(
    goal: str,
    option_1: tuple[str, str, str],
    option_2: tuple[str, str, str],
    final_recommendation: str,
    why_fit: str,
    domain: str | None = None,
) -> str:
    o1_name, _, _ = option_1
    o2_name, _, _ = option_2
    goal_text = (goal or "").strip().lower()

    if any(term in goal_text for term in ["compare", "last month", "month over month", "trend"]):
        intro = "Based on your month-over-month pattern, here are the most useful corrections:"
    elif any(term in goal_text for term in ["cut", "overspend", "reduce", "save"]):
        intro = "Here are the highest-impact corrections for reducing spend now:"
    else:
        intro = "Here are the most relevant corrections for your request:"

    options: list[str] = []
    seen: set[str] = set()
    for item in [final_recommendation, o1_name, o2_name]:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(item.strip())

    lines = [intro]
    for item in options[:3]:
        lines.append(f"- {item}")
    return "\n".join(lines)


def format_betterment_plan(
    items: list[ImprovementSuggestion],
    summary: str,
    quick_wins: list[str],
    strategic: list[str],
    domain: str | None = None,
) -> str:
    lines = [_context_line(domain), "", "Summary:", f"- {summary}", "", "Key Improvement Areas:"]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"{index}. {item.area}",
                "Observation:",
                f"- {item.observation}",
                "Gap:",
                f"- {item.why_it_matters}",
                "Recommendation:",
                f"- {item.recommendation}",
                "Expected Impact:",
                f"- {item.expected_impact}",
                "Priority:",
                f"- {item.priority.capitalize()}",
            ]
        )

    lines.extend(["", "Quick Wins:"])
    for item in quick_wins[:3]:
        lines.append(f"- {item}")

    lines.extend(["", "Strategic Improvements:"])
    for item in strategic[:5]:
        lines.append(f"- {item}")

    return "\n".join(lines)


def format_audit_summary(strengths: list[str], weaknesses: list[str], quick_wins: list[str], strategic: list[str], domain: str | None = None) -> str:
    return "\n".join(
        [
            _context_line(domain),
            "",
            "Overall View:",
            "- The website appears to have a solid base with opportunities to improve usability and outcomes.",
            "",
            "Strengths:",
            *[f"- {item}" for item in (strengths or ["None identified yet"])],
            "",
            "Weaknesses:",
            *[f"- {item}" for item in (weaknesses or ["None identified yet"])],
            "",
            "Opportunities:",
            *[f"- {item}" for item in (strategic[:3] or ["No major opportunities identified yet"])],
            "",
            "Suggested Next Steps:",
            *[f"- {item}" for item in (quick_wins[:3] or ["No immediate next steps identified yet"])],
        ]
    )


def format_troubleshooting(problem: str, causes: list[str], steps: list[str], escalation: str, domain: str | None = None) -> str:
    return "\n".join(
        [
            _context_line(domain),
            "",
            "Problem Understanding:",
            f"- {problem}",
            "",
            "Possible Causes:",
            *[f"- {item}" for item in causes[:4]],
            "",
            "Solution Steps:",
            *[f"{i + 1}. {step}" for i, step in enumerate(steps[:5])],
            "",
            "If Issue Persists:",
            f"- {escalation}",
            "",
            "Suggested Next Step:",
            "- Start with Step 1 and I can refine based on what you observe.",
        ]
    )


def format_navigation_help(intent: str, location: str, steps: list[str], domain: str | None = None) -> str:
    return "\n".join(
        [
            _context_line(domain),
            "",
            "What You’re Looking For:",
            f"- {intent}",
            "",
            "Where to Find It:",
            f"- {location}",
            "",
            "Steps:",
            *[f"{i + 1}. {step}" for i, step in enumerate(steps[:5])],
        ]
    )


def format_research_benchmark(current_state: str, patterns: list[str], gaps: list[str], recommendations: list[str], expected_outcome: str, domain: str | None = None) -> str:
    return "\n".join(
        [
            _context_line(domain),
            "",
            "Current State (Website-Based):",
            f"- {current_state}",
            "",
            "Industry Patterns:",
            *[f"- {item}" for item in patterns[:5]],
            "",
            "Gap Analysis:",
            *[f"- {item}" for item in gaps[:5]],
            "",
            "Recommendations:",
            *[f"- {item}" for item in recommendations[:7]],
            "",
            "Likely Outcome:",
            f"- {expected_outcome}",
            "",
            "Suggested Next Step:",
            "- Pick one recommendation to trial first, then review results.",
        ]
    )
