import re


COMMON_REPLACEMENTS = {
    "gve": "give",
    "acnt": "account",
    "accnt": "account",
    "overveiw": "overview",
    "ovrview": "overview",
    "hw": "how",
    "bttr": "better",
    "sugst": "suggest",
    "usge": "usage",
    "shud": "should",
    "chnge": "change",
}


def normalize_user_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.strip().lower())
    words = compact.split(" ")
    normalized = [COMMON_REPLACEMENTS.get(w, w) for w in words]
    return " ".join(normalized)
