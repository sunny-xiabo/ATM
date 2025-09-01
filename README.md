# ATM - AI测试用例生成系统

## 项目简介

ATM (AI Test Case Generator) 是一个基于人工智能的自动化测试用例生成系统。该系统利用多个AI代理协同工作，能够自动分析需求文档，设计测试策略，生成测试用例，并进行质量审查。

## 系统架构

系统包含以下核心AI代理：

- **需求分析师 (Requirement Analyst)**: 分析需求文档，提取关键信息
- **测试设计师 (Test Designer)**: 基于需求设计测试策略
- **测试用例编写器 (Test Case Writer)**: 生成具体的测试用例
- **质量保证 (Quality Assurance)**: 审查和优化测试用例
- **协调助手 (Assistant)**: 协调各代理之间的工作流程

## 功能特性

- 🚀 支持PDF、Word等多种文档格式的需求分析
- 🤖 多AI代理协同工作，提高测试用例质量
- 📊 支持功能测试和API测试两种类型
- 📈 可配置并发工作线程，提升处理效率
- 📋 自动导出Excel格式的测试用例
- 🔧 灵活的模板系统，支持自定义测试用例结构

## 环境要求

- Python 3.13+
- 支持的操作系统：Windows, macOS, Linux

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd Atm
```

### 2. 安装依赖

#### 生产环境依赖

```bash
# 使用 pip 安装
pip install -r requirements.txt

# 使用 uv 安装（推荐）
uv sync
```

#### 开发环境依赖（可选）

```bash
# 安装开发工具和测试依赖
pip install -r requirements-dev.txt
```

### 3. 环境配置

创建 `.env` 文件并配置必要的环境变量：

```bash
# OpenAI API配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1

# 其他配置
LOG_LEVEL=INFO
```

## 启动操作步骤

### 基本用法

#### 1. 生成功能测试用例

```bash
cd ai_test_cases
python main.py -d docs/需求文档.pdf -t functional -o test_cases.xlsx
```

#### 2. 生成API测试用例

```bash
python main.py -d docs/需求文档.pdf -t api -o api_test_cases.xlsx
```

#### 3. 使用自定义输入文件

```bash
python main.py -i existing_test_cases.xlsx -o improved_test_cases.xlsx
```

### 命令行参数说明

| 参数 | 短参数 | 说明 | 必需 | 默认值 |
|------|--------|------|------|--------|
| `--doc_path` | `-d` | 需求文档路径 | 是* | - |
| `--input` | `-i` | 输入测试用例文件路径 | 是* | - |
| `--output` | `-o` | 输出文件路径 | 否 | test_cases.xlsx |
| `--type` | `-t` | 测试类型 (functional/api) | 否 | functional |
| `--concurrent` | `-c` | 并发工作线程数 | 否 | 1 |

*注：`-d` 和 `-i` 参数至少需要提供一个

### 高级用法

#### 1. 设置并发工作线程

```bash
python main.py -d docs/需求文档.pdf -t functional -o test_cases.xlsx -c 4
```

#### 2. 批量处理多个文档

```bash
# 可以编写脚本批量处理
for doc in docs/*.pdf; do
    python main.py -d "$doc" -t functional -o "output/$(basename "$doc" .pdf)_test_cases.xlsx"
done
```

## 项目结构

```
ai_test_cases/
├── main.py                 # 主程序入口
├── src/
│   ├── agents/            # AI代理模块
│   │   ├── requirement_analyst.py
│   │   ├── test_designer.py
│   │   ├── test_case_writer.py
│   │   ├── quality_assurance.py
│   │   └── assistant.py
│   ├── models/            # 数据模型
│   ├── services/          # 业务服务
│   ├── templates/         # 测试用例模板
│   │   ├── func_test_template.json
│   │   └── api_test_template.json
│   ├── utils/             # 工具函数
│   └── schemas/           # 数据模式定义
├── docs/                  # 需求文档目录
├── logs/                  # 日志文件
└── test_cases.xlsx        # 生成的测试用例
```

## 模板配置

系统提供了两种预定义模板：

### 功能测试模板 (`func_test_template.json`)
- 包含测试场景定义
- 支持参数化测试
- 包含环境配置要求

### API测试模板 (`api_test_template.json`)
- 支持接口测试用例
- 包含请求/响应验证
- 支持性能测试要求

## 日志和调试

系统会自动生成详细的日志文件：

```bash
# 查看日志
tail -f ai_test_cases/logs/ai_test.log
```

## 故障排除

### 常见问题

1. **OpenAI API错误**
   - 检查API密钥是否正确
   - 确认API配额是否充足

2. **文档解析失败**
   - 确认文档格式是否支持
   - 检查文档是否损坏

3. **内存不足**
   - 减少并发工作线程数 (`-c` 参数)
   - 分批处理大型文档

### 获取帮助

```bash
python main.py --help
```

## 开发指南

### 添加新的AI代理

1. 在 `src/agents/` 目录下创建新的代理类
2. 继承基础代理类并实现必要方法
3. 在 `main.py` 中注册新代理

### 自定义模板

1. 修改 `src/templates/` 目录下的模板文件
2. 确保模板格式符合系统要求
3. 重启系统使模板生效

## 贡献指南

欢迎提交Issue和Pull Request来改进项目！

## 许可证

[添加许可证信息]

## 联系方式

[添加联系方式信息]
