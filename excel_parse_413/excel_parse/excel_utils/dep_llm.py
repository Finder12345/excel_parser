# -*- coding: utf-8 -*-
"""LLM adapter (OpenAI-compatible, via LangChain init_chat_model).

对外接口保持不变：
- call_model(query: str, prompt: str) -> str
- set_models() 用于刷新模型实例（当 cur_model 更新后调用）

实现要点：
- 统一使用 langchain.chat_models.init_chat_model
- 收敛全局状态：仅保留模块内缓存的 chat model（_chat_model）
"""

import logging
import random
import time

from langchain.chat_models import init_chat_model

from .cfg import cur_model


# 移除自定义 ssl_ctx/http_client：统一使用 init_chat_model 的默认网络栈


def clear_think(llm_response_text: str) -> str:
    # @Description：清除千问模型返回的<think>...</think>
    if "<think>" in llm_response_text:
        start_index = llm_response_text.find("<think>")
        end_index = llm_response_text.find("</think>", start_index)
        return llm_response_text[end_index + len("</think>") :].strip()
    return llm_response_text


# 模块内缓存：避免散落的全局 dict
_chat_model = None


def _build_chat_model():
    # 统一走 OpenAI-compatible 服务
    return init_chat_model(
        model=cur_model["model_name"],
        model_provider="openai",
        base_url=cur_model["base_url"],
        api_key=cur_model["api_key"],
        temperature=cur_model.get("temperature", 0),
        max_tokens=cur_model.get("max_tokens", None),
        top_p=cur_model.get("top_p", None),
    )


def get_models():
    """兼容旧结构：仅保留 cur_chat 字段。"""
    global _chat_model
    if _chat_model is None:
        _chat_model = _build_chat_model()
    return {"change_model": False, "cur_chat": _chat_model}


def set_models():
    """刷新 chat model（当 cur_model 更新后调用）。"""
    global _chat_model
    _chat_model = _build_chat_model()


def call_model(query: str, prompt: str):
    """Call the model to generate a response based on the given query and prompt.

    兼容旧调用方：返回 (text, spend_token)
    """
    global _chat_model
    if _chat_model is None:
        _chat_model = _build_chat_model()

    max_retries = 5
    retry_delay = 1

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": query},
    ]

    for attempt in range(max_retries):
        try:
            logging.info("[performance test] LLM request sent")
            start_time = time.perf_counter()

            resp = _chat_model.invoke(messages)

            end_time = time.perf_counter()
            logging.info(
                f"[performance test] LLM response received, elapsed time: {(end_time - start_time):.4f} s"
            )

            content = getattr(resp, "content", resp)
            return clear_think(content), 0
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2**attempt) + random.uniform(0, 1)
                logging.warning(
                    f"Rate limit encountered, retrying after {wait_time:.2f}s (attempt {attempt + 1})..."
                )
                time.sleep(wait_time)
            else:
                logging.error("Maximum retry attempts reached, rate limit still encountered")
                raise e

llm_model = get_models()
