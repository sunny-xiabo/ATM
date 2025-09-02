"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: communication.py
# @Date: 2025/8/27 11:27
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class AgentMessage(BaseModel):
    """
    基础消息模型，所有agent间通信的消息都必须继承此类
    """
    msg_type: str = Field(default="agent_message", description="消息类型")
    version: str = Field(default="1.0", description="消息版本")
    timestamp: Optional[str] = Field(default=None, description="消息时间戳")


class RequirementAnalysisRequest(AgentMessage):
    """
    需求分析请求消息模型
    """
    doc_content: str = Field(..., description="需求文档内容")


class TestScenario(BaseModel):
    """
    测试场景模型
    """
    id: str = Field(..., description="测试场景ID")
    description: str = Field(..., description="测试场景描述")
    test_steps: List[str] = Field(default_factory=list, description="关联的测试用例ID列表")


class RequirementAnalysisResponse(AgentMessage):
    """
    需求分析响应消息模型
    """
    functional_requirements: List[str] = Field(default_factory=list, description="功能需求列表")
    non_functional_requirements: List[str] = Field(default_factory=list, description="非功能需求列表")
    test_scenarios: List[TestScenario] = Field(default_factory=list, description="测试场景列表")
    risk_areas: List[str] = Field(default_factory=list, description="风险区列表")


class TestDesignRequest(AgentMessage):
    """
    测试设计请求消息模型
    """
    requirements: Dict = Field(..., description="需求分析结果")
    original_doc: Optional[str] = Field(default=None, description="原始需求文档")


class TestDesignResponse(AgentMessage):
    """
    测试设计响应消息模型
    """
    test_approach: Dict = Field(..., description="测试方法")
    coverage_matrix: List[Dict] = Field(..., description="测试覆盖矩阵")
    priorities: List[Dict] = Field(..., description="测试优先级")
    resource_estimation: Dict = Field(..., description="资源估算")


class TestCaseWriteRequest(AgentMessage):
    """
    测试用例写入请求消息模型
    """
    test_strategy: Dict = Field(..., description="测试策略")


class TestCase(BaseModel):
    """
    测试用例模型
    """
    id: str = Field(..., description="用例ID")
    title: str = Field(..., description="用例标题")
    preconditions: List[str] = Field(default_factory=list, description="前置条件")
    steps: List[str] = Field(..., description="测试步骤")
    expected_results: List[str] = Field(..., description="预期结果")
    priority: str = Field(..., description="优先级")
    category: str = Field(..., description="类别")


class TestCaseWriteResponse(AgentMessage):
    """测试用例编写响应消息"""
    test_cases: List[TestCase] = Field(..., description="测试用例列表")


class QualityAssuranceRequest(AgentMessage):
    """质量保证请求消息"""
    test_cases: List[Dict] = Field(..., description="待审查的测试用例列表")


class QualityAssuranceResponse(AgentMessage):
    """质量保证响应消息"""
    reviewed_cases: List[Dict] = Field(..., description="审查后的测试用例列表")
    review_comments: List[str] = Field(default_factory=list, description="审查意见")


class ErrorResponse(AgentMessage):
    """错误响应消息"""
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误信息")
    details: Optional[Dict] = Field(default=None, description="错误详情")
