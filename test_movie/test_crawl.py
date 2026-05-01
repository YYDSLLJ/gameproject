# -*- coding: utf-8 -*-
"""
测试脚本 - 测试评论和弹幕爬取，保存为CSV文件
"""

import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comment_crawler import CommentCrawler
from danmaku_crawler import DanmakuCrawler


def test_comments(video_url: str, cookie: str = None, output_dir: str = None):
    """
    测试评论爬取

    Args:
        video_url: B站视频链接或BV号
        cookie: B站Cookie（可选）
        output_dir: 输出目录（可选）
    """
    print(f"=" * 50)
    print(f"开始测试评论爬取")
    print(f"视频URL: {video_url}")
    print(f"=" * 50)

    crawler = CommentCrawler(cookie=cookie)

    try:
        # 获取评论（最多50页）
        print("正在爬取评论...")
        comments = crawler.fetch_all(video_url, max_pages=50)
        print(f"获取到 {len(comments)} 条评论")

        if not comments:
            print("没有获取到评论数据")
            return

        # 保存到CSV
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))

        # 生成文件名
        if "BV" in video_url:
            bv_id = video_url.split("BV")[1][:10] if "BV" in video_url else "unknown"
        else:
            bv_id = "unknown"

        filename = os.path.join(output_dir, f"comments_{bv_id}.csv")
        count = crawler.save_to_csv(comments, filename)
        print(f"评论已保存到: {filename}")
        print(f"共保存 {count} 条评论")

        # 显示前几条评论
        print("\n前5条评论示例:")
        for i, c in enumerate(comments[:5]):
            print(f"  {i+1}. [{c['昵称']}] {c['评论内容'][:50]}...")

    except Exception as e:
        print(f"评论爬取出错: {e}")
        import traceback
        traceback.print_exc()


def test_danmaku(video_url: str, cookie: str = None, output_dir: str = None):
    """
    测试弹幕爬取

    Args:
        video_url: B站视频链接或BV号
        cookie: B站Cookie（可选）
        output_dir: 输出目录（可选）
    """
    print(f"=" * 50)
    print(f"开始测试弹幕爬取")
    print(f"视频URL: {video_url}")
    print(f"=" * 50)

    try:
        crawler = DanmakuCrawler(video_url, cookie=cookie)
        print(f"视频信息: BV={crawler.bv_id}, CID={crawler.oid}, 时长={crawler.duration}秒")

        # 爬取所有分段
        print("正在爬取弹幕...")
        crawler.crawl_all_segments(sleep=0.5)
        print(f"获取到 {len(crawler.all_danmaku)} 条弹幕")

        if not crawler.all_danmaku:
            print("没有获取到弹幕数据")
            return

        # 保存到CSV
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))

        filename = os.path.join(output_dir, f"danmaku_{crawler.bv_id}.csv")
        count = crawler.save_to_csv(filename)
        print(f"弹幕已保存到: {filename}")
        print(f"共保存 {count} 条弹幕")

        # 显示前几条弹幕
        print("\n前5条弹幕示例:")
        for i, d in enumerate(crawler.all_danmaku[:5]):
            appear = f"{d.progress // 60000:02d}:{(d.progress // 1000) % 60:02d}"
            print(f"  {i+1}. [{appear}] {d.content[:50]}...")

    except Exception as e:
        print(f"弹幕爬取出错: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主测试函数"""
    # 测试视频（可以改成其他视频链接）
    test_bv = "BV1xx411c7mu"  # 一个测试视频

    # 也可以从命令行参数获取
    if len(sys.argv) > 1:
        test_bv = sys.argv[1]

    # 如果有第二个参数，作为Cookie
    cookie = ""
    if len(sys.argv) > 2:
        cookie = sys.argv[2]

    video_url = f"https://www.bilibili.com/video/{test_bv}"

    # 输出目录
    output_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"输出目录: {output_dir}")

    # 从环境变量获取Cookie
    if not cookie:
        cookie = os.getenv("BILI_COOKIE", "")

    if cookie:
        print("使用Cookie")
    else:
        print("未设置Cookie，将使用匿名方式爬取（可能受限）")

    print("\n" + "=" * 60)
    print("测试1: 评论爬取")
    print("=" * 60)
    test_comments(video_url, cookie, output_dir)

    print("\n" + "=" * 60)
    print("测试2: 弹幕爬取")
    print("=" * 60)
    test_danmaku(video_url, cookie, output_dir)

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()