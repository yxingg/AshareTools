# logger.py - 日志与通知模块
"""日志配置与钉钉通知模块"""

import logging
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import threading
from logging.handlers import TimedRotatingFileHandler

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import LOG_PATH, LOG_LEVEL, LOG_BACKUP_COUNT


class DingTalkNotifier:
    """钉钉通知器"""
    
    _last_msg_hash = None
    _last_msg_time = 0
    _recent_msg_hashes = {}
    _lock = threading.Lock()

    def __init__(self, webhook_url: str = "", secret: str = ""):
        self.webhook_url = webhook_url
        self.secret = secret

    def update_config(self, webhook_url: str, secret: str):
        """更新配置"""
        self.webhook_url = webhook_url
        self.secret = secret

    def send(self, content: str):
        """异步发送钉钉消息"""
        if not self.webhook_url:
            return
        
        current_time = time.time()
        msg_hash = hash(content)
        
        with DingTalkNotifier._lock:
            # 清理过期记录
            expired = [h for h, t in DingTalkNotifier._recent_msg_hashes.items() 
                      if current_time - t > 60]
            for h in expired:
                del DingTalkNotifier._recent_msg_hashes[h]
            
            # 30秒内去重
            if msg_hash in DingTalkNotifier._recent_msg_hashes:
                if current_time - DingTalkNotifier._recent_msg_hashes[msg_hash] < 30.0:
                    return
            
            DingTalkNotifier._recent_msg_hashes[msg_hash] = current_time
        
        t = threading.Thread(target=self._send_sync, args=(content,))
        t.daemon = True
        t.start()

    def _send_sync(self, content: str):
        """同步发送"""
        try:
            post_url = self.webhook_url
            if self.secret:
                timestamp = str(round(time.time() * 1000))
                secret_enc = self.secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{self.secret}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                post_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            
            headers = {"Content-Type": "application/json"}
            data = {
                "msgtype": "text",
                "text": {"content": content},
                "at": {"isAtAll": False}
            }
            
            session = requests.Session()
            session.trust_env = False
            
            retries = Retry(total=0, connect=0, read=0, redirect=0, status=0)
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            session.post(post_url, headers=headers, data=json.dumps(data), timeout=10)
        except Exception:
            pass


class DingTalkHandler(logging.Handler):
    """钉钉日志处理器"""
    
    def __init__(self, notifier: DingTalkNotifier):
        super().__init__()
        self.notifier = notifier

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            msg = self.format(record)
            self.notifier.send(f"【程序报错】\n{msg}")


def setup_logger(name: str = "AShareTools") -> tuple:
    """
    配置日志
    
    Returns:
        (logger, notifier)
    """
    import shutil
    import os
    
    # 初始化通知器
    notifier = DingTalkNotifier()

    # 配置日志
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.handlers = []

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 文件处理器 - 按天轮转
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    try:
        file_handler = TimedRotatingFileHandler(
            str(LOG_PATH),
            when='midnight',
            interval=1,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8',
            delay=True
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # Windows 兼容的轮转器
        def windows_rotator(source, dest):
            try:
                os.rename(source, dest)
            except PermissionError:
                try:
                    shutil.copy2(source, dest)
                    with open(source, 'w', encoding='utf-8'):
                        pass
                except Exception:
                    pass

        file_handler.rotator = windows_rotator
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法创建日志文件: {e}")

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 钉钉处理器
    dingtalk_handler = DingTalkHandler(notifier)
    dingtalk_handler.setFormatter(formatter)
    logger.addHandler(dingtalk_handler)

    return logger, notifier
