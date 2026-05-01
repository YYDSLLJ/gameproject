# dm_pb2.py
# Protobuf definitions for Bilibili danmaku
from dataclasses import dataclass
from typing import List
import betterproto


@dataclass
class DanmakuElem(betterproto.Message):
    id: int = betterproto.uint64_field(1)
    progress: int = betterproto.int32_field(2)  # 弹幕出现时间点（毫秒）
    mode: int = betterproto.int32_field(3)
    fontsize: int = betterproto.int32_field(4)
    color: int = betterproto.uint32_field(5)
    mid_hash: str = betterproto.string_field(6)
    content: str = betterproto.string_field(7)
    ctime: int = betterproto.int64_field(8)
    weight: int = betterproto.int32_field(9)
    action: str = betterproto.string_field(10)
    pool: int = betterproto.int32_field(11)
    id_str: str = betterproto.string_field(12)
    attr: int = betterproto.int32_field(13)


@dataclass
class DmSegDanmaku(betterproto.Message):
    elems: List[DanmakuElem] = betterproto.message_field(1)