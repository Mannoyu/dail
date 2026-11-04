import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo

from shared.calendar import is_workday
from shared.config import load
from shared.demo import build
from shared.health import check
from shared.logger import get_logger
from shared.pipeline import run, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily Brief · 智能日报生成器")
    parser.add_argument("--config", default="config.yaml")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="只读配置、权限与连接检查")
    mode.add_argument("--demo", action="store_true", help="无需凭据的离线演示，不推送")
    parser.add_argument("--dry-run", action="store_true", help="真实采集和保存，但不推送")
    parser.add_argument("--date", type=date.fromisoformat, help="补跑指定日期 YYYY-MM-DD")
    parser.add_argument("--force", action="store_true", help="允许在非工作日生成日报")
    parser.add_argument("--output", default="output", help="演示文件输出目录")
    args = parser.parse_args(argv)
    logger = get_logger("daily")
    logger.info("run_started")
    try:
        if args.demo:
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
            if args.date:
                now = datetime.combine(args.date, datetime.max.time(), tzinfo=now.tzinfo)
            path = write_report(build(now), args.output)
            logger.info(f"demo_ready={path.resolve()}")
            return 0
        cfg = load(args.config)
        if args.check:
            return 0 if check(cfg) else 1
        now = datetime.now(ZoneInfo(cfg.timezone))
        if args.date:
            if args.date > now.date():
                parser.error("不能补跑未来日期")
            if args.date != now.date():
                now = datetime.combine(args.date, datetime.max.time(), tzinfo=now.tzinfo)
        if not args.force and not is_workday(now.date(), cfg.calendar):
            logger.info("非工作日，跳过日报生成")
            return 0
        return 0 if run(cfg, now, dry_run=args.dry_run) else 1
    except Exception as exc:
        logger.error(f"run_failed type={type(exc).__name__}")
        # Config errors contain field names, not environment values.
        from shared.errors import ConfigError

        if isinstance(exc, ConfigError):
            logger.error(str(exc))
        return 1
    finally:
        logger.info("run_finished")


if __name__ == "__main__":
    raise SystemExit(main())
