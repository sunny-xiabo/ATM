"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: logger.py
# @Date: 2025/8/26 14:03
"""
from pathlib import Path
import logging
import sys
from logging.handlers import RotatingFileHandler
from colorlog import ColoredFormatter


def setup_logger(log_level: str = "INFO", log_file: str = "ai_test.log"):
    """设置日志记录器"""
    # 创建日志目录如果不存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / log_file

    # 设置日志等级
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # 日志格式化
    log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                   datefmt='%Y-%m-%d %H:%M:%S')

    # 配置带有轮转功能的文件处理程序
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1024 * 1024 * 10, # 10MB
        backupCount=5,
        encoding='utf-8')  # 明确指定文件编码

    file_handler.setFormatter(log_format)

    # 配置控制台处理
    console_handler = logging.StreamHandler(sys.stdout)
    color_formatter = ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'white',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white'
        }
    )
    console_handler.setFormatter(color_formatter)



    # 设置根日志记录
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 设置初始设置信息
    logging.info(f"Logging configured with level: {log_level}, file: {log_path}")


if __name__ == "__main__":
    setup_logger(log_level="DEBUG")  # 设置最低日志等级为DEBUG，方便测试所有日志输出

    logging.debug("这是调试日志 (DEBUG)")
    logging.info("这是信息日志 (INFO)")
    logging.warning("这是警告日志 (WARNING)")
    logging.error("这是错误日志 (ERROR)")
    logging.critical("这是严重错误日志 (CRITICAL)")
