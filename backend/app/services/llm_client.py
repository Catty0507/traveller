"""OpenAI 兼容接口的轻量封装:聊天 + 稳健 JSON 解析。

不依赖 response_format 等各家支持不一的参数,靠 prompt 约束 JSON 输出,
解析时兼容 markdown 代码围栏,保证通义/Kimi/GLM/DeepSeek 都能用。
"""

import json
import logging
import re

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """大模型调用失败或返回无法解析。"""


class LLMNotConfiguredError(LLMError):
    """未配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。"""


def is_configured() -> bool:
    s = get_settings()
    return bool(s.llm_api_key and s.llm_base_url and s.llm_model)


def not_configured_message() -> str:
    return "未配置大模型接口。请在 backend/.env 中填写 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 后重启服务"


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if not is_configured():
        raise LLMNotConfiguredError(not_configured_message())
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(
            api_key=s.llm_api_key,
            base_url=s.llm_base_url,
            timeout=s.llm_timeout_seconds,
            max_retries=2,
        )
    return _client


def extract_json(text: str) -> dict:
    """从模型返回文本中提取 JSON,兼容 ```json 围栏与前后杂文本。"""
    stripped = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if match:
        stripped = match.group(1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        # 最后再试一次:截取首个 { 到最后一个 } 之间的内容
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"模型返回的不是有效 JSON: {e}") from e


async def chat_json(system: str, user: str, client: AsyncOpenAI | None = None) -> dict:
    """调用 OpenAI 兼容接口并返回解析后的 JSON dict。

    使用流式接收:token 一边生成一边收,超时只约束块间等待,
    长输出(如 16 天行程攻略)不会因整体生成时间过长而超时。
    JSON 解析失败自动重试一次;网络/接口错误直接抛 LLMError(SDK 自带 2 次重试)。
    client 参数用于测试时注入假客户端。
    """
    s = get_settings()
    client = client or get_client()
    last_error: Exception | None = None
    for _ in range(2):
        try:
            stream = await client.chat.completions.create(
                model=s.llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=True,
            )
            parts: list[str] = []
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    parts.append(chunk.choices[0].delta.content)
            return extract_json("".join(parts))
        except LLMError as e:
            last_error = e
            logger.warning("LLM 返回内容解析失败,重试中: %s", e)
        except Exception as e:
            logger.warning("LLM 调用失败: %s: %s", type(e).__name__, e)
            raise LLMError(f"大模型调用失败: {e}") from e
    logger.warning("LLM 连续两次未返回有效 JSON: %s", last_error)
    raise LLMError(f"大模型未返回有效 JSON: {last_error}") from last_error
