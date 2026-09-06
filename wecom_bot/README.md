# 企业微信 API 机器人 + 扣子工作流 中转服务

## 一、这是什么

一个轻量中转服务，把企业微信智能机器人（API 模式）和扣子工作流串起来：

```
家长在企微发消息
   ↓ 企微加密回调 POST /callback
解密 → 调扣子工作流 → 加密回复
   ↓
家长看到机器人回复
```

## 二、你需要准备

### 1. 企微侧（机器人编辑页）
- `Token`：回调配置里自定义
- `EncodingAESKey`：43 位
- 企业 ID（corp_id）

> 智能机器人场景 `RECEIVE_ID` 固定传空字符串 `""`，代码里已设好，不用改。

### 2. 扣子侧
发布工作流后，在扣子后台拿到：
- `COZE_API_URL`：国内版 `https://api.coze.cn/v1/workflow/run`，国际版 `https://api.coze.com/v1/workflow/run`
- `COZE_TOKEN`：Bearer Token
- `COZE_WORKFLOW_ID`：工作流 ID

### 3. 公网地址
你的服务要能被企微访问，需公网 URL，可选：云函数 / 云服务器 / 内网穿透（frp、cpolar）。

## 三、启动

```bash
pip install -r requirements.txt
python app.py
```

服务跑在 `0.0.0.0:8080`，回调地址填：`http://你的公网域名:8080/callback`

## 四、配置要点（改 app.py 顶部配置区）

```python
TOKEN = "你的Token"
ENCODING_AES_KEY = "你的EncodingAESKey"
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"
COZE_TOKEN = "你的扣子Token"
COZE_WORKFLOW_ID = "你的工作流ID"
```

## 五、常见坑

1. **签名校验失败**：`receiveid` 必须传空字符串，普通自建应用才传 corp_id。
2. **扣子参数名不匹配**：代码里 `parameters` 的 key（`query`、`userid`）要和扣子工作流的输入参数名一致，按实际改。
3. **扣子返回结构**：`call_coze` 里解析 `data.get("data")`，若你的工作流输出在别的字段，按实际返回调整。
4. **URL 验证**：企微点「保存」时会发 GET，1 秒内要返回明文 `echostr`，代码已处理。
