import os
import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs, urljoin
import requests

from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from summarizer import summarize

app = Flask(__name__)

REGISTRATION = os.getenv("REGISTRATION", "FA23-BDS-033")
NEWS_SOURCE = "China Daily"
NEWS_DOMAIN = "chinadaily.com.cn"


def create_driver():
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1365,900")

    return webdriver.Chrome(options=options)



def find_article(keyword):
    homepage = "https://www.chinadaily.com.cn/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        homepage, headers=headers, timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    query = keyword.lower().strip()

    # Treat "artificial intelligence" and "AI" as equivalent.
    ai_query = (
        "artificial intelligence" in query
        or re.search(r"\bai\b", query) is not None
    )

    candidates = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        article_url = urljoin(homepage, link["href"])
        parsed = urlparse(article_url)
        host = (parsed.hostname or "").lower()

        if not (
            host == "chinadaily.com.cn"
            or host.endswith(".chinadaily.com.cn")
        ):
            continue

        if not parsed.path.startswith("/a/"):
            continue

        if not title or article_url in seen:
            continue

        seen.add(article_url)
        title_lower = title.lower()

        if ai_query and re.search(r"\bai\b", title_lower):
            score = 10
        else:
            words = re.findall(r"[a-z0-9]+", query)
            words = [
                word for word in words
                if word not in {"the", "a", "an", "for", "of", "in"}
            ]
            score = sum(
                1 for word in words
                if re.search(
                    r"\b" + re.escape(word) + r"\b",
                    title_lower
                )
            )

        if score > 0:
            candidates.append((score, title, article_url))

    if not candidates:
        raise RuntimeError(
            "No matching article title was found on the "
            "China Daily homepage. Try a keyword related "
            "to a current headline."
        )

    # Highest title-match score; preserve homepage order for ties.
    candidates.sort(key=lambda item: item[0], reverse=True)
    score, title, article_url = candidates[0]

    print("Matched article title:", title)
    print("Matched article URL:", article_url)

    return article_url


def extract_article(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        )
    }

    response = requests.get(
        url, headers=headers, timeout=20
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(
        ["script", "style", "nav", "footer", "header"]
    ):
        element.decompose()

    article = soup.find("article")

    if article:
        paragraphs = article.find_all("p")
    else:
        paragraphs = soup.find_all("p")

    text = " ".join(
        p.get_text(" ", strip=True)
        for p in paragraphs
    )

    text = re.sub(r"\s+", " ", text).strip()

    if len(text.split()) < 40:
        raise RuntimeError(
            "The article text could not be extracted. "
            "The website may require different selectors."
        )

    return text


@app.route("/", methods=["GET"])
def home():
    return (
        f"<h1>Selenium News API</h1>"
        f"<p>Registration Number: {REGISTRATION}</p>"
        f"<p>News Source: {NEWS_SOURCE}</p>"
        f"<p>API: /get?keyword=your_keyword</p>"
    )


@app.route("/get", methods=["GET"])
def get_news():
    keyword = request.args.get("keyword", "").strip()

    if not keyword:
        return jsonify({
            "error": "Please provide a keyword."
        }), 400

    try:
        url = find_article(keyword)
        article_text = extract_article(url)
        summary = summarize(article_text)

        return jsonify({
            "registration": REGISTRATION,
            "newssource": NEWS_SOURCE,
            "keyword": keyword,
            "url": url,
            "summary": summary
        })

    except Exception as exc:
        app.logger.exception("News retrieval failed")
        return jsonify({
            "registration": REGISTRATION,
            "newssource": NEWS_SOURCE,
            "keyword": keyword,
            "url": "",
            "summary": "",
            "error": str(exc)
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
