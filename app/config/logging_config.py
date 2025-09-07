import logging
import logging.config
import os
import sys
from datetime import datetime
from typing import Dict, Any


class CustomFormatter(logging.Formatter):
    """カスタムログフォーマッター（構造化ログ対応）"""
    
    def format(self, record):
        # 基本的な構造化ログ形式
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 例外情報があれば追加
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # 追加属性があれば追加
        if hasattr(record, 'symbol'):
            log_entry["symbol"] = record.symbol
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'user_ip'):
            log_entry["user_ip"] = record.user_ip
        
        return str(log_entry)


def setup_logging() -> None:
    """ログ設定を初期化"""
    
    # ログレベルを環境変数から取得
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    
    # ログディレクトリを作成
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # ログ設定辞書
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s:%(lineno)-4d | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s: %(message)s"
            },
            "json": {
                "()": CustomFormatter
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "detailed" if debug_mode else "simple",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": os.path.join(log_dir, "app.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": os.path.join(log_dir, "error.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "app.services": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "app.api": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "yfinance": {
                "level": "WARNING",  # yfinanceのログを制限
                "handlers": ["file"],
                "propagate": False
            },
            "urllib3": {
                "level": "WARNING",  # HTTP接続ログを制限
                "handlers": ["file"],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"]
        }
    }
    
    # 本番環境では JSON 形式のログを使用
    if not debug_mode:
        config["handlers"]["file"]["formatter"] = "json"
        config["handlers"]["error_file"]["formatter"] = "json"
    
    # ログ設定を適用
    logging.config.dictConfig(config)
    
    # 起動ログを出力
    logger = logging.getLogger("app.config")
    logger.info(f"Logging configured - Level: {log_level}, Debug: {debug_mode}")


def get_logger(name: str) -> logging.Logger:
    """指定された名前のロガーを取得"""
    return logging.getLogger(name)


# アクセスログ用のミドルウェア設定用関数
def get_access_logger() -> logging.Logger:
    """アクセスログ用のロガーを取得"""
    access_logger = logging.getLogger("app.access")
    
    # アクセスログ専用のハンドラーがない場合は追加
    if not access_logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            "logs/access.log",
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding="utf8"
        )
        formatter = logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        access_logger.addHandler(handler)
        access_logger.setLevel(logging.INFO)
    
    return access_logger