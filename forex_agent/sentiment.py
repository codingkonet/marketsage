import yfinance as yf

_POSITIVE = {
    "bullish","surge","rally","gain","rise","positive","strong","growth","beat",
    "record","upgrade","buy","outperform","above","profit","boost","high","win",
    "recovery","climb","momentum","breakout","opportunity","optimistic","peak",
}
_NEGATIVE = {
    "bearish","drop","fall","decline","loss","weak","miss","crash","fear","sell",
    "downgrade","underperform","below","concern","risk","warn","cut","low","plunge",
    "recession","contraction","sell-off","selloff","dump","collapse","trouble",
}


def analyze_sentiment(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
    except Exception:
        news = []

    if not news:
        return {"score": 0.0, "label": "Neutral", "headlines": [], "article_count": 0}

    total_pos = total_neg = 0
    headlines = []

    for article in news[:15]:
        title = (article.get("title") or "").lower()
        words = set(title.replace("-", " ").split())
        pos = len(words & _POSITIVE)
        neg = len(words & _NEGATIVE)
        total_pos += pos
        total_neg += neg
        sent = "positive" if pos > neg else "negative" if neg > pos else "neutral"
        headlines.append({"title": article.get("title", ""), "sentiment": sent})

    net = total_pos - total_neg
    n = len(news[:15])
    score = round(net / max(n, 1), 2)
    label = "Bullish" if score > 0.15 else "Bearish" if score < -0.15 else "Neutral"

    return {
        "score": score,
        "label": label,
        "headlines": headlines[:6],
        "article_count": n,
    }
