# 后端 联网搜索工具 — Tavily API + DuckDuckGo 兜底 + 天气
import urllib.request
import urllib.parse
import json
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


def search_internet(query: str, max_results: int = 5) -> str:
    """后端 联网搜索 — Tavily 优先，不可用则降级 DDG"""
    if settings.tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.tavily_api_key)
            response = client.search(
                query=query, max_results=max_results,
                search_depth="advanced", days=30,
            )
            results = response.get("results", [])
            if results:
                lines = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "无标题")
                    url = r.get("url", "无链接")
                    content = r.get("content", "无摘要")
                    lines.append(f"{i}. {title}\n   链接: {url}\n   摘要: {content}\n")
                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Tavily 失败，降级 DDG: {str(e)[:80]}")

    # 后端 DDG 兜底
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
        if not results:
            return f"未找到与「{query}」相关的结果"
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("href", "无链接")
            content = r.get("body", "无摘要")
            lines.append(f"{i}. {title}\n   链接: {url}\n   摘要: {content}\n")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)[:100]}")
        return f"搜索失败: {str(e)[:200]}"


def fetch_weather(city: str) -> str:
    """后端 查询城市实时天气（wttr.in 免费 API）"""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=zh"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        current = data.get("current_condition", [{}])[0]
        return (
            f"城市: {city}\n"
            f"温度: {current.get('temp_C', '?')}°C\n"
            f"天气: {current.get('weatherDesc', [{}])[0].get('value', '?')}\n"
            f"湿度: {current.get('humidity', '?')}%\n"
            f"风速: {current.get('windspeedKmph', '?')} km/h"
        )
    except Exception as e:
        logger.warning(f"天气查询失败: {city} - {e}")
        return f"天气查询失败: {str(e)}"


SEARCH_TOOL_SCHEMAS = {
    "search_internet": {
        "name": "search_internet",
        "description": "搜索最新信息（优先 Tavily API，自动降级 DuckDuckGo）。查新闻/趋势/数据时必调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最多返回条数，默认 5"}
            },
            "required": ["query"]
        }
    },
    "fetch_weather": {
        "name": "fetch_weather",
        "description": "查询指定城市的实时天气信息",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名称"}},
            "required": ["city"]
        }
    }
}
