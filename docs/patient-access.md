# 角色、医护审批与患者授权

当前范围包括普通患者注册、医护申请和研发管理审批、创建/添加医护、账号人数统计、患者授权与撤销、医护只读列表及详情。医护数据来自已有健康档案和设备记录；时间范围选择、趋势扩展、结构化血糖导入、研究数据管理与预测留待后续。手机号验证码登录已记录，用户同意待真实短信配置可用后再接入，当前保留账号密码登录。

## 使用与演示

1. 在 App 注册患者账号；医护从登录首页的“医护人员注册”填写姓名、所属机构和账号信息。医护注册是申请，通过前没有医护权限。
2. 研发账号登录“研发管理”，在“医护审批”通过或拒绝申请，拒绝须填写原因；申请人刷新审批状态后进入医护界面，或修改后重新提交。研发也可在“医护账号”直接创建医护，或按完整用户名添加已有患者账号为医护。
3. 医护登录后进入“授权患者”，初始列表为空。患者在聊天侧边栏进入“医护授权”，输入医护完整用户名，核对返回的用户名和 ID 后点“确认授权”。
4. 医护刷新患者列表，每行仅姓名与账号 ID，点击该行读取基础档案、健康情况、设备最近记录与近 30 天概况。旧账号可在“医护授权”页补充姓名；没有姓名或健康记录时明确显示未填写或暂无记录。
5. 患者撤销授权。医护保持原登录状态，在详情点“重新查询患者数据”，应看到无有效授权提示，旧详情被清除；返回患者列表并刷新后，该患者不再列出。
6. 研发在“人员总览”查看注册总数、患者、医护、开发协作者人数和分布图。按当前身份统计，待审批账号仍计入患者；这些管理权限不包含患者健康资料。

撤销控制后续查询，无法追回已经读取的内容。App 切换患者、重新查询、退到后台及返回前台时清除旧详情；每次查询都经过后端检查。首批不提供授权到期时间，患者可手动撤销。

## 维护角色

初始化研发管理账号仍由维护者执行命令；后续医护审批和添加可在研发管理界面完成，不公开任意角色修改能力。服务器命令仅在审核通过并更新服务器后使用。

```bash
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml exec api \
  .venv/bin/python -m antang_api.manage_roles 医护用户名 clinician --actor 维护者标识

docker compose -p antang-prod -f compose.yaml -f compose.server.yaml exec api \
  .venv/bin/python -m antang_api.manage_roles 研发用户名 researcher --actor 维护者标识
```

本地开发可在 `api` 目录用 `.venv/bin/python -m antang_api.manage_roles 用户名 patient --actor 维护者标识` 恢复患者角色。先注册，再赋予身份；角色更改会撤销涉及该账号的全部有效授权，恢复身份也不会恢复旧授权，须患者重新授予。重新登录会切换 App 入口；现有会话的服务端角色权限在下一次请求生效。

## 数据和接口

迁移 `j37d8e0f5a41` 增加角色与授权，`k48e9f1a6b52` 增加姓名和医护申请历史。每次请求从数据库读取账号启用状态和角色；医护数据查询还检查患者启用状态、患者角色与未撤销授权。审批与角色变更在同一事务中完成，重复处理返回 409。医护查询响应使用 `Cache-Control: no-store`。授权关系不包含聊天记录、附件、记忆、写入及批量导出能力；现有 Agent 工具仍仅访问当前用户。

| 接口 | 访问者与行为 |
| --- | --- |
| `GET /api/v1/auth/me` | 当前账号，包括 `role` |
| `PATCH /api/v1/auth/me` | 当前账号维护姓名，不能修改角色 |
| `GET /api/v1/clinician-applications/me`、`POST /api/v1/clinician-applications` | 查询本人申请、拒绝后重新提交 |
| `GET /api/v1/admin/overview` | 研发读取真实人数统计 |
| `GET /api/v1/admin/clinician-applications`、`POST /api/v1/admin/clinician-applications/{id}/review` | 研发分页读取及审批医护申请 |
| `GET/POST /api/v1/admin/clinicians`、`POST /api/v1/admin/clinicians/assign` | 研发读取医护列表、创建医护、添加已有账号 |
| `POST /api/v1/patient-access-grants/resolve` | 患者按完整用户名核对启用的医护账号 |
| `GET /api/v1/patient-access-grants` | 患者自己的授权历史 |
| `POST /api/v1/patient-access-grants` | 患者提交核对过的 `clinician_id` |
| `DELETE /api/v1/patient-access-grants/{grant_id}` | 患者撤销自己的授权；重复撤销返回 204 |
| `GET /api/v1/patients?limit=30&after=UUID` | 当前医护有效授权患者，按 ID 分页 |
| `GET /api/v1/patients/{patient_id}/health-profile` | 授权医护只读档案和最近设备记录 |
| `GET /api/v1/patients/{patient_id}/wearable-dashboard` | 授权医护只读近 30 天设备概况 |

重复有效授权返回 409。患者不能管理其他患者的授权；研发及普通患者调用医护接口返回 403。停用账号不能继续使用原登录会话；停用患者不再出现在医护列表且不能被读取。授权、撤销、角色变更、医护列表读取及患者数据读取结果记录在 `patient_access_audits`，不记录健康正文或凭证。

## 验证与发布

- 2026-10-15 本机：后端完整 312 项、移动端 189 项测试通过；类型、Lint 与 Android JS 打包通过。新增审批与管理页面仍需在新安装包上进行手机体验审核。
- 后端隔离测试覆盖注册不可提权、完整授权/读取/撤销/重新授权、真实入库档案与设备值、患者间隔离、医护只读、研发隔离、角色变更、停用和分页。
- App 测试覆盖核对/授权/撤销、姓名行展示、查询拒绝后清理详情、医护申请入口、审批状态刷新和重新提交、研发审批与账号管理和真实计数展示。
- 运行 `bash scripts/check api` 和 `bash scripts/check mobile`；APK 使用 `bash scripts/build-android preview`。
- 开发和审核预览连接本机后端。先启动 `bash scripts/dev-api --base-only`，再启动手机开发服务，或生成绑定本机局域网地址的审核包。两账号手机体验通过后再发布线上，不要求为了预览先更新服务器。

实现依据为 [OWASP 授权建议](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) 的逐请求检查与资源关系授权、[FastAPI 依赖机制](https://fastapi.tiangolo.com/tutorial/dependencies/)；单角色、患者主动授权、医护首批只读是本项目已确认的产品范围。

## 审核通过后，源码上传服务器怎么启动

源码包按项目根目录布局，可覆盖服务器现有项目源码。它不包含 `.env`、`api/.env`、数据库数据、`node_modules` 或本地虚拟环境。沿用服务器现有配置，在原项目目录操作；数据库备份沿用 [维护说明](maintainers.md) 的发布流程。

```bash
cd /home/ubuntu/antang-prod
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml build api
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml up -d --no-build --wait api proactive-care-worker
docker compose -p antang-prod -f compose.yaml -f compose.server.yaml exec api .venv/bin/alembic current
curl --fail https://82.157.48.200:8000/health
```

API 镜像启动时先自动执行 `alembic upgrade head`，成功才启动服务。`alembic current` 应显示 `k48e9f1a6b52 (head)`。初始化研发账号后，安装新 APK，验证医护申请、审批、授权读取与撤销。无需重建数据库或重新录入既有患者档案。
