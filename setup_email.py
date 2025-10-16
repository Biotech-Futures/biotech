import os
import sys
import getpass
import subprocess


def prompt_bool(message: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        ans = input(message + suffix + ": ").strip().lower()
        if ans == "" and default is not None:
            return default
        if ans in ("y", "yes", "1", "true"):
            return True
        if ans in ("n", "no", "0", "false"):
            return False
        print("请输入 y 或 n")


def write_env_file(path: str, env: dict) -> None:
    lines = []
    for k, v in env.items():
        lines.append(f"{k}={v}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_powershell_file(path: str, env: dict) -> None:
    lines = ["# 使用方法：在 PowerShell 中执行 . \\" + path.replace("\\", "/") + "\n"]
    for k, v in env.items():
        vv = str(v).replace('"', '`"')
        lines.append(f"$env:{k}=\"{vv}\"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def setx_windows(env: dict) -> None:
    for k, v in env.items():
        try:
            subprocess.run(["setx", k, str(v)], check=True, shell=True)
        except Exception as e:
            print(f"警告：setx {k} 失败：{e}")


def main() -> int:
    print("=== 邮件环境一键配置（Windows 适用）===")
    mode_smtp = prompt_bool("是否使用 SMTP 真实发信？(选否将使用控制台模拟)", default=False)

    env = {}
    if mode_smtp:
        host = input("EMAIL_HOST (如 smtp.gmail.com): ").strip()
        port = input("EMAIL_PORT (如 587/465，留空默认587): ").strip() or "587"
        user = input("EMAIL_HOST_USER (登录用户名/邮箱): ").strip()
        pwd = getpass.getpass("EMAIL_HOST_PASSWORD: ")
        use_tls = prompt_bool("EMAIL_USE_TLS? (587 通常为 TLS)", default=True)
        use_ssl = prompt_bool("EMAIL_USE_SSL? (465 通常为 SSL)", default=False)
        default_from = input("DEFAULT_FROM_EMAIL (留空默认与 USER 相同): ").strip() or user

        env.update({
            "EMAIL_HOST": host,
            "EMAIL_PORT": port,
            "EMAIL_HOST_USER": user,
            "EMAIL_HOST_PASSWORD": pwd,
            "EMAIL_USE_TLS": "true" if use_tls else "false",
            "EMAIL_USE_SSL": "true" if use_ssl else "false",
            "DEFAULT_FROM_EMAIL": default_from,
            "SERVER_EMAIL": default_from,
        })
    else:
        env.update({
            "EMAIL_HOST": "",
            "EMAIL_PORT": "587",
            "EMAIL_HOST_USER": "",
            "EMAIL_HOST_PASSWORD": "",
            "EMAIL_USE_TLS": "true",
            "EMAIL_USE_SSL": "false",
            "DEFAULT_FROM_EMAIL": "noreply@example.com",
            "SERVER_EMAIL": "noreply@example.com",
        })

    project_root = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(project_root, "backend")
    env_path = os.path.join(backend_dir, ".env")
    ps1_path = os.path.join(backend_dir, "email_env.ps1")
    write_env_file(env_path, env)
    write_powershell_file(ps1_path, env)
    print(f"已写入本地环境文件: {env_path}")
    print(f"已生成 PowerShell 会话脚本: {ps1_path}")

    if os.name == "nt":
        if prompt_bool("是否将配置持久化到当前用户环境变量（setx）？", default=True):
            setx_windows(env)
            print("已尝试通过 setx 写入用户环境变量（请重启 PowerShell 生效）")
        else:
            print("你可以在 PowerShell 中运行如下命令临时生效（当前会话）：")
            print(f". {ps1_path}")
    else:
        print("非 Windows 平台未自动持久化，请参考 backend/.env 内容自行导入环境变量。")

    print("完成。现在可运行:  cd backend; python manage.py runserver 127.0.0.1:8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())


