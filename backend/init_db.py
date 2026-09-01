"""Initialize the database: create tables + seed default admin user."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, engine, SessionLocal
import app.models  # noqa: F401
from app.models import SysUser
from app.security import hash_password


def init_db():
    print("创建数据表...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed default admin (idempotent)
        existing = db.query(SysUser).filter(SysUser.username == "admin").first()
        if not existing:
            admin = SysUser(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="管理员",
                role="admin",
                status="active",
            )
            db.add(admin)
            db.commit()
            print("已创建默认管理员：admin / admin123")
        else:
            print("默认管理员已存在，跳过")

        # 打印表清单
        tables = list(Base.metadata.tables.keys())
        print(f"\n共 {len(tables)} 张表：")
        for t in tables:
            print(f"  - {t}")
    finally:
        db.close()

    print("\n数据库初始化完成！")


if __name__ == "__main__":
    init_db()
