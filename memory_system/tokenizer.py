"""
中英文混合分词器

策略:
  - 中文: 字符级 bigram (连续2字对), 保留单字作为 unigram 兜底
  - 英文: 小写化 + 按非字母数字字符分割 + 最小长度过滤(>=2)
  - 混合: 检测 Unicode 范围, 中文段用 bigram, 英文段用空格分词

保留停用词 — BM25 的 IDF 会自然降低高频词权重。
零外部依赖, 纯 Python 标准库实现。
"""

import re
from typing import List

# Unicode 范围常量
CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F), # CJK Compatibility Ideographs Supplement
]

CHINESE_CHAR_PATTERN = re.compile(r"[一-鿿㐀-䶿豈-﫿]")


def _is_chinese(ch: str) -> bool:
    """判断单个字符是否为 CJK 字符."""
    return bool(CHINESE_CHAR_PATTERN.match(ch))


def _tokenize_chinese(text: str) -> List[str]:
    """
    对中文文本做字符级 bigram 分词.

    "用户偏好组合优于继承"
    → ["用户", "户偏", "偏好", "好组", "组合", "合优", "优于", "于继", "继承"]
    """
    tokens: List[str] = []
    chars = [ch for ch in text if _is_chinese(ch)]
    n = len(chars)
    if n == 0:
        return tokens
    # Bigram
    for i in range(n - 1):
        tokens.append(chars[i] + chars[i + 1])
    # Unigram 兜底 (单字)
    tokens.extend(chars)
    return tokens


def _tokenize_english(text: str) -> List[str]:
    """
    对英文文本做空格 + 标点分割分词.

    "UserRepository pattern"
    → ["userrepository", "pattern"]
    """
    # 小写化, 按非字母数字分割
    words = re.split(r"[^a-zA-Z0-9]+", text.lower())
    # 过滤过短词 & 纯数字
    return [w for w in words if len(w) >= 2 and not w.isdigit()]


def tokenize(text: str) -> List[str]:
    """
    混合分词: 自动检测中英文段, 分别处理.

    Args:
        text: 输入文本 (可包含中英文混合)

    Returns:
        分词结果列表 (去重但保持顺序)

    Example:
        >>> tokenize("UserRepository 用组合优于继承")
        ['userrepository', '用组', '组合', '合优', '优于', '于继', '继承', '用', '组', '合', '优', '于', '继', '承']
    """
    if not text or not text.strip():
        return []

    tokens: List[str] = []

    # 切分为中英文交替的片段
    segments: List[tuple[str, bool]] = []  # [(text, is_chinese)]
    current_chars: List[str] = []
    current_is_chinese: bool | None = None

    for ch in text:
        is_cj = _is_chinese(ch)
        if current_is_chinese is None:
            current_is_chinese = is_cj

        if is_cj == current_is_chinese:
            current_chars.append(ch)
        else:
            # 片段切换
            segments.append(("".join(current_chars), current_is_chinese))
            current_chars = [ch]
            current_is_chinese = is_cj

    if current_chars:
        segments.append(("".join(current_chars), current_is_chinese))

    # 分别处理中文和英文段
    for seg_text, is_cj in segments:
        if is_cj:
            tokens.extend(_tokenize_chinese(seg_text))
        else:
            tokens.extend(_tokenize_english(seg_text))

    # 去重保持顺序
    seen: set[str] = set()
    unique: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique


def tokenize_for_index(text: str) -> List[str]:
    """
    用于 BM25 索引的分词 —— 包含重复 token (用于 TF 计算).

    与 tokenize() 的区别: 不去重, 保留原始频率信息.
    """
    if not text or not text.strip():
        return []

    tokens: List[str] = []

    segments: List[tuple[str, bool]] = []
    current_chars: List[str] = []
    current_is_chinese: bool | None = None

    for ch in text:
        is_cj = _is_chinese(ch)
        if current_is_chinese is None:
            current_is_chinese = is_cj
        if is_cj == current_is_chinese:
            current_chars.append(ch)
        else:
            segments.append(("".join(current_chars), current_is_chinese))
            current_chars = [ch]
            current_is_chinese = is_cj

    if current_chars:
        segments.append(("".join(current_chars), current_is_chinese))

    for seg_text, is_cj in segments:
        if is_cj:
            tokens.extend(_tokenize_chinese(seg_text))
        else:
            tokens.extend(_tokenize_english(seg_text))

    return tokens
