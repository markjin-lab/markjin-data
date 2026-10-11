# fulltext 2026-10-11

全文入库规则（王总确认，quote_ref grok-bot:t163s794）：只有许可允许转载的全文才放入公开仓库；其余只记录 URL 和 sha256。

抓取时间：2026-10-11 09:35 SGT（UTC+8），curl，公开页面，未登录。`ORIGINALS.sha256` 列出全部 9 个抓取文件原件的 sha256（原件均不在本仓库：arxiv-2610.12360v1 的两个原件只保留在本机；其余 7 个原件在仓库中只记哈希，原件文件保留在本机 90 天）；`PUBLIC.sha256` 只列入库的 2 个公开版本（已遮盖邮箱）的 sha256，格式为纯 `sha256  路径`，可直接 `sha256sum -c PUBLIC.sha256`。`MANIFEST.sha256` 是首次入库时的原始清单（带 original/public/hash-only 标注，不是纯 sha256sum 格式），按只追加规则保持不变。

| 文件 | 来源 URL | 许可 | 是否入库 |
|---|---|---|---|
| arxiv-2610.12360v1.html / .pdf | https://arxiv.org/html/2610.12360v1 · https://arxiv.org/pdf/2610.12360v1 | CC BY 4.0（Creative Commons Attribution 4.0 International，https://creativecommons.org/licenses/by/4.0/；arXiv 页面声明的许可链接：http://creativecommons.org/licenses/by/4.0/） | 是 |
| arxiv-2610.12463v1.html / .pdf | https://arxiv.org/html/2610.12463v1 · https://arxiv.org/pdf/2610.12463v1 | arXiv nonexclusive-distrib 1.0（不授权转载） | 否，只记 sha256 |
| arxiv-2610.12361v1.html / .pdf | https://arxiv.org/html/2610.12361v1 · https://arxiv.org/pdf/2610.12361v1 | arXiv nonexclusive-distrib 1.0（不授权转载） | 否，只记 sha256 |
| anthropic-alignment-security.html | https://www.anthropic.com/news/improving-alignment-security-efforts | 版权页面 | 否，只记 sha256 |
| guardian-gemini-hack-2026-09-18.html | https://www.theguardian.com/technology/2026/sep/18/google-gemini-ai-hack（抓取于 2026-10-11 09:41 SGT；页面注明 2026-09-29 修订） | 版权页面 | 否，只记 sha256 |
| huggingface-security-incident-july-2026.html | https://huggingface.co/blog/security-incident-july-2026 | 版权页面 | 否，只记 sha256 |

未入库的文件不在公开仓库中转载，按上述 URL 重新下载后用 `ORIGINALS.sha256` 核对；若来源页面已改动，哈希不再一致。
未抓取成功：https://www.reuters.com/business/gemini-hacked-three-companies-first-known-breakout-by-google-ai-wsj-reports-2026-09-18/（HTTP 401），稿件中不使用 Reuters 该报道的内容；https://openai.com/index/hugging-face-model-evaluation-security-incident/（HTTP 403），因此稿件中不使用 OpenAI 一手页面的内容。
本轮未使用 X 帖子，因此没有 X 回复/引用 JSON。

## 入库全文的许可
- 仓库中存放的全文只有 `arxiv-2610.12360v1.html` 与 `arxiv-2610.12360v1.pdf`（公开版本）：Sun, K. et al., *Accurate but Not Humble*, arXiv:2610.12360v1，许可 Creative Commons Attribution 4.0 International（CC BY 4.0），https://creativecommons.org/licenses/by/4.0/ 。唯一有意的改动是遮盖作者联系邮箱 h***@…（处理步骤见下节）。原件只保留在本机 /workspace/fulltext-cache/，不入库。
- The Guardian 报道（guardian-gemini-hack-2026-09-18.html）不在仓库中，只在 `ORIGINALS.sha256` 记 sha256；其余未入库文件同理。
- 邮箱检查：其他仅记哈希的原件中也含邮箱（arXiv 2610.12463 与 2610.12361 的作者联系邮箱、Hugging Face 页面的公开联系地址、Guardian 页面脚本中的服务地址），这些文件不在仓库中，不受影响。

## 公开版本的处理步骤（如实记录）
- HTML：用 Python 3 以 UTF-8 读入原件，做两次字符串替换：`mailto:h***@…`（作者邮箱的 mailto 链接）→ `#email-redacted`，`h***@…`（作者邮箱本身）→ `[email redacted]`；再以 UTF-8 写出。其余字节未改。
- PDF：原件由 arXiv 生成（Creator `arXiv GenPDF (tex2pdf:07e334b)`，Producer `pikepdf 8.15.1`，即 arXiv 生成流程写入的元数据）。本次只用 PyMuPDF 1.28.2（MuPDF 1.28.2）处理：打开原件，`search_for` 定位该邮箱所在矩形（共 1 处），`add_redact_annot` 加遮盖注释（覆盖文字 `[email redacted]`，字号 6），`apply_redactions`（删除该矩形内的文字；图像不处理），然后 `save(garbage=4, deflate=True)`。这次保存会删除未用对象、重新编号对象并重新压缩数据流，所以公开版与原件除邮箱外在字节上也不同；文字内容经 pdftotext 抽取核对，只少了该邮箱。PyMuPDF 保存时没有改写 Producer 字段，公开版中显示的 `pikepdf 8.15.1` 来自原件，并非本次处理所用的工具；本次没有使用 pikepdf。
- 例外（由审查 bot 决定，不是王总的决定）：PDF 内嵌字体（对象 869，一个 Type 1 字体程序）的版权声明中含字体作者的邮箱（此处写作 m***@…）以及一个占位地址（f***@…）。这是字体许可文本的一部分，审查 bot 决定保留，未遮盖。
