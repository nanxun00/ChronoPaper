# PlantUML 生成提示词模板

以下是各类图的生成指令，Claude 在阶段 3 中参考这些提示词生成对应的 PlantUML 代码。

---

## 数据流图（DFD）

根据文档中的核心业务流程，生成数据流图。要求：
- 用 `rectangle` 表示外部实体
- 用 `database` 表示数据存储
- 用箭头标注数据流向和数据名称
- 保持层次清晰，不超过 2 层

```plantuml
@startuml
rectangle "外部用户" as user
rectangle "系统" as system
database "数据库" as db

user -> system : 输入数据
system -> db : 存储
db -> system : 查询结果
system -> user : 输出结果
@enduml
```

---

## 用例图（Use Case）

根据文档中的用户故事和核心功能，生成用例图。要求：
- 每个目标用户对应一个 actor
- 每个核心功能对应一个 usecase
- 用 `-->` 表示 include/extend 关系

```plantuml
@startuml
actor "用户" as user
rectangle 系统 {
  usecase "功能 1" as uc1
  usecase "功能 2" as uc2
}
user --> uc1
user --> uc2
@enduml
```

---

## 活动图（Activity）

根据文档中的核心业务流程，生成活动图。要求：
- 用 `start` / `stop` 标注起止
- 用 `if` / `else` 表示分支
- 保持流程线性，避免过多交叉

```plantuml
@startuml
start
:步骤 1;
if (条件?) then (是)
  :步骤 2a;
else (否)
  :步骤 2b;
endif
:步骤 3;
stop
@enduml
```

---

## 时序图（Sequence）

根据文档中的模块划分和接口定义，生成时序图。要求：
- 参与者为系统中的主要模块或角色
- 标注每条消息的方法名或数据名
- 用 `activate` / `deactivate` 表示生命周期

```plantuml
@startuml
actor 用户
participant 前端
participant 后端
database 数据库

用户 -> 前端 : 操作
前端 -> 后端 : API 请求
activate 后端
后端 -> 数据库 : 查询
数据库 --> 后端 : 返回数据
后端 --> 前端 : 响应
deactivate 后端
前端 --> 用户 : 展示结果
@enduml
```
