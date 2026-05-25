# PTMF to PCAP

把华为 PTMF 用户消息跟踪文件中的 SIP 报文抽取出来，封装为 Wireshark 可打开的 `.pcap`。

## 用法

```bash
python3 ptmf2pcap.py input.ptmf -o output.pcap
python3 ptmf2pcap.py input.zip -o output.pcap
python3 ptmf2pcap.py input.zip -o output.pcap --summary
```

默认按 `+08:00` 解释 PTMF 里的时间戳，这样 Wireshark 的 Time 列会显示 PTMF 中看到的本地时间。若文件来自其他时区，可指定：

```bash
python3 ptmf2pcap.py input.zip -o output.pcap --timezone UTC
python3 ptmf2pcap.py input.zip -o output.pcap --timezone +07:00
```

如果 Wireshark 没有自动把 5062、6060 等非标准端口识别为 SIP，可以使用：

```bash
python3 ptmf2pcap.py input.zip -o output-normalized.pcap --normalize-ports
```

`--normalize-ports` 会把请求方向的目标端口、响应方向的源端口改为 `5060`，便于 Wireshark/tcpdump 自动识别 SIP。原始 SIP 报文内容不变，真实端口仍可在 `Via`、`Contact`、`Route` 等 SIP 头里查看。

## 说明

- 工具不依赖第三方 Python 包。
- 输出 pcap 使用 Ethernet + IPv4 + UDP + SIP 载荷。
- 源/目的 IP 和端口优先取 PTMF 记录头，并按 PTMF 方向码修正顺序；SIP 报文正文保持原样，便于分析 Call-ID、CSeq、SDP、Route 等字段。
