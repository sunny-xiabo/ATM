"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_case.py
# @Date: 2025/8/27 10:39
"""

import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class TestCase:
    """
    测试用例model
    """

    title: str
    description: str
    preconditions: List[str]
    steps: List[str]
    expected_results: List[str]
    priority: str
    category: str
    test_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        # 验证输入参数
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("标题不能为空且必须是字符串类型")
        if not isinstance(self.description, str):
            raise ValueError("描述必须是字符串类型")
        if not isinstance(self.preconditions, list) or not all(isinstance(x, str) for x in self.preconditions):
            raise ValueError("前置条件必须是字符串列表")
        if not isinstance(self.steps, list) or not all(isinstance(x, str) for x in self.steps):
            raise ValueError("测试步骤必须是字符串列表")
        if not isinstance(self.expected_results, list) or not all(isinstance(x, str) for x in self.expected_results):
            raise ValueError("预期结果必须是字符串列表")
        if not isinstance(self.priority, str) or self.priority not in ["P0", "P1", "P2", "P3"]:
            raise ValueError("优先级必须是'P0'、'P1'、'P2'、'P3'之一")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("类别不能为空且必须是字符串类型")
        if self.test_data is not None and not isinstance(self.test_data, dict):
            raise ValueError("测试数据必须是字典类型")

        # 初始化其他属性
        self.id = str(uuid.uuid4())
        self.status = "Draft"
        self.created_at = datetime.datetime.now().isoformat()
        self.updated_at = self.created_at
        self.created_by = None
        self.last_updated_by = None

    def to_dict(self) -> dict:
        """
        将测试用例转换为字典格式
        :return:
        """
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'preconditions': self.preconditions,
            'steps': self.steps,
            'expected_results': self.expected_results,
            'priority': self.priority,
            'category': self.category,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'created_by': self.created_by,
            'last_updated_by': self.last_updated_by
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TestCase':
        """从字典创建测试用例"""
        instance = cls(
            title=data['title'],
            description=data['description'],
            preconditions=data['preconditions'],
            steps=data['steps'],
            expected_results=data['expected_results'],
            priority=data['priority'],
            category=data['category']
        )

        # 设置其他属性
        instance.id = data.get('id', instance.id)
        instance.status = data.get('status', instance.status)
        instance.created_at = data.get('created_at')
        instance.updated_at = data.get('updated_at')
        instance.created_by = data.get('created_by')
        instance.last_updated_by = data.get('last_updated_by')

        return instance
