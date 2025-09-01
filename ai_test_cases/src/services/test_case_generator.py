"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_case_generator.py
# @Date: 2025/8/26 17:37
"""

import json
from typing import List, Dict, Any, Optional

from src.models.test_case import TestCase
from datetime import datetime
from src.schemas.communication import TestScenario


class TestCaseGenerator:

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path
        self.base_template = self._load_template() if template_path else {}

    def _load_template(self) -> Dict[str, Any]:
        """
        加载测试用例模板
        :return:
        """
        if self.template_path is None:
            return {}
        try:
            with open(file=self.template_path, mode='r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载测试用例模板时出错: {str(e)}")
            return {}

    def generate_test_cases(self, test_strategy: Dict[str, Any]) -> List[TestCase]:
        """
        根据测试策略生成测试用例
        :param test_strategy: test_strategy: 包含测试策略的字典，应包含以下字段
                                - scenarios: 测试场景列表
                                - test_types: 测试类型配置
                                - priorities: 测试优先级
                                - validations: 验证规则
        :return: List[TestCase]: 生成的测试用例
        """
        test_cases = []
        scenarios = test_strategy.get('scenarios', [])
        test_types = test_strategy.get('test_types', {})
        priorities = test_strategy.get('priorities', {})
        vaidations = test_strategy.get('validation_rules', {})

        for scenario in scenarios:
            # 根据场景类型生成对应的测试用例
            scenario_type = scenario.get('type')
            if scenario_type in test_types:
                test_case = self._create_test_case(
                    scenario=scenario,
                    test_type=test_types[scenario_type],
                    priorities=priorities,
                    validation_rules=vaidation_rules
                )
                if test_case:
                    test_cases.append(test_case)
        return test_cases

    def _create_test_case(self,
                          scenario: Dict[str, Any],
                          test_type: Dict[str, Any],
                          priorities: Dict[str, Any],
                          validation_rules: Dict[str, Any]) -> Optional[TestCase]:
        """
        创建单个测试用例
        :param scenario: 测试场景信息
        :param test_type: 测试类型配置
        :param priorities: 优先级定义
        :param validation_rules: 验证规则
        :return: Optional[TestCase]: 生成的测试用例，如果生成失败则返回None
        """
        try:
            # 获取用例基本信息
            title = f"{test_type.get('name', '')} - {scenario.get('description', '')}"
            priority = self._determine_priority(scenario, priorities)
            category = test_type.get('category', '功能测试')

            # 生成测试步骤和预期结果
            steps = self._generate_steps(test_type, scenario)
            expected_results = self._generate_expected_results(test_type, scenario, validation_rules)

            # 创建测试用例
            test_case = TestCase(
                title=title,
                description=scenario.get('description', ''),
                preconditions=scenario.get('preconditions', []),
                steps=steps,
                expected_results=expected_results,
                priority=priority,
                category=category
            )

            # 添加额外的测试数据
            test_case.test_data = self._generate_test_data(test_type, scenario)

            return test_case
        except Exception as e:
            logger.error(f"创建测试用例时出错: {str(e)}")
            return None

    def _determine_priority(self, scenario: Dict[str, Any], priorities: Dict[str, Any]) -> str:

        """
        根据场景和优先级定义确定测试用例优先级
        :param scenario: 测试场景信息
        :param priorities: 优先级定义
        :return: str: 优先级名称
        """

        scenario_priority = scenario.get('priority')
        if scenario_priority in priorities:
            return priorities[scenario_priority].get('level', 'P2')
        return 'P2'

    def _generate_steps(self, test_type: Dict[str, Any], scenario: Dict[str, Any]) -> List[str]:

        """
        根据测试类型和测试场景生成测试步骤
        :param test_type: 测试类型配置
        :param scenario: 测试场景信息
        :return: List[str]: 生成的测试步骤列表
        """

        base_steps = test_type.get('base_steps', [])
        scenario_steps = scenario.get('steps', [])
        return base_steps + scenario_steps

    def _generate_expected_results(self,
                                   test_type: Dict[str, Any],
                                   scenario: Dict[str, Any],
                                   validation_rules: Dict[str, Any]) -> List[str]:
        """
        根据测试类型和测试场景生成预期结果
        :param test_type: 测试类型配置
        :param scenario: 测试场景信息
        :param validation_rules: 验证规则
        :return: List[str]: 生成的预期结果列表
        """
        base_results = test_type.get('base_expected_results', [])
        scenario_results = scenario.get('expected_results', [])

        # 添加验证规则的预期结果
        if validation_rules:
            rule_results = self._generate_validation_results(test_type, validation_rules)
            return base_results + scenario_results + rules_results
        return base_results + scenario_results

    def _generate_validation_rule_results(self,
                                          test_type: Dict[str, Any],
                                          validation_rules: Dict[str, Any]) -> List[str]:

        """
        根据测试类型和验证规则生成预期结果
        :param self:
        :param test_type:
        :param validation_rules:
        :return:
        """
        results = []
        type_rules = validation_rules.get(test_type.get('name', ''), {})

        for rule_name, rule_value in type_rules.items():
            if isinstance(rule_value, dict):
                threshold = rule_value.get('threshold')
                if threshold is not None:
                    results.append(f"验证规则 {rule_name} 的预期结果为 {threshold}")
                else:
                    results.append(f"验证规则 {rule_name} 的预期结果为 {rule_value}")
        return results

    def _generate_test_data(self, test_type: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据测试类型和测试场景生成测试数据
        :param test_type:
        :param scenario:
        :return:
        """
        test_data = {}

        # 合并测试类型的基础数据和测试场景特定数据
        base_data = test_type.get('test_data', {})
        scenario_data = scenario.get('test_data', {})

        test_data.update(base_data)
        test_data.update(scenario_data)

        return test_data
