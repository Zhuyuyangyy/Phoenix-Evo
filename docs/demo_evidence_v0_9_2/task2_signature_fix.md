# Task 2: 函数签名错误修复 - V0.9.2 证据

## 任务信息
- task_id: task2_20260510_154545
- 时间戳: 2026-05-10T15:45:45.568589
- 损坏文件: `/tmp/call_user.py`

## 技能检索
- 检索 query: "TypeError 参数数量不对"
- 检索到: ['signature_first_debugging', 'demo_repair_workflow', 'error_message_as_contract_signal']
- 命中: ['signature_first_debugging', 'error_message_as_contract_signal']

## Advisory Context
- 注入成功: True
- 注入后长度: 950 chars

## 修复过程
1. Phoenix advisory 注入 signature_first_debugging + error_message_as_contract_signal
2. 读 /tmp/broken_sign.py 确认 create_user 真实签名
3. 确认正确参数: name, age, email
4. 修复: 删除不存在的 user_age 参数

## Before/After
### Before
```
TypeError: create_user() got an unexpected keyword argument 'user_age'
```

### After
```
{'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}
```

## 函数签名
```
create_user(name, age, email='unknown@example.com')
```

## Outcome
- written: True
- processed: 1

## Task 2 结论
- Skill Retrieval: PASS
- Advisory Injection: PASS
- Fix Success: PASS
- Outcome Write-back: PASS
