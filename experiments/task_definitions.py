"""
Task Definitions for Phoenix-Evo Agent Experiment
定义20个agent任务，用于对比实验
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class TaskCategory(str, Enum):
    """任务类别"""
    CODING = "coding"
    DEBUGGING = "debugging"
    OPTIMIZATION = "optimization"
    EXPLANATION = "explanation"
    REFACTORING = "refactoring"
    DATA_ANALYSIS = "data_analysis"
    SYSTEM_DESIGN = "system_design"
    SECURITY_REVIEW = "security_review"
    DOCUMENTATION = "documentation"
    TEST_WRITING = "test_writing"
    DEPLOYMENT = "deployment"


class DifficultyLevel(str, Enum):
    """难度级别"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class AgentTask:
    """Agent任务定义"""
    task_id: str
    category: TaskCategory
    difficulty: DifficultyLevel
    description: str
    input_context: str
    expected_output_type: str
    skill_keywords: List[str]  # 相关技能关键词
    estimated_tokens: int  # 预估token消耗
    time_limit_seconds: int  # 时间限制

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "description": self.description,
            "input_context": self.input_context,
            "expected_output_type": self.expected_output_type,
            "skill_keywords": self.skill_keywords,
            "estimated_tokens": self.estimated_tokens,
            "time_limit_seconds": self.time_limit_seconds,
        }


# 定义20个agent任务
TASK_DEFINITIONS: List[AgentTask] = [
    # ========== CODING TASKS ==========
    AgentTask(
        task_id="T01",
        category=TaskCategory.CODING,
        difficulty=DifficultyLevel.EASY,
        description="写一个Python冒泡排序函数",
        input_context="实现一个接受列表参数的冒泡排序函数，返回排序后的列表",
        expected_output_type="python_function",
        skill_keywords=["python", "sorting", "algorithm", "bubble_sort"],
        estimated_tokens=500,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T02",
        category=TaskCategory.CODING,
        difficulty=DifficultyLevel.MEDIUM,
        description="实现一个LRU缓存装饰器",
        input_context="创建一个LRU缓存装饰器，支持maxsize参数，使用OrderedDict实现",
        expected_output_type="python_decorator",
        skill_keywords=["python", "caching", "decorator", "lru", "ordereddict"],
        estimated_tokens=1200,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T03",
        category=TaskCategory.CODING,
        difficulty=DifficultyLevel.HARD,
        description="实现一个协程任务调度器",
        input_context="使用asyncio实现一个简单的协程任务调度器，支持任务优先级和超时",
        expected_output_type="python_module",
        skill_keywords=["python", "asyncio", "coroutine", "scheduler", "concurrency"],
        estimated_tokens=2500,
        time_limit_seconds=180,
    ),
    AgentTask(
        task_id="T04",
        category=TaskCategory.CODING,
        difficulty=DifficultyLevel.EASY,
        description="写一个二分查找函数",
        input_context="实现一个接受有序列表和目标值的二分查找函数，返回索引或-1",
        expected_output_type="python_function",
        skill_keywords=["python", "search", "binary_search", "algorithm"],
        estimated_tokens=400,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T05",
        category=TaskCategory.CODING,
        difficulty=DifficultyLevel.MEDIUM,
        description="实现一个简单的Markdown解析器",
        input_context="解析Markdown文本，支持标题、粗体、斜体、链接、列表的基本语法",
        expected_output_type="python_class",
        skill_keywords=["python", "parser", "markdown", "text_processing", "regex"],
        estimated_tokens=2000,
        time_limit_seconds=150,
    ),

    # ========== DEBUGGING TASKS ==========
    AgentTask(
        task_id="T06",
        category=TaskCategory.DEBUGGING,
        difficulty=DifficultyLevel.EASY,
        description="调试一个索引越界错误",
        input_context="代码报错：IndexError: list index out of range\n```python\ndef get_last_element(lst):\n    return lst[len(lst)]\n```",
        expected_output_type="bug_fix",
        skill_keywords=["python", "debugging", "index_error", "list"],
        estimated_tokens=300,
        time_limit_seconds=30,
    ),
    AgentTask(
        task_id="T07",
        category=TaskCategory.DEBUGGING,
        difficulty=DifficultyLevel.MEDIUM,
        description="调试一个递归深度溢出问题",
        input_context="代码报错：RecursionError: maximum recursion depth exceeded\n```python\ndef factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n)\n```",
        expected_output_type="bug_fix",
        skill_keywords=["python", "debugging", "recursion", "factorial"],
        estimated_tokens=400,
        time_limit_seconds=45,
    ),
    AgentTask(
        task_id="T08",
        category=TaskCategory.DEBUGGING,
        difficulty=DifficultyLevel.HARD,
        description="调试一个并发竞态条件",
        input_context="多线程环境下，共享计数器结果不一致：\n```python\nimport threading\ncounter = 0\ndef increment():\n    global counter\n    for _ in range(100000):\n        counter += 1\n```",
        expected_output_type="bug_fix",
        skill_keywords=["python", "debugging", "threading", "race_condition", "concurrency"],
        estimated_tokens=800,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T09",
        category=TaskCategory.DEBUGGING,
        difficulty=DifficultyLevel.MEDIUM,
        description="调试一个内存泄漏问题",
        input_context="长时间运行的程序内存持续增长，疑似存在内存泄漏",
        expected_output_type="diagnosis_and_fix",
        skill_keywords=["python", "debugging", "memory_leak", "profiling", "gc"],
        estimated_tokens=1000,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T10",
        category=TaskCategory.DEBUGGING,
        difficulty=DifficultyLevel.EASY,
        description="调试一个类型错误",
        input_context="代码报错：TypeError: can only concatenate str (not \"int\") to str\n```python\ndef greet(name, age):\n    return \"Hello \" + name + \", you are \" + age + \" years old\"\n```",
        expected_output_type="bug_fix",
        skill_keywords=["python", "debugging", "type_error", "string"],
        estimated_tokens=300,
        time_limit_seconds=30,
    ),

    # ========== OPTIMIZATION TASKS ==========
    AgentTask(
        task_id="T11",
        category=TaskCategory.OPTIMIZATION,
        difficulty=DifficultyLevel.MEDIUM,
        description="优化一个O(n^2)的算法到O(n log n)",
        input_context="有一个嵌套循环的列表去重函数，时间复杂度O(n^2)，需要优化",
        expected_output_type="optimized_code",
        skill_keywords=["python", "optimization", "algorithm", "complexity", "sorting"],
        estimated_tokens=800,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T12",
        category=TaskCategory.OPTIMIZATION,
        difficulty=DifficultyLevel.HARD,
        description="优化数据库查询性能",
        input_context="一个慢SQL查询，涉及多表JOIN和子查询，需要优化执行计划",
        expected_output_type="optimized_sql",
        skill_keywords=["sql", "optimization", "database", "indexing", "query_plan"],
        estimated_tokens=1500,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T13",
        category=TaskCategory.OPTIMIZATION,
        difficulty=DifficultyLevel.EASY,
        description="优化字符串拼接性能",
        input_context="使用+号循环拼接大量字符串，性能很差",
        expected_output_type="optimized_code",
        skill_keywords=["python", "optimization", "string", "join", "performance"],
        estimated_tokens=400,
        time_limit_seconds=45,
    ),
    AgentTask(
        task_id="T14",
        category=TaskCategory.OPTIMIZATION,
        difficulty=DifficultyLevel.MEDIUM,
        description="优化一个函数的缓存策略",
        input_context="一个计算密集型函数被频繁调用相同参数，需要添加缓存",
        expected_output_type="optimized_code",
        skill_keywords=["python", "optimization", "caching", "memoization", "performance"],
        estimated_tokens=600,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T15",
        category=TaskCategory.OPTIMIZATION,
        difficulty=DifficultyLevel.HARD,
        description="优化一个大规模数据处理管道",
        input_context="处理百万级数据的ETL管道，内存占用过高，处理速度慢",
        expected_output_type="optimized_pipeline",
        skill_keywords=["python", "optimization", "data_processing", "streaming", "memory"],
        estimated_tokens=2000,
        time_limit_seconds=180,
    ),

    # ========== EXPLANATION TASKS ==========
    AgentTask(
        task_id="T16",
        category=TaskCategory.EXPLANATION,
        difficulty=DifficultyLevel.EASY,
        description="解释Python装饰器的工作原理",
        input_context="请解释什么是装饰器，以及它在Python中是如何工作的",
        expected_output_type="explanation",
        skill_keywords=["python", "decorator", "concept", "explanation"],
        estimated_tokens=800,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T17",
        category=TaskCategory.EXPLANATION,
        difficulty=DifficultyLevel.MEDIUM,
        description="解释Python的GIL及其影响",
        input_context="请解释Python的全局解释器锁(GIL)，它如何影响多线程性能",
        expected_output_type="explanation",
        skill_keywords=["python", "gil", "threading", "performance", "concept"],
        estimated_tokens=1200,
        time_limit_seconds=90,
    ),

    # ========== REFACTORING TASKS ==========
    AgentTask(
        task_id="T18",
        category=TaskCategory.REFACTORING,
        difficulty=DifficultyLevel.MEDIUM,
        description="将一个长函数重构为多个小函数",
        input_context="一个200行的函数处理多个职责，需要拆分为单一职责的小函数",
        expected_output_type="refactored_code",
        skill_keywords=["python", "refactoring", "solid", "single_responsibility"],
        estimated_tokens=1500,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T19",
        category=TaskCategory.REFACTORING,
        difficulty=DifficultyLevel.HARD,
        description="将过程式代码重构为面向对象设计",
        input_context="一堆散落的函数和全局变量，需要重构为合理的类结构",
        expected_output_type="refactored_code",
        skill_keywords=["python", "refactoring", "oop", "class_design", "encapsulation"],
        estimated_tokens=2000,
        time_limit_seconds=150,
    ),
    AgentTask(
        task_id="T20",
        category=TaskCategory.REFACTORING,
        difficulty=DifficultyLevel.EASY,
        description="提取重复代码为工具函数",
        input_context="多处重复的字符串处理逻辑，需要提取为公共工具函数",
        expected_output_type="refactored_code",
        skill_keywords=["python", "refactoring", "utility", "code_reuse", "dry"],
        estimated_tokens=600,
        time_limit_seconds=60,
    ),

    # ========== DATA ANALYSIS TASKS ==========
    AgentTask(
        task_id="T21",
        category=TaskCategory.DATA_ANALYSIS,
        difficulty=DifficultyLevel.EASY,
        description="用Pandas读取CSV并计算基本统计量",
        input_context="读取sales.csv文件，计算每列的均值、中位数、标准差",
        expected_output_type="python_script",
        skill_keywords=["python", "pandas", "data_analysis", "statistics", "csv"],
        estimated_tokens=600,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T22",
        category=TaskCategory.DATA_ANALYSIS,
        difficulty=DifficultyLevel.MEDIUM,
        description="实现数据透视表和分组聚合",
        input_context="对销售数据按地区和产品类别分组，计算总销售额和平均订单金额",
        expected_output_type="python_script",
        skill_keywords=["python", "pandas", "pivot_table", "groupby", "aggregation"],
        estimated_tokens=1000,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T23",
        category=TaskCategory.DATA_ANALYSIS,
        difficulty=DifficultyLevel.HARD,
        description="实现时间序列异常检测",
        input_context="检测服务器监控数据中的异常峰值，使用Z-score和移动平均方法",
        expected_output_type="python_module",
        skill_keywords=["python", "time_series", "anomaly_detection", "statistics", "monitoring"],
        estimated_tokens=2000,
        time_limit_seconds=150,
    ),
    AgentTask(
        task_id="T24",
        category=TaskCategory.DATA_ANALYSIS,
        difficulty=DifficultyLevel.MEDIUM,
        description="实现数据清洗管道",
        input_context="处理缺失值、重复值、异常值，标准化数据格式",
        expected_output_type="python_class",
        skill_keywords=["python", "data_cleaning", "pandas", "preprocessing", "pipeline"],
        estimated_tokens=1200,
        time_limit_seconds=100,
    ),
    AgentTask(
        task_id="T25",
        category=TaskCategory.DATA_ANALYSIS,
        difficulty=DifficultyLevel.EASY,
        description="生成数据可视化报告",
        input_context="使用Matplotlib创建柱状图、折线图、散点图，保存为PNG",
        expected_output_type="python_script",
        skill_keywords=["python", "matplotlib", "visualization", "plotting", "reporting"],
        estimated_tokens=800,
        time_limit_seconds=80,
    ),

    # ========== SYSTEM DESIGN TASKS ==========
    AgentTask(
        task_id="T26",
        category=TaskCategory.SYSTEM_DESIGN,
        difficulty=DifficultyLevel.MEDIUM,
        description="设计一个消息队列系统",
        input_context="设计支持发布/订阅、消息持久化、消费者组的消息队列",
        expected_output_type="design_document",
        skill_keywords=["system_design", "message_queue", "pub_sub", "architecture", "distributed"],
        estimated_tokens=2000,
        time_limit_seconds=150,
    ),
    AgentTask(
        task_id="T27",
        category=TaskCategory.SYSTEM_DESIGN,
        difficulty=DifficultyLevel.HARD,
        description="设计一个分布式缓存系统",
        input_context="设计支持一致性哈希、故障转移、缓存失效的分布式缓存",
        expected_output_type="design_document",
        skill_keywords=["system_design", "caching", "distributed", "consistent_hashing", "fault_tolerance"],
        estimated_tokens=2500,
        time_limit_seconds=180,
    ),
    AgentTask(
        task_id="T28",
        category=TaskCategory.SYSTEM_DESIGN,
        difficulty=DifficultyLevel.EASY,
        description="设计一个RESTful API",
        input_context="为用户管理系统设计CRUD API，包括认证和分页",
        expected_output_type="api_specification",
        skill_keywords=["api", "rest", "http", "authentication", "design"],
        estimated_tokens=1200,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T29",
        category=TaskCategory.SYSTEM_DESIGN,
        difficulty=DifficultyLevel.MEDIUM,
        description="设计一个任务调度系统",
        input_context="设计支持定时任务、依赖关系、重试机制的调度器",
        expected_output_type="design_document",
        skill_keywords=["system_design", "scheduler", "cron", "task_queue", "reliability"],
        estimated_tokens=1800,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T30",
        category=TaskCategory.SYSTEM_DESIGN,
        difficulty=DifficultyLevel.HARD,
        description="设计一个实时推荐系统",
        input_context="设计支持协同过滤、内容推荐、实时更新的推荐引擎",
        expected_output_type="design_document",
        skill_keywords=["system_design", "recommendation", "machine_learning", "real_time", "scalability"],
        estimated_tokens=3000,
        time_limit_seconds=200,
    ),

    # ========== SECURITY REVIEW TASKS ==========
    AgentTask(
        task_id="T31",
        category=TaskCategory.SECURITY_REVIEW,
        difficulty=DifficultyLevel.EASY,
        description="审查SQL注入漏洞",
        input_context="检查以下代码是否存在SQL注入风险：\n```python\nquery = f\"SELECT * FROM users WHERE id = {user_id}\"\n```",
        expected_output_type="security_report",
        skill_keywords=["security", "sql_injection", "vulnerability", "code_review", "owasp"],
        estimated_tokens=500,
        time_limit_seconds=45,
    ),
    AgentTask(
        task_id="T32",
        category=TaskCategory.SECURITY_REVIEW,
        difficulty=DifficultyLevel.MEDIUM,
        description="审查XSS漏洞",
        input_context="检查Web应用中用户输入的处理和输出编码",
        expected_output_type="security_report",
        skill_keywords=["security", "xss", "web_security", "encoding", "sanitization"],
        estimated_tokens=800,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T33",
        category=TaskCategory.SECURITY_REVIEW,
        difficulty=DifficultyLevel.HARD,
        description="审查认证和授权机制",
        input_context="分析JWT实现、密码存储、会话管理的安全性",
        expected_output_type="security_report",
        skill_keywords=["security", "authentication", "authorization", "jwt", "password_hashing"],
        estimated_tokens=1500,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T34",
        category=TaskCategory.SECURITY_REVIEW,
        difficulty=DifficultyLevel.MEDIUM,
        description="审查依赖项安全",
        input_context="检查requirements.txt中的依赖是否存在已知漏洞",
        expected_output_type="security_report",
        skill_keywords=["security", "dependencies", "vulnerability", "supply_chain", "audit"],
        estimated_tokens=600,
        time_limit_seconds=50,
    ),
    AgentTask(
        task_id="T35",
        category=TaskCategory.SECURITY_REVIEW,
        difficulty=DifficultyLevel.EASY,
        description="审查敏感数据暴露",
        input_context="检查代码中是否存在硬编码密码、API密钥、日志泄露",
        expected_output_type="security_report",
        skill_keywords=["security", "secrets", "hardcoded", "logging", "data_exposure"],
        estimated_tokens=400,
        time_limit_seconds=40,
    ),

    # ========== DOCUMENTATION TASKS ==========
    AgentTask(
        task_id="T36",
        category=TaskCategory.DOCUMENTATION,
        difficulty=DifficultyLevel.EASY,
        description="为函数编写docstring",
        input_context="为以下函数添加Google风格的docstring：\n```python\ndef process_data(data, threshold=0.5):\n    ...\n```",
        expected_output_type="documented_code",
        skill_keywords=["documentation", "docstring", "python", "google_style", "comments"],
        estimated_tokens=400,
        time_limit_seconds=40,
    ),
    AgentTask(
        task_id="T37",
        category=TaskCategory.DOCUMENTATION,
        difficulty=DifficultyLevel.MEDIUM,
        description="编写API文档",
        input_context="为REST API端点编写OpenAPI/Swagger文档",
        expected_output_type="api_documentation",
        skill_keywords=["documentation", "api", "openapi", "swagger", "rest"],
        estimated_tokens=1200,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T38",
        category=TaskCategory.DOCUMENTATION,
        difficulty=DifficultyLevel.HARD,
        description="编写架构设计文档",
        input_context="为微服务系统编写架构文档，包括组件图、数据流、部署图",
        expected_output_type="architecture_document",
        skill_keywords=["documentation", "architecture", "microservices", "diagrams", "design"],
        estimated_tokens=2500,
        time_limit_seconds=180,
    ),
    AgentTask(
        task_id="T39",
        category=TaskCategory.DOCUMENTATION,
        difficulty=DifficultyLevel.EASY,
        description="编写README快速开始指南",
        input_context="为开源项目编写安装、配置、使用的快速开始指南",
        expected_output_type="readme_section",
        skill_keywords=["documentation", "readme", "getting_started", "installation", "usage"],
        estimated_tokens=800,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T40",
        category=TaskCategory.DOCUMENTATION,
        difficulty=DifficultyLevel.MEDIUM,
        description="编写变更日志",
        input_context="根据git提交历史生成CHANGELOG.md，遵循语义化版本",
        expected_output_type="changelog",
        skill_keywords=["documentation", "changelog", "versioning", "git", "release"],
        estimated_tokens=1000,
        time_limit_seconds=70,
    ),

    # ========== TEST WRITING TASKS ==========
    AgentTask(
        task_id="T41",
        category=TaskCategory.TEST_WRITING,
        difficulty=DifficultyLevel.EASY,
        description="为函数编写单元测试",
        input_context="为calculator.py中的add、subtract、multiply、divide函数编写pytest测试",
        expected_output_type="test_file",
        skill_keywords=["testing", "unit_test", "pytest", "python", "assertions"],
        estimated_tokens=600,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T42",
        category=TaskCategory.TEST_WRITING,
        difficulty=DifficultyLevel.MEDIUM,
        description="编写集成测试",
        input_context="为数据库CRUD操作编写集成测试，使用fixtures管理测试数据",
        expected_output_type="test_file",
        skill_keywords=["testing", "integration_test", "pytest", "database", "fixtures"],
        estimated_tokens=1200,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T43",
        category=TaskCategory.TEST_WRITING,
        difficulty=DifficultyLevel.HARD,
        description="编写端到端测试",
        input_context="为Web应用编写Selenium/Playwright端到端测试",
        expected_output_type="test_file",
        skill_keywords=["testing", "e2e_test", "selenium", "playwright", "browser"],
        estimated_tokens=2000,
        time_limit_seconds=150,
    ),
    AgentTask(
        task_id="T44",
        category=TaskCategory.TEST_WRITING,
        difficulty=DifficultyLevel.MEDIUM,
        description="编写性能测试",
        input_context="使用locust或pytest-benchmark编写API性能测试",
        expected_output_type="test_file",
        skill_keywords=["testing", "performance", "load_test", "benchmark", "api"],
        estimated_tokens=1500,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T45",
        category=TaskCategory.TEST_WRITING,
        difficulty=DifficultyLevel.EASY,
        description="编写参数化测试",
        input_context="使用pytest.mark.parametrize为边界条件编写参数化测试",
        expected_output_type="test_file",
        skill_keywords=["testing", "parametrize", "pytest", "edge_cases", "boundary"],
        estimated_tokens=500,
        time_limit_seconds=50,
    ),

    # ========== DEPLOYMENT TASKS ==========
    AgentTask(
        task_id="T46",
        category=TaskCategory.DEPLOYMENT,
        difficulty=DifficultyLevel.EASY,
        description="编写Dockerfile",
        input_context="为Python Flask应用编写多阶段构建的Dockerfile",
        expected_output_type="dockerfile",
        skill_keywords=["docker", "container", "flask", "python", "deployment"],
        estimated_tokens=600,
        time_limit_seconds=60,
    ),
    AgentTask(
        task_id="T47",
        category=TaskCategory.DEPLOYMENT,
        difficulty=DifficultyLevel.MEDIUM,
        description="编写Kubernetes部署配置",
        input_context="编写Deployment、Service、Ingress的YAML配置",
        expected_output_type="kubernetes_manifests",
        skill_keywords=["kubernetes", "k8s", "deployment", "service", "yaml"],
        estimated_tokens=1200,
        time_limit_seconds=90,
    ),
    AgentTask(
        task_id="T48",
        category=TaskCategory.DEPLOYMENT,
        difficulty=DifficultyLevel.HARD,
        description="设计CI/CD管道",
        input_context="设计GitHub Actions工作流，包含测试、构建、部署阶段",
        expected_output_type="ci_cd_config",
        skill_keywords=["ci_cd", "github_actions", "automation", "pipeline", "deployment"],
        estimated_tokens=1800,
        time_limit_seconds=120,
    ),
    AgentTask(
        task_id="T49",
        category=TaskCategory.DEPLOYMENT,
        difficulty=DifficultyLevel.MEDIUM,
        description="配置Nginx反向代理",
        input_context="配置Nginx作为反向代理，支持负载均衡和SSL终止",
        expected_output_type="nginx_config",
        skill_keywords=["nginx", "reverse_proxy", "load_balancer", "ssl", "configuration"],
        estimated_tokens=800,
        time_limit_seconds=70,
    ),
    AgentTask(
        task_id="T50",
        category=TaskCategory.DEPLOYMENT,
        difficulty=DifficultyLevel.EASY,
        description="编写docker-compose配置",
        input_context="为多服务应用编写docker-compose.yml，包含数据库、缓存、应用服务",
        expected_output_type="docker_compose",
        skill_keywords=["docker_compose", "container", "multi_service", "orchestration", "deployment"],
        estimated_tokens=700,
        time_limit_seconds=60,
    ),
]


def get_task_by_id(task_id: str) -> Optional[AgentTask]:
    """根据ID获取任务"""
    for task in TASK_DEFINITIONS:
        if task.task_id == task_id:
            return task
    return None


def get_tasks_by_category(category: TaskCategory) -> List[AgentTask]:
    """根据类别获取任务"""
    return [t for t in TASK_DEFINITIONS if t.category == category]


def get_tasks_by_difficulty(difficulty: DifficultyLevel) -> List[AgentTask]:
    """根据难度获取任务"""
    return [t for t in TASK_DEFINITIONS if t.difficulty == difficulty]


if __name__ == "__main__":
    print(f"Total tasks: {len(TASK_DEFINITIONS)}")
    for category in TaskCategory:
        tasks = get_tasks_by_category(category)
        print(f"  {category.value}: {len(tasks)} tasks")
    for difficulty in DifficultyLevel:
        tasks = get_tasks_by_difficulty(difficulty)
        print(f"  {difficulty.value}: {len(tasks)} tasks")
