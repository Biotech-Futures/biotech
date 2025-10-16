# 导师管理系统 (Mentor Management System)

这是一个基于Django的导师-学生匹配管理系统，用于自动分配学生小组和导师，并提供导师管理功能。

## 项目概述

该系统主要功能包括：
- 从Excel文件导入学生和导师数据
- 自动分组学生（基于预分配组号和兴趣匹配）
- 自动分配导师给小组
- 导师替换和账户管理
- 邮件通知功能

## 环境要求

- Python 3.8+
- Django 4.2.23
- SQLite数据库（默认）
- 其他依赖见 `backend/requirements.txt`

## 快速开始

### 1. 环境准备

```bash
# 克隆项目（如果从Git仓库）
# git clone <repository-url>
# cd COMP5615_xinsheng_demo_mentorManage

# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库初始化

```bash
# 在backend目录下执行
python manage.py migrate

# 创建超级用户（可选，用于Django管理后台）
python manage.py createsuperuser
```

### 3. 导入测试数据

```bash
# 导入Excel文件中的数据（使用项目根目录的测试数据）
python manage.py import_p11 "../P11 Test User Data.xlsx"
```

### 4. 启动服务

```bash
# 启动Django开发服务器
python manage.py runserver

# 服务将在 http://127.0.0.1:8000 启动
```

## 功能测试指南

### 1. 基础功能测试

#### 1.1 健康检查
访问：http://127.0.0.1:8000/api/health/
应该返回：`{"status": "ok", "service": "ws3-backend"}`

#### 1.2 查看Django管理后台
访问：http://127.0.0.1:8000/admin/
使用创建的超级用户登录，可以查看和管理：
- 学生 (Students)
- 导师 (Mentors) 
- 学生小组 (Student Groups)
- 兴趣标签 (Interests)

### 2. 核心功能测试

#### 2.1 重置所有小组和导师分配

使用项目根目录的 `test.py` 脚本：

```bash
# 在项目根目录执行
python test.py
```

或者直接调用API：
```bash
curl -X POST "http://127.0.0.1:8000/api/reset_groups/?mode=delete_all&reset_seq=1"
```

**功能说明**：
- 删除所有现有小组
- 清除所有导师分配
- 重置小组ID序列号（已注释掉）

#### 2.2 自动分组学生

```bash
curl -X POST "http://127.0.0.1:8000/api/auto_group/"
```

**功能说明**：
- 首先处理预分配组号的学生（从Excel的"Group Number"列）
- 然后为没有预分配组号的学生按兴趣自动分组
- 每组最多5人
- 按轨道（Track）分组

#### 2.3 兜底分组（处理剩余学生）

```bash
curl -X POST "http://127.0.0.1:8000/api/auto_group_fallback/"
```

**功能说明**：
- 处理仍未分组的学生
- 优先按共同兴趣分组
- 其次按年级和地区相近性分组

#### 2.4 分配导师

```bash
curl -X POST "http://127.0.0.1:8000/api/assign_mentors/"
```

**功能说明**：
- 为没有导师的小组自动分配导师
- 匹配规则：
  - 必须有至少一个共同兴趣
  - 考虑导师容量限制
  - 按轨道优先级匹配
  - 考虑经验水平匹配

### 3. 导师管理功能测试

#### 3.1 使用Web界面

**访问Web界面**：

方法1：直接打开HTML文件（该界面仅为测试界面 非实际功能界面）
- 在文件管理器中找到 `frontend/admin.html` 并双击打开

方法2：通过Django服务器访问（推荐）

快速设置步骤：
```bash
# 1. 复制前端文件到Django模板目录
cp frontend/admin.html backend/matching/templates/admin_interface.html

# 2. 在 backend/matching/views.py 末尾添加：
def admin_interface(request):
    return render(request, 'admin_interface.html')

# 3. 在 backend/matching/urls.py 的 urlpatterns 中添加：
path("admin-interface/", admin_interface, name="admin_interface"),

# 4. 重启Django服务器
python manage.py runserver
```

然后访问：http://127.0.0.1:8000/api/admin-interface/

该界面提供以下功能：

**替换单个小组的导师**：
1. 输入小组ID和新导师ID
2. 点击"Replacement of mentors and notification"
3. 系统会发送邮件通知相关人员

**停用导师账户**：
1. 输入导师ID
2. 点击"Deactivate the mentorstutor and clear the group"
3. 导师被标记为非活跃，其负责的小组导师分配被清除

#### 3.2 使用API接口

**替换小组导师**：
```bash
curl -X POST "http://127.0.0.1:8000/api/replace_group_mentor/" \
  -H "Content-Type: application/json" \
  -d '{"group_id": 1, "new_mentor_id": 2}'
```

**停用导师**：
```bash
curl -X POST "http://127.0.0.1:8000/api/deactivate_mentor/" \
  -H "Content-Type: application/json" \
  -d '{"mentor_id": 2}'
```

**批量操作预览**（占位功能）：
```bash
curl "http://127.0.0.1:8000/api/bulk_inactive_mentors_preview/"
```

### 4. 完整工作流程测试

#### 4.1 完整重置和重新分配流程

```bash
# 1. 重置所有数据
python test.py

# 2. 自动分组
curl -X POST "http://127.0.0.1:8000/api/auto_group/"

# 3. 兜底分组（如果需要）
curl -X POST "http://127.0.0.1:8000/api/auto_group_fallback/"

# 4. 分配导师
curl -X POST "http://127.0.0.1:8000/api/assign_mentors/"
```

#### 4.2 验证结果

1. **查看Django管理后台**：
   - 访问 http://127.0.0.1:8000/admin/
   - 检查学生小组是否正确创建
   - 检查导师分配是否合理

2. **查看API响应**：
   - 每个API调用都会返回详细的执行结果
   - 包括创建的小组数量、分配的导师信息等

## 邮件通知功能

### 开发环境
在开发环境中，邮件会输出到Django控制台，不会实际发送。

### 生产环境
要启用真实邮件发送，需要设置以下环境变量：

```bash
export EMAIL_HOST="smtp.gmail.com"
export EMAIL_PORT="587"
export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-password"
export EMAIL_USE_TLS="true"
export DEFAULT_FROM_EMAIL="your-email@gmail.com"
```

## 数据模型说明

### 学生 (Student)
- 基本信息：姓名、邮箱、学校、年级
- 地理信息：国家、地区、轨道
- 兴趣标签：多对多关系
- 预分配组号：来自Excel的Group Number列

### 导师 (Mentor)
- 基本信息：姓名、邮箱、机构
- 背景信息：经验水平、专业领域
- 地理信息：国家、地区、轨道
- 容量限制：最多可带的小组数量
- 活跃状态：是否可用

### 学生小组 (StudentGroup)
- 基本信息：组名、轨道
- 年级范围：最小和最大年级
- 成员：多对多关系
- 兴趣：成员兴趣的并集
- 导师：外键关系

## 故障排除

### 常见问题

1. **导入Excel失败**：
   - 确保Excel文件路径正确
   - 检查Excel文件是否包含"Students"和"Mentors"工作表
   - 确保列名符合预期格式

2. **API调用失败**：
   - 检查Django服务是否正在运行
   - 确认API端点URL正确
   - 检查请求格式（JSON格式、Content-Type等）

3. **邮件发送失败**：
   - 开发环境：检查控制台输出
   - 生产环境：检查SMTP配置

4. **数据库错误**：
   - 运行 `python manage.py migrate` 更新数据库
   - 检查数据库文件权限

### 调试技巧

1. **查看Django日志**：
   - 在settings.py中设置 `DEBUG = True`
   - 查看控制台输出的详细错误信息

2. **使用Django Shell**：
   ```bash
   python manage.py shell
   ```
   可以交互式地测试模型和查询

3. **检查数据库内容**：
   ```bash
   python manage.py dbshell
   ```
   直接访问SQLite数据库

## 扩展功能

### 批量操作（占位功能）
系统预留了批量处理不活跃导师的接口，目前返回占位数据：
- `GET /api/bulk_inactive_mentors_preview/` - 预览不活跃导师
- `POST /api/bulk_replace_inactive_mentors/` - 批量替换导师

### 自定义配置
可以通过修改 `backend/core/settings.py` 来调整：
- 数据库配置
- 邮件设置
- 其他Django设置

## 贡献指南

1. 每个工作流使用独立分支
2. 保持提交信息简洁明确
3. 通过Pull Request合并到main分支
4. 确保main分支始终稳定可部署

## 许可证

请根据项目需要添加相应的许可证信息。
