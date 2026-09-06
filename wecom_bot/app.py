# -*- coding: utf-8 -*-
"""
企业微信 API 模式智能机器人 -> 扣子(Coze)工作流 中转服务
==========================================================
功能：接收企微回调(解密) -> 调用扣子工作流 -> 加密回复

依赖：pip install flask requests cryptography
"""

import json
import time
import hashlib
import base64
import random
import string
import requests
from flask import Flask, request, jsonify

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ==================== 配置区（改成你自己的） ====================
TOKEN = "你的Token"                # 企微机器人回调 Token
ENCODING_AES_KEY = "你的EncodingAESKey"  # 43位
RECEIVE_ID = ""                    # 智能机器人场景固定传空字符串

# 扣子工作流 API（在扣子后台发布工作流后获取）
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"   # 国际版用 api.coze.com
COZE_TOKEN = "你的扣子Token"        # Bearer Token
COZE_WORKFLOW_ID = "你的工作流ID"    # 工作流ID
# ============================================================

app = Flask(__name__)


# ==================== 企微加解密工具 ====================
class WXBizMsgCrypt:
    def __init__(self, token, encoding_aes_key, receive_id):
        self.token = token
        self.receive_id = receive_id
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        if len(self.aes_key) != 32:
            raise ValueError("EncodingAESKey 长度不正确")

    def _signature(self, timestamp, nonce, encrypt):
        arr = sorted([self.token, str(timestamp), str(nonce), encrypt])
        return hashlib.sha1("".join(arr).encode("utf-8")).hexdigest()

    def _decrypt(self, text):
        cipher = Cipher(algorithms.AES(self.aes_key),
                        modes.CBC(self.aes_key[:16]),
                        backend=default_backend())
        d = cipher.decryptor()
        plain = d.update(base64.b64decode(text)) + d.finalize()
        # 去掉 PKCS#7 填充
        pad = plain[-1]
        content = plain[:-pad]
        # content = 16字节随机数 + 4字节长度 + 明文 + receive_id
        msg_len = int.from_bytes(content[16:20], "big")
        msg = content[20:20 + msg_len].decode("utf-8")
        rid = content[20 + msg_len:].decode("utf-8")
        return msg, rid

    def _encrypt(self, msg):
        random_bytes = "".join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(16)).encode("utf-8")
        msg_bytes = msg.encode("utf-8")
        rid_bytes = self.receive_id.encode("utf-8")
        content = random_bytes + len(msg_bytes).to_bytes(4, "big") + \
            msg_bytes + rid_bytes
        # PKCS#7 填充
        pad = 32 - (len(content) % 32)
        content += bytes([pad]) * pad
        cipher = Cipher(algorithms.AES(self.aes_key),
                        modes.CBC(self.aes_key[:16]),
                        backend=default_backend())
        e = cipher.encryptor()
        encrypted = e.update(content) + e.finalize()
        return base64.b64encode(encrypted).decode("utf-8")

    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        _, plain = self._decrypt(echostr)
        sig = self._signature(timestamp, nonce, echostr)
        return plain if sig == msg_signature else None

    def decrypt_msg(self, msg_signature, timestamp, nonce, encrypt):
        sig = self._signature(timestamp, nonce, encrypt)
        if sig != msg_signature:
            return None
        plain, _ = self._decrypt(encrypt)
        return plain

    def encrypt_msg(self, reply_plain, nonce, timestamp=None):
        encrypt = self._encrypt(reply_plain)
        timestamp = timestamp or int(time.time())
        sig = self._signature(timestamp, nonce, encrypt)
        return {
            "encrypt": encrypt,
            "msgsignature": sig,
            "timestamp": timestamp,
            "nonce": nonce,
        }


crypt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, RECEIVE_ID)


# ==================== 扣子工作流调用 ====================
def call_coze(user_text, userid=""):
    """调用扣子工作流，把用户输入传给工作流，返回生成结果文本。"""
    payload = {
        "workflow_id": COZE_WORKFLOW_ID,
        "parameters": {
            "query": user_text,       # 对应扣子工作流的输入参数名，按实际改
            "userid": userid,
        },
    }
    headers = {
        "Authorization": f"Bearer {COZE_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(COZE_API_URL, json=payload, headers=headers, timeout=120)
    data = resp.json()
    # 扣子返回结构：{"code":0,"data":"..."} 或 data 里含 output 字段，按实际调整
    if data.get("code") == 0:
        return str(data.get("data", ""))
    return "抱歉，评估服务暂时不可用，请稍后再试。"


# ==================== 路由 ====================
@app.route("/callback", methods=["GET", "POST"])
def callback():
    # 1. URL 验证（企微点保存时发 GET）
    if request.method == "GET":
        sig = request.args.get("msg_signature")
        ts = request.args.get("timestamp")
        nonce = request.args.get("nonce")
        echostr = request.args.get("echostr")
        plain = crypt.verify_url(sig, ts, nonce, echostr)
        return plain if plain else "verify fail"

    # 2. 接收消息（POST）
    body = request.json
    sig = body.get("msg_signature") or body.get("msgsignature")
    ts = body.get("timestamp")
    nonce = body.get("nonce")
    encrypt = body.get("encrypt")
    if not encrypt:
        return "ok"

    plain = crypt.decrypt_msg(sig, ts, nonce, encrypt)
    if plain is None:
        return "ok"

    msg = json.loads(plain)
    msgtype = msg.get("msgtype", "")
    userid = msg.get("from", {}).get("userid", "")
    user_text = ""
    if msgtype == "text":
        user_text = msg.get("text", {}).get("content", "")
    elif msgtype == "mixed":
        items = msg.get("msg_item", [])
        user_text = "".join(
            i.get("text", {}).get("content", "") for i in items
            if i.get("msgtype") == "text"
        )

    # 3. 调用扣子工作流得到结果
    answer = call_coze(user_text, userid)

    # 4. 构造回复（流式文本，finish=True 直接一次返回完整内容）
    reply_plain = json.dumps({
        "msgtype": "stream",
        "stream": {
            "id": f"stream_{int(time.time()*1000)}",
            "finish": True,
            "content": answer,
        },
    }, ensure_ascii=False)

    # 5. 加密回复
    return jsonify(crypt.encrypt_msg(reply_plain, nonce, ts))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
