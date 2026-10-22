"""在受控服务器环境运行：python -m antang_api.manage_roles USER ROLE --actor NAME。"""

import argparse
import asyncio

from antang_api.database import engine, session_factory
from antang_api.models import UserRole
from antang_api.patient_access import set_user_role


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="维护用户业务角色（不提供公开角色修改接口）"
    )
    parser.add_argument("username")
    parser.add_argument("role", choices=list(UserRole))
    parser.add_argument("--actor", required=True, help="维护者标识，写入数据库审计")
    args = parser.parse_args()
    if not 1 <= len(args.actor.strip()) <= 128:
        parser.error("维护者标识须为 1–128 个字符")
    try:
        async with session_factory() as session:
            try:
                user = await set_user_role(
                    session,
                    username=args.username,
                    role=UserRole(args.role),
                    maintainer=args.actor.strip(),
                )
            except ValueError as error:
                parser.error(str(error))
            else:
                print(f"{user.username}: {user.role.value}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
